from __future__ import annotations

from typing import Sequence

from .base import ExecutionPacket
from .subprocess_executor import CommandExecutor


class HermesAgentExecutor(CommandExecutor):
    """Drives Hermes Agent (Nous Research) through its one-shot interface.

    `hermes -z/--oneshot` is the only subprocess-safe entry point: the
    interactive CLI actively refuses to run through a pipe. One-shot prints
    just the final response to stdout and, with --usage-file, drops a JSON
    spend report even when the run fails — which is what the budget
    controller reconciles against.

    Caveat that shapes the contract: one-shot **auto-bypasses Hermes' own
    approvals**. StarHome's PermissionEngine is therefore the only gate, so
    it must clear the action *before* dispatch, and `toolsets` must scope
    what the run can reach.
    """

    def __init__(
        self,
        command: str = "hermes",
        mode: str = "dry_run",
        model: str | None = None,
        provider: str | None = None,
        toolsets: Sequence[str] | None = None,
    ) -> None:
        super().__init__("hermes-agent", command, mode)
        self.model = model
        self.provider = provider
        self.toolsets = tuple(toolsets or ())

    def build_args(self, packet: ExecutionPacket) -> Sequence[str]:
        meta = packet.metadata
        # Per-task overrides win, so the router can pin a tier per delegation.
        model = meta.get("model") or self.model
        provider = meta.get("provider") or self.provider
        toolsets = meta.get("toolsets") or self.toolsets
        reasoning = meta.get("reasoning")

        args = [self.command, "--oneshot", packet.objective]
        if model:
            args += ["--model", str(model)]
        if provider:
            args += ["--provider", str(provider)]
        if toolsets:
            joined = toolsets if isinstance(toolsets, str) else ",".join(toolsets)
            args += ["--toolsets", joined]
        if reasoning:
            args += ["--reasoning", str(reasoning)]
        # Spend report lands beside the task's artifacts for reconciliation.
        args += ["--usage-file", str(packet.workspace / f"usage-{packet.task_id}.json")]
        return args
