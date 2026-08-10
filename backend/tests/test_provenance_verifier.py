from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app

# Ensure API is activated for tests
app.state.activated = True
client = TestClient(app)


class FakeProvider:
    def __init__(self, response_text: str):
        self._response = response_text

    def is_ready(self):
        return True

    async def generate(self, prompt: str, model: str | None = None) -> str:
        return self._response


def _fake_context():
    prompt = "Use the following repository context when relevant:\n[1] File: src/example.py\ndef add(a,b):\n    return a+b\n"
    chunk_map = {
        1: {"file": "src/example.py", "snippet": "def add(a,b):\n    return a+b"}
    }
    return prompt, chunk_map


def test_generation_rejects_uncited_output():
    fake = FakeProvider("def add(a,b):\n    return a+b")
    with patch("app.llm.factory.LLMFactory.create_provider", return_value=fake), \
         patch("app.routes.generation.build_context_prompt", return_value=_fake_context()):
        payload = {"prompt": "Add two numbers", "language": "python"}
        response = client.post("/generate-code", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["confidence"] == 0.0
        assert data.get("provenance") is None


def test_generation_accepts_cited_output():
    fake = FakeProvider("def add(a,b):\n    return a+b  # [1]")
    with patch("app.llm.factory.LLMFactory.create_provider", return_value=fake), \
         patch("app.routes.generation.build_context_prompt", return_value=_fake_context()):
        payload = {"prompt": "Add two numbers", "language": "python"}
        response = client.post("/generate-code", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["confidence"] > 0.0
        assert "# [1]" in data["code"]
        prov = data.get("provenance")
        assert prov is not None
        assert prov["cited_indices"] == [1]
        assert "1" in prov["sources"]
        src = prov["sources"]["1"]
        assert src["file"] == "src/example.py"
        assert "def add(a,b)" in src["snippet"]
