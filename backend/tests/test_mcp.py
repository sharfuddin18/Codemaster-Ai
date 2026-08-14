from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from backend.app.main import app

# Ensure API is active for endpoints that require activation
app.state.activated = True

client = TestClient(app)


def test_mcp_capabilities():
    resp = client.get("/mcp/capabilities")
    assert resp.status_code == 200
    data = resp.json()
    assert "capabilities" in data
    assert "provider" in data


@patch("backend.app.routes.generation.get_vector_engine")
def test_mcp_retrieve(mock_get_vector):
    mock_engine = MagicMock()
    mock_engine.chunks = ["File: README.md\nsample snippet"]
    mock_engine.search_context.return_value = mock_engine.chunks
    mock_get_vector.return_value = mock_engine

    payload = {"query": "sample", "top_k": 3}
    resp = client.post("/mcp/retrieve", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["query"] == "sample"
    assert isinstance(data["results"], list)


@patch("backend.app.routes.generation.get_vector_engine")
@patch("backend.app.routes.generation.LLMFactory.create_provider")
def test_mcp_generate(mock_create_provider, mock_get_vector):
    # Vector engine returns context chunks
    mock_engine = MagicMock()
    mock_engine.chunks = ["File: README.md\nsnippet"]
    mock_engine.search_context.return_value = mock_engine.chunks
    mock_get_vector.return_value = mock_engine

    # Provider-instantiation boundary
    mock_provider = MagicMock()
    mock_provider.is_ready.return_value = True
    mock_provider.provider_name = "mock"
    mock_provider.generate = AsyncMock(return_value="def foo():\n    return 1 [1]")
    mock_create_provider.return_value = mock_provider

    payload = {"prompt": "Create foo", "language": "python"}
    resp = client.post("/mcp/generate", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "code" in data
    assert "model_used" in data and isinstance(data.get("model_used"), str)


@patch("backend.app.routes.generation.get_vector_engine")
@patch("backend.app.routes.generation.LLMFactory.create_provider")
def test_mcp_fix(mock_create_provider, mock_get_vector):
    mock_engine = MagicMock()
    mock_engine.chunks = ["File: README.md\nsnippet"]
    mock_engine.search_context.return_value = mock_engine.chunks
    mock_get_vector.return_value = mock_engine

    mock_provider = MagicMock()
    mock_provider.is_ready.return_value = True
    mock_provider.provider_name = "mock"
    mock_provider.generate = AsyncMock(return_value="def foo():\n    return 2 [1]")
    mock_create_provider.return_value = mock_provider

    payload = {"file_code": "def foo():\n    pass", "instructions": "add return"}
    resp = client.post("/mcp/fix", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "code" in data
    assert "model_used" in data and isinstance(data.get("model_used"), str)
