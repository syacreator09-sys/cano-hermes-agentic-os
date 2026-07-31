from __future__ import annotations

from typing import Sequence

from .base import ExecutionPacket
from .subprocess_executor import CommandExecutor


class ClaudeCodeExecutor(CommandExecutor):
    def __init__(self, command: str = "claude", mode: str = "dry_run") -> None:
        super().__init__("claude-code", command, mode)

    def build_args(self, packet: ExecutionPacket) -> Sequence[str]:
        return [
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
