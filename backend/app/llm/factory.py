from __future__ import annotations

import logging
import os
from typing import Dict, Type

from app.config import settings
from app.llm.providers.base import BaseLLMProvider
from app.llm.providers.fallback import FallbackProvider
from app.llm.providers.ollama import OllamaProvider
from app.llm.providers.openai import OpenAIProvider

logger = logging.getLogger("codemaster-ai")


class LLMFactory:
    """Factory and registry for provider instantiation."""

    _registry: Dict[str, Type[BaseLLMProvider]] = {
        "ollama": OllamaProvider,
        "openai": OpenAIProvider,
        "fallback": FallbackProvider,
    }

    @classmethod
    def create_provider(cls, provider_name: str | None = None) -> BaseLLMProvider:
        provider_key = (provider_name or os.getenv("LLM_PROVIDER") or getattr(settings, "LLM_PROVIDER", "fallback") or "fallback").strip().lower()
        provider_cls = cls._registry.get(provider_key)
        if provider_cls is None:
            logger.warning("Unknown provider '%s'; using fallback provider", provider_key)
            return FallbackProvider("fallback")

        provider = provider_cls(provider_key)
        logger.info("LLMFactory selected provider '%s'", provider_key)
        return provider

    @classmethod
    def register_provider(cls, name: str, provider_cls: Type[BaseLLMProvider]) -> None:
        cls._registry[name.strip().lower()] = provider_cls
