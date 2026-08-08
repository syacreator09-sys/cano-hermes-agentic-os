"""A3 (plan AUTONOMÍA TOTAL, 2026-08-08) -- browser-capable agents route
through HermesAgentExecutor + hermes-agent's real local browser toolset,
not the never-existed "openclaw" binary.

Confirmed live before writing this: no `openclaw` binary exists anywhere
on this machine or in any referenced repo (always a documented "stand-in"
in docs/OPERATIONS.md); `hermes -z "..." -t browser` and
`hermes -z "..." -t nexus_search,task_events,browser` (the exact shape
_build_metadata produces from an agent manifest's `tools:` list) both
completed for real against a real public page, tier-0/kimi, $0 cost.
"""

from __future__ import annotations

from pathlib import Path
import unittest

from cano_hermes.orchestration.execution_service import AGENT_RUNTIME_TO_EXECUTOR
from cano_hermes.registry.agents import AgentRegistry
from cano_hermes.runtimes.base import ExecutionPacket
from cano_hermes.runtimes.hermes_agent import HermesAgentExecutor

ROOT = Path(__file__).resolve().parents[1]


class BrowserRuntimeRetiredTests(unittest.TestCase):
    def test_browser_runtime_string_no_longer_maps_to_openclaw(self):
        self.assertNotIn("browser", AGENT_RUNTIME_TO_EXECUTOR)


class BrowserAgentManifestsTests(unittest.TestCase):
    def setUp(self):
        self.registry = AgentRegistry(ROOT / "agents")

    def test_ui_reviewer_uses_hermes_runtime_with_browser_tool(self):
        agent = self.registry.get("ui-reviewer")
        self.assertIsNotNone(agent)
        self.assertEqual(agent.runtime, "hermes")
        self.assertIn("browser", agent.tools)

    def test_browser_operator_uses_hermes_runtime_with_browser_tool(self):
        agent = self.registry.get("browser-operator")
        self.assertIsNotNone(agent)
        self.assertEqual(agent.runtime, "hermes")
        self.assertIn("browser", agent.tools)


class HermesAgentExecutorToolsetPassthroughTests(unittest.TestCase):
    """The actual mechanism these agents rely on: _build_metadata already
    copies manifest.tools into packet.metadata["toolsets"] verbatim
    (pre-existing, not new in A3) -- confirming build_args turns that
    into a real --toolsets flag that reaches "browser"."""

    def test_toolsets_metadata_reaches_toolsets_flag(self):
        packet = ExecutionPacket(
            task_id="t-1", objective="obj", workspace=Path("/tmp/ws"),
            metadata={"toolsets": ["nexus_search", "task_events", "browser"]},
        )
        args = list(HermesAgentExecutor(mode="supervised").build_args(packet))
        self.assertIn("--toolsets", args)
        self.assertEqual(args[args.index("--toolsets") + 1], "nexus_search,task_events,browser")


if __name__ == "__main__":
    unittest.main()
