import re


def clean_llm_markdown(text: str) -> str:
    """Extract only clean code from fenced markdown blocks if present."""
    text = (text or "").strip()

    fence_pattern = r"\x60\x60\x60(?:[a-zA-Z0-9_+\-#.]*)?\s*\n(.*?)\x60\x60\x60"
    matches = re.findall(fence_pattern, text, flags=re.DOTALL)
    if matches:
        best = max(matches, key=lambda s: len(s.strip()))
        return best.strip()

    return text


def parse_ollama_models_response(models_response):
    """Parses response payloads from Ollama safely across library versions."""
    if hasattr(models_response, "model_dump"):
        data = models_response.model_dump()
    elif isinstance(models_response, dict):
        data = models_response
    else:
        data = models_response

    if isinstance(data, list):
        names = []
        for item in data:
            if isinstance(item, dict):
                name = item.get("model") or item.get("name") or item.get("tag") or item.get("id")
                if name:
                    names.append(name)
            elif isinstance(item, str):
                names.append(item)
        return names

    if not isinstance(data, dict):
        return []

    candidates = data.get("models") or data.get("tags") or data.get("items") or []
    if isinstance(candidates, dict):
        candidates = [candidates]

    names = []
    for item in candidates:
        if isinstance(item, dict):
            name = item.get("model") or item.get("name") or item.get("tag") or item.get("id")
            if name:
                names.append(name)
        elif isinstance(item, str):
            names.append(item)
    return names


def extract_ollama_response_text(response):
    """Extracts raw text strings cleanly out of Ollama generation structures."""
    code = None

    if hasattr(response, "response"):
        code = response.response

    if not code and hasattr(response, "model_dump"):
        data = response.model_dump()
        if isinstance(data, dict):
            code = (
                data.get("response")
                or data.get("text")
                or data.get("output")
            )
            if not code and "message" in data:
                msg = data["message"]
                code = msg.get("content") if isinstance(msg, dict) else msg

    if not code and isinstance(response, dict):
        code = (
            response.get("response")
            or response.get("text")
            or response.get("output")
        )
        if not code and "message" in response:
            msg = response["message"]
            code = msg.get("content") if isinstance(msg, dict) else msg

    if code is None:
        return ""

    return clean_llm_markdown(str(code))
