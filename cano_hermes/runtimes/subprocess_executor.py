from __future__ import annotations

import asyncio
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from cano_hermes.domain.models import ExecutionResult
from .base import ExecutionPacket, Executor


class CommandExecutor(Executor):
    def __init__(self, executor_id: str, command: str, mode: str = "dry_run") -> None:
        self.id = executor_id
        self.command = command
        self.mode = mode

    def build_args(self, packet: ExecutionPacket) -> Sequence[str]:
        raise NotImplementedError

    async def execute(self, packet: ExecutionPacket) -> ExecutionResult:
        started = datetime.now(timezone.utc)
        packet.workspace.mkdir(parents=True, exist_ok=True)
        args = list(self.build_args(packet))
        if self.mode == "dry_run":
            return ExecutionResult(
                task_id=packet.task_id,
                executor=self.id,
                status="simulated",
                summary=f"Would execute: {json.dumps(args)} in {packet.workspace}",
                metrics={"mode": self.mode},
                started_at=started,
                finished_at=datetime.now(timezone.utc),
            )
        if shutil.which(self.command) is None:
            return ExecutionResult(
                task_id=packet.task_id,
                executor=self.id,
                status="unavailable",
                summary=f"Command not found: {self.command}",
                exit_code=127,
                started_at=started,
                finished_at=datetime.now(timezone.utc),
            )
        env = os.environ.copy()
        env["HERMES_TASK_ID"] = packet.task_id
        process = await asyncio.create_subprocess_exec(
            *args,
            cwd=packet.workspace,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=packet.timeout_seconds)
        except TimeoutError:
            process.kill()
            await process.wait()
            return ExecutionResult(
                task_id=packet.task_id,
                executor=self.id,
                status="timeout",
                summary="Execution exceeded timeout",
                exit_code=-9,
                started_at=started,
                finished_at=datetime.now(timezone.utc),
            )
        output = stdout.decode("utf-8", errors="replace")
        error = stderr.decode("utf-8", errors="replace")
        summary = (output or error or "No output")[-8000:]
        return ExecutionResult(
            task_id=packet.task_id,
            executor=self.id,
            status="completed" if process.returncode == 0 else "failed",
            summary=summary,
            exit_code=process.returncode,
            metrics={"stdout_chars": len(output), "stderr_chars": len(error)},
            started_at=started,
            finished_at=datetime.now(timezone.utc),
        )
