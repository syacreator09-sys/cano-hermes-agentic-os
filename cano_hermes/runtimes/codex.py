from __future__ import annotations

from typing import Sequence

from .base import ExecutionPacket
from .subprocess_executor import CommandExecutor


class CodexExecutor(CommandExecutor):
    def __init__(self, command: str = "codex", mode: str = "dry_run") -> None:
        super().__init__("codex", command, mode)

    def build_args(self, packet: ExecutionPacket) -> Sequence[str]:
        # `exec` keeps the integration non-interactive. Exact flags are kept minimal
        # and can be adapted by the host-specific runtime probe.
        return [self.command, "exec", packet.objective]
