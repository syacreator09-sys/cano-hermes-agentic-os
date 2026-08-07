from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Sequence

from cano_hermes.domain.models import ExecutionResult

from .base import ExecutionPacket
from .subprocess_executor import CommandExecutor


class AAHExecutor(CommandExecutor):
    """Adaptive Agent Harness (`syacreator09-sys/adaptive-agent-harness`),
    invoked by contract per `docs/AAH_INTEGRATION_CONTRACT.md`. Subscription-
    first: `EXECUTOR_SECRET_ALLOWLIST["aah"]` is an empty frozenset (see
    `subprocess_executor.py`) -- AAH uses the host's already-authenticated
    `claude`/`codex` CLIs, never an API key.

    `command` is the absolute path to the project-local binary
    `install.sh` creates (`<target>/.aah/bin/factory`) -- there is no
    global `factory` on PATH, AAH is installed per-project. Confirmed live
    (2026-08-07, workbench `~/repos/aah-workbench`) that `factory run`
    prints the FINAL_REPORT dict as JSON to stdout and exits 0 when
    `done=True`, 2 when incomplete (e.g. LITE exhausted its passes and
    escalated), 3 when no authenticated provider is available
    (`factory/cli.py::run_cmd`) -- this is the real, confirmed contract
    the integration doc's section 5 asked to verify before writing this.
    """

    def __init__(self, command: str, mode: str = "dry_run") -> None:
        super().__init__("aah", command, mode)

    def build_args(self, packet: ExecutionPacket) -> Sequence[str]:
        # --profile auto / --guardian guarded: AAH's own router decides
        # LITE/PRO/FACTORY and Guardian escalates for sensitive domains --
        # StarHome does not duplicate that decision (contract section 5).
        # --target: AAH needs its own `.aah/` (written by `install.sh`) to
        # exist at this path -- packet.workspace, same as every other
        # executor's containment boundary.
        return [
            self.command, "run", packet.objective,
            "--target", str(packet.workspace),
            "--profile", "auto", "--guardian", "guarded",
        ]

    def parse_result(
        self, packet: ExecutionPacket, stdout: bytes, stderr: bytes,
        returncode: int, started: datetime, finished: datetime,
    ) -> ExecutionResult:
        output = stdout.decode("utf-8", errors="replace")
        error = stderr.decode("utf-8", errors="replace")
        try:
            report = json.loads(output)
        except json.JSONDecodeError:
            # Exit code 3 (no provider) or a crash before FINAL_REPORT was
            # ever printed -- fall back to the generic flat-text summary
            # rather than losing the run entirely, same discipline
            # ClaudeCodeExecutor.parse_result already uses.
            return super().parse_result(packet, stdout, stderr, returncode, started, finished)

        done = bool(report.get("done"))
        gate: dict[str, Any] = report.get("gate") or {}
        summary = (
            f"AAH {report.get('profile', '?').upper()} {report.get('run_id', '?')}: "
            f"{'DONE' if done else 'INCOMPLETE'} -- rubric {gate.get('passed', '?')}/{gate.get('required', '?')}"
        )
        if gate.get("failures"):
            summary += f"; blocking: {', '.join(str(f) for f in gate['failures'][:5])}"

        return ExecutionResult(
            task_id=packet.task_id,
            executor=self.id,
            # AAH's own Final Gate is evidence-based and deterministic
            # (spec: Producer != approver), but it is not a StarHome
            # approval -- "completed" here only means the AAH run finished
            # its own gate, not that ApprovalService cleared it (contract
            # section 8.3: AAH's gate complements, never replaces, ours).
            status="completed" if returncode == 0 and done else "failed",
            summary=summary[-8000:],
            exit_code=returncode,
            artifacts=[f"{packet.workspace}/.aah/runs/{report.get('run_id', '')}/FINAL_REPORT.md"] if report.get("run_id") else [],
            metrics={"aah_run_id": report.get("run_id"), "aah_profile": report.get("profile"), "aah_done": done, "aah_gate": gate},
            started_at=started,
            finished_at=finished,
        )
