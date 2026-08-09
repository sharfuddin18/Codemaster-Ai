import httpx
import logging
import os

logger = logging.getLogger("codemaster-ai")

class OllamaProvider:


    provider_name = "ollama"
    def get_status(self) -> dict:
        """Return the operational status of the Ollama provider."""
        return {
            "provider": "ollama",
            "status": "healthy" if (self.is_available() if callable(getattr(self, "is_available", None)) else getattr(self, "is_available", True)) else "degraded"
        }
    def __init__(self, provider_key: str = "ollama"):
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.is_available = os.getenv("OLLAMA_ENABLED", "true").lower() == "true"
        self._last_error = None

    async def generate(self, prompt: str, **kwargs) -> str:
        if not self.is_available:
            raise RuntimeError("ollama provider is disabled")

        model = kwargs.get("model", "qwen2.5-coder:1.5b")
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False
        }
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, json=payload)
                if response.status_code != 200:
                    raise RuntimeError(f"Ollama API error: {response.text}")
                data = response.json()
                return data.get("response", "")
        except Exception as e:
            logger.error(f"Ollama generation failed: {e}")
            raise RuntimeError(f"Ollama generation failed: {e}")

    def is_ready(self) -> bool:
        import os
        val = os.getenv("OLLAMA_ENABLED")
        if val is not None:
            return val.lower() not in ("false", "0", "no", "off")
        return True
