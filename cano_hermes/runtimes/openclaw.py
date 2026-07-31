from __future__ import annotations

from typing import Sequence

from .base import ExecutionPacket
from .subprocess_executor import CommandExecutor


class OpenClawExecutor(CommandExecutor):
    def __init__(self, command: str = "openclaw", mode: str = "dry_run") -> None:
        super().__init__("openclaw", command, mode)

    def build_args(self, packet: ExecutionPacket) -> Sequence[str]:
        return [self.command, "run", "--task", packet.objective]
