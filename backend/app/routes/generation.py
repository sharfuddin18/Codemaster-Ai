import asyncio
import logging
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status

from ..agents.code_agent import SYSTEM_PROMPT
from ..config import settings
from ..llm.factory import LLMFactory
from ..llm.routing import AgentRequest, ModelRouter, TaskType
from ..models import CodeRequest, CodeResponse, FixRequest, Provenance, Source
from ..services.hybrid_retriever import HybridRetriever
from ..services.patch_generator import generate_unified_patch
from ..services.response_verifier import verify_response
from ..services.vector_service import VectorService
from ..utils.vector_engine import CodeVectorEngine, IndexConfig
from database.db import is_activated

logger = logging.getLogger("codemaster-ai")
router = APIRouter(tags=["Generation"])

_model_router = ModelRouter()
_vector_engine = None
_hybrid_retriever: HybridRetriever | None = None


def get_vector_engine() -> CodeVectorEngine:
    global _vector_engine
    if _vector_engine is None:
        repo_root = Path(__file__).resolve().parents[3]
        index_dir = Path(settings.INDEX_DIR)
        if not index_dir.is_absolute():
            index_dir = repo_root / index_dir
        index_dir.mkdir(parents=True, exist_ok=True)
        _vector_engine = CodeVectorEngine(
            config=IndexConfig(
                source_dir=repo_root,
                cache_db_path=index_dir / "cache.db",
                persist_path=index_dir / "vector_index",
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
        logger.exception("Hybrid retrieval failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Repository retrieval unavailable",
        ) from exc

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
        logger.exception("Hybrid retrieval failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Repository retrieval unavailable",
        ) from exc
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


def _ensure_provider_ready(provider, decision) -> None:
    if provider.is_ready():
        return
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=f"LLM provider '{decision.provider}' is not ready",
    )


def _route_generation(prompt: str, language: str | None, model_override: str | None):
    request = AgentRequest(
        prompt=prompt,
        language=language,
        task_type=TaskType.GENERATION,
        model_override=model_override,
        provider_override=settings.LLM_PROVIDER,
    )
    return _model_router.route(request)


def _route_fix(file_code: str, model_override: str | None):
    request = AgentRequest(
        prompt=file_code,
        task_type=TaskType.FIX,
        model_override=model_override,
        provider_override=settings.LLM_PROVIDER,
    )
    return _model_router.route(request)


def _build_generation_prompt(prompt: str, language: str | None, context_prompt: str) -> str:
    language_label = language or "[AUTO DETECTED]"
    if context_prompt:
        return (
            f"{SYSTEM_PROMPT}\n"
            "Only use information from the provided repository context when it is relevant.\n"
            "When you reference or rely on repository content, cite the supporting context by placing the chunk index in square brackets (e.g. [1], [2]) inline next to the code or comment.\n"
            "If you cannot find supporting repository context for the request, respond with exactly:\n"
            "I don't have enough repository context to answer this. Abstaining.\n"
            f"Generate clean, optimized {language_label} code for:\n{prompt}\n"
            f"{context_prompt}"
            "Return only code. Do not include explanations or markdown fences."
        )
    return (
        f"{SYSTEM_PROMPT}\n"
        f"Generate clean, optimized {language_label} code for:\n{prompt}\n"
        "No repository context was retrieved. Produce a complete solution from the prompt.\n"
        "Return only code. Do not include explanations or markdown fences."
    )


def _build_fix_prompt(file_code: str, instructions: str | None, context_prompt: str) -> str:
    instruction_text = instructions or "Fix all bugs and optimize for best practices."
    if context_prompt:
        return (
            f"{SYSTEM_PROMPT}\n"
            "Only use the provided repository context to inform fixes; cite chunk indices inline when referencing repository content.\n"
            f"Given this code:\n{file_code}\n\n"
            f"Instructions: {instruction_text}\n"
            f"{context_prompt}"
            "Return only the fixed code. Do not include explanations or markdown fences."
        )
    return (
        f"{SYSTEM_PROMPT}\n"
        f"Given this code:\n{file_code}\n\n"
        f"Instructions: {instruction_text}\n"
        "No repository context was retrieved. Apply the requested fixes directly.\n"
        "Return only the fixed code. Do not include explanations or markdown fences."
    )


def _finalize_output(code: str, index_map: dict[int, dict[str, str]]) -> tuple[str, str, float, Provenance | None]:
    if not index_map:
        return code, "Generated without repository citations because no context was retrieved.", 0.8, None

    ok, reason, cited = verify_response(code, allowed_indices=list(index_map.keys()))
    if not ok:
        logger.warning("Generation output rejected: %s", reason)
        return (
            "// Aborted: generated output missing required repository citations.",
            "Abstained due to missing citations in model output.",
            0.0,
            None,
        )
    return code, "verified", 0.95, _build_provenance(cited, index_map)


def _optional_patch(file_path: str | None, original: str, modified: str) -> str | None:
    if not file_path or not modified or modified.startswith("// Aborted:"):
        return None
    try:
        patch_res = generate_unified_patch(file_path, original, modified)
    except ValueError as exc:
        logger.warning("Skipping patch generation: %s", exc)
        return None
    if not patch_res.get("has_changes"):
        return None
    return patch_res.get("patch")


async def _invoke_provider(provider, prompt: str, model: str, timeout_detail: str) -> str:
    try:
        response_text = await asyncio.wait_for(
            provider.generate(prompt, model=model),
            timeout=settings.GENERATION_TIMEOUT,
        )
        return response_text or "// No code generated."
    except asyncio.TimeoutError:
        logger.exception("%s timeout", timeout_detail)
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail=f"{timeout_detail} timed out") from None
    except Exception as exc:
        logger.exception("%s failed", timeout_detail)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"{timeout_detail} failed: {exc}",
        ) from exc


async def _generate_code_core(
    prompt: str,
    language: str | None = None,
    model_override: str | None = None,
) -> CodeResponse:
    decision = _route_generation(prompt, language, model_override)
    provider, chosen_model = LLMFactory.create(decision)
    _ensure_provider_ready(provider, decision)

    context_prompt, index_map = build_context_prompt(prompt)
    task_prompt = _build_generation_prompt(prompt, language, context_prompt)

    start = time.time()
    code = await _invoke_provider(provider, task_prompt, chosen_model, "Code generation")
    elapsed = int((time.time() - start) * 1000)

    code, explanation, confidence, provenance = _finalize_output(code, index_map)
    if explanation == "verified":
        explanation = f"Generated by {chosen_model} ({decision.reason})."
    elif index_map:
        pass
    else:
        explanation = f"Generated by {chosen_model} ({decision.reason}) without retrieved repository context."

    return CodeResponse(
        code=code,
        explanation=explanation,
        confidence=confidence,
        model_used=chosen_model,
        elapsed_ms=elapsed,
        provenance=provenance,
    )


async def _fix_code_core(
    file_code: str,
    instructions: str | None = None,
    model_override: str | None = None,
    file_path: str | None = None,
) -> CodeResponse:
    decision = _route_fix(file_code, model_override)
    provider, chosen_model = LLMFactory.create(decision)
    _ensure_provider_ready(provider, decision)

    context_prompt, index_map = build_context_prompt(file_code)
    prompt = _build_fix_prompt(file_code, instructions, context_prompt)

    start = time.time()
    code = await _invoke_provider(provider, prompt, chosen_model, "Code fixing")
    elapsed = int((time.time() - start) * 1000)

    code, explanation, confidence, provenance = _finalize_output(code, index_map)
    if explanation == "verified":
        explanation = f"Fixed by {chosen_model} ({decision.reason})."
    elif not index_map:
        explanation = f"Fixed by {chosen_model} ({decision.reason}) without retrieved repository context."

    return CodeResponse(
        code=code,
        explanation=explanation,
        confidence=confidence,
        model_used=chosen_model,
        elapsed_ms=elapsed,
        provenance=provenance,
        patch=_optional_patch(file_path, file_code, code),
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
    return await _fix_code_core(
        payload.file_code,
        payload.instructions,
        file_path=payload.file_path,
    )
