import os
from typing import Dict, Any

class ProviderManager:
    """
    Unified manager for local LLM providers (Ollama, LM Studio, vLLM).
    """
    PROVIDERS = {
        "ollama": "http://localhost:11434/api/generate",
        "lm_studio": "http://localhost:1234/v1/chat/completions",
        "vllm": "http://localhost:8000/v1/completions"
    }

    def __init__(self, default_provider: str = "ollama"):
        self.active_provider = default_provider if default_provider in self.PROVIDERS else "ollama"

    def set_provider(self, provider_name: str) -> bool:
        if provider_name.lower() in self.PROVIDERS:
            self.active_provider = provider_name.lower()
            return True
        return False

    def get_endpoint(self) -> str:
        return self.PROVIDERS[self.active_provider]
