from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from cano_hermes.domain.models import ExecutionResult
from .base import ExecutionPacket, Executor


# Anything whose name looks like a credential is stripped from the child
# environment. AGENTS.md: "Agents must not receive Docker socket access,
# global secrets, unrestricted filesystem access or production permissions."
SECRET_NAME_PATTERN = re.compile(
    r"(API_KEY|ACCESS_KEY|SECRET|PASSWORD|PASSWD|CREDENTIAL|_TOKEN|TOKEN_|^TOKEN$)",
    re.IGNORECASE,
)

# Each executor gets back only the credentials its own tier needs. An executor
# absent from this map runs with no secrets at all. Names match the real .env
# (NVIDIA_NIM_API_KEY, KIMI_*), not idealized ones.
EXECUTOR_SECRET_ALLOWLIST: dict[str, frozenset[str]] = {
    "claude-code": frozenset({"ANTHROPIC_API_KEY"}),
    "codex": frozenset({"OPENAI_API_KEY"}),
    "hermes-agent": frozenset({
        # NVIDIA_API_KEY is what Hermes' own CLI reads (hermes_cli/auth.py);
        # NVIDIA_NIM_API_KEY is Cano's .env naming for the same key — both
        # kept so neither a config change nor a naming fix silently drops it.
        "NVIDIA_API_KEY", "NVIDIA_NIM_API_KEY",  # tier 0 — motor gratis de las oficinas
        "KIMI_API_KEY", "KIMI_BASE_URL",  # tier 0 — orquestación de oficinas
        "OPENROUTER_API_KEY",   # tier 2 — desbordamiento
    }),
    "openclaw": frozenset(),
    "container-sandbox": frozenset(),  # ephemeral workers get zero secrets, ever
}


class CommandExecutor(Executor):
    def __init__(self, executor_id: str, command: str, mode: str = "dry_run") -> None:
        self.id = executor_id
        self.command = command
        self.mode = mode

    def build_args(self, packet: ExecutionPacket) -> Sequence[str]:
        raise NotImplementedError

    def build_env(self, packet: ExecutionPacket) -> dict[str, str]:
        """Child environment with every credential stripped, then only this
        executor's own allowlisted secrets restored."""
        env = {k: v for k, v in os.environ.items() if not SECRET_NAME_PATTERN.search(k)}
        for name in EXECUTOR_SECRET_ALLOWLIST.get(self.id, frozenset()):
            value = os.environ.get(name)
            if value:
                env[name] = value
        env["HERMES_TASK_ID"] = packet.task_id
        return env

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
        env = self.build_env(packet)
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
        return self.parse_result(packet, stdout, stderr, process.returncode, started, datetime.now(timezone.utc))

    def parse_result(
        self,
        packet: ExecutionPacket,
        stdout: bytes,
        stderr: bytes,
        returncode: int,
        started: datetime,
        finished: datetime,
    ) -> ExecutionResult:
        """Turn raw subprocess output into an ExecutionResult.

        Only called for a real (non-dry_run) run that actually produced
        stdout/stderr — timeout/unavailable/dry_run all return earlier in
        `execute()` and never reach here. Executors whose CLI emits a
        structured format (e.g. claude-code's stream-json) override this to
        extract cost/usage/artifacts instead of the flat truncated-text
        summary built here.
        """
        output = stdout.decode("utf-8", errors="replace")
        error = stderr.decode("utf-8", errors="replace")
        summary = (output or error or "No output")[-8000:]
        return ExecutionResult(
            task_id=packet.task_id,
            executor=self.id,
            status="completed" if returncode == 0 else "failed",
            summary=summary,
            exit_code=returncode,
            metrics={"stdout_chars": len(output), "stderr_chars": len(error)},
            started_at=started,
            finished_at=finished,
        )
