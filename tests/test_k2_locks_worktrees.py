"""K2 -- wiring WriteLockManager and WorktreeManager into ExecutionService.

Both classes (cano_hermes/runtimes/locks.py, cano_hermes/runtimes/
worktrees.py) existed fully-formed but unimported anywhere before K2.

1. Every run is now held under WriteLockManager -- and any task whose
   metadata marks it a render (`{"kind": "render"}`) contends for one
   shared global lock key instead of its own workspace, so two renders can
   never overlap on this GPU-less machine. `WriteLockManager.acquire` is
   fail-fast by itself (raises on contention); ExecutionService wraps it in
   a poll loop (`_run_locked`) so the second contender actually *waits* and
   then runs, rather than erroring out -- this is what a real serialization
   test needs to demonstrate, not just "didn't crash".
2. Engineering-domain tasks run inside an isolated git worktree
   (WorktreeManager) instead of the shared workspace tree, whenever a real
   git repository is configured on the ExecutionService.
"""
from __future__ import annotations

import asyncio
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from cano_hermes.domain.models import ExecutionResult, TaskCreate
from cano_hermes.intelligence.router import ModelRouter
from cano_hermes.orchestration.conductor import Conductor
from cano_hermes.orchestration.execution_service import ExecutionService
from cano_hermes.orchestration.task_engine import TaskEngine
from cano_hermes.registry.agents import AgentRegistry
from cano_hermes.runtimes.base import Executor
from cano_hermes.runtimes.locks import WriteLockManager
from cano_hermes.runtimes.worktrees import WorktreeManager
from cano_hermes.storage.sqlite import SQLiteStore

ROOT = Path(__file__).resolve().parents[1]


def _engine(d: str) -> TaskEngine:
    return TaskEngine(SQLiteStore(f"sqlite:///{d}/db.sqlite"), Conductor(AgentRegistry(ROOT / "agents"), ModelRouter()))


async def _run_both(service: ExecutionService, task_id_a: str, task_id_b: str) -> None:
    """`asyncio.gather(...)` must be constructed *inside* a running loop
    (Python 3.12's `ensure_future` eagerly calls `get_event_loop()`) --
    calling it directly as an argument to `asyncio.run(...)` raises "no
    current event loop" before the loop exists. This is the coroutine
    `asyncio.run` actually drives."""
    await asyncio.gather(service.run(task_id_a, "claude-code"), service.run(task_id_b, "claude-code"))


class _SlowExecutor(Executor):
    """Records a (task_id, "start"/"end", timestamp) entry around a short
    sleep, so the test can prove real, non-overlapping ordering rather than
    just the absence of an exception."""

    id = "claude-code"

    def __init__(self, log: list, delay: float = 0.15) -> None:
        self.log = log
        self.delay = delay

    async def execute(self, packet):
        self.log.append((packet.task_id, "start", time.monotonic()))
        await asyncio.sleep(self.delay)
        self.log.append((packet.task_id, "end", time.monotonic()))
        return ExecutionResult(task_id=packet.task_id, executor=self.id, status="completed", summary="rendered")


class _RecordingExecutor(Executor):
    def __init__(self, executor_id: str) -> None:
        self.id = executor_id
        self.received_packet = None

    async def execute(self, packet):
        self.received_packet = packet
        return ExecutionResult(task_id=packet.task_id, executor=self.id, status="simulated", summary="recorded")


class RenderLockSerializationTests(unittest.TestCase):
    def test_two_render_tasks_never_overlap(self):
        with tempfile.TemporaryDirectory() as d:
            engine = _engine(d)
            t1 = engine.create(
                TaskCreate(title="Render A", objective="render clip A", domain="operations", metadata={"kind": "render"})
            )
            t2 = engine.create(
                TaskCreate(title="Render B", objective="render clip B", domain="operations", metadata={"kind": "render"})
            )
            engine.plan(t1.id)
            engine.plan(t2.id)
            service = ExecutionService(
                engine,
                "dry_run",
                Path(d) / "ws",
                artifacts_root=Path(d) / "artifacts",
                lock_manager=WriteLockManager(Path(d) / "locks"),
            )
            log: list = []
            service.executors["claude-code"] = _SlowExecutor(log)

            asyncio.run(_run_both(service, t1.id, t2.id))

            self.assertEqual(len(log), 4)
            first_task, first_event, _ = log[0]
            self.assertEqual(first_event, "start")
            self.assertEqual(log[1], (first_task, "end", log[1][2]))
            second_task, second_event, second_start = log[2]
            self.assertEqual(second_event, "start")
            self.assertNotEqual(second_task, first_task)
            self.assertEqual(log[3], (second_task, "end", log[3][2]))
            # the actual proof of serialization: the second run only starts
            # once the first one has finished -- never in parallel.
            first_end = log[1][2]
            self.assertGreaterEqual(second_start, first_end)

    def test_non_render_tasks_do_not_contend_for_the_render_lock(self):
        """A control: two ordinary (non-render) tasks have different
        workspaces, so they get different per-workspace lock keys and must
        run *concurrently* -- proving the serialization above comes from the
        shared render lock key specifically, not from some accidental
        global bottleneck in `_run_locked`.

        Asserted on the executor-level start/end log, not total wall-clock:
        each task run also does real, synchronous sqlite writes (task
        create/plan/transition/save_execution), and those interleave on the
        single-threaded event loop regardless of the lock, so wall-clock
        alone is too noisy a signal for "did these overlap".
        """
        with tempfile.TemporaryDirectory() as d:
            engine = _engine(d)
            t1 = engine.create(TaskCreate(title="Task A", objective="do A", domain="operations"))
            t2 = engine.create(TaskCreate(title="Task B", objective="do B", domain="operations"))
            engine.plan(t1.id)
            engine.plan(t2.id)
            service = ExecutionService(
                engine,
                "dry_run",
                Path(d) / "ws",
                artifacts_root=Path(d) / "artifacts",
                lock_manager=WriteLockManager(Path(d) / "locks"),
            )
            log: list = []
            service.executors["claude-code"] = _SlowExecutor(log, delay=0.1)

            asyncio.run(_run_both(service, t1.id, t2.id))

            self.assertEqual(len(log), 4)
            starts = sorted(ts for (_task, event, ts) in log if event == "start")
            ends = sorted(ts for (_task, event, ts) in log if event == "end")
            # real concurrency: the second task starts before the first one
            # ends -- the opposite of the render test's assertion above.
            self.assertLess(starts[1], ends[0])


class WorktreeIsolationTests(unittest.TestCase):
    def _init_repo(self, path: Path) -> Path:
        path.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init", "-q", str(path)], check=True)
        subprocess.run(["git", "-C", str(path), "config", "user.email", "test@example.com"], check=True)
        subprocess.run(["git", "-C", str(path), "config", "user.name", "Test"], check=True)
        (path / "README.md").write_text("demo repo\n")
        subprocess.run(["git", "-C", str(path), "add", "."], check=True)
        subprocess.run(["git", "-C", str(path), "commit", "-q", "-m", "init"], check=True)
        return path

    def test_engineering_task_runs_in_an_isolated_worktree(self):
        with tempfile.TemporaryDirectory() as d:
            repo = self._init_repo(Path(d) / "repo")
            engine = _engine(d)
            task = engine.create(TaskCreate(title="Fix a bug", objective="patch something", domain="engineering"))
            engine.plan(task.id)
            service = ExecutionService(
                engine,
                "dry_run",
                Path(d) / "ws",
                artifacts_root=Path(d) / "artifacts",
                worktree_manager=WorktreeManager(Path(d) / "worktrees"),
                repository=repo,
            )
            recorder = _RecordingExecutor("claude-code")
            service.executors["claude-code"] = recorder

            asyncio.run(service.run(task.id, "claude-code"))

            packet = recorder.received_packet
            self.assertIsNotNone(packet)
            self.assertNotEqual(packet.workspace.resolve(), repo.resolve())
            self.assertTrue(str(packet.workspace.resolve()).startswith(str((Path(d) / "worktrees").resolve())))

            worktree_list = subprocess.run(
                ["git", "-C", str(repo), "worktree", "list"], capture_output=True, text=True, check=True
            ).stdout
            self.assertIn(str(packet.workspace), worktree_list)

    def test_non_engineering_task_keeps_the_shared_workspace(self):
        with tempfile.TemporaryDirectory() as d:
            repo = self._init_repo(Path(d) / "repo")
            engine = _engine(d)
            task = engine.create(TaskCreate(title="Research something", objective="look into it", domain="research"))
            engine.plan(task.id)
            service = ExecutionService(
                engine,
                "dry_run",
                Path(d) / "ws",
                artifacts_root=Path(d) / "artifacts",
                worktree_manager=WorktreeManager(Path(d) / "worktrees"),
                repository=repo,
            )
            recorder = _RecordingExecutor("hermes-agent")
            service.executors["hermes-agent"] = recorder

            asyncio.run(service.run(task.id))

            packet = recorder.received_packet
            self.assertEqual(packet.workspace, Path(d) / "ws" / task.id / "hermes-agent")

    def test_engineering_task_without_a_configured_repository_keeps_the_shared_workspace(self):
        """Backward-compat guard: ExecutionService instances that never set
        `repository` (every pre-K2 caller, and most of this test suite)
        must keep behaving exactly as before -- no surprise git operations
        against whatever repo happens to be the process cwd."""
        with tempfile.TemporaryDirectory() as d:
            engine = _engine(d)
            task = engine.create(TaskCreate(title="Fix a bug", objective="patch something", domain="engineering"))
            engine.plan(task.id)
            service = ExecutionService(engine, "dry_run", Path(d) / "ws", artifacts_root=Path(d) / "artifacts")
            recorder = _RecordingExecutor("claude-code")
            service.executors["claude-code"] = recorder

            asyncio.run(service.run(task.id, "claude-code"))

            packet = recorder.received_packet
            self.assertEqual(packet.workspace, Path(d) / "ws" / task.id / "claude-code")


if __name__ == "__main__":
    unittest.main()
