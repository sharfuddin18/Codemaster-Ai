import asyncio
import logging
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status

from app.config import settings
from app.models import CodeRequest, CodeResponse, FixRequest, Provenance, Source
from app.llm.factory import LLMFactory
from app.services.ollama_service import select_best_model
from app.utils.vector_engine import CodeVectorEngine
from app.services.response_verifier import verify_response
from database.db import is_activated

logger = logging.getLogger("codemaster-ai")
router = APIRouter(tags=["Generation"])

_vector_engine = None


def get_vector_engine() -> CodeVectorEngine:
    global _vector_engine
    if _vector_engine is None:
        repo_root = Path(__file__).resolve().parents[3]
        _vector_engine = CodeVectorEngine(repo_root)
    return _vector_engine


def build_context_prompt(query: str) -> tuple[str, dict[int, dict[str, str]]]:
    try:
        engine = get_vector_engine()
        context_chunks = engine.search_context(query, top_k=3)
    except Exception as exc:
        logger.warning("Vector context lookup failed: %s", exc)
        return "", {}

    if not context_chunks:
        return "", {}

    formatted = "\n\n".join(f"[{index}] {chunk}" for index, chunk in enumerate(context_chunks, start=1))

    # Build a mapping of chunk index -> {file, snippet} when available for provenance.
    chunk_map: dict[int, dict[str, str]] = {}
    for idx, chunk in enumerate(context_chunks, start=1):
        lines = chunk.splitlines()
        first_line = lines[0] if lines else ""
        if first_line.startswith("File:"):
            src = first_line.replace("File:", "", 1).strip()
            snippet = "\n".join(lines[1:]).strip()
        else:
            src = "unknown"
            snippet = "\n".join(lines).strip()
        chunk_map[idx] = {"file": src, "snippet": snippet}

    prompt_text = (
        "Use the following repository context when relevant:\n"
        f"{formatted}\n"
    )
    return prompt_text, chunk_map


def build_context_results(query: str, top_k: int = 3) -> list[dict[str, Any]]:
    engine = get_vector_engine()
    context_chunks = engine.search_context(query, top_k=top_k)

    results: list[dict[str, Any]] = []
    for idx, chunk in enumerate(context_chunks, start=1):
        lines = chunk.splitlines()
        first_line = lines[0] if lines else ""
        if first_line.startswith("File:"):
            src = first_line.replace("File:", "", 1).strip()
            snippet = "\n".join(lines[1:]).strip()
        else:
            src = "unknown"
            snippet = "\n".join(lines).strip()

        results.append({
            "index": idx,
            "file": src,
            "snippet": snippet,
            "text": chunk,
            "hybrid_score": 0.0,
        })

    return results


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
        logger.exception("💥 Code generation timeout")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Code generation timed out",
        ) from None
    except Exception as ex:
        logger.exception("💥 Code generation failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Code generation failed: {ex}",
        ) from ex

    elapsed = int((time.time() - start) * 1000)
    allowed_indices = list(index_map.keys())
    ok, reason, cited = verify_response(code, allowed_indices=allowed_indices)
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
    logger.info(f"✅ Generated {len(code)} chars in {elapsed}ms with {chosen_model}")
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
        response_text = await asyncio.wait_for(
            provider.generate(prompt, model=chosen_model),
            timeout=settings.GENERATION_TIMEOUT,
        )
        code = response_text or "// No fixes generated."
    except asyncio.TimeoutError:
        logger.exception("💥 Code fix timeout")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Code fixing timed out",
        ) from None
    except Exception as exc:
        logger.exception("💥 Code fix failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Code fixing failed: {exc}",
        ) from exc

    elapsed = int((time.time() - start) * 1000)
    allowed_indices = list(index_map.keys())
    ok, reason, cited = verify_response(code, allowed_indices=allowed_indices)
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
    logger.info(f"✅ Fixed code with {chosen_model} in {elapsed}ms")
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
    """Generate clean, optimized code based on a prompt using AI models."""
    if not is_activated() and not getattr(request.app.state, "activated", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="AI Agent inactive. Use /activate."
        )
    return await _generate_code_core(payload.prompt, payload.language, payload.model)


@router.post("/fix-code", response_model=CodeResponse)
async def fix_code(request: Request, payload: FixRequest):
    """Fix bugs and optimize code based on instructions using AI models."""
    if not is_activated() and not getattr(request.app.state, "activated", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="AI Agent inactive. Use /activate."
        )
    return await _fix_code_core(payload.file_code, payload.instructions)
