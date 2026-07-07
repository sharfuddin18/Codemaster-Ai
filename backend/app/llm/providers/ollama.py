from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from app.config import settings
from app.services.ollama_service import generate_with_retry, get_ollama_client
from app.llm.providers.base import BaseLLMProvider

logger = logging.getLogger("codemaster-ai")


class OllamaProvider(BaseLLMProvider):
    """Provider implementation for the Ollama backend."""

    def __init__(self, provider_name: str | None = None):
        super().__init__(provider_name or "ollama")
        self._last_error: Optional[str] = None

    def is_ready(self) -> bool:
        if not self._ollama_enabled():
            self._last_error = "ollama provider is disabled"
            return False

        try:
            self._initialize_client()
            return True
        except Exception as exc:
            self._last_error = str(exc)
            return False

    def get_status(self) -> Dict[str, Any]:
        if not self._ollama_enabled():
            return {
                "provider": self.provider_name,
                "ready": False,
                "reason": "ollama provider is disabled",
            }

        if self._last_error:
            return {
                "provider": self.provider_name,
                "ready": False,
                "reason": self._last_error,
            }

        try:
            self._initialize_client()
            return {
                "provider": self.provider_name,
                "ready": True,
                "host": str(settings.OLLAMA_HOST),
            }
        except Exception as exc:
            return {
                "provider": self.provider_name,
                "ready": False,
                "reason": str(exc),
            }

    def _ollama_enabled(self) -> bool:
        value = os.getenv("OLLAMA_ENABLED")
        if value is None:
            return bool(getattr(settings, "OLLAMA_ENABLED", False))
        return value.strip().lower() in {"1", "true", "yes", "on"}

    def _initialize_client(self):
        get_ollama_client()
        self._last_error = None
        return True

    async def generate(self, prompt: str, model: str | None = None) -> str:
        if not self.is_ready():
            raise RuntimeError(self._last_error or "Ollama provider is not ready")

        client = get_ollama_client()
        response = await generate_with_retry(
            client,
            model=model or "qwen2.5-coder:1.5b",
            prompt=prompt,
            options={
                "temperature": settings.GENERATION_TEMPERATURE,
                "top_p": settings.GENERATION_TOP_P,
                "top_k": settings.GENERATION_TOP_K,
            },
        )
        return response.get("response", "")
