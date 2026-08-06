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

    # Free tier-0 brain for offices/workers (cerebro de dos niveles, PLAN-MAESTRO §8-ter).
    # kimi-office is proven live via direct Moonshot key (KIMI_API_KEY) as of
    # 2026-08-05; the nvidia/* entries route through NVIDIA NIM and are
    # currently blocked (403 on inference, key valid mechanically but rejected
    # by the API — see memory nvidia-key-invalida). Declared now so no code
    # change is needed once Cano regenerates the NVIDIA key.
    ModelProfile("kimi-office", "moonshot", "kimi-k2.6", "api", 0, 4, 5),
    ModelProfile("glm-nim", "nvidia", "z-ai/glm-5.2", "api", 0, 4, 6),
    ModelProfile("qwen-nim-batch", "nvidia", "qwen3.5-397b", "api", 0, 3, 4),
    ModelProfile("nemotron-nim-worker", "nvidia", "nemotron-3-ultra-550b-a55b", "api", 0, 4, 4),
]
