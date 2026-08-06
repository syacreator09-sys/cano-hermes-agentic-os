"""Plan Prometeo F3 — the three soldered links:

1. ExecutionService actually builds and persists an ApprovalRequest through
   ApprovalService when policy or budget blocks a run, with a schema that
   rejects incomplete requests; the "nobody approves their own request" rule
   holds through the HTTP layer too.
2. BudgetLedger is sqlite-persisted, reads `default_daily_budget_usd` from
   Settings, and a budget breach forces approval exactly like a sensitive
   action does.
3. ContainerSandboxExecutor is registered in ExecutionService and runs
   (simulated) in dry_run mode without a real Docker daemon.
"""
from __future__ import annotations

import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from pydantic import ValidationError

from cano_hermes.domain.enums import RiskLevel, TaskStatus
from cano_hermes.domain.models import ApprovalRequest, TaskCreate
from cano_hermes.governance.approvals import ApprovalService
from cano_hermes.governance.budget import BudgetLedger, BudgetService
from cano_hermes.intelligence.router import ModelRouter
from cano_hermes.orchestration.conductor import Conductor
from cano_hermes.orchestration.execution_service import ExecutionService
from cano_hermes.orchestration.task_engine import TaskEngine
from cano_hermes.registry.agents import AgentRegistry
from cano_hermes.storage.sqlite import SQLiteStore

ROOT = Path(__file__).resolve().parents[1]


def _full_approval_kwargs(**overrides):
    kwargs = {
        "task_id": "task-1",
        "action": "production_write",
        "motivo": "sensitive action requires human approval",
        "risk": RiskLevel.HIGH,
        "requested_by": "conductor",
        "costo_estimado_usd": 1.5,
        "presupuesto_restante": 3.5,
        "canal": "engineering",
        "evidencia": "storage/workspaces/task-1/approval-evidence-task-1.json",
    }
    kwargs.update(overrides)
    return kwargs


class ApprovalRequestSchemaTests(unittest.TestCase):
    def test_full_request_constructs(self):
        approval = ApprovalRequest(**_full_approval_kwargs())
        self.assertEqual(approval.motivo, "sensitive action requires human approval")
        # backward-compatible alias for the pre-F3 field name
        self.assertEqual(approval.reason, approval.motivo)

    def test_missing_costo_estimado_rejected_with_clear_message(self):
        kwargs = _full_approval_kwargs()
        del kwargs["costo_estimado_usd"]
        with self.assertRaises(ValidationError) as ctx:
            ApprovalRequest(**kwargs)
        self.assertIn("costo_estimado_usd", str(ctx.exception))

    def test_missing_canal_rejected(self):
        kwargs = _full_approval_kwargs()
        del kwargs["canal"]
        with self.assertRaises(ValidationError) as ctx:
            ApprovalRequest(**kwargs)
        self.assertIn("canal", str(ctx.exception))

    def test_missing_evidencia_rejected(self):
        kwargs = _full_approval_kwargs()
        del kwargs["evidencia"]
        with self.assertRaises(ValidationError):
            ApprovalRequest(**kwargs)

    def test_blank_motivo_rejected(self):
        with self.assertRaises(ValidationError):
            ApprovalRequest(**_full_approval_kwargs(motivo=""))


class ApprovalServiceSelfApprovalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = SQLiteStore(f"sqlite:///{self.tmp.name}/db.sqlite")
        self.service = ApprovalService(self.store)

    def tearDown(self):
        self.tmp.cleanup()

    def test_requester_cannot_resolve_their_own_request(self):
        approval = self.service.request(ApprovalRequest(**_full_approval_kwargs(requested_by="office-content")))
        with self.assertRaises(PermissionError):
            self.service.resolve(approval.id, True, "office-content")

    def test_a_different_actor_can_resolve_it(self):
        approval = self.service.request(ApprovalRequest(**_full_approval_kwargs(requested_by="office-content")))
        resolved = self.service.resolve(approval.id, True, "cano")
        self.assertEqual(resolved.resolved_by, "cano")


class BudgetPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = SQLiteStore(f"sqlite:///{self.tmp.name}/db.sqlite")

    def tearDown(self):
        self.tmp.cleanup()

    def test_reads_default_daily_budget_from_settings_when_unset(self):
        from cano_hermes.config import settings

        service = BudgetService(self.store)
        self.assertEqual(service.daily_limit_usd, settings.default_daily_budget_usd)

    def test_ledger_persists_across_service_instances(self):
        first = BudgetService(self.store, daily_limit_usd=2.0)
        first.record_spend(0.75, day="2026-08-05")
        second = BudgetService(self.store, daily_limit_usd=2.0)
        ledger = second.ledger_for(day="2026-08-05")
        self.assertAlmostEqual(ledger.spent_usd, 0.75)
        self.assertAlmostEqual(ledger.remaining_usd, 1.25)

    def test_can_spend_false_once_over_budget(self):
        service = BudgetService(self.store, daily_limit_usd=1.0)
        service.record_spend(0.9, day="2026-08-05")
        self.assertFalse(service.can_spend(0.5, day="2026-08-05"))

    def test_ingest_usage_file_reads_hermes_agent_schema(self):
        service = BudgetService(self.store, daily_limit_usd=5.0)
        usage = Path(self.tmp.name) / "usage-task-1.json"
        usage.write_text(json.dumps({"estimated_cost_usd": 0.42, "model": "kimi-k2.6"}))
        recorded = service.ingest_usage_file(usage, day="2026-08-05")
        self.assertAlmostEqual(recorded, 0.42)
        self.assertAlmostEqual(service.ledger_for(day="2026-08-05").spent_usd, 0.42)

    def test_ingest_missing_file_is_a_noop_not_a_crash(self):
        service = BudgetService(self.store, daily_limit_usd=5.0)
        recorded = service.ingest_usage_file(Path(self.tmp.name) / "does-not-exist.json")
        self.assertEqual(recorded, 0.0)

    def test_force_record_never_raises_even_over_budget(self):
        ledger = BudgetLedger(daily_limit_usd=1.0, spent_usd=0.9)
        ledger.record(5.0, force=True)  # would raise without force
        self.assertAlmostEqual(ledger.spent_usd, 5.9)


class ExecutionServiceWiringTests(unittest.TestCase):
    def _engine(self, d: str) -> TaskEngine:
        return TaskEngine(SQLiteStore(f"sqlite:///{d}/db.sqlite"), Conductor(AgentRegistry(ROOT / "agents"), ModelRouter()))

    def test_container_sandbox_is_registered(self):
        with tempfile.TemporaryDirectory() as d:
            service = ExecutionService(self._engine(d), "dry_run", Path(d) / "ws")
            self.assertIn("container-sandbox", service.executors)

    def test_container_sandbox_runs_simulated_in_dry_run(self):
        with tempfile.TemporaryDirectory() as d:
            engine = self._engine(d)
            task = engine.create(TaskCreate(title="Sandbox smoke test", objective="run isolated command", domain="engineering"))
            engine.plan(task.id)
            service = ExecutionService(engine, "dry_run", Path(d) / "ws")
            result = asyncio.run(service.run(task.id, "container-sandbox"))
            self.assertEqual(result.status, "simulated")
            self.assertEqual(engine.require(task.id).status, TaskStatus.REVIEW)

    def test_blocked_run_persists_a_full_approval_request(self):
        with tempfile.TemporaryDirectory() as d:
            engine = self._engine(d)
            task = engine.create(
                TaskCreate(
                    title="Publish external content",
                    objective="Publish a video to the channel",
                    domain="engineering",
                    risk=RiskLevel.HIGH,
                    metadata={"requested_by": "office-content"},
                )
            )
            engine.plan(task.id)
            # non-dry-run mode: PermissionEngine always requires approval for
            # "production_write" (SENSITIVE_ACTIONS), independent of budget.
            service = ExecutionService(engine, "supervised", Path(d) / "ws")
            result = asyncio.run(service.run(task.id, "claude-code"))
            self.assertEqual(result.status, "approval_required")
            self.assertEqual(engine.require(task.id).status, TaskStatus.APPROVAL)

            approvals = service.approvals.store.list_approvals()
            self.assertEqual(len(approvals), 1)
            approval = approvals[0]
            self.assertEqual(approval.task_id, task.id)
            self.assertEqual(approval.requested_by, "office-content")
            self.assertEqual(approval.canal, "engineering")
            self.assertTrue(approval.evidencia)
            self.assertTrue(Path(approval.evidencia).exists())
            self.assertGreaterEqual(approval.presupuesto_restante, 0)

    def test_budget_breach_also_forces_approval(self):
        with tempfile.TemporaryDirectory() as d:
            engine = self._engine(d)
            task = engine.create(
                TaskCreate(
                    title="Cheap but over-budget task",
                    objective="Do a small simulated task",
                    domain="engineering",
                    budget={"max_cost_usd": 10.0},
                )
            )
            engine.plan(task.id)
            budget = BudgetService(engine.store, daily_limit_usd=1.0)
            service = ExecutionService(engine, "dry_run", Path(d) / "ws", budget=budget)
            result = asyncio.run(service.run(task.id, "claude-code"))
            self.assertEqual(result.status, "approval_required")


class ApprovalApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["HERMES_DATABASE_URL"] = f"sqlite:///{self.tmp.name}/api.db"
        from cano_hermes.api import dependencies

        dependencies.store.cache_clear()
        dependencies.registry.cache_clear()
        dependencies.engine.cache_clear()
        dependencies.approvals.cache_clear()
        dependencies.budget.cache_clear()
        dependencies.execution_service.cache_clear()
        from cano_hermes.api.app import app

        self.client = TestClient(app)

    def tearDown(self):
        self.tmp.cleanup()
        os.environ.pop("HERMES_DATABASE_URL", None)

    def test_execute_endpoint_triggers_approval_flow_and_resolve_blocks_self_approval(self):
        created = self.client.post(
            "/api/tasks",
            json={
                "title": "Deploy the office",
                "objective": "Deploy a production change",
                "domain": "engineering",
                "risk": "critical",
                "metadata": {"requested_by": "office-content"},
            },
        )
        self.assertEqual(created.status_code, 200)
        task_id = created.json()["id"]
        self.client.post(f"/api/tasks/{task_id}/plan")

        from cano_hermes.api import dependencies

        dependencies.execution_service().mode = "supervised"
        dependencies.execution_service().policy.execution_mode = "supervised"

        executed = self.client.post(f"/api/tasks/{task_id}/execute")
        self.assertEqual(executed.status_code, 200)
        self.assertEqual(executed.json()["status"], "approval_required")

        approvals_list = self.client.get("/api/approvals").json()
        self.assertEqual(len(approvals_list), 1)
        approval_id = approvals_list[0]["id"]

        # nobody approves their own request, enforced through the HTTP layer
        self_resolve = self.client.post(
            f"/api/approvals/{approval_id}/resolve",
            json={"approved": True, "actor": "office-content"},
        )
        self.assertEqual(self_resolve.status_code, 403)

        other_resolve = self.client.post(
            f"/api/approvals/{approval_id}/resolve",
            json={"approved": True, "actor": "cano"},
        )
        self.assertEqual(other_resolve.status_code, 200)
        self.assertEqual(other_resolve.json()["status"], "approved")

    def test_resolve_unknown_approval_is_404(self):
        response = self.client.post(
            "/api/approvals/approval-does-not-exist/resolve",
            json={"approved": True, "actor": "cano"},
        )
        self.assertEqual(response.status_code, 404)

    def test_execute_unknown_task_is_404(self):
        response = self.client.post("/api/tasks/task-does-not-exist/execute")
        self.assertEqual(response.status_code, 404)


class SkillRegistryWarningTests(unittest.TestCase):
    def test_manifest_without_skill_md_warns_but_still_loads(self):
        from cano_hermes.registry.skills import SkillRegistry

        with tempfile.TemporaryDirectory() as d:
            skill_dir = Path(d) / "orphan-skill"
            skill_dir.mkdir()
            (skill_dir / "manifest.json").write_text(json.dumps({"id": "orphan-skill", "version": "0.1.0"}))
            with self.assertLogs("cano_hermes.registry.skills", level="WARNING") as ctx:
                skills = SkillRegistry(Path(d)).load()
            self.assertIn("orphan-skill", skills)
            self.assertTrue(any("SKILL.md" in message for message in ctx.output))

    def test_invalid_manifest_json_is_skipped_with_warning_not_fatal(self):
        from cano_hermes.registry.skills import SkillRegistry

        with tempfile.TemporaryDirectory() as d:
            broken_dir = Path(d) / "broken-skill"
            broken_dir.mkdir()
            (broken_dir / "manifest.json").write_text("{not valid json")
            good_dir = Path(d) / "good-skill"
            good_dir.mkdir()
            (good_dir / "manifest.json").write_text(json.dumps({"id": "good-skill"}))
            (good_dir / "SKILL.md").write_text("# good skill")

            with self.assertLogs("cano_hermes.registry.skills", level="WARNING") as ctx:
                skills = SkillRegistry(Path(d)).load()
            self.assertNotIn("broken-skill", skills)
            self.assertIn("good-skill", skills)
            self.assertTrue(any("Skipping" in message for message in ctx.output))


if __name__ == "__main__":
    unittest.main()
