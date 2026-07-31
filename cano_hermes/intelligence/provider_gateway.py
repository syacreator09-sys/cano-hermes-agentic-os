from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class ProviderConfig:
    id: str
    base_url: str
    api_key_env: str
    api_style: str = "openai"


PROVIDERS = {
    "openai": ProviderConfig("openai", "https://api.openai.com/v1", "OPENAI_API_KEY"),
    "deepseek": ProviderConfig("deepseek", "https://api.deepseek.com", "DEEPSEEK_API_KEY"),
    "moonshot": ProviderConfig("moonshot", "https://api.moonshot.ai/v1", "MOONSHOT_API_KEY"),
    "qwen": ProviderConfig("qwen", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1", "DASHSCOPE_API_KEY"),
    "xai": ProviderConfig("xai", "https://api.x.ai/v1", "XAI_API_KEY"),
    "anthropic": ProviderConfig("anthropic", "https://api.anthropic.com/v1", "ANTHROPIC_API_KEY", "anthropic"),
}


class ProviderGateway:
    """Network client used only after policy and approval checks."""

    def __init__(self, timeout: float = 60.0) -> None:
        self.timeout = timeout

    def configured(self, provider_id: str) -> bool:
        config = PROVIDERS[provider_id]
        return bool(os.getenv(config.api_key_env))

    async def complete_openai_compatible(
        self, provider_id: str, model: str, messages: list[dict[str, str]], **kwargs: Any
    ) -> dict[str, Any]:
        config = PROVIDERS[provider_id]
        if config.api_style != "openai":
            raise ValueError(f"Provider {provider_id} is not OpenAI-compatible in this adapter")
        key = os.getenv(config.api_key_env)
        if not key:
            raise RuntimeError(f"Missing {config.api_key_env}")
        payload = {"model": model, "messages": messages, **kwargs}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{config.base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    async def complete_anthropic(
        self, model: str, messages: list[dict[str, str]], max_tokens: int = 2048
    ) -> dict[str, Any]:
        config = PROVIDERS["anthropic"]
        key = os.getenv(config.api_key_env)
        if not key:
            raise RuntimeError(f"Missing {config.api_key_env}")
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{config.base_url}/messages",
                headers={
                    "x-api-key": key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={"model": model, "messages": messages, "max_tokens": max_tokens},
            )
            response.raise_for_status()
            return response.json()
