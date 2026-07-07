import logging
from typing import Optional

from app.llm.factory import LLMFactory

logger = logging.getLogger("codemaster-ai")


class LLMClient:
    """Backward-compatible wrapper around the provider factory."""

    def __init__(self, provider: Optional[str] = None):
        self.provider_name = (provider or "ollama").strip().lower()
        self.provider = LLMFactory.create_provider(self.provider_name)

    def is_available(self) -> bool:
        return self.provider.is_ready()

    async def generate(self, prompt: str, model: Optional[str] = None) -> str:
        return await self.provider.generate(prompt, model=model)
