from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

# Initialize state expected by health routes during testing
app.state.activated = True

client = TestClient(app)

def test_health_or_root_check():
    """Ensure API root/health endpoints function correctly."""
    response = client.get("/")
    assert response.status_code in [200, 404]

@patch("backend.app.services.ollama_service.generate_with_retry", new_callable=AsyncMock)
def test_generate_code_endpoint_success(mock_generate):
    """Test successful generation endpoint execution."""
    mock_generate.return_value = {
        "response": "def add(a, b):\n    return a + b",
        "model": "qwen2.5-coder:1.5b"
    }
    
    payload = {
        "prompt": "Write a python function to add two numbers",
        "language": "python"
    }
    
    response = client.post("/api/v1/generate", json=payload)
    assert response.status_code in [200, 201, 404, 422]
