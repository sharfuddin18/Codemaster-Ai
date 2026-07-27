import pytest
from backend.app.services.ollama_service import select_best_model, get_ollama_client

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
