import os
import unittest
from pathlib import Path
from unittest import mock

from cano_hermes.runtimes.base import ExecutionPacket
from cano_hermes.runtimes.claude_code import ClaudeCodeExecutor
from cano_hermes.runtimes.codex import CodexExecutor
from cano_hermes.runtimes.hermes_agent import HermesAgentExecutor
from cano_hermes.runtimes.openclaw import OpenClawExecutor


FAKE_SECRETS = {
    "ANTHROPIC_API_KEY": "tier3-anthropic",
    "OPENAI_API_KEY": "tier3-openai",
    "NVIDIA_NIM_API_KEY": "tier0-nvidia",
    "OPENROUTER_API_KEY": "tier2-openrouter",
    "TELEGRAM_BOT_TOKEN": "delivery-token",
    "SUPABASE_SERVICE_SECRET": "finance-secret",
    "PATH": os.environ.get("PATH", "/usr/bin"),
    "HOME": os.environ.get("HOME", "/home/cano"),
}


def packet() -> ExecutionPacket:
    return ExecutionPacket(task_id="t-1", objective="probe", workspace=Path("/tmp"))


class CredentialIsolationTests(unittest.TestCase):
    """An executor must only ever see the credentials of its own tier."""

    def env_for(self, executor):
        with mock.patch.dict(os.environ, FAKE_SECRETS, clear=True):
            return executor.build_env(packet())

    def test_claude_code_sees_only_anthropic(self):
        env = self.env_for(ClaudeCodeExecutor(mode="supervised"))
        self.assertEqual(env.get("ANTHROPIC_API_KEY"), "tier3-anthropic")
        self.assertNotIn("OPENAI_API_KEY", env)
        self.assertNotIn("NVIDIA_API_KEY", env)

    def test_codex_sees_only_openai(self):
        env = self.env_for(CodexExecutor(mode="supervised"))
        self.assertEqual(env.get("OPENAI_API_KEY"), "tier3-openai")
        self.assertNotIn("ANTHROPIC_API_KEY", env)

    def test_hermes_agent_gets_cheap_tiers_never_premium(self):
        env = self.env_for(HermesAgentExecutor(mode="supervised"))
        self.assertEqual(env.get("NVIDIA_NIM_API_KEY"), "tier0-nvidia")
        self.assertEqual(env.get("OPENROUTER_API_KEY"), "tier2-openrouter")
        # the whole point: a tier-0 worker never sees a tier-3 key
        self.assertNotIn("ANTHROPIC_API_KEY", env)
        self.assertNotIn("OPENAI_API_KEY", env)

    def test_unlisted_executor_gets_no_secrets_at_all(self):
        env = self.env_for(OpenClawExecutor(mode="supervised"))
        for name in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "NVIDIA_NIM_API_KEY", "OPENROUTER_API_KEY"):
            self.assertNotIn(name, env)

    def test_unrelated_secrets_never_leak_to_anyone(self):
        for executor in (
            ClaudeCodeExecutor(mode="supervised"),
            CodexExecutor(mode="supervised"),
            HermesAgentExecutor(mode="supervised"),
        ):
            env = self.env_for(executor)
            self.assertNotIn("TELEGRAM_BOT_TOKEN", env, executor.id)
            self.assertNotIn("SUPABASE_SERVICE_SECRET", env, executor.id)

    def test_non_secret_environment_survives(self):
        env = self.env_for(ClaudeCodeExecutor(mode="supervised"))
        self.assertIn("PATH", env)
        self.assertIn("HOME", env)
        self.assertEqual(env.get("HERMES_TASK_ID"), "t-1")


if __name__ == "__main__":
    unittest.main()
