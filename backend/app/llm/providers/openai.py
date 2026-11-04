from __future__ import annotations

import os
from typing import Any, Dict

from ...config import settings
from .base import BaseLLMProvider


class OpenAIProvider(BaseLLMProvider):
    """Provider implementation for the OpenAI-compatible API."""

    def __init__(self, provider_name: str | None = None):
        super().__init__(provider_name or "openai")

    async def generate(self, prompt: str, model: str | None = None) -> str:
        if not self.is_ready():
            raise RuntimeError("OpenAI provider is not configured")

        try:
            import openai
        except ImportError as exc:
            raise RuntimeError("openai package is not installed") from exc

        client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        try:
            response = await client.responses.create(
                model=model or settings.OPENAI_MODEL,
                input=prompt,
            )
            return getattr(response, "output_text", "") or ""
        finally:
            await client.close()

    def is_ready(self) -> bool:
        return bool(settings.OPENAI_API_KEY)

    def get_status(self) -> Dict[str, Any]:
        return {
            "provider": self.provider_name,
            "ready": self.is_ready(),
            "reason": "OPENAI_API_KEY is configured" if self.is_ready() else "OPENAI_API_KEY is missing",
        }
