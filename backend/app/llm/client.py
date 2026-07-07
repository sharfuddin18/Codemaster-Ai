import os
import logging
from typing import Optional

logger = logging.getLogger("codemaster-ai")


class LLMClient:
    """Simple abstraction for text generation with configurable providers."""

    def __init__(self, provider: Optional[str] = None):
        self.provider = (provider or os.getenv("LLM_PROVIDER", "ollama")).strip().lower()

    def is_available(self) -> bool:
        if self.provider == "openai":
            return bool(os.getenv("OPENAI_API_KEY"))
        if self.provider == "anthropic":
            return bool(os.getenv("ANTHROPIC_API_KEY"))
        return True

    async def generate(self, prompt: str, model: Optional[str] = None) -> str:
        if self.provider == "openai":
            return await self._generate_with_openai(prompt, model)
        if self.provider == "anthropic":
            return await self._generate_with_anthropic(prompt, model)
        return await self._generate_with_ollama(prompt, model)

    async def _generate_with_openai(self, prompt: str, model: Optional[str] = None) -> str:
        try:
            import openai
        except ImportError as exc:
            raise RuntimeError("openai package is not installed") from exc

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured")

        client = openai.AsyncOpenAI(api_key=api_key)
        response = await client.responses.create(
            model=model or os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            input=prompt,
        )
        return getattr(response, "output_text", "") or ""

    async def _generate_with_anthropic(self, prompt: str, model: Optional[str] = None) -> str:
        try:
            import anthropic
        except ImportError as exc:
            raise RuntimeError("anthropic package is not installed") from exc

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not configured")

        client = anthropic.AsyncAnthropic(api_key=api_key)
        response = await client.messages.create(
            model=model or os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307"),
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        text_parts = []
        for block in getattr(response, "content", []) or []:
            if getattr(block, "type", None) == "text":
                text_parts.append(getattr(block, "text", ""))
        return "".join(text_parts)

    async def _generate_with_ollama(self, prompt: str, model: Optional[str] = None) -> str:
        from app.services.ollama_service import get_ollama_client

        client = get_ollama_client()
        response = await client.generate(model=model or "qwen2.5-coder:1.5b", prompt=prompt)
        return response.get("response", "")
