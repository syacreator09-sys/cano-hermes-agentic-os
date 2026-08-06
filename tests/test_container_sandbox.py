import unittest
from pathlib import Path

from cano_hermes.runtimes.base import ExecutionPacket
from cano_hermes.runtimes.container_sandbox import ContainerSandboxExecutor
from cano_hermes.runtimes.subprocess_executor import EXECUTOR_SECRET_ALLOWLIST


class ContainerSandboxSecurityTests(unittest.TestCase):
    """Verify the constructed `docker run` never grants what AGENTS.md forbids,
    without needing a real Docker daemon."""

    def args_for(self, **metadata):
        packet = ExecutionPacket(
            task_id="t-sandbox",
            objective="run task",
            workspace=Path("/home/cano/repos/demo-worktree"),
            metadata=metadata,
        )
        return list(ContainerSandboxExecutor(mode="supervised").build_args(packet))

    def test_never_mounts_docker_socket(self):
        args = self.args_for(command=["ls"])
        joined = " ".join(args)
        self.assertNotIn("docker.sock", joined)

    def test_drops_all_capabilities(self):
        args = self.args_for(command=["ls"])
        self.assertIn("--cap-drop", args)
        self.assertEqual(args[args.index("--cap-drop") + 1], "ALL")

    def test_runs_as_non_root(self):
        args = self.args_for(command=["ls"])
        self.assertIn("--user", args)
        self.assertEqual(args[args.index("--user") + 1], "10001:10001")

    def test_no_new_privileges(self):
        args = self.args_for(command=["ls"])
        self.assertIn("no-new-privileges:true", args)

    def test_network_defaults_to_none(self):
        args = self.args_for(command=["ls"])
        self.assertIn("--network", args)
        self.assertEqual(args[args.index("--network") + 1], "none")

    def test_only_the_assigned_workspace_is_mounted(self):
        args = self.args_for(command=["ls"])
        mounts = [a for a in args if ":/workspace:" in a]
        self.assertEqual(len(mounts), 1)
        self.assertTrue(mounts[0].startswith("/home/cano/repos/demo-worktree:"))

    def test_root_filesystem_is_read_only(self):
        args = self.args_for(command=["ls"])
        self.assertIn("--read-only", args)

    def test_gets_zero_secrets_by_allowlist(self):
        self.assertEqual(EXECUTOR_SECRET_ALLOWLIST["container-sandbox"], frozenset())

    def test_container_is_removed_after_the_task(self):
        args = self.args_for(command=["ls"])
        self.assertIn("--rm", args)


if __name__ == "__main__":
    unittest.main()
