"""LLM providers for different backends."""

from __future__ import annotations

import os
from typing import Optional


class DeepSeekProvider:
    """Cloud DeepSeek via OpenAI-compatible API."""

    def __init__(self, api_key: str) -> None:
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(api_key=api_key, base_url="https://api.deepseek.com")

    async def generate(
        self, system_prompt: str, user_prompt: str = "",
        *, temperature: float = 0.7, max_tokens: int = 4096,
    ) -> tuple[str, int]:
        resp = await self.client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt or "请开始"},
            ],
            temperature=temperature, max_tokens=max_tokens,
        )
        text = resp.choices[0].message.content or ""
        tokens = resp.usage.total_tokens if resp.usage else 0
        return text, tokens


class OllamaProvider:
    """Local Ollama provider."""

    def __init__(self, model: str = "qwen3.5:9b", host: str = "http://127.0.0.1:11434") -> None:
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(api_key="ollama", base_url=f"{host}/v1")
        self.model = model

    async def generate(
        self, system_prompt: str, user_prompt: str = "",
        *, temperature: float = 0.7, max_tokens: int = 4096,
    ) -> tuple[str, int]:
        resp = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt or "请开始"},
            ],
            temperature=temperature, max_tokens=max_tokens,
        )
        text = resp.choices[0].message.content or ""
        tokens = resp.usage.total_tokens if resp.usage else 0
        return text, tokens


def get_provider(
    use_local: bool = False,
    local_model: str = "qwen3.5:9b",
    api_key: Optional[str] = None,
    host: str = "http://127.0.0.1:11434",
):
    """Factory: return the right LLM provider."""
    if use_local:
        return OllamaProvider(model=local_model, host=host)
    return DeepSeekProvider(api_key or os.environ.get("DEEPSEEK_API_KEY", ""))
