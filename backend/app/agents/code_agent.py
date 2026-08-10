from ..services.router_service import classify_query_intent

SYSTEM_PROMPT = """You are an expert AI programmer.
CRITICAL RULES:
1. The provided repository context is strictly for style and API reference.
2. Do NOT copy, repeat, or output existing files from the context unless the user explicitly commands you to modify that exact file.
3. Fulfill the user's prompt directly and write clean, original code.
"""


def process_code_request(prompt: str, vector_service=None):
    """Route a coding request to repository retrieval only when local context is needed."""
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt must be a non-empty string")

    intent = classify_query_intent(prompt)
    is_greenfield = any(keyword in prompt.lower() for keyword in ("write a", "create a", "build a", "generate a", "code a"))
    if is_greenfield or intent != "LOCAL_RAG" or vector_service is None:
        return None

    try:
        return vector_service.retrieve(prompt)
    except Exception as exc:
        raise RuntimeError("Repository context retrieval failed") from exc
