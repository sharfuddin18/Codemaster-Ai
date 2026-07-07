from __future__ import annotations

from typing import Any, Dict

from app.llm.providers.base import BaseLLMProvider


class FallbackProvider(BaseLLMProvider):
    """A safe fallback provider used when no provider is configured or available."""

    def __init__(self, provider_name: str | None = None):
        super().__init__(provider_name or "fallback")

    async def generate(self, prompt: str, model: str | None = None) -> str:
        raise RuntimeError("No LLM provider is currently available")

    def is_ready(self) -> bool:
        return False

    def get_status(self) -> Dict[str, Any]:
        return {
            "provider": self.provider_name,
            "ready": False,
            "reason": "fallback provider is active",
        }
