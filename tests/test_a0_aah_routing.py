"""A0 (plan AUTONOMÍA TOTAL, 2026-08-08) -- engineering tasks at MEDIUM+
risk route to the `aah` agent (AAHExecutor); LOW risk (and every other
team) is unchanged from the pre-existing "first match" behavior.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from cano_hermes.domain.enums import RiskLevel
from cano_hermes.domain.models import TaskRecord
from cano_hermes.intelligence.router import ModelRouter
from cano_hermes.orchestration.conductor import Conductor
from cano_hermes.registry.agents import AgentRegistry

ROOT = Path(__file__).resolve().parents[1]


class AahRoutingTests(unittest.TestCase):
    def setUp(self):
        self.conductor = Conductor(AgentRegistry(ROOT / "agents"), ModelRouter())

    def _assign(self, domain: str, risk: RiskLevel):
        task = TaskRecord(title="A0 probe", objective="routing dry-run", domain=domain, risk=risk)
        return self.conductor.assign(task)

    def test_low_risk_engineering_does_not_land_on_aah(self):
        assignment = self._assign("engineering", RiskLevel.LOW)
        self.assertNotEqual(assignment.agent_id, "aah-runner")

    def test_medium_risk_engineering_lands_on_aah(self):
        assignment = self._assign("engineering", RiskLevel.MEDIUM)
        self.assertEqual(assignment.agent_id, "aah-runner")

    def test_high_and_critical_risk_engineering_land_on_aah(self):
        for risk in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            with self.subTest(risk=risk):
                self.assertEqual(self._assign("engineering", risk).agent_id, "aah-runner")

    def test_medium_risk_outside_engineering_is_unaffected(self):
        """The aah preference is engineering-only -- other teams keep
        their existing first-match agent regardless of risk."""
        assignment = self._assign("content", RiskLevel.MEDIUM)
        self.assertNotEqual(assignment.agent_id, "aah-runner")

    def test_aah_runner_manifest_is_registered_and_uses_aah_runtime(self):
        agent = AgentRegistry(ROOT / "agents").get("aah-runner")
        self.assertIsNotNone(agent)
        self.assertEqual(agent.team, "engineering")
        self.assertEqual(agent.runtime, "aah")
        self.assertEqual(agent.status.value, "approved")


if __name__ == "__main__":
    unittest.main()
