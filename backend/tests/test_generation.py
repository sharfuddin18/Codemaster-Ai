from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from backend.app.main import app
from database.db import set_state

app.state.activated = True
client = TestClient(app)


def test_health_or_root_check():
    """Ensure API root/health endpoints function correctly."""
    response = client.get("/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "online"


@patch("backend.app.routes.generation.build_context_prompt", return_value=("", {}))
@patch("backend.app.llm.factory.LLMFactory.create_provider")
def test_generate_code_endpoint_success(mock_create_provider, _mock_context):
    """Test successful generation on the production /generate-code route."""
    set_state(True)
    app.state.activated = True

    provider = MagicMock()
    provider.is_ready.return_value = True
    provider.generate = AsyncMock(return_value="def add(a, b):\n    return a + b")
    mock_create_provider.return_value = provider

    payload = {
        "prompt": "Write a python function to add two numbers",
        "language": "python",
    }
    response = client.post("/generate-code", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "def add" in data["code"]
    assert data["confidence"] > 0
    assert data["model_used"]
    assert data.get("provenance") is None


@patch("backend.app.routes.generation.build_context_prompt", return_value=("", {}))
@patch("backend.app.llm.factory.LLMFactory.create_provider")
def test_fix_code_endpoint_returns_reviewable_patch(mock_create_provider, _mock_context):
    set_state(True)
    app.state.activated = True

    provider = MagicMock()
    provider.is_ready.return_value = True
    provider.generate = AsyncMock(return_value="def hello():\n    print('codemaster')\n")
    mock_create_provider.return_value = provider

    payload = {
        "file_code": "def hello():\n    print('hello')\n",
        "instructions": "Update the greeting",
        "file_path": "src/hello.py",
    }
    response = client.post("/fix-code", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "print('codemaster')" in data["code"]
    assert data["patch"]
    assert "--- a/src/hello.py" in data["patch"]
    assert "+++ b/src/hello.py" in data["patch"]
