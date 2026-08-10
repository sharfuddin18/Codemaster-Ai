import asyncio
import logging
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status

from ..config import settings
from ..models import CodeRequest, CodeResponse, FixRequest, Provenance, Source
from ..llm.factory import LLMFactory
from ..services.hybrid_retriever import HybridRetriever
from ..services.ollama_service import select_best_model
from ..services.response_verifier import verify_response
from ..services.vector_service import VectorService
from ..utils.vector_engine import CodeVectorEngine
from database.db import is_activated

logger = logging.getLogger("codemaster-ai")
router = APIRouter(tags=["Generation"])

_vector_engine = None
_hybrid_retriever: HybridRetriever | None = None


def get_vector_engine() -> CodeVectorEngine:
    global _vector_engine
    if _vector_engine is None:
        repo_root = Path(__file__).resolve().parents[3]
        _vector_engine = CodeVectorEngine(
            config=__import__("backend.app.utils.vector_engine", fromlist=["IndexConfig"]).IndexConfig(
                source_dir=repo_root,
                cache_db_path=repo_root / ".codemaster" / "cache.db",
                persist_path=repo_root / ".codemaster" / "vector_index",
            )
        )
    return _vector_engine


def get_hybrid_retriever() -> HybridRetriever:
    global _hybrid_retriever
    if _hybrid_retriever is None:
        engine = get_vector_engine()
        dense_service = VectorService()
        documents = [
            {"id": str(index), "content": chunk}
            for index, chunk in enumerate(engine.chunks, start=1)
        ]
        retriever = HybridRetriever(dense_vector_engine=dense_service)
        retriever.index_documents(documents)
        _hybrid_retriever = retriever
    return _hybrid_retriever


def _parse_retrieval_doc(doc: dict[str, Any]) -> dict[str, Any]:
    text = str(doc.get("content", ""))
    lines = text.splitlines()
    first_line = lines[0] if lines else ""
    if first_line.startswith("File:"):
        src = first_line.replace("File:", "", 1).strip()
        snippet = "\n".join(lines[1:]).strip()
    else:
        src = "unknown"
        snippet = text.strip()
    return {
        "index": int(doc.get("id", 0)),
        "file": src,
        "snippet": snippet,
        "text": text,
        "hybrid_score": float(doc.get("hybrid_score", 0.0)),
        "bm25_score": float(doc.get("bm25_score", 0.0)),
        "dense_score": float(doc.get("dense_score", 0.0)),
    }


def build_context_prompt(query: str) -> tuple[str, dict[int, dict[str, str]]]:
    try:
        results = get_hybrid_retriever().search(query, top_k=3, alpha=0.5, min_score=0.0)
    except Exception as exc:
        logger.warning("Hybrid retrieval failed: %s", exc)
        return "", {}

    if not results:
        return "", {}

    parsed = [_parse_retrieval_doc(result) for result in results]
    formatted = "\n\n".join(f"[{item['index']}] {item['text']}" for item in parsed)
    chunk_map = {
        item["index"]: {"file": item["file"], "snippet": item["snippet"]}
        for item in parsed
    }
    return "Use the following repository context when relevant:\n" + formatted + "\n", chunk_map


def build_context_results(query: str, top_k: int = 3) -> list[dict[str, Any]]:
    if not isinstance(top_k, int) or top_k < 1:
        return []
    try:
        results = get_hybrid_retriever().search(query, top_k=top_k)
    except Exception as exc:
        logger.warning("Hybrid retrieval failed: %s", exc)
        return []
    return [_parse_retrieval_doc(result) for result in results]


def _build_provenance(cited: list[int], index_map: dict[int, dict[str, str]]) -> Provenance:
    return Provenance(
        cited_indices=cited,
        sources={
            str(i): Source(
                file=index_map.get(i, {}).get("file", "unknown"),
                snippet=index_map.get(i, {}).get("snippet", ""),
            )
            for i in cited
        },
        verification_status="verified",
    )


async def _generate_code_core(
    prompt: str,
    language: str | None = None,
    model_override: str | None = None,
) -> CodeResponse:
    selection = select_best_model(prompt, language)
    chosen_model = model_override or selection["model"]
    provider = LLMFactory.create_provider(settings.LLM_PROVIDER)
    if not provider.is_ready() and settings.LLM_PROVIDER != "ollama":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"LLM provider '{settings.LLM_PROVIDER}' is not configured",
        )

    context_prompt, index_map = build_context_prompt(prompt)
    if not context_prompt:
        return CodeResponse(
            code="// Aborted: no supporting repository context found.",
            explanation="Abstained due to lack of repository context.",
            confidence=0.0,
            model_used=chosen_model,
            elapsed_ms=0,
        )

    task_prompt = (
        "You are a careful, expert AI programmer.\n"
        "Only use information from the provided repository context.\n"
        "When you reference or rely on repository content, cite the supporting context by placing the chunk index in square brackets (e.g. [1], [2]) inline next to the code or comment.\n"
        "If you cannot find supporting repository context for the request, respond with exactly:\n"
        "I don't have enough repository context to answer this. Abstaining.\n"
        f"Generate clean, optimized {language or '[AUTO DETECTED]'} code for:\n{prompt}\n"
        f"{context_prompt}"
        "Return only code. Do not include explanations or markdown fences."
    )

    start = time.time()
    try:
        response_text = await asyncio.wait_for(
            provider.generate(task_prompt, model=chosen_model),
            timeout=settings.GENERATION_TIMEOUT,
        )
        code = response_text or "// No code generated."
    except asyncio.TimeoutError:
        logger.exception("Code generation timeout")
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Code generation timed out") from None
    except Exception as ex:
        logger.exception("Code generation failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Code generation failed: {ex}") from ex

    elapsed = int((time.time() - start) * 1000)
    ok, reason, cited = verify_response(code, allowed_indices=list(index_map.keys()))
    if not ok:
        logger.warning("Generation output rejected: %s", reason)
        return CodeResponse(
            code="// Aborted: generated output missing required repository citations.",
            explanation="Abstained due to missing citations in model output.",
            confidence=0.0,
            model_used=chosen_model,
            elapsed_ms=elapsed,
        )

    provenance = _build_provenance(cited, index_map)
    return CodeResponse(
        code=code,
        explanation=f"Generated by {chosen_model} ({selection['reason']}).",
        confidence=0.95,
        model_used=chosen_model,
        elapsed_ms=elapsed,
        provenance=provenance,
    )


async def _fix_code_core(
    file_code: str,
    instructions: str | None = None,
    model_override: str | None = None,
) -> CodeResponse:
    selection = select_best_model(file_code, None)
    chosen_model = model_override or selection["model"]
    provider = LLMFactory.create_provider(settings.LLM_PROVIDER)
    if not provider.is_ready() and settings.LLM_PROVIDER != "ollama":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"LLM provider '{settings.LLM_PROVIDER}' is not configured",
        )

    context_prompt, index_map = build_context_prompt(file_code)
    if not context_prompt:
        return CodeResponse(
            code="// Aborted: no supporting repository context found.",
            explanation="Abstained due to lack of repository context.",
            confidence=0.0,
            model_used=chosen_model,
            elapsed_ms=0,
        )

    prompt = (
        "You are an expert senior developer.\n"
        "Only use the provided repository context to inform fixes; cite chunk indices inline when referencing repository content.\n"
        f"Given this code:\n{file_code}\n\n"
        f"Instructions: {instructions or 'Fix all bugs and optimize for best practices.'}\n"
        f"{context_prompt}"
        "Return only the fixed code. Do not include explanations or markdown fences."
    )

    start = time.time()
    try:
        response_text = await asyncio.wait_for(provider.generate(prompt, model=chosen_model), timeout=settings.GENERATION_TIMEOUT)
        code = response_text or "// No fixes generated."
    except asyncio.TimeoutError:
        logger.exception("Code fix timeout")
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Code fixing timed out") from None
    except Exception as exc:
        logger.exception("Code fix failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Code fixing failed: {exc}") from exc

    elapsed = int((time.time() - start) * 1000)
    ok, reason, cited = verify_response(code, allowed_indices=list(index_map.keys()))
    if not ok:
        logger.warning("Fix output rejected: %s", reason)
        return CodeResponse(
            code="// Aborted: generated output missing required repository citations.",
            explanation="Abstained due to missing citations in model output.",
            confidence=0.0,
            model_used=chosen_model,
            elapsed_ms=elapsed,
        )

    provenance = _build_provenance(cited, index_map)
    return CodeResponse(
        code=code,
        explanation=f"Fixed by {chosen_model} ({selection['reason']}).",
        confidence=0.95,
        model_used=chosen_model,
        elapsed_ms=elapsed,
        provenance=provenance,
    )


@router.post("/generate-code", response_model=CodeResponse)
async def generate_code(request: Request, payload: CodeRequest):
    if not is_activated() and not getattr(request.app.state, "activated", False):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="AI Agent inactive. Use /activate.")
    return await _generate_code_core(payload.prompt, payload.language, payload.model)


@router.post("/fix-code", response_model=CodeResponse)
async def fix_code(request: Request, payload: FixRequest):
    if not is_activated() and not getattr(request.app.state, "activated", False):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="AI Agent inactive. Use /activate.")
    return await _fix_code_core(payload.file_code, payload.instructions)
