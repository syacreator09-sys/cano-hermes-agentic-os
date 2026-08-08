"""A1 (plan AUTONOMÍA TOTAL, 2026-08-08) -- caller-supplied task_kind
("plan"/"consulta"/"rutina") picks the model Claude Code uses,
independent of and taking priority over risk-based RISK_TO_MODEL.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cano_hermes.domain.models import TaskCreate
from cano_hermes.orchestration.conductor import Conductor
from cano_hermes.orchestration.execution_service import ExecutionService
from cano_hermes.orchestration.task_engine import TaskEngine
from cano_hermes.intelligence.router import ModelRouter
from cano_hermes.registry.agents import AgentRegistry
from cano_hermes.runtimes.base import ExecutionPacket
from cano_hermes.runtimes.claude_code import ClaudeCodeExecutor
from cano_hermes.storage.sqlite import SQLiteStore

ROOT = Path(__file__).resolve().parents[1]


class TaskKindModelOverrideTests(unittest.TestCase):
    def _args_for(self, task_kind: str | None, risk: str | None = None) -> list[str]:
        metadata = {}
        if task_kind is not None:
            metadata["task_kind"] = task_kind
        if risk is not None:
            metadata["risk"] = risk
        packet = ExecutionPacket(task_id="t-1", objective="obj", workspace=Path("/tmp/ws"), metadata=metadata)
        return list(ClaudeCodeExecutor(mode="supervised").build_args(packet))

    def test_plan_uses_fable(self):
        args = self._args_for("plan")
        self.assertEqual(args[args.index("--model") + 1], "fable")

    def test_consulta_uses_fable(self):
        args = self._args_for("consulta")
        self.assertEqual(args[args.index("--model") + 1], "fable")

    def test_rutina_uses_haiku(self):
        args = self._args_for("rutina")
        self.assertEqual(args[args.index("--model") + 1], "haiku")

    def test_task_kind_wins_over_high_risk(self):
        """A HIGH-risk task that's explicitly routine grunt work should
        still get haiku, not opus -- task_kind is an explicit override."""
        args = self._args_for("rutina", risk="high")
        self.assertEqual(args[args.index("--model") + 1], "haiku")

    def test_unknown_task_kind_falls_back_to_risk(self):
        args = self._args_for("some-other-kind", risk="low")
        self.assertEqual(args[args.index("--model") + 1], "haiku")

    def test_no_task_kind_falls_back_to_risk_as_before(self):
        args = self._args_for(None, risk="high")
        self.assertEqual(args[args.index("--model") + 1], "opus")


class TaskKindPropagationTests(unittest.TestCase):
    """End-to-end: TaskCreate.metadata["task_kind"] must actually reach
    ExecutionPacket.metadata via ExecutionService._build_metadata --
    otherwise the override above is unreachable from real task creation."""

    def test_task_kind_reaches_execution_packet_metadata(self):
        with tempfile.TemporaryDirectory() as d:
            engine = TaskEngine(SQLiteStore(f"sqlite:///{d}/db.sqlite"), Conductor(AgentRegistry(ROOT / "agents"), ModelRouter()))
            task = engine.create(TaskCreate(
                title="Consulta", objective="Evalúa este approach", domain="engineering",
                metadata={"task_kind": "consulta"},
            ))
            engine.plan(task.id)
            service = ExecutionService(engine, "dry_run", Path(d) / "ws")
            metadata = service._build_metadata(engine.require(task.id))
            self.assertEqual(metadata.get("task_kind"), "consulta")

    def test_absent_task_kind_is_not_added(self):
        with tempfile.TemporaryDirectory() as d:
            engine = TaskEngine(SQLiteStore(f"sqlite:///{d}/db.sqlite"), Conductor(AgentRegistry(ROOT / "agents"), ModelRouter()))
            task = engine.create(TaskCreate(title="Rutina", objective="Haz algo", domain="engineering"))
            engine.plan(task.id)
            service = ExecutionService(engine, "dry_run", Path(d) / "ws")
            metadata = service._build_metadata(engine.require(task.id))
            self.assertNotIn("task_kind", metadata)


if __name__ == "__main__":
    unittest.main()
