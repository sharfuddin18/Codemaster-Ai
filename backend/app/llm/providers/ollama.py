from __future__ import annotations

import logging
import os
from typing import Any, Dict

import httpx

from .base import BaseLLMProvider

logger = logging.getLogger("codemaster-ai")


class OllamaProvider(BaseLLMProvider):
    """Local Ollama provider implementation.

    Model selection is supplied by ModelRouter/LLMFactory. The provider only
    executes the already-selected provider/model request.
    """

    def __init__(self, provider_name: str | None = None):
        super().__init__(provider_name or "ollama")
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.enabled = os.getenv("OLLAMA_ENABLED", "true").lower() == "true"
        self._last_error: str | None = None

    async def generate(self, prompt: str, model: str | None = None) -> str:
        if not self.is_ready():
            raise RuntimeError("ollama provider is disabled")

        selected_model = model or "qwen2.5-coder:1.5b"
        url = f"{self.base_url.rstrip('/')}/api/generate"
        payload = {"model": selected_model, "prompt": prompt, "stream": False}
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, json=payload)
                if response.status_code != 200:
                    raise RuntimeError(f"Ollama API error: {response.text}")
                data = response.json()
                result = data.get("response", "")
                if not isinstance(result, str):
                    raise RuntimeError("Ollama returned a malformed response")
                self._last_error = None
                return result
        except Exception as exc:
            self._last_error = str(exc)
            logger.error("Ollama generation failed: %s", exc)
            raise RuntimeError(f"Ollama generation failed: {exc}") from exc

    def is_ready(self) -> bool:
        value = os.getenv("OLLAMA_ENABLED")
        if value is not None:
            return value.lower() not in ("false", "0", "no", "off")
        return self.enabled

    def get_status(self) -> Dict[str, Any]:
        return {
            "provider": self.provider_name,
            "ready": self.is_ready(),
            "last_error": self._last_error,
        }
