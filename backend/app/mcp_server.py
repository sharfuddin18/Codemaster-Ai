"""MCP protocol server exposing Codemaster-AI's existing capabilities."""

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from .agents.explain_agent import build_explanation_prompt
from .agents.review_agent import build_review_prompt
from .config import settings
from .llm.routing import TaskType
from .models import CodeRequest, ExplainRequest, FixRequest, ReviewRequest
from .routes.generation import (
    _analysis_core,
    _fix_code_core,
    _generate_code_core,
    _parse_retrieval_doc,
    get_hybrid_retriever,
)
from .routes.mcp import MCPRetrieveRequest
from database.db import is_activated


def _csv_values(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


allowed_hosts = {
    "localhost",
    "127.0.0.1",
    "localhost:*",
    "127.0.0.1:*",
    *_csv_values(settings.MCP_ALLOWED_HOSTS),
}
allowed_origins = _csv_values(settings.MCP_ALLOWED_ORIGINS)

def _require_active_agent() -> None:
    if not is_activated():
        raise RuntimeError("AI Agent inactive. Activate Codemaster-AI before using this tool.")


async def retrieve_context(
    query: str,
    top_k: int = 5,
    alpha: float = 0.5,
    min_score: float = 0.0,
) -> dict[str, object]:
    """Search the indexed repository and return ranked source context."""
    payload = MCPRetrieveRequest(query=query, top_k=top_k, alpha=alpha, min_score=min_score)
    results = get_hybrid_retriever().search(
        payload.query,
        top_k=payload.top_k,
        alpha=payload.alpha,
        min_score=payload.min_score,
    )
    return {
        "query": payload.query,
        "count": len(results),
        "results": [_parse_retrieval_doc(result) for result in results],
    }


async def generate_code(
    prompt: str,
    language: str | None = None,
    model: str | None = None,
) -> dict[str, object]:
    """Generate code using the configured provider and repository context."""
    _require_active_agent()
    payload = CodeRequest(prompt=prompt, language=language, model=model)
    result = await _generate_code_core(payload.prompt, payload.language, payload.model)
    return result.model_dump(mode="json", exclude_none=True)


async def fix_code(
    file_code: str,
    instructions: str | None = None,
    file_path: str | None = None,
    model: str | None = None,
) -> dict[str, object]:
    """Fix supplied code and return a reviewable patch when a path is provided."""
    _require_active_agent()
    payload = FixRequest(
        file_code=file_code,
        instructions=instructions,
        file_path=file_path,
    )
    result = await _fix_code_core(
        payload.file_code,
        payload.instructions,
        model_override=model,
        file_path=payload.file_path,
    )
    return result.model_dump(mode="json", exclude_none=True)


async def review_code(
    code: str,
    language: str | None = None,
    focus: str | None = None,
    model: str | None = None,
) -> dict[str, object]:
    """Review code for actionable correctness, security, and maintainability findings."""
    _require_active_agent()
    payload = ReviewRequest(code=code, language=language, focus=focus, model=model)
    prompt = build_review_prompt(payload.code, payload.language, payload.focus)
    result = await _analysis_core(prompt, TaskType.REVIEW, payload.language, payload.model)
    return result.model_dump(mode="json")


async def explain_code(
    code: str,
    language: str | None = None,
    audience: str = "intermediate",
    model: str | None = None,
) -> dict[str, object]:
    """Explain code execution, inputs, side effects, and edge cases."""
    _require_active_agent()
    payload = ExplainRequest(code=code, language=language, audience=audience, model=model)
    prompt = build_explanation_prompt(payload.code, payload.language, payload.audience)
    result = await _analysis_core(prompt, TaskType.EXPLAIN, payload.language, payload.model)
    return result.model_dump(mode="json")


def create_mcp_server() -> FastMCP:
    server = FastMCP(
        "Codemaster-AI",
        instructions=(
            "Use these tools to retrieve repository context, generate or fix code, "
            "review snippets, and explain code. Generation and analysis tools require "
            "the Codemaster agent to be activated."
        ),
        streamable_http_path="/",
        json_response=True,
        stateless_http=True,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=sorted(allowed_hosts),
            allowed_origins=allowed_origins,
        ),
    )
    for tool in (retrieve_context, generate_code, fix_code, review_code, explain_code):
        server.tool()(tool)
    return server


mcp_server = create_mcp_server()
mcp_protocol_app = mcp_server.streamable_http_app()