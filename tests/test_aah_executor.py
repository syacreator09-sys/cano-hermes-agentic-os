"""Plan AUTONOMÍA TOTAL A0 -- cano_hermes/runtimes/aah.py.

`AAHExecutor.parse_result` is tested against the REAL FINAL_REPORT.json
shape confirmed live from `~/repos/adaptive-agent-harness/factory/
profiles/common.py::_write_report` and `factory/cli.py::run_cmd` (which
`print(json.dumps(result,indent=2))`s that exact dict to stdout and exits
0 when done, 2 when incomplete) -- fixtures below mirror it exactly, not
guessed.
"""
from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

from cano_hermes.runtimes.aah import AAHExecutor
from cano_hermes.runtimes.base import ExecutionPacket

NOW = datetime(2026, 8, 7, tzinfo=timezone.utc)


def _packet(workspace: str = "/tmp/ws/t-1/aah") -> ExecutionPacket:
    return ExecutionPacket(task_id="t-1", objective="arregla el bug X", workspace=Path(workspace))


class BuildArgsTests(unittest.TestCase):
    def test_uses_project_local_binary_and_target(self):
        executor = AAHExecutor("/home/cano/repos/cano-hermes-agentic-os/.aah/bin/factory", mode="supervised")
        args = list(executor.build_args(_packet()))
        self.assertEqual(args[0], "/home/cano/repos/cano-hermes-agentic-os/.aah/bin/factory")
        self.assertEqual(args[1], "run")
        self.assertEqual(args[2], "arregla el bug X")
        self.assertIn("--target", args)
        self.assertEqual(args[args.index("--target") + 1], "/tmp/ws/t-1/aah")
        self.assertIn("--profile", args)
        self.assertEqual(args[args.index("--profile") + 1], "auto")
        self.assertIn("--guardian", args)
        self.assertEqual(args[args.index("--guardian") + 1], "guarded")


class ParseResultDoneTests(unittest.TestCase):
    """Real shape: {"run_id","profile","done","gate":{"done","failures","required","passed"},"state":{...},"extra":{...}}"""

    def test_done_true_maps_to_completed(self):
        report = {
            "run_id": "RUN-20260807-003", "profile": "lite", "done": True,
            "gate": {"done": True, "failures": [], "required": 3, "passed": 3},
            "state": {"phase": "done"}, "extra": {"passes": 1},
        }
        executor = AAHExecutor("/fake/factory", mode="supervised")
        result = executor.parse_result(
            _packet(), stdout=json.dumps(report).encode(), stderr=b"",
            returncode=0, started=NOW, finished=NOW,
        )
        self.assertEqual(result.status, "completed")
        self.assertIn("DONE", result.summary)
        self.assertIn("3/3", result.summary)
        self.assertEqual(result.metrics["aah_run_id"], "RUN-20260807-003")
        self.assertTrue(result.metrics["aah_done"])
        self.assertEqual(result.artifacts, ["/tmp/ws/t-1/aah/.aah/runs/RUN-20260807-003/FINAL_REPORT.md"])

    def test_done_false_maps_to_failed_with_blocking_items(self):
        report = {
            "run_id": "RUN-20260807-004", "profile": "lite", "done": False,
            "gate": {"done": False, "failures": ["req-1:status=UNVERIFIED"], "required": 3, "passed": 2},
            "state": {"phase": "paused"}, "extra": {"passes": 3, "escalation": "pro"},
        }
        executor = AAHExecutor("/fake/factory", mode="supervised")
        result = executor.parse_result(
            _packet(), stdout=json.dumps(report).encode(), stderr=b"",
            returncode=2, started=NOW, finished=NOW,
        )
        self.assertEqual(result.status, "failed")
        self.assertIn("INCOMPLETE", result.summary)
        self.assertIn("req-1:status=UNVERIFIED", result.summary)
        self.assertFalse(result.metrics["aah_done"])

    def test_returncode_zero_but_done_false_is_still_failed(self):
        """Never trust exit code alone over the gate's own verdict -- the
        Final Gate (Producer != approver) is the source of truth."""
        report = {"run_id": "RUN-X", "profile": "lite", "done": False, "gate": {"done": False, "failures": ["x"], "required": 1, "passed": 0}}
        executor = AAHExecutor("/fake/factory", mode="supervised")
        result = executor.parse_result(
            _packet(), stdout=json.dumps(report).encode(), stderr=b"",
            returncode=0, started=NOW, finished=NOW,
        )
        self.assertEqual(result.status, "failed")

    def test_unparseable_stdout_falls_back_to_generic_summary(self):
        """Exit code 3 (no authenticated provider) prints a plain-text
        error to stderr, not JSON to stdout -- must not crash parsing."""
        executor = AAHExecutor("/fake/factory", mode="supervised")
        result = executor.parse_result(
            _packet(), stdout=b"", stderr=b"No provider CLI detected.",
            returncode=3, started=NOW, finished=NOW,
        )
        self.assertEqual(result.status, "failed")
        self.assertIn("No provider CLI detected", result.summary)


if __name__ == "__main__":
    unittest.main()
