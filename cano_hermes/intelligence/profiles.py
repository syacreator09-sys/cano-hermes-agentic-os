from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelProfile:
    id: str
    provider: str
    model: str
    runtime: str
    cost_tier: int
    quality: int
    context: int
    supports_tools: bool = True
    supports_vision: bool = False
    subscription: bool = False


DEFAULT_PROFILES = [
    ModelProfile("local-daily", "local", "qwen-local", "local", 0, 2, 2, False),
    ModelProfile("deepseek-daily", "deepseek", "configurable", "api", 1, 3, 4),
    ModelProfile("qwen-daily", "qwen", "configurable", "api", 1, 3, 4),
    ModelProfile("kimi-research", "moonshot", "configurable", "api", 2, 4, 5),
    ModelProfile("grok-trends", "xai", "configurable", "api", 3, 4, 4, True, True),
    ModelProfile("claude-subscription", "anthropic", "claude-code", "cli", 1, 5, 5, True, True, True),
    ModelProfile("codex-subscription", "openai", "codex", "app_server", 1, 5, 4, True, True, True),
    ModelProfile("anthropic-premium", "anthropic", "configurable", "api", 5, 5, 5, True, True),
    ModelProfile("openai-premium", "openai", "configurable", "api", 5, 5, 5, True, True),
]
