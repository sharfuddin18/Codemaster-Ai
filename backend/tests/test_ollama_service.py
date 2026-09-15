from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.ollama_service import get_ollama_client, select_best_model
from database.db import set_state

def test_select_best_model_python_routing():
    result = select_best_model("Write a python script to parse JSON", "python")
    assert result["model"] == "codellama:7b-instruct"
    assert "Python detected" in result["reason"]

def test_select_best_model_ml_routing():
    result = select_best_model("Train a random forest regression model using pandas", "python")
    assert result["model"] == "mistral:7b-instruct"
    assert "Data Science/ML detected" in result["reason"]

def test_select_best_model_js_routing():
    result = select_best_model("Create a responsive React component", "javascript")
    assert result["model"] == "qwen2.5-coder:1.5b"
    assert "JavaScript/Web detected" in result["reason"]

def test_select_best_model_fallback():
    result = select_best_model("Hello world", None)
    assert result["model"] == "qwen2.5-coder:1.5b"
    assert "Default fallback" in result["reason"]

def test_get_ollama_client_singleton():
    client1 = get_ollama_client()
    client2 = get_ollama_client()
    assert client1 is client2


@patch("backend.app.services.ollama_service.get_ollama_client")
def test_models_endpoint_lists_and_caches(mock_get_client):
    import backend.app.services.ollama_service as ollama_service

    ollama_service._models_cache = None
    ollama_service._cache_timestamp = 0.0
    set_state(True)
    app.state.activated = True
    fake_client = MagicMock()
    fake_client.list = AsyncMock(return_value={"models": [{"name": "qwen2.5-coder:1.5b"}]})
    mock_get_client.return_value = fake_client

    client = TestClient(app)
    first = client.get("/models")
    second = client.get("/models")
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["models"] == ["qwen2.5-coder:1.5b"]
    assert fake_client.list.await_count == 1
