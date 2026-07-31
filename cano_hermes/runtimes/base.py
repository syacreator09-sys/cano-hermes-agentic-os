from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from cano_hermes.domain.models import ExecutionResult


@dataclass(frozen=True)
class ExecutionPacket:
    task_id: str
    objective: str
    workspace: Path
    allowed_write_paths: tuple[Path, ...] = field(default_factory=tuple)
    timeout_seconds: int = 900
    max_turns: int = 12
    metadata: dict = field(default_factory=dict)


class Executor(ABC):
    id: str

    @abstractmethod
    async def execute(self, packet: ExecutionPacket) -> ExecutionResult:
        raise NotImplementedError
