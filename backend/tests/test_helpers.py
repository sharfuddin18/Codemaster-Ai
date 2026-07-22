import pytest
from backend.app.utils.helpers import extract_ollama_response_text, parse_ollama_models_response

def test_extract_ollama_response_text():
    """Verify extracting response text from various Ollama dict payloads."""
    # Standard response payload
    dict_payload = {"response": "generated code here"}
    assert extract_ollama_response_text(dict_payload) == "generated code here"
    
    # Message-based format
    chat_payload = {"message": {"content": "chat output"}}
    assert extract_ollama_response_text(chat_payload) == "chat output"
    
    # Fallback for empty or non-dict payloads
    assert extract_ollama_response_text({}) == ""
    assert extract_ollama_response_text(None) == ""

def test_parse_ollama_models_response():
    """Verify parsing model lists from Ollama tags response."""
    sample_response = {
        "models": [
            {"name": "qwen2.5-coder:1.5b", "size": 1000000},
            {"name": "llama3:8b", "size": 8000000},
        ]
    }
    parsed = parse_ollama_models_response(sample_response)
    assert len(parsed) == 2
    assert "qwen2.5-coder:1.5b" in parsed
    
    # Verify fallback for empty or non-dict payloads
    assert parse_ollama_models_response({}) == []
    assert parse_ollama_models_response(None) == []
