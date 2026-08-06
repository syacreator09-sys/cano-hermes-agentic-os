"""K2 -- gaps 5 and 10 of the original plan.

1. `storage/artifacts/<task_id>/<executor_id>/` actually gets populated from
   a completed/simulated run's workspace, excluding known junk and the
   usage-file sidecar; the copied paths land on both `ExecutionResult.
   artifacts` and the `executions.artifacts_json` row.
2. REVIEW is no longer a de facto terminal state: LOW-risk tasks
   auto-transition REVIEW -> DONE; MEDIUM/HIGH/CRITICAL stay in REVIEW until
   a human (or an authorized later step) calls
   `POST /api/tasks/{id}/complete`.
"""
from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from cano_hermes.domain.enums import RiskLevel, TaskStatus
from cano_hermes.domain.models import ExecutionResult, TaskCreate
from cano_hermes.intelligence.router import ModelRouter
from cano_hermes.orchestration.conductor import Conductor
from cano_hermes.orchestration.execution_service import ExecutionService
from cano_hermes.orchestration.task_engine import TaskEngine
from cano_hermes.registry.agents import AgentRegistry
from cano_hermes.runtimes.base import Executor
from cano_hermes.storage.sqlite import SQLiteStore

ROOT = Path(__file__).resolve().parents[1]


class _WritingExecutor(Executor):
    """None of the current executors write real output files in dry_run
    (nothing touches disk) or in the test suite's non-subprocess paths, so
    this stands in for one that does -- the only way to exercise the
    artifact-copy path without spawning a real `claude`/`hermes` process."""

    id = "claude-code"

    async def execute(self, packet):
        packet.workspace.mkdir(parents=True, exist_ok=True)
        (packet.workspace / "output.txt").write_text("deliverable content")
        (packet.workspace / f"usage-{packet.task_id}.json").write_text("{}")
        cache_dir = packet.workspace / "__pycache__"
        cache_dir.mkdir()
        (cache_dir / "junk.pyc").write_text("noise")
        return ExecutionResult(task_id=packet.task_id, executor=self.id, status="completed", summary="wrote output")


class ArtifactsTests(unittest.TestCase):
    def _engine(self, d: str) -> TaskEngine:
        return TaskEngine(SQLiteStore(f"sqlite:///{d}/db.sqlite"), Conductor(AgentRegistry(ROOT / "agents"), ModelRouter()))

    def test_artifacts_are_copied_and_recorded_excluding_junk(self):
        with tempfile.TemporaryDirectory() as d:
            engine = self._engine(d)
            task = engine.create(
                TaskCreate(title="Write a doc", objective="produce output", domain="engineering", risk=RiskLevel.LOW)
            )
            engine.plan(task.id)
            service = ExecutionService(engine, "dry_run", Path(d) / "ws", artifacts_root=Path(d) / "artifacts")
            service.executors["claude-code"] = _WritingExecutor()

            result = asyncio.run(service.run(task.id, "claude-code"))

            self.assertEqual(len(result.artifacts), 1)
            artifact_path = Path(result.artifacts[0])
            self.assertTrue(artifact_path.exists())
            self.assertEqual(artifact_path.read_text(), "deliverable content")
            self.assertTrue(str(artifact_path).startswith(str(Path(d) / "artifacts")))
            # the usage-file sidecar and __pycache__ junk must NOT be copied
            self.assertFalse(any("usage-" in p for p in result.artifacts))
            self.assertFalse(any("__pycache__" in p for p in result.artifacts))

            rows = engine.store.get_executions_for_task(task.id)
            self.assertEqual(rows[0]["artifacts"], result.artifacts)

            events = engine.store.list_events(task.id)
            self.assertTrue(any(e.kind == "task.artifacts" for e in events))

    def test_no_artifacts_is_not_an_error_for_an_untouched_workspace(self):
        with tempfile.TemporaryDirectory() as d:
            engine = self._engine(d)
            task = engine.create(TaskCreate(title="Plan only", objective="think about it", domain="engineering"))
            engine.plan(task.id)
            service = ExecutionService(engine, "dry_run", Path(d) / "ws", artifacts_root=Path(d) / "artifacts")
            result = asyncio.run(service.run(task.id, "container-sandbox"))
            self.assertEqual(result.artifacts, [])


class RiskBasedCompletionTests(unittest.TestCase):
    def _engine(self, d: str) -> TaskEngine:
        return TaskEngine(SQLiteStore(f"sqlite:///{d}/db.sqlite"), Conductor(AgentRegistry(ROOT / "agents"), ModelRouter()))

    def test_low_risk_auto_completes_to_done(self):
        with tempfile.TemporaryDirectory() as d:
            engine = self._engine(d)
            task = engine.create(
                TaskCreate(title="Low risk chore", objective="do something small", domain="engineering", risk=RiskLevel.LOW)
            )
            engine.plan(task.id)
            service = ExecutionService(engine, "dry_run", Path(d) / "ws", artifacts_root=Path(d) / "artifacts")
            asyncio.run(service.run(task.id, "container-sandbox"))
            self.assertEqual(engine.require(task.id).status, TaskStatus.DONE)

    def test_medium_risk_stays_in_review_pending_manual_completion(self):
        with tempfile.TemporaryDirectory() as d:
            engine = self._engine(d)
            task = engine.create(
                TaskCreate(title="Ship carefully", objective="do risky work", domain="engineering", risk=RiskLevel.MEDIUM)
            )
            engine.plan(task.id)
            service = ExecutionService(engine, "dry_run", Path(d) / "ws", artifacts_root=Path(d) / "artifacts")
            service.executors["claude-code"] = _WritingExecutor()
            asyncio.run(service.run(task.id, "claude-code"))
            self.assertEqual(engine.require(task.id).status, TaskStatus.REVIEW)


class CompleteEndpointTests(unittest.TestCase):
    """POST /api/tasks/{id}/complete -- the manual close for whatever K2's
    auto-completion left in REVIEW."""

    def setUp(self):
        from cano_hermes.config import settings

        self.tmp = tempfile.TemporaryDirectory()
        self._original_database_url = settings.database_url
        settings.database_url = f"sqlite:///{self.tmp.name}/api.db"

        from cano_hermes.api import dependencies

        self._cached = (
            dependencies.store, dependencies.registry, dependencies.engine,
            dependencies.approvals, dependencies.budget, dependencies.execution_service,
        )
        for cached in self._cached:
            cached.cache_clear()
        from cano_hermes.api.app import app

        self.client = TestClient(app)

    def tearDown(self):
        self.tmp.cleanup()
        from cano_hermes.config import settings

        settings.database_url = self._original_database_url
        for cached in self._cached:
            cached.cache_clear()

    def test_complete_closes_a_task_stuck_in_review(self):
        created = self.client.post(
            "/api/tasks",
            json={"title": "Ship a feature", "objective": "do the work", "domain": "engineering", "risk": "medium"},
        )
        task_id = created.json()["id"]

        from cano_hermes.api import dependencies

        # Put the task in REVIEW the same way a real MEDIUM-risk run would
        # leave it -- exercising the endpoint doesn't require a real
        # execution, just the state it's meant to close out.
        dependencies.engine().transition(task_id, TaskStatus.REVIEW, "test-setup", {})

        resolved = self.client.post(f"/api/tasks/{task_id}/complete", json={"actor": "cano"})
        self.assertEqual(resolved.status_code, 200)
        self.assertEqual(resolved.json()["status"], "done")

    def test_complete_refuses_a_task_not_in_review(self):
        created = self.client.post(
            "/api/tasks", json={"title": "Still in the inbox", "objective": "not started yet", "domain": "engineering"}
        )
        task_id = created.json()["id"]

        response = self.client.post(f"/api/tasks/{task_id}/complete")
        self.assertEqual(response.status_code, 409)

    def test_complete_unknown_task_is_404(self):
        response = self.client.post("/api/tasks/task-does-not-exist/complete")
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
