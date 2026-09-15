import logging
from typing import List

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from ..config import settings
from ..llm.factory import LLMFactory
from ..models import CodeRequest, CodeResponse, FixRequest
from .generation import (
    _fix_code_core,
    _generate_code_core,
    _parse_retrieval_doc,
    get_hybrid_retriever,
)
from database.db import is_activated

logger = logging.getLogger("codemaster-ai")
router = APIRouter(prefix="/mcp", tags=["MCP"])


class MCPRetrieveRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Search query for repository context")
    top_k: int = Field(5, ge=1, le=20, description="Number of top context chunks to return")
    alpha: float = Field(0.5, ge=0.0, le=1.0, description="Balance between dense and sparse search")
    min_score: float = Field(0.0, ge=0.0, le=1.0, description="Minimum normalized hybrid score")


class MCPContextChunk(BaseModel):
    index: int
    file: str
    snippet: str
    text: str
    hybrid_score: float
    bm25_score: float
    dense_score: float


class MCPRetrieveResponse(BaseModel):
    query: str
    count: int
    results: List[MCPContextChunk]


@router.get("/capabilities")
async def mcp_capabilities():
    provider = LLMFactory.create_provider(settings.LLM_PROVIDER)
    return {
        "name": "Codemaster-AI MCP",
        "version": "1.0",
        "capabilities": ["hybrid-retrieval", "verified-generation", "code-fix", "patch-generation"],
        "active": is_activated(),
        "provider": provider.provider_name,
        "provider_ready": provider.is_ready(),
    }


@router.post("/retrieve", response_model=MCPRetrieveResponse)
async def retrieve_context(payload: MCPRetrieveRequest):
    """Search repository context and expose retrieval failures as controlled errors."""
    try:
        results = get_hybrid_retriever().search(
            payload.query,
            top_k=payload.top_k,
            alpha=payload.alpha,
            min_score=payload.min_score,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("MCP retrieval failed")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Repository retrieval unavailable") from exc

    parsed = [_parse_retrieval_doc(doc) for doc in results]
    return MCPRetrieveResponse(query=payload.query, count=len(parsed), results=parsed)


@router.post("/generate", response_model=CodeResponse)
async def mcp_generate(request: Request, payload: CodeRequest):
    if not is_activated() and not getattr(request.app.state, "activated", False):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="AI Agent inactive. Use /activate.")
    return await _generate_code_core(payload.prompt, payload.language, payload.model)


@router.post("/fix", response_model=CodeResponse)
async def mcp_fix(request: Request, payload: FixRequest):
    if not is_activated() and not getattr(request.app.state, "activated", False):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="AI Agent inactive. Use /activate.")
    return await _fix_code_core(
        payload.file_code,
        payload.instructions,
        file_path=payload.file_path,
    )
