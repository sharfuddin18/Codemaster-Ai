import asyncio
import logging
import os
import time

from fastapi import APIRouter, HTTPException, Request, status

from app.config import settings
from app.llm.factory import LLMFactory
from app.services import ollama_service
from app.utils.helpers import parse_ollama_models_response

logger = logging.getLogger("codemaster-ai")
router = APIRouter(tags=["Health"])


@router.get("/")
async def root(request: Request):
    """Welcome endpoint and health check."""
    return {
        "status": "online",
        "service": request.app.title,
        "version": request.app.version,
        "docs_url": "/docs",
        "health_check_url": "/health",
        "agent_activated": request.app.state.activated,
    }


async def health_check():
    """Return readiness for the configured provider without performing generation."""
    provider = LLMFactory.create_provider(os.getenv("LLM_PROVIDER") or getattr(settings, "LLM_PROVIDER", "ollama"))
    status = provider.get_status()

    if provider.is_ready():
        return {
            "status": "healthy",
            "provider": provider.provider_name,
            "details": status,
        }

    return {
        "status": "degraded",
        "provider": provider.provider_name,
        "details": status,
    }


@router.get("/health")
async def health():
    """Health check endpoint that reports provider readiness without crashing the service."""
    return await health_check()


@router.get("/models")
async def models():
    """List available Ollama models with optional caching."""
    try:
        current_time = time.time()
        if ollama_service._models_cache and (current_time - ollama_service._cache_timestamp) < ollama_service.CACHE_TTL:
            logger.info("📦 Returning cached models list")
            return {"models": ollama_service._models_cache}

        client = ollama_service.get_ollama_client()
        mlist = await asyncio.wait_for(client.list(), timeout=settings.OLLAMA_TIMEOUT)
        ollama_service._models_cache = parse_ollama_models_response(mlist)
        ollama_service._cache_timestamp = current_time

        return {"models": ollama_service._models_cache}
    except asyncio.TimeoutError:
        logger.error("❌ Model list retrieval timeout")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Ollama server is not responding",
        ) from None
    except Exception as exc:
        logger.error(f"❌ Model list retrieval failed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
