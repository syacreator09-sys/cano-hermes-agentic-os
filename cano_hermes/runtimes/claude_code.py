from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Sequence

from cano_hermes.domain.models import ExecutionResult
from .base import ExecutionPacket
from .subprocess_executor import CommandExecutor


def _parse_stream_json(output: str) -> list[dict[str, Any]]:
    """Parse Claude Code's `--output-format stream-json`: NDJSON, one JSON
    object per line (init/assistant/tool_use/... events, terminated by a
    `result` event carrying cost/usage). Lines that aren't valid JSON objects
    are skipped rather than raising — stray stderr-ish noise on stdout must
    not blow up result parsing."""
    events: list[dict[str, Any]] = []
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


class ClaudeCodeExecutor(CommandExecutor):
    # P1 (plan POTENCIA, 2026-08-07): risk -> model, all on the same
    # subscription (no extra credential, no extra cost tier -- Claude Code
    # Max/Pro already covers every alias). LOW is deliberately the only
    # tier that downgrades to haiku; MEDIUM (the TaskRecord default) keeps
    # today's implicit behavior of just calling `claude` with no
    # --model, i.e. its own configured default.
    RISK_TO_MODEL = {"high": "opus", "critical": "opus", "low": "haiku"}

    def __init__(self, command: str = "claude", mode: str = "dry_run") -> None:
        super().__init__("claude-code", command, mode)

    def build_args(self, packet: ExecutionPacket) -> Sequence[str]:
        args = [
            self.command,
            "-p",
            packet.objective,
            "--output-format",
            "stream-json",
            "--max-turns",
            str(packet.max_turns),
            "--permission-mode",
            "plan" if self.mode == "dry_run" else "default",
        ]
        model = self.RISK_TO_MODEL.get(str(packet.metadata.get("risk", "")))
        if model:
            args += ["--model", model]
        return args

    def parse_result(
        self,
        packet: ExecutionPacket,
        stdout: bytes,
        stderr: bytes,
        returncode: int,
        started: datetime,
        finished: datetime,
    ) -> ExecutionResult:
        output = stdout.decode("utf-8", errors="replace")
        error = stderr.decode("utf-8", errors="replace")
        events = _parse_stream_json(output)
        if not events:
            # Not NDJSON (unexpected plain-text output, empty stdout, etc.)
            # -- fall back to the generic flat-text summary rather than
            # losing the run entirely.
            return super().parse_result(packet, stdout, stderr, returncode, started, finished)

        result_event = next((e for e in reversed(events) if e.get("type") == "result"), None)
        metrics: dict[str, Any] = {
            "stdout_chars": len(output),
            "stderr_chars": len(error),
            "event_count": len(events),
        }
        summary = error or "No output"
        artifacts: list[str] = []
        if result_event is not None:
            summary = result_event.get("result") or summary
            # Key names mirror what `claude -p --output-format stream-json`
            # actually emits on its terminal `result` event, and
            # `total_cost_usd` matches BudgetService.USAGE_COST_FIELDS so
            # ExecutionService can reconcile it like a hermes-agent usage file.
            for key in ("total_cost_usd", "usage", "duration_ms", "num_turns", "is_error"):
                if key in result_event:
                    metrics[key] = result_event[key]
            artifacts = list(result_event.get("artifacts", []) or [])

        return ExecutionResult(
            task_id=packet.task_id,
            executor=self.id,
            status="completed" if returncode == 0 else "failed",
            summary=str(summary)[-8000:],
            exit_code=returncode,
            artifacts=artifacts,
            metrics=metrics,
            started_at=started,
            finished_at=finished,
        )
