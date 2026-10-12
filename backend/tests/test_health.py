import asyncio

import httpx

from backend.app.llm.factory import LLMFactory
from backend.app.llm.providers import ollama as ollama_provider
from backend.app.routes.health import health_check


def test_health_check_reports_ollama_server_unreachable(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_ENABLED", "true")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama.test")
    provider = ollama_provider.OllamaProvider()
    monkeypatch.setattr(LLMFactory, "create_provider", lambda *_args: provider)

    transport = httpx.MockTransport(lambda _request: httpx.Response(503))
    async_client = httpx.AsyncClient
    monkeypatch.setattr(
        ollama_provider.httpx,
        "AsyncClient",
        lambda **kwargs: async_client(transport=transport, **kwargs),
    )

    result = asyncio.run(health_check())

    assert result["status"] == "degraded"
    assert result["details"]["ready"] is False
    assert result["details"]["last_error"]


def test_health_check_reports_reachable_ollama(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_ENABLED", "true")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama.test")
    provider = ollama_provider.OllamaProvider()
    monkeypatch.setattr(LLMFactory, "create_provider", lambda *_args: provider)

    transport = httpx.MockTransport(lambda _request: httpx.Response(200, json={"models": []}))
    async_client = httpx.AsyncClient
    monkeypatch.setattr(
        ollama_provider.httpx,
        "AsyncClient",
        lambda **kwargs: async_client(transport=transport, **kwargs),
    )

    result = asyncio.run(health_check())

    assert result["status"] == "healthy"
    assert result["details"]["ready"] is True
    assert result["details"]["last_error"] is None