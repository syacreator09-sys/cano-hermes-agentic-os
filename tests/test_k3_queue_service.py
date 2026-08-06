"""K3 -- queue + real parallelism.

Three things this proves that didn't exist before K3:

1. `QueueService` actually bounds concurrent `ExecutionService.run()` calls
   to `max_concurrent_workers` -- four tasks enqueued at once with the limit
   set to 2 never have more than 2 RUNNING simultaneously, and all four
   still complete (`RenderLockSerializationTests` in test_k2_locks_worktrees
   proved *sequential* via the render lock; this proves *bounded parallel*
   via the semaphore, a different mechanism entirely).
2. `POST /api/tasks/{id}/execute` returns 202 immediately (no longer blocks
   on the run), and `GET /api/executions/{id}` reflects the real
   pending -> running -> done progression by polling, not by inspecting
   internals.
3. The periodic reaper (QueueService's own loop, distinct from the
   once-at-startup call K0 already had) actually fires more than once, using
   a short interval instead of waiting out real minutes.
"""

from __future__ import annotations

import asyncio
import tempfile
import time
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from cano_hermes.domain.enums import TaskStatus
from cano_hermes.domain.models import ExecutionResult, TaskCreate
from cano_hermes.intelligence.router import ModelRouter
from cano_hermes.orchestration.conductor import Conductor
from cano_hermes.orchestration.execution_service import ExecutionService
from cano_hermes.orchestration.queue_service import QueueService
from cano_hermes.orchestration.task_engine import TaskEngine
from cano_hermes.registry.agents import AgentRegistry
from cano_hermes.runtimes.base import Executor
from cano_hermes.storage.sqlite import SQLiteStore

ROOT = Path(__file__).resolve().parents[1]


def _engine(d: str) -> TaskEngine:
    return TaskEngine(SQLiteStore(f"sqlite:///{d}/db.sqlite"), Conductor(AgentRegistry(ROOT / "agents"), ModelRouter()))


class _SlowExecutor(Executor):
    """Same instrumentation pattern K2's RenderLockSerializationTests used:
    a (task_id, "start"/"end", monotonic timestamp) log around a short
    sleep, so concurrency can be measured from real timestamps instead of
    inferred from absence-of-exception."""

    id = "claude-code"

    def __init__(self, log: list, delay: float = 0.12) -> None:
        self.log = log
        self.delay = delay

    async def execute(self, packet):
        self.log.append((packet.task_id, "start", time.monotonic()))
        await asyncio.sleep(self.delay)
        self.log.append((packet.task_id, "end", time.monotonic()))
        return ExecutionResult(task_id=packet.task_id, executor=self.id, status="completed", summary="done")


def _peak_concurrency(log: list) -> int:
    events = sorted((ts, 1 if kind == "start" else -1) for (_task_id, kind, ts) in log)
    current = peak = 0
    for _, delta in events:
        current += delta
        peak = max(peak, current)
    return peak


class BoundedParallelismTests(unittest.TestCase):
    def test_four_tasks_never_exceed_two_running_and_all_complete(self):
        with tempfile.TemporaryDirectory() as d:
            engine = _engine(d)
            service = ExecutionService(engine, "dry_run", Path(d) / "ws", artifacts_root=Path(d) / "artifacts")
            log: list = []
            service.executors["claude-code"] = _SlowExecutor(log, delay=0.12)
            queue = QueueService(service, engine, max_concurrent_workers=2)

            async def scenario():
                await queue.start()
                task_ids = []
                for i in range(4):
                    task = engine.create(
                        TaskCreate(title=f"Task {i}", objective=f"do thing {i}", domain="operations")
                    )
                    engine.plan(task.id)
                    task_ids.append(task.id)
                execution_ids = [await queue.enqueue(tid, "claude-code") for tid in task_ids]
                await queue.join()
                await queue.stop()
                return task_ids, execution_ids

            task_ids, execution_ids = asyncio.run(scenario())

            # The actual proof: at no point did more than 2 executions
            # overlap, even though 4 were enqueued simultaneously.
            self.assertEqual(len(log), 8)  # 4 tasks * (start + end)
            self.assertLessEqual(_peak_concurrency(log), 2)
            # ... and every one of the 4 still ran to completion.
            started_tasks = {t for (t, kind, _ts) in log if kind == "start"}
            self.assertEqual(started_tasks, set(task_ids))
            for task_id in task_ids:
                self.assertEqual(engine.require(task_id).status, TaskStatus.DONE)
            for execution_id in execution_ids:
                row = engine.store.get_execution(execution_id)
                self.assertIsNotNone(row)
                self.assertEqual(row["status"], "completed")

    def test_semaphore_reads_settings_max_concurrent_workers_by_default(self):
        """api/dependencies.queue_service() wires Settings.max_concurrent_workers
        straight into the semaphore -- this is the "config finally read"
        part of K3, checked directly rather than through a full HTTP round
        trip."""
        from cano_hermes.api import dependencies
        from cano_hermes.config import settings

        dependencies.queue_service.cache_clear()
        try:
            svc = dependencies.queue_service()
            self.assertEqual(svc.max_concurrent_workers, settings.max_concurrent_workers)
        finally:
            dependencies.queue_service.cache_clear()


class AsyncExecuteEndpointTests(unittest.TestCase):
    def setUp(self):
        from cano_hermes.config import settings

        self.tmp = tempfile.TemporaryDirectory()
        self._original_database_url = settings.database_url
        settings.database_url = f"sqlite:///{self.tmp.name}/api.db"

        from cano_hermes.api import dependencies

        for dep in (
            dependencies.store,
            dependencies.registry,
            dependencies.engine,
            dependencies.approvals,
            dependencies.budget,
            dependencies.execution_service,
            dependencies.queue_service,
        ):
            dep.cache_clear()

    def tearDown(self):
        self.tmp.cleanup()
        from cano_hermes.config import settings

        settings.database_url = self._original_database_url
        from cano_hermes.api import dependencies

        for dep in (
            dependencies.store,
            dependencies.registry,
            dependencies.engine,
            dependencies.approvals,
            dependencies.budget,
            dependencies.execution_service,
            dependencies.queue_service,
        ):
            dep.cache_clear()

    def test_execute_returns_202_immediately_and_execution_progresses_to_done(self):
        from cano_hermes.api import dependencies
        from cano_hermes.api.app import app

        with TestClient(app) as client:
            # This process's real `.env` sets HERMES_EXECUTION_MODE=supervised
            # (production default), under which PermissionEngine always
            # routes to approval_required -- force dry_run here, the same
            # way test_execution_wiring.py's ApprovalApiTests forces the
            # opposite (supervised) for its own approval-flow test, so this
            # test exercises the pending -> running -> done path instead.
            dependencies.execution_service().mode = "dry_run"
            dependencies.execution_service().policy.execution_mode = "dry_run"
            # Swap in a slow, deterministic executor before it can be
            # dispatched, so the run is guaranteed to still be in flight
            # right after /execute returns.
            log: list = []
            dependencies.execution_service().executors["container-sandbox"] = _SlowExecutor(log, delay=0.3)

            created = client.post(
                "/api/tasks",
                json={"title": "Slow op", "objective": "do a slow simulated thing", "domain": "operations"},
            )
            self.assertEqual(created.status_code, 200)
            task_id = created.json()["id"]
            client.post(f"/api/tasks/{task_id}/plan")

            started_at = time.monotonic()
            executed = client.post(f"/api/tasks/{task_id}/execute", params={"executor_id": "container-sandbox"})
            elapsed = time.monotonic() - started_at

            self.assertEqual(executed.status_code, 202)
            body = executed.json()
            self.assertEqual(body["status"], "pending")
            execution_id = body["execution_id"]
            self.assertTrue(execution_id)
            # The HTTP request itself must not have waited for the 0.3s run.
            self.assertLess(elapsed, 0.25)

            # Immediately after 202, GET must already resolve the id (not 404)
            # and must not yet claim it's done.
            immediate = client.get(f"/api/executions/{execution_id}")
            self.assertEqual(immediate.status_code, 200)
            self.assertIn(immediate.json()["state"], {"pending", "running"})

            final = self._poll_until_done(client, execution_id)
            self.assertEqual(final["state"], "done")
            self.assertEqual(final["status"], "completed")
            self.assertEqual(final["task_id"], task_id)

    def test_get_unknown_execution_is_404(self):
        from cano_hermes.api.app import app

        with TestClient(app) as client:
            response = client.get("/api/executions/exec-does-not-exist")
            self.assertEqual(response.status_code, 404)

    @staticmethod
    def _poll_until_done(client, execution_id: str, timeout: float = 5.0) -> dict:
        deadline = time.monotonic() + timeout
        last = None
        while time.monotonic() < deadline:
            response = client.get(f"/api/executions/{execution_id}")
            if response.status_code == 200:
                last = response.json()
                if last["state"] == "done":
                    return last
            time.sleep(0.02)
        raise AssertionError(f"execution {execution_id} never reached done, last seen: {last}")


class PeriodicReaperTests(unittest.TestCase):
    def test_reaper_loop_fires_more_than_once_on_a_short_interval(self):
        with tempfile.TemporaryDirectory() as d:
            engine = _engine(d)
            service = ExecutionService(engine, "dry_run", Path(d) / "ws", artifacts_root=Path(d) / "artifacts")
            # A tiny interval stands in for the real 60s production value --
            # this proves the repetition mechanism is armed and actually
            # loops, without the test waiting out real minutes.
            queue = QueueService(service, engine, max_concurrent_workers=2, reap_interval_seconds=0.03)

            async def scenario():
                await queue.start()
                await asyncio.sleep(0.16)
                await queue.stop()
                return queue.reap_count

            reap_count = asyncio.run(scenario())
            self.assertGreaterEqual(reap_count, 2)

    def test_reaper_loop_actually_reaps_orphaned_tasks_created_after_startup(self):
        """Distinguishes the periodic loop from K0's once-at-boot call: a
        task orphaned *while the process is already running* (not just one
        left over from before a restart) still gets cleared, on the next
        tick, with no restart required."""
        with tempfile.TemporaryDirectory() as d:
            engine = _engine(d)
            service = ExecutionService(engine, "dry_run", Path(d) / "ws", artifacts_root=Path(d) / "artifacts")
            queue = QueueService(service, engine, max_concurrent_workers=2, reap_interval_seconds=0.03)

            async def scenario():
                await queue.start()
                task = engine.create(TaskCreate(title="Orphan mid-flight", objective="crash", domain="operations"))
                engine.transition(task.id, TaskStatus.RUNNING, "worker")
                await asyncio.sleep(0.16)
                await queue.stop()
                return task.id

            task_id = asyncio.run(scenario())
            self.assertEqual(engine.require(task_id).status, TaskStatus.FAILED)


if __name__ == "__main__":
    unittest.main()
