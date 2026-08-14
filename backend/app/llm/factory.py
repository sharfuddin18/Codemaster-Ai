from __future__ import annotations

import logging
import os
from typing import Dict, Type

from ..config import settings
from .providers.base import BaseLLMProvider
from .providers.fallback import FallbackProvider
from .providers.ollama import OllamaProvider
from .providers.openai import OpenAIProvider
from .routing import RoutingDecision

logger = logging.getLogger("codemaster-ai")


class LLMFactory:
    """Single authoritative provider-instantiation boundary."""

    _registry: Dict[str, Type[BaseLLMProvider]] = {
        "ollama": OllamaProvider,
        "openai": OpenAIProvider,
        "fallback": FallbackProvider,
    }

    @classmethod
    def create_provider(cls, provider_name: str | None = None) -> BaseLLMProvider:
        """Create a provider; production routing normally supplies the name."""
        provider_key = (
            provider_name
            or os.getenv("LLM_PROVIDER")
            or getattr(settings, "LLM_PROVIDER", "fallback")
            or "fallback"
        ).strip().lower()
        provider_cls = cls._registry.get(provider_key)
        if provider_cls is None:
            logger.warning("Unknown provider '%s'; using fallback provider", provider_key)
            provider_key = "fallback"
            provider_cls = FallbackProvider

        provider = provider_cls(provider_key)
        logger.info("LLMFactory created provider '%s'", provider_key)
        return provider

    @classmethod
    def create(cls, decision: RoutingDecision) -> tuple[BaseLLMProvider, str]:
        """Create the provider selected by one structured routing decision."""
        provider = cls.create_provider(decision.provider)
        return provider, decision.model

    @classmethod
    def register_provider(cls, name: str, provider_cls: Type[BaseLLMProvider]) -> None:
        cls._registry[name.strip().lower()] = provider_cls
