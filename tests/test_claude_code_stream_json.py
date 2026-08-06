"""K1 task 4: `claude -p --output-format stream-json` writes NDJSON (one
JSON object per line) to stdout, terminated by a `result` event carrying
`total_cost_usd`/`usage`. Before this, `subprocess_executor.py` treated that
whole blob as flat text and truncated it -- cost/usage/tool-calls Claude
Code actually reports were silently dropped. `ClaudeCodeExecutor.parse_result`
(runtimes/claude_code.py) now parses it; these tests exercise that parser
directly against fixture NDJSON, without spawning the real `claude` binary
(which is installed on this machine, so a real subprocess call here would be
a real, billable invocation)."""
from __future__ import annotations

import unittest
from datetime import UTC, datetime
from pathlib import Path

from cano_hermes.runtimes.base import ExecutionPacket
from cano_hermes.runtimes.claude_code import ClaudeCodeExecutor, _parse_stream_json

# A trimmed but realistic fixture of what `claude -p --output-format
# stream-json` emits: an init event, an assistant turn, then the terminal
# `result` event carrying cost/usage -- one JSON object per line (NDJSON).
STREAM_JSON_FIXTURE = "\n".join(
    [
        '{"type": "system", "subtype": "init", "session_id": "sess-1", "model": "claude-sonnet-5"}',
        '{"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "Working on it..."}]}}',
        (
            '{"type": "result", "subtype": "success", "is_error": false, "result": "Task completed successfully.", '
            '"total_cost_usd": 0.0842, "duration_ms": 4210, "num_turns": 3, '
            '"usage": {"input_tokens": 1200, "output_tokens": 340, "cache_read_input_tokens": 500}}'
        ),
    ]
)


class StreamJsonParsingTests(unittest.TestCase):
    def _packet(self) -> ExecutionPacket:
        return ExecutionPacket(task_id="t-stream", objective="do work", workspace=Path("/tmp/ws/t-stream"))

    def test_parses_ndjson_lines_into_events(self):
        events = _parse_stream_json(STREAM_JSON_FIXTURE)
        self.assertEqual(len(events), 3)
        self.assertEqual(events[0]["type"], "system")
        self.assertEqual(events[-1]["type"], "result")

    def test_ignores_blank_lines_and_non_json_noise(self):
        noisy = STREAM_JSON_FIXTURE + "\n\n   \nnot json at all\n"
        events = _parse_stream_json(noisy)
        self.assertEqual(len(events), 3)

    def test_parse_result_extracts_cost_usage_and_summary(self):
        executor = ClaudeCodeExecutor(mode="supervised")
        started = datetime.now(UTC)
        finished = datetime.now(UTC)
        result = executor.parse_result(
            self._packet(),
            stdout=STREAM_JSON_FIXTURE.encode("utf-8"),
            stderr=b"",
            returncode=0,
            started=started,
            finished=finished,
        )
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.summary, "Task completed successfully.")
        self.assertAlmostEqual(result.metrics["total_cost_usd"], 0.0842)
        self.assertEqual(result.metrics["usage"]["input_tokens"], 1200)
        self.assertEqual(result.metrics["duration_ms"], 4210)
        self.assertEqual(result.metrics["num_turns"], 3)
        self.assertEqual(result.metrics["event_count"], 3)

    def test_parse_result_marks_failed_on_nonzero_exit_even_with_a_result_event(self):
        executor = ClaudeCodeExecutor(mode="supervised")
        started = datetime.now(UTC)
        finished = datetime.now(UTC)
        result = executor.parse_result(
            self._packet(), stdout=STREAM_JSON_FIXTURE.encode("utf-8"), stderr=b"", returncode=1,
            started=started, finished=finished,
        )
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.exit_code, 1)

    def test_non_json_stdout_falls_back_to_generic_flat_summary_without_crashing(self):
        """Today's actual behavior (plain-text stdout, no stream-json) --
        this must keep working exactly as before."""
        executor = ClaudeCodeExecutor(mode="supervised")
        started = datetime.now(UTC)
        finished = datetime.now(UTC)
        result = executor.parse_result(
            self._packet(), stdout=b"just some plain text output\n", stderr=b"", returncode=0,
            started=started, finished=finished,
        )
        self.assertEqual(result.status, "completed")
        self.assertIn("plain text output", result.summary)
        self.assertNotIn("total_cost_usd", result.metrics)

    def test_empty_stdout_falls_back_without_crashing(self):
        executor = ClaudeCodeExecutor(mode="supervised")
        started = datetime.now(UTC)
        finished = datetime.now(UTC)
        result = executor.parse_result(
            self._packet(), stdout=b"", stderr=b"some stderr", returncode=1,
            started=started, finished=finished,
        )
        self.assertEqual(result.status, "failed")
        self.assertIn("some stderr", result.summary)


if __name__ == "__main__":
    unittest.main()
