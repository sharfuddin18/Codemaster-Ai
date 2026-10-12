from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app


@pytest.mark.parametrize(
    ("endpoint", "payload", "expected_prompt"),
    [
        (
            "/review-code",
            {"code": "def add(a, b): return a + b", "language": "python", "focus": "edge cases"},
            "senior software reviewer",
        ),
        (
            "/explain-code",
            {"code": "def add(a, b): return a + b", "language": "python", "audience": "beginner"},
            "beginner-level developer",
        ),
    ],
)
def test_analysis_endpoints_return_provider_result(endpoint, payload, expected_prompt):
    app.state.activated = True
    provider = MagicMock()
    provider.is_ready.return_value = True
    provider.generate = AsyncMock(return_value="Analysis result")

    with patch("backend.app.routes.generation.LLMFactory.create", return_value=(provider, "test-model")):
        response = TestClient(app).post(endpoint, json=payload)

    assert response.status_code == 200
    assert response.json()["result"] == "Analysis result"
    assert response.json()["model_used"] == "test-model"
    assert expected_prompt in provider.generate.await_args.args[0]


def test_analysis_endpoint_maps_provider_failure_to_500():
    app.state.activated = True
    provider = MagicMock()
    provider.is_ready.return_value = True
    provider.generate = AsyncMock()
    provider.generate.side_effect = RuntimeError("provider unavailable")

    with patch("backend.app.routes.generation.LLMFactory.create", return_value=(provider, "test-model")):
        response = TestClient(app).post("/review-code", json={"code": "print(1)"})

    assert response.status_code == 500
    assert "Code review failed" in response.json()["detail"]


def test_analysis_endpoint_rejects_empty_code_and_inactive_agent(monkeypatch):
    client = TestClient(app)
    app.state.activated = True
    invalid = client.post("/explain-code", json={"code": ""})

    assert invalid.status_code == 422

    app.state.activated = False
    monkeypatch.setattr("backend.app.routes.generation.is_activated", lambda: False)
    inactive = client.post("/explain-code", json={"code": "print(1)"})

    assert inactive.status_code == 403
