"""A3 (plan AUTONOMÍA TOTAL, 2026-08-08) -- "regla dura: el navegador
autónomo NUNCA hace logins/OAuth, nunca compra, nunca publica" must be a
real, enforced property, not just documentation.

Traced the actual mechanism rather than assuming one: under
execution_mode="supervised" (this machine's real default, see
governance/auto_approval.py's own docstring), EVERY task's action label
is the coarse "production_write" (ExecutionService.run), which is itself
in policy.SENSITIVE_ACTIONS -- so every non-dry-run task already lands in
TaskStatus.APPROVAL first, browser or not. The K12 auto-approval engine
(governance/auto_approval.py::try_auto_approve) can clear that
automatically, but only when ALL of its conditions hold, including
costo_estimado_usd == 0 exactly. ui-reviewer and browser-operator both
declare budget.max_cost_usd: 0.5 (nonzero) -- so that condition always
fails for them, and a human always sees the request before a browser
task runs, regardless of risk level.
"""

from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path

from cano_hermes.domain.enums import RiskLevel, TaskStatus
from cano_hermes.domain.models import TaskCreate
from cano_hermes.orchestration.conductor import Conductor
from cano_hermes.orchestration.execution_service import ExecutionService
from cano_hermes.orchestration.task_engine import TaskEngine
from cano_hermes.intelligence.router import ModelRouter
from cano_hermes.registry.agents import AgentRegistry
from cano_hermes.storage.sqlite import SQLiteStore

ROOT = Path(__file__).resolve().parents[1]


class BrowserTaskNeverAutoApprovesTests(unittest.TestCase):
    def _engine(self, d: str) -> TaskEngine:
        return TaskEngine(SQLiteStore(f"sqlite:///{d}/db.sqlite"), Conductor(AgentRegistry(ROOT / "agents"), ModelRouter()))

    def _status_after_run(self, d: str, agent_id: str, risk: RiskLevel) -> TaskStatus:
        engine = self._engine(d)
        task = engine.create(TaskCreate(
            title="Navega y verifica", objective="visita una página pública y reporta",
            domain="operations", risk=risk,
        ))
        engine.plan(task.id)
        # Pin to the real browser-capable agent regardless of which
        # "operations" agent Conductor.assign happened to pick first
        # (agents[0] in registry-load order, not risk-aware for this
        # team) -- what this test cares about is what happens once a
        # task genuinely IS assigned to a browser-tool agent.
        pinned = engine.require(task.id)
        pinned.assigned_agent = agent_id
        engine.store.save_task(pinned)

        service = ExecutionService(engine, "supervised", Path(d) / "ws")
        result = asyncio.run(service.run(task.id))
        return engine.require(result.task_id).status

    def test_browser_operator_low_risk_lands_in_approval_not_done(self):
        with tempfile.TemporaryDirectory() as d:
            status = self._status_after_run(d, "browser-operator", RiskLevel.LOW)
        self.assertEqual(status, TaskStatus.APPROVAL)

    def test_ui_reviewer_low_risk_lands_in_approval_not_done(self):
        with tempfile.TemporaryDirectory() as d:
            status = self._status_after_run(d, "ui-reviewer", RiskLevel.LOW)
        self.assertEqual(status, TaskStatus.APPROVAL)

    def test_browser_operator_never_silently_executes_at_any_risk(self):
        for risk in (RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH):
            with self.subTest(risk=risk):
                with tempfile.TemporaryDirectory() as d:
                    status = self._status_after_run(d, "browser-operator", risk)
                self.assertEqual(status, TaskStatus.APPROVAL)


if __name__ == "__main__":
    unittest.main()
