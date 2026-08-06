"""K3 -- the missing worker loop.

Before this, `Settings.max_concurrent_workers` (config.py) existed but
nothing ever read it, and `POST /api/tasks/{id}/execute` called
`ExecutionService.run()` directly and *blocked the HTTP request* until the
subprocess finished or hit its (up to 24h) timeout -- zero queue, zero
parallelism, one request-thread hostage per run.

`QueueService` sits in front of `ExecutionService.run()` as a thin
asyncio-native queue + semaphore. It does not reimplement any part of
execution -- every actual run still goes through the exact same
`ExecutionService.run()` K1/K2 already built (governance checks, executor
dispatch, WriteLockManager, worktrees, artifacts, budget ledger, all of it).
This module only adds:

1. An in-process `asyncio.Queue` of execution requests (task_id + optional
   executor_id), so `/execute` can enqueue and return immediately instead of
   awaiting the whole run.
2. `asyncio.Semaphore(max_concurrent_workers)` bounding how many
   `ExecutionService.run()` calls are in flight at once -- the config value
   is *finally* read here.
3. A placeholder row in the `executions` table (K1's schema) written at
   enqueue time (status "pending") and updated to "running" once a worker
   picks it up, so `GET /api/executions/{id}` has something to return the
   instant `/execute` responds 202 -- not just once the run eventually
   finishes. `ExecutionService.run()` is threaded an `execution_id` so its
   own internal `save_execution()` calls (and `completion.py`'s) land on
   *this same* row instead of minting a second, disconnected one.
4. A periodic reaper: K0's `TaskEngine.reap_orphaned()` ran once at startup;
   here it also runs on an interval so a task orphaned by a crash *while the
   process keeps running* (not just "died before this restart") still gets
   cleared without needing a manual restart.
5. Best-effort stale write-lock eviction (the gap K2 documented and
   deliberately left open: `WriteLockManager` has no eviction if the holder
   process dies mid-run, so a crash leaves `storage/locks/*.lock` behind
   forever and every future contender for that key waits indefinitely). This
   is a coarse TTL sweep, not process-liveness detection (a lock file
   carries no PID) -- a lock idle longer than `stale_lock_ttl_seconds` is
   assumed dead. Simple by design; a real owner-liveness check is out of
   K3's scope.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from pathlib import Path

from cano_hermes.domain.models import ExecutionResult
from cano_hermes.orchestration.execution_service import ExecutionService
from cano_hermes.orchestration.task_engine import TaskEngine


class ExecutionRequest:
    __slots__ = ("execution_id", "executor_id", "task_id")

    def __init__(self, execution_id: str, task_id: str, executor_id: str | None) -> None:
        self.execution_id = execution_id
        self.task_id = task_id
        self.executor_id = executor_id


def _placeholder_result(execution_id: str, task_id: str, executor_id: str | None, status: str, summary: str) -> ExecutionResult:
    return ExecutionResult(
        execution_id=execution_id,
        task_id=task_id,
        executor=executor_id or "unresolved",
        status=status,
        summary=summary,
    )


def evict_stale_locks(lock_root: Path, ttl_seconds: float) -> int:
    """Delete any `*.lock` file under `lock_root` older than `ttl_seconds`,
    read from the `created_at` timestamp `WriteLockManager.acquire` writes
    into the file itself. Returns the count evicted. Missing directory or an
    unreadable/corrupt lock file is treated as "nothing to evict" rather
    than an error -- this sweep is a safety net, not a source of truth."""
    if not lock_root.exists():
        return 0
    now = time.time()
    evicted = 0
    for lock_file in lock_root.glob("*.lock"):
        try:
            payload = json.loads(lock_file.read_text(encoding="utf-8"))
            created_at = float(payload.get("created_at", 0))
        except (OSError, ValueError, json.JSONDecodeError):
            created_at = 0.0
        if now - created_at > ttl_seconds:
            lock_file.unlink(missing_ok=True)
            evicted += 1
    return evicted


class QueueService:
    def __init__(
        self,
        execution_service: ExecutionService,
        engine: TaskEngine,
        max_concurrent_workers: int,
        reap_interval_seconds: float = 60.0,
        stale_lock_ttl_seconds: float = 3600.0,
    ) -> None:
        self.execution_service = execution_service
        self.engine = engine
        self.max_concurrent_workers = max_concurrent_workers
        self.reap_interval_seconds = reap_interval_seconds
        self.stale_lock_ttl_seconds = stale_lock_ttl_seconds
        self._queue: asyncio.Queue[ExecutionRequest] | None = None
        self._semaphore: asyncio.Semaphore | None = None
        self._worker_task: asyncio.Task | None = None
        self._reaper_task: asyncio.Task | None = None
        self._inflight: set[asyncio.Task] = set()
        # Instrumentation only -- read by tests to confirm the periodic
        # reaper actually fires more than once, without waiting out real
        # `reap_interval_seconds` gaps.
        self.reap_count = 0
        self.evicted_lock_count = 0

    async def start(self) -> None:
        """Idempotent, and safe to call even if this `QueueService` object
        is being reused across a *different* event loop than the one it was
        last `start()`-ed under (e.g. two separate `TestClient(app)` runs
        against the same process-wide `lru_cache`d instance) -- `_queue`/
        `_semaphore` are always rebuilt fresh here rather than reused, and a
        leftover `Task` from a now-dead loop reads as `.done()` so this
        self-heals instead of silently no-op'ing forever."""
        if self._worker_task is not None and not self._worker_task.done():
            return
        self._queue = asyncio.Queue()
        self._semaphore = asyncio.Semaphore(self.max_concurrent_workers)
        self._worker_task = asyncio.create_task(self._worker_loop())
        self._reaper_task = asyncio.create_task(self._reaper_loop())

    async def stop(self) -> None:
        tasks = [t for t in (self._worker_task, self._reaper_task) if t is not None]
        tasks.extend(self._inflight)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._worker_task = None
        self._reaper_task = None
        self._inflight.clear()
        self._queue = None
        self._semaphore = None

    async def join(self) -> None:
        """Block until every enqueued request has been fully processed.
        Mainly for tests -- production code polls `GET /api/executions/{id}`
        instead of blocking."""
        if self._queue is not None:
            await self._queue.join()

    async def enqueue(self, task_id: str, executor_id: str | None = None) -> str:
        """Generate the execution id up front, write the "pending" placeholder
        row so it's immediately visible via `GET /api/executions/{id}`, queue
        the request, and return the id without waiting for a worker."""
        if self._queue is None:
            await self.start()
        execution_id = f"exec-{uuid.uuid4().hex[:12]}"
        self.engine.store.save_execution(
            _placeholder_result(execution_id, task_id, executor_id, "pending", "queued")
        )
        assert self._queue is not None
        await self._queue.put(ExecutionRequest(execution_id, task_id, executor_id))
        return execution_id

    async def _worker_loop(self) -> None:
        """Dequeues continuously and spawns one task per request; the
        `asyncio.Semaphore` inside `_process` -- not this loop -- is what
        actually bounds concurrent *executions*. This lets the queue keep
        draining (and marking requests "running" the instant a slot frees
        up) instead of only ever looking at one item at a time."""
        try:
            while True:
                assert self._queue is not None
                request = await self._queue.get()
                task = asyncio.create_task(self._process(request))
                self._inflight.add(task)
                task.add_done_callback(self._inflight.discard)
        except asyncio.CancelledError:
            pass

    async def _process(self, request: ExecutionRequest) -> None:
        assert self._semaphore is not None
        try:
            async with self._semaphore:
                self.engine.store.save_execution(
                    _placeholder_result(request.execution_id, request.task_id, request.executor_id, "running", "running")
                )
                try:
                    result = await self.execution_service.run(
                        request.task_id, request.executor_id, execution_id=request.execution_id
                    )
                except Exception as exc:  # noqa: BLE001 — this is the queue's own safety net; see docstring below
                    # A crash inside run() (bad executor_id, unhandled
                    # executor error, ...) must still resolve the placeholder
                    # row instead of leaving it stuck on "running" forever --
                    # this is a queue-layer safety net, not a replacement for
                    # ExecutionService's own error handling.
                    self.engine.store.save_execution(
                        _placeholder_result(request.execution_id, request.task_id, request.executor_id, "failed", f"queue worker error: {exc}")
                    )
                    return
                # `run()` already saved this row for completed/simulated/
                # failed outcomes (with our pinned execution_id, so this is
                # an idempotent no-op re-upsert for those). It does *not*
                # save anything for "approval_required" (K2's contract: a
                # blocked run leaves no executions row) -- this is the one
                # outcome that needs this explicit write, so GET
                # /api/executions/{id} doesn't stay stuck on "running".
                self.engine.store.save_execution(result)
        finally:
            if self._queue is not None:
                self._queue.task_done()

    async def _reaper_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(self.reap_interval_seconds)
                self.engine.reap_orphaned(actor="queue-reaper")
                self.evicted_lock_count += evict_stale_locks(
                    self.execution_service.lock_manager.root, self.stale_lock_ttl_seconds
                )
                self.reap_count += 1
        except asyncio.CancelledError:
            pass
