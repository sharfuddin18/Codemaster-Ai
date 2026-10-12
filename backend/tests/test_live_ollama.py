import os

import pytest
from fastapi.testclient import TestClient

from backend.app.config import settings
from backend.app.main import app


@pytest.fixture
def live_ollama_client(monkeypatch):
    if os.getenv("CODEMASTER_RUN_LIVE_OLLAMA") != "1":
        pytest.skip("Set CODEMASTER_RUN_LIVE_OLLAMA=1 to enable live Ollama checks")

    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_ENABLED", "true")
    monkeypatch.setenv(
        "OLLAMA_BASE_URL",
        os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
    )
    monkeypatch.setattr("backend.app.routes.generation.is_activated", lambda: True)

    headers = {"x-api-key": settings.API_KEY} if settings.API_KEY else {}
    with TestClient(app) as client:
        yield client, headers


def test_live_ollama_health(live_ollama_client):
    client, headers = live_ollama_client

    response = client.get("/health", headers=headers)

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert response.json()["provider"] == "ollama"


@pytest.mark.parametrize(
    ("endpoint", "payload"),
    [
        (
            "/review-code",
            {
                "code": "def add(a, b):\n    return a + b\n",
                "language": "python",
                "focus": "edge cases",
            },
        ),
        (
            "/explain-code",
            {
                "code": "def square(value):\n    return value * value\n",
                "language": "python",
                "audience": "beginner",
            },
        ),
    ],
)
def test_live_ollama_analysis_routes(live_ollama_client, endpoint, payload):
    client, headers = live_ollama_client
    model = os.getenv("CODEMASTER_OLLAMA_MODEL", "qwen2.5-coder:1.5b")

    response = client.post(
        endpoint,
        headers=headers,
        json={**payload, "model": model},
    )

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["result"].strip()
    assert result["model_used"] == model
