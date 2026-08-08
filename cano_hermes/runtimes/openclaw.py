from __future__ import annotations

from typing import Sequence

from .base import ExecutionPacket
from .subprocess_executor import CommandExecutor


class OpenClawExecutor(CommandExecutor):
    """A3 (plan AUTONOMÍA TOTAL, 2026-08-08): kept for reference/tests only
    -- NOT registered in `ExecutionService.executors` and no agent
    manifest points `runtime` at it anymore. `openclaw` was always a
    placeholder name (docs/OPERATIONS.md called it a "stand-in" pending
    "K10 will give it a dedicated runtime"); confirmed live there is no
    `openclaw` binary anywhere on this machine and no repo (including
    hermes-agent) ships or references it as a real tool. K10 landed
    differently: the two agents that needed a browser (`ui-reviewer`,
    `browser-operator`) were redirected to `runtime: hermes` with
    `browser` added to their `tools` list, which reaches hermes-agent's
    own real, local, free browser toolset (agent-browser + a Playwright-
    managed Chromium, confirmed live via a real `hermes -z "..." -t
    browser` call that fetched a real public price) through the
    HermesAgentExecutor path that already existed -- no new executor
    code needed. This class stays only so
    tests/test_credential_isolation.py's "an unlisted executor gets zero
    secrets" case has a real, structurally-correct example to exercise.
    """

    def __init__(self, command: str = "openclaw", mode: str = "dry_run") -> None:
        super().__init__("openclaw", command, mode)

    def build_args(self, packet: ExecutionPacket) -> Sequence[str]:
        return [self.command, "run", "--task", packet.objective]
