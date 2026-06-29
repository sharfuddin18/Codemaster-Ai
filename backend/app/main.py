import asyncio
import logging
import re
import time
import uuid
from typing import Dict, Optional

import ollama
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from config import settings

# ==== Logging config ====
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(asctime)s [%(name)s] %(message)s",
)
logger = logging.getLogger("codemaster-ai")

# ==== Ollama client config ====
_client: Optional[ollama.AsyncClient] = None
_models_cache: Optional[Dict] = None
_cache_timestamp: float = 0
CACHE_TTL = 300  # 5 minutes


def get_ollama_client() -> ollama.AsyncClient:
    """Lazy-initializes the async Ollama client instance with timeout."""
    global _client
    if _client is None:
        try:
            _client = ollama.AsyncClient(
                host=settings.OLLAMA_HOST,
                timeout=settings.OLLAMA_TIMEOUT,
            )
            logger.info(f"✅ Async Ollama client initialized at {settings.OLLAMA_HOST}")
        except Exception as e:
            logger.error(f"❌ Ollama client init failed: {e}")
            raise RuntimeError(f"Could not connect to Ollama server: {e}")
    return _client


async def close_ollama_client():
    """Gracefully close the Ollama client on shutdown."""
    global _client
    if _client:
        try:
            logger.info("🛑 Ollama client closed")
        except Exception as e:
            logger.error(f"Error closing Ollama client: {e}")
        finally:
            _client = None


def clean_llm_markdown(text: str) -> str:
    """Extract only clean code from fenced markdown blocks if present.
    Uses hexadecimal escapes to prevent markdown parser truncation.
    """
    text = (text or "").strip()

    # Matches standard triple-backtick boundaries with hex escaping (\x60 = `)
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
    """Extracts raw text strings cleanly out of Ollama generation structures.
    Safely navigates nested structure blocks and dictionaries.
    """
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


# ==== Models (Pydantic) ====
class CodeRequest(BaseModel):
    """Request model for code generation."""
    prompt: str = Field(..., min_length=1, max_length=settings.MAX_PROMPT_LENGTH)
    language: Optional[str] = Field(None, description="Programming language (optional)")
    model: Optional[str] = Field(None, description="Override model selection (optional)")


class CodeResponse(BaseModel):
    """Response model for code generation and fixing."""
    code: str
    explanation: str
    confidence: float
    model_used: str
    elapsed_ms: int


class FixRequest(BaseModel):
    """Request model for code fixing."""
    file_code: str = Field(..., min_length=1, max_length=settings.MAX_CODE_LENGTH)
    instructions: Optional[str] = Field(None, max_length=1000, description="Fix instructions (optional)")


# ==== Model selector ====
def select_best_model(prompt: str, language: Optional[str]) -> Dict[str, str]:
    """Dynamically routes code tasks to specific models using clean word boundaries."""
    p = (prompt or "").lower()
    l = (language or "").lower()

    def matches_boundary(keyword: str, text: str) -> bool:
        """Helper to check for exact word boundaries, resolving substring collision errors.
        Using negative lookbehinds and lookaheads allows exact matching of strings that
        contain punctuation symbols (like C++ or C#) without triggering word-boundary failures.
        """
        escaped_kw = re.escape(keyword)
        return bool(re.search(rf"(?<!\w){escaped_kw}(?!\w)", text))

    mapping = [
        (
            "mistral:7b-instruct",
            "Data Science/ML detected",
            lambda: any(
                matches_boundary(x, p)
                for x in [
                    "machine learning",
                    "ml",
                    "pandas",
                    "numpy",
                    "dataframe",
                    "scikit",
                    "keras",
                    "data science",
                    "deep learning",
                    "regression",
                    "classification",
                    "training",
                    "inference",
                    "stats",
                ]
            ),
        ),
        ("codellama:7b-instruct", "Python detected", lambda: matches_boundary("python", l) or matches_boundary("python", p)),
        (
            "qwen2.5-coder:7b",
            "JavaScript/Web detected",
            lambda: matches_boundary("javascript", l)
            or matches_boundary("js", l)
            or any(
                matches_boundary(x, p)
                for x in [
                    "javascript",
                    "js",
                    "web",
                    "html",
                    "css",
                    "browser",
                    "frontend",
                    "react",
                    "vue",
                ]
            ),
        ),
        ("mistral:7b-instruct", "Java detected", lambda: matches_boundary("java", l) or matches_boundary("java", p)),
        (
            "mistral:7b-instruct",
            "C/C++ detected",
            lambda: any(matches_boundary(x, l) for x in ["c++", "cpp", "c language"])
            or any(matches_boundary(x, p) for x in ["c++", "cpp"]),
        ),
        ("mistral:7b-instruct", "C# detected", lambda: matches_boundary("c#", l) or matches_boundary("c#", p)),
        (
            "mistral:7b-instruct",
            "Go detected",
            lambda: matches_boundary("go", l) or matches_boundary("golang", l) or matches_boundary("go lang", p),
        ),
        ("mistral:7b-instruct", "Rust detected", lambda: matches_boundary("rust", l) or matches_boundary("rust", p)),
        ("mistral:7b-instruct", "Ruby detected", lambda: matches_boundary("ruby", l) or matches_boundary("ruby", p)),
        (
            "mistral:7b-instruct",
            "TypeScript detected",
            lambda: matches_boundary("typescript", l) or matches_boundary("typescript", p),
        ),
        (
            "mistral:7b-instruct",
            "Swift/Kotlin detected",
            lambda: any(matches_boundary(x, l) for x in ["swift", "kotlin"])
            or any(matches_boundary(x, p) for x in ["swift", "kotlin", "android", "ios"]),
        ),
        (
            "qwen2.5-coder:7b",
            "SQL/Database detected",
            lambda: matches_boundary("sql", l)
            or matches_boundary("sql", p)
            or any(
                matches_boundary(x, p)
                for x in [
                    "query",
                    "database",
                    "mysql",
                    "postgres",
                    "sqlite",
                    "mongodb",
                    "oracle",
                    "db",
                    "table",
                    "column",
                ]
            ),
        ),
        (
            "qwen2.5-coder:7b",
            "Shell/Bash detected",
            lambda: any(matches_boundary(x, l) for x in ["bash", "shell", "sh"])
            or any(
                matches_boundary(x, p)
                for x in [
                    "shell script",
                    "bash script",
                    "automation",
                    "cli",
                    "powershell",
                ]
            ),
        ),
        ("qwen2.5-coder:7b", "PHP detected", lambda: matches_boundary("php", l) or matches_boundary("php", p)),
        (
            "qwen2.5-coder:7b",
            "DevOps detected",
            lambda: any(matches_boundary(x, l) for x in ["yaml", "docker", "compose"])
            or any(
                matches_boundary(x, p)
                for x in [
                    "yaml",
                    "docker",
                    "docker-compose",
                    "kubernetes",
                ]
            ),
        ),
        (
            "qwen2.5-coder:7b",
            "Frontend/UI/UX detected",
            lambda: any(matches_boundary(x, l) for x in ["html", "css"])
            or any(
                matches_boundary(x, p)
                for x in [
                    "html",
                    "css",
                    "ui",
                    "ux",
                    "responsive",
                    "design",
                ]
            ),
        ),
        (
            "mistral:7b-instruct",
            "Statistical/Matlab/R/SAS detected",
            lambda: any(matches_boundary(x, l) for x in ["matlab", "r", "sas"])
            or any(
                matches_boundary(x, p)
                for x in [
                    "matlab",
                    "r language",
                    "sas",
                    "regression analysis",
                    "statistical",
                ]
            ),
        ),
    ]

    for model, reason, cond in mapping:
        try:
            if cond():
                logger.info(f"Model selected: {model} | Reason: {reason}")
                return {"model": model, "reason": reason}
        except Exception:
            continue

    logger.info("Model selected: qwen2.5-coder:7b | Reason: Default fallback")
    return {"model": "qwen2.5-coder:7b", "reason": "Default fallback"}


# ==== FastAPI app ====
app = FastAPI(
    title="Codemaster-AI Ultra Boss",
    description="Brutal AI code agent with full safety & zero crash tolerance",
    version="9.9.9",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared state on the app instance for multi-worker safety
app.state.activated = False


# ==== Middleware ====
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all HTTP requests with unique request ID and execution time."""
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    
    start_time = time.time()
    logger.info(f"[{request_id}] {request.method} {request.url}")
    try:
        response = await call_next(request)
        return response
    except Exception as e:
        logger.exception(f"[{request_id}] 🔥 Unhandled error in request")
        raise
    finally:
        duration = (time.time() - start_time) * 1000
        logger.info(f"[{request_id}] → {request.method} {request.url} finished in {duration:.2f}ms")


# ==== Root route ====
@app.get("/", tags=["Health"])
async def root():
    """Welcome endpoint and health check."""
    return {
        "status": "online",
        "service": app.title,
        "version": app.version,
        "docs_url": "/docs",
        "health_check_url": "/health",
        "agent_activated": app.state.activated,
    }


# ==== Activate & Deactivate ====
@app.post("/activate", tags=["Control"])
async def activate_ai():
    """Activate the AI agent to enable code generation and fixing."""
    app.state.activated = True
    logger.info("✅ AI agent ACTIVATED.")
    return {"status": "activated", "message": "AI agent is active."}


@app.post("/deactivate", tags=["Control"])
async def deactivate_ai():
    """Deactivate the AI agent to disable code generation and fixing."""
    app.state.activated = False
    logger.info("🛑 AI agent DEACTIVATED.")
    return {"status": "deactivated", "message": "AI agent is inactive."}


# ==== Health ====
@app.get("/health", tags=["Health"])
async def health():
    """Health check endpoint that verifies Ollama connection and lists available models."""
    try:
        client = get_ollama_client()
        models = await asyncio.wait_for(client.list(), timeout=settings.OLLAMA_TIMEOUT)
        return {
            "status": "healthy",
            "models": parse_ollama_models_response(models),
        }
    except asyncio.TimeoutError:
        logger.error("⚠️ Health check timeout")
        return {"status": "unhealthy", "error": "Ollama connection timeout"}
    except Exception as e:
        logger.error(f"⚠️ Health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}


# ==== Models list ====
@app.get("/models", tags=["Models"])
async def models():
    """List available Ollama models with optional caching."""
    try:
        global _models_cache, _cache_timestamp
        current_time = time.time()
        
        # Return cached models if fresh
        if _models_cache and (current_time - _cache_timestamp) < CACHE_TTL:
            logger.info("📦 Returning cached models list")
            return {"models": _models_cache}
        
        client = get_ollama_client()
        mlist = await asyncio.wait_for(client.list(), timeout=settings.OLLAMA_TIMEOUT)
        _models_cache = parse_ollama_models_response(mlist)
        _cache_timestamp = current_time
        
        return {"models": _models_cache}
    except asyncio.TimeoutError:
        logger.error("❌ Model list retrieval timeout")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Ollama server is not responding"
        )
    except Exception as e:
        logger.error(f"❌ Model list retrieval failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ==== Generate code ====
@app.post("/generate-code", response_model=CodeResponse, tags=["Generation"])
async def generate_code(request: CodeRequest):
    """Generate clean, optimized code based on a prompt using AI models."""
    if not app.state.activated:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="AI Agent inactive. Use /activate."
        )
    
    try:
        client = get_ollama_client()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ollama client not initialized: {e}"
        )

    selection = select_best_model(request.prompt, request.language)
    chosen_model = request.model or selection["model"]

    task_prompt = (
        "You are a brutal, expert-level AI programmer.\n"
        f"Generate clean, optimized {request.language or '[AUTO DETECTED]'} code for:\n{request.prompt}\n"
        "Return only code. Do not include explanations or markdown fences."
    )

    start = time.time()
    try:
        response = await asyncio.wait_for(
            client.generate(
                model=chosen_model,
                prompt=task_prompt,
                options={
                    "temperature": settings.GENERATION_TEMPERATURE,
                    "top_p": settings.GENERATION_TOP_P,
                    "top_k": settings.GENERATION_TOP_K,
                },
            ),
            timeout=settings.GENERATION_TIMEOUT
        )
    except asyncio.TimeoutError:
        logger.exception("💥 Code generation timeout")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Code generation timed out"
        )
    except Exception as ex:
        logger.exception("💥 Code generation failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Code generation failed: {ex}"
        )

    elapsed = int((time.time() - start) * 1000)
    code = extract_ollama_response_text(response) or "// No code generated."

    logger.info(f"✅ Generated {len(code)} chars in {elapsed}ms with {chosen_model}")
    return CodeResponse(
        code=code,
        explanation=f"Generated by {chosen_model} ({selection['reason']}).",
        confidence=0.95,
        model_used=chosen_model,
        elapsed_ms=elapsed,
    )


# ==== Fix code ====
@app.post("/fix-code", response_model=CodeResponse, tags=["Generation"])
async def fix_code(req: FixRequest):
    """Fix bugs and optimize code based on instructions using AI models."""
    if not app.state.activated:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="AI Agent inactive. Use /activate."
        )
    
    try:
        client = get_ollama_client()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ollama client not initialized: {e}"
        )

    prompt = (
        "You are an expert senior developer.\n"
        f"Given this code:\n{req.file_code}\n\n"
        f"Instructions: {req.instructions or 'Fix all bugs and optimize for best practices.'}\n"
        "Return only the fixed code. Do not include explanations or markdown fences."
    )

    selection = select_best_model(req.file_code, None)
    chosen_model = selection["model"]

    start = time.time()
    try:
        response = await asyncio.wait_for(
            client.generate(
                model=chosen_model,
                prompt=prompt,
                options={
                    "temperature": settings.GENERATION_TEMPERATURE,
                    "top_p": settings.GENERATION_TOP_P,
                    "top_k": settings.GENERATION_TOP_K,
                },
            ),
            timeout=settings.GENERATION_TIMEOUT
        )
    except asyncio.TimeoutError:
        logger.exception("💥 Code fix timeout")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Code fixing timed out"
        )
    except Exception as e:
        logger.exception("💥 Code fix failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Code fixing failed: {str(e)}"
        )

    elapsed = int((time.time() - start) * 1000)
    code = extract_ollama_response_text(response) or "// No fixes generated."

    logger.info(f"✅ Fixed code with {chosen_model} in {elapsed}ms")
    return CodeResponse(
        code=code,
        explanation=f"Fixed by {chosen_model} ({selection['reason']}).",
        confidence=0.95,
        model_used=chosen_model,
        elapsed_ms=elapsed,
    )


# ==== Shutdown event ====
@app.on_event("shutdown")
async def shutdown_event():
    """Gracefully close connections on server shutdown."""
    await close_ollama_client()


# ==== Run server ====
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=settings.HOST,
        port=settings.PORT,
    )
