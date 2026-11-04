from __future__ import annotations

import logging
import os
from typing import Any, Dict

import httpx

from ...config import settings
from .base import BaseLLMProvider

logger = logging.getLogger("codemaster-ai")


class OllamaProvider(BaseLLMProvider):
    """Local Ollama provider implementation.

    Model selection is supplied by ModelRouter/LLMFactory. The provider only
    executes the already-selected provider/model request.
    """

    def __init__(self, provider_name: str | None = None):
        super().__init__(provider_name or "ollama")
        self.base_url = (
            os.getenv("OLLAMA_BASE_URL")
            or os.getenv("OLLAMA_HOST")
            or settings.OLLAMA_BASE_URL
            or settings.OLLAMA_HOST
        ).rstrip("/") or "http://127.0.0.1:11434"
        self.enabled = self._enabled_from_env()
        self._last_error: str | None = None

    @staticmethod
    def _enabled_from_env() -> bool:
        value = os.getenv("OLLAMA_ENABLED")
        if value is not None:
            return value.lower() not in ("false", "0", "no", "off")
        return bool(settings.OLLAMA_ENABLED)

    async def generate(self, prompt: str, model: str | None = None) -> str:
        if not self.is_ready():
            raise RuntimeError(f"ollama provider is unavailable at {self.base_url}")

        selected_model = model or settings.OLLAMA_DEFAULT_MODEL
        url = f"{self.base_url.rstrip('/')}/api/generate"
        payload = {"model": selected_model, "prompt": prompt, "stream": False}
        timeout = settings.OLLAMA_TIMEOUT or 60.0
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
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
        if not self._enabled_from_env():
            return False
        try:
            response = httpx.get(
                f"{self.base_url.rstrip('/')}/api/tags",
                timeout=min(settings.OLLAMA_TIMEOUT or 5.0, 5.0),
            )
            if response.status_code == 200:
                self._last_error = None
                return True
            self._last_error = f"Ollama health check returned {response.status_code}"
            logger.warning("Ollama readiness check failed: %s", self._last_error)
            return False
        except httpx.HTTPError as exc:
            self._last_error = str(exc)
            logger.warning("Ollama readiness check failed: %s", exc)
            return False

    async def check_connection(self) -> bool:
        if not self._enabled_from_env():
            self._last_error = "Ollama provider is disabled"
            return False

        timeout = min(settings.OLLAMA_TIMEOUT or 5.0, 5.0)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(f"{self.base_url.rstrip('/')}/api/tags")
                if response.status_code != 200:
                    self._last_error = f"Ollama health check returned {response.status_code}"
                    logger.warning("Ollama health check failed: %s", self._last_error)
                    return False
            self._last_error = None
            return True
        except httpx.HTTPError as exc:
            self._last_error = str(exc)
            logger.warning("Ollama health check failed: %s", exc)
            return False

    def get_status(self) -> Dict[str, Any]:
        return {
            "provider": self.provider_name,
            "ready": self._last_error is None and self._enabled_from_env(),
            "base_url": self.base_url,
            "last_error": self._last_error,
        }
