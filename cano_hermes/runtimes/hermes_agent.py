from __future__ import annotations

from typing import Sequence

from .base import ExecutionPacket
from .subprocess_executor import CommandExecutor


class HermesAgentExecutor(CommandExecutor):
    def __init__(self, command: str = "hermes", mode: str = "dry_run") -> None:
        super().__init__("hermes-agent", command, mode)

    def build_args(self, packet: ExecutionPacket) -> Sequence[str]:
        return [self.command, "chat", "--message", packet.objective]
