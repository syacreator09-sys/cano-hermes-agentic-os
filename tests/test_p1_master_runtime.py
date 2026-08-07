"""Plan POTENCIA P1 -- Hermes Master 24/7 suscripción-first.

Covers the three pieces wired in this phase:
1. ModelRouter gives governance-domain requests the same subscription-first
   bonus engineering already had (router.py).
2. ClaudeCodeExecutor.build_args picks --model from packet.metadata["risk"]
   (opus for high/critical, haiku for low, no override for medium/unset).
3. ExecutionService.run degrades from claude-code/codex to hermes-agent
   (tier-0) on a usage-limit failure, annotating metrics -- never escalates
   to a paid tier on its own.
"""
from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path

from cano_hermes.domain.enums import RiskLevel
from cano_hermes.domain.models import ExecutionResult, TaskCreate
from cano_hermes.intelligence.router import ModelRouter, RouteRequest
from cano_hermes.orchestration.conductor import Conductor
from cano_hermes.orchestration.execution_service import ExecutionService
from cano_hermes.orchestration.task_engine import TaskEngine
from cano_hermes.registry.agents import AgentRegistry
from cano_hermes.runtimes.base import ExecutionPacket, Executor
from cano_hermes.runtimes.claude_code import ClaudeCodeExecutor
from cano_hermes.storage.sqlite import SQLiteStore

ROOT = Path(__file__).resolve().parents[1]


class GovernanceRouterBonusTests(unittest.TestCase):
    def test_governance_prefers_subscription_over_tier0(self):
        router = ModelRouter()
        decision = router.route(RouteRequest(domain="governance", tools_required=True))
        self.assertIn(decision.profile.id, ("claude-subscription", "codex-subscription"))
        self.assertIn("master-runtime", decision.reasons)

    def test_engineering_bonus_unaffected(self):
        router = ModelRouter()
        decision = router.route(RouteRequest(domain="engineering", tools_required=True))
        self.assertIn("engineering-runtime", decision.reasons)


class ModelByRiskTests(unittest.TestCase):
    def _args_for(self, risk: str | None) -> list[str]:
        metadata = {"risk": risk} if risk is not None else {}
        packet = ExecutionPacket(task_id="t-1", objective="obj", workspace=Path("/tmp/ws"), metadata=metadata)
        return list(ClaudeCodeExecutor(mode="supervised").build_args(packet))

    def test_high_risk_uses_opus(self):
        args = self._args_for("high")
        self.assertIn("--model", args)
        self.assertEqual(args[args.index("--model") + 1], "opus")

    def test_critical_risk_uses_opus(self):
        args = self._args_for("critical")
        self.assertEqual(args[args.index("--model") + 1], "opus")

    def test_low_risk_uses_haiku(self):
        args = self._args_for("low")
        self.assertEqual(args[args.index("--model") + 1], "haiku")

    def test_medium_risk_has_no_override(self):
        args = self._args_for("medium")
        self.assertNotIn("--model", args)

    def test_missing_risk_has_no_override(self):
        args = self._args_for(None)
        self.assertNotIn("--model", args)


class _UsageLimitExecutor(Executor):
    """Simulates a subscription CLI hitting its window."""

    def __init__(self, executor_id: str) -> None:
        self.id = executor_id

    async def execute(self, packet):
        return ExecutionResult(
            task_id=packet.task_id, executor=self.id, status="failed",
            summary="Error: usage limit reached, try again later", exit_code=1,
        )


class _RecordingSuccessExecutor(Executor):
    def __init__(self, executor_id: str) -> None:
        self.id = executor_id
        self.received_packet = None

    async def execute(self, packet):
        self.received_packet = packet
        return ExecutionResult(task_id=packet.task_id, executor=self.id, status="simulated", summary="ok (fallback)")


class QuotaDegradationTests(unittest.TestCase):
    def _engine(self, d: str) -> TaskEngine:
        return TaskEngine(SQLiteStore(f"sqlite:///{d}/db.sqlite"), Conductor(AgentRegistry(ROOT / "agents"), ModelRouter()))

    def test_usage_limit_failure_degrades_to_hermes_agent(self):
        with tempfile.TemporaryDirectory() as d:
            engine = self._engine(d)
            task = engine.create(TaskCreate(title="Ad-hoc", objective="do a thing", domain="engineering"))
            service = ExecutionService(engine, "dry_run", Path(d) / "ws")
            service.executors["claude-code"] = _UsageLimitExecutor("claude-code")
            fallback = _RecordingSuccessExecutor("hermes-agent")
            service.executors["hermes-agent"] = fallback

            result = asyncio.run(service.run(task.id, "claude-code"))

            self.assertEqual(result.executor, "hermes-agent")
            self.assertEqual(result.status, "simulated")
            self.assertEqual(result.metrics.get("degraded_from"), "claude-code")
            self.assertEqual(result.metrics.get("degradation_reason"), "usage_limit")
            self.assertIsNotNone(fallback.received_packet)

    def test_non_usage_limit_failure_does_not_degrade(self):
        class _OtherFailureExecutor(Executor):
            id = "claude-code"

            async def execute(self, packet):
                return ExecutionResult(task_id=packet.task_id, executor="claude-code", status="failed", summary="syntax error in generated code", exit_code=1)

        with tempfile.TemporaryDirectory() as d:
            engine = self._engine(d)
            task = engine.create(TaskCreate(title="Ad-hoc", objective="do a thing", domain="engineering"))
            service = ExecutionService(engine, "dry_run", Path(d) / "ws")
            service.executors["claude-code"] = _OtherFailureExecutor()
            fallback = _RecordingSuccessExecutor("hermes-agent")
            service.executors["hermes-agent"] = fallback

            result = asyncio.run(service.run(task.id, "claude-code"))

            self.assertEqual(result.executor, "claude-code")
            self.assertEqual(result.status, "failed")
            self.assertIsNone(fallback.received_packet)

    def test_hermes_agent_itself_never_degrades_further(self):
        """hermes-agent is already the cheapest tier -- a usage-limit-shaped
        failure there must not attempt to degrade into itself."""
        with tempfile.TemporaryDirectory() as d:
            engine = self._engine(d)
            task = engine.create(TaskCreate(title="Ad-hoc", objective="do a thing", domain="research"))
            service = ExecutionService(engine, "dry_run", Path(d) / "ws")
            service.executors["hermes-agent"] = _UsageLimitExecutor("hermes-agent")

            result = asyncio.run(service.run(task.id, "hermes-agent"))

            self.assertEqual(result.executor, "hermes-agent")
            self.assertEqual(result.status, "failed")


class MasterRuntimeDashboardTests(unittest.TestCase):
    def test_no_store_degrades_honestly(self):
        from cano_hermes.orchestration.dashboards import _master_runtime_summary
        result = _master_runtime_summary(None)
        self.assertEqual(result["status"], "sin_datos")

    def test_counts_by_executor_and_degradations(self):
        from cano_hermes.orchestration.dashboards import _master_runtime_summary

        with tempfile.TemporaryDirectory() as d:
            store = SQLiteStore(f"sqlite:///{d}/db.sqlite")
            store.save_execution(ExecutionResult(task_id="t1", executor="claude-code", status="completed", summary="ok"))
            store.save_execution(ExecutionResult(
                task_id="t2", executor="hermes-agent", status="simulated", summary="ok (fallback)",
                metrics={"degraded_from": "codex", "degradation_reason": "usage_limit"},
            ))
            result = _master_runtime_summary(store)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["by_executor"], {"claude-code": 1, "hermes-agent": 1})
        self.assertEqual(result["degradations_count"], 1)
        self.assertEqual(len(result["recent"]), 2)


if __name__ == "__main__":
    unittest.main()
