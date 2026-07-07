from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseLLMProvider(ABC):
    """Common contract for all LLM providers."""

    def __init__(self, provider_name: str | None = None):
        self.provider_name = provider_name or self.__class__.__name__

    @abstractmethod
    async def generate(self, prompt: str, model: str | None = None) -> str:
        """Generate a response for the supplied prompt."""

    @abstractmethod
    def is_ready(self) -> bool:
        """Return whether the provider is ready to serve requests."""

    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """Return a JSON-serializable status payload for diagnostics."""

    def close(self) -> None:
        """Release provider-specific resources if needed."""
