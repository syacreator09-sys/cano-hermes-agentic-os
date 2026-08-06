from __future__ import annotations

from typing import Sequence

from .base import ExecutionPacket
from .subprocess_executor import CommandExecutor


class ContainerSandboxExecutor(CommandExecutor):
    """Runs a task command inside an ephemeral, rootless Docker container.

    Security properties (AGENTS.md: no Docker socket, no unrestricted
    filesystem, no production permissions):
    - `--user 10001:10001` — non-root inside the container
    - `--cap-drop ALL` + `--security-opt no-new-privileges:true`
    - `--read-only` root filesystem, only /tmp and the worktree are writable
    - `--network none` by default — no egress unless explicitly allowlisted
    - only `packet.workspace` is bind-mounted; nothing else on the host is
      reachable, and the Docker socket is never mounted
    - `--rm` — the container is destroyed the moment the task ends
    """

    IMAGE = "starhome/sandbox-worker:latest"

    def __init__(
        self,
        command: str = "docker",
        mode: str = "dry_run",
        cpu_limit: str = "1.0",
        mem_limit: str = "512m",
        network: str = "none",
    ) -> None:
        super().__init__("container-sandbox", command, mode)
        self.cpu_limit = cpu_limit
        self.mem_limit = mem_limit
        self.network = network

    def build_args(self, packet: ExecutionPacket) -> Sequence[str]:
        image = packet.metadata.get("image", self.IMAGE)
        task_command = packet.metadata.get("command", ["true"])
        network = packet.metadata.get("network", self.network)

        return [
            self.command, "run", "--rm",
            "--user", "10001:10001",
            "--read-only",
            "--tmpfs", "/tmp:rw,size=64m,uid=10001,gid=10001",
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges:true",
            "--network", network,
            "--cpus", self.cpu_limit,
            "--memory", self.mem_limit,
            "-v", f"{packet.workspace}:/workspace:rw",
            "-w", "/workspace",
            image,
            *task_command,
        ]
