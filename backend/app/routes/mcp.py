import logging
from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.config import settings
from app.llm.factory import LLMFactory
from app.models import CodeRequest, CodeResponse, FixRequest
from app.routes.generation import _generate_code_core, _fix_code_core, get_vector_engine
from app.services.hybrid_retriever import HybridRetriever
from app.services.vector_service import VectorService
from database.db import is_activated

logger = logging.getLogger("codemaster-ai")
router = APIRouter(prefix="/mcp", tags=["MCP"])

_hybrid_retriever: HybridRetriever | None = None


class MCPRetrieveRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Search query for repository context")
    top_k: int = Field(5, ge=1, le=20, description="Number of top context chunks to return")
    alpha: float = Field(
        0.5,
        ge=0.0,
        le=1.0,
        description="Balance between dense and sparse search (0.0 = BM25 only, 1.0 = dense only)",
    )
    min_score: float = Field(
        0.0,
        ge=0.0,
        le=1.0,
        description="Minimum normalized hybrid score threshold for returned results",
    )


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


def get_hybrid_retriever() -> HybridRetriever:
    global _hybrid_retriever
    if _hybrid_retriever is None:
        dense_service = VectorService()
        retriever = HybridRetriever(dense_vector_engine=dense_service)

        engine = get_vector_engine()
        documents = [
            {"id": str(index), "content": chunk}
            for index, chunk in enumerate(engine.chunks, start=1)
        ]
        retriever.index_documents(documents)
        _hybrid_retriever = retriever

    return _hybrid_retriever


def _parse_chunk_entry(doc: dict) -> dict:
    text = doc.get("content", "")
    lines = text.splitlines()
    first_line = lines[0] if lines else ""
    if first_line.startswith("File:"):
        file_path = first_line.replace("File:", "", 1).strip()
        snippet = "\n".join(lines[1:]).strip()
    else:
        file_path = "unknown"
        snippet = text.strip()

    return {
        "index": int(doc.get("id", 0)),
        "file": file_path,
        "snippet": snippet,
        "text": text,
        "hybrid_score": float(doc.get("hybrid_score", 0.0)),
        "bm25_score": float(doc.get("bm25_score", 0.0)),
        "dense_score": float(doc.get("dense_score", 0.0)),
    }


@router.get("/capabilities")
async def mcp_capabilities():
    provider = LLMFactory.create_provider(settings.LLM_PROVIDER)
    return {
        "name": "Codemaster-AI MCP",
        "version": "1.0",
        "capabilities": [
            "hybrid-retrieval",
            "verified-generation",
            "code-fix",
        ],
        "active": is_activated(),
        "provider": provider.provider_name,
        "provider_ready": provider.is_ready(),
    }


@router.post("/retrieve", response_model=MCPRetrieveResponse)
async def retrieve_context(payload: MCPRetrieveRequest):
    """Search repository context using the hybrid vector + BM25 retriever."""
    retriever = get_hybrid_retriever()
    results = retriever.search(
        payload.query,
        top_k=payload.top_k,
        alpha=payload.alpha,
        min_score=payload.min_score,
    )
    parsed = [_parse_chunk_entry(doc) for doc in results]
    return MCPRetrieveResponse(query=payload.query, count=len(parsed), results=parsed)


@router.post("/generate", response_model=CodeResponse)
async def mcp_generate(request: Request, payload: CodeRequest):
    """Generate verified code for external MCP clients."""
    if not is_activated() and not getattr(request.app.state, "activated", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="AI Agent inactive. Use /activate.",
        )
    return await _generate_code_core(payload.prompt, payload.language, payload.model)


@router.post("/fix", response_model=CodeResponse)
async def mcp_fix(request: Request, payload: FixRequest):
    """Fix code with provenance-aware instructions for external MCP clients."""
    if not is_activated() and not getattr(request.app.state, "activated", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="AI Agent inactive. Use /activate.",
        )
    return await _fix_code_core(payload.file_code, payload.instructions)
