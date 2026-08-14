"""Low-level Ollama compatibility helpers.

Business-level model selection lives in ``backend.app.llm.routing``. This
module retains the legacy client/retry helpers used by existing tests and
integrations, but it no longer owns provider or model routing.
"""
from __future__ import annotations

from typing import Dict, Optional

import ollama

from ..config import settings
from ..llm.routing import select_best_model
from ..utils.retry_handler import retry_on_transient_error

_client: Optional[ollama.AsyncClient] = None


def get_ollama_client() -> ollama.AsyncClient:
    """Lazy-initialize the legacy low-level Ollama client."""
    global _client
    if _client is None:
        _client = ollama.AsyncClient(
            host=settings.OLLAMA_HOST,
            timeout=settings.OLLAMA_TIMEOUT,
        )
    return _client


async def close_ollama_client() -> None:
    """Release the legacy client reference."""
    global _client
    _client = None


@retry_on_transient_error(retries=3, base_delay=0.5, max_delay=4.0)
async def generate_with_retry(client, **kwargs):
    """Retry a low-level Ollama client generation call."""
    return await client.generate(**kwargs)


def provider_status() -> Dict[str, object]:
    """Return configuration status without performing live model execution."""
    return {
        "provider": "ollama",
        "configured": bool(settings.OLLAMA_HOST),
        "enabled": settings.OLLAMA_ENABLED,
    }


__all__ = [
    "close_ollama_client",
    "generate_with_retry",
    "get_ollama_client",
    "provider_status",
    "select_best_model",
]
