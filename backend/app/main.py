import logging
import os
import re
import time
from typing import Dict, Optional

import ollama
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ==== Logging config ====
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(asctime)s [%(name)s] %(message)s",
)
logger = logging.getLogger("codemaster-ai")

# ==== Ollama client config ====
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
_client: Optional[ollama.AsyncClient] = None


def get_ollama_client() -> ollama.AsyncClient:
    """Lazy-initializes the async Ollama client instance."""
    global _client
    if _client is None:
        try:
            _client = ollama.AsyncClient(host=OLLAMA_HOST)
            logger.info(f"✅ Async Ollama client initialized at {OLLAMA_HOST}")
        except Exception as e:
            logger.error(f"❌ Ollama client init failed: {e}")
            raise RuntimeError(f"Could not connect to Ollama server: {e}")
    return _client


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
    prompt: str
    language: Optional[str] = None
    model: Optional[str] = None


class CodeResponse(BaseModel):
    code: str
    explanation: str
    confidence: float
    model_used: str
    elapsed_ms: int


class FixRequest(BaseModel):
    file_code: str
    instructions: Optional[str] = None


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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared state on the app instance for multi-worker safety
app.state.activated = False


# ==== Middleware ====
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    logger.info(f"{request.method} {request.url}")
    try:
        response = await call_next(request)
        return response
    except Exception:
        logger.exception("🔥 Unhandled error in request")
        raise
    finally:
        duration = (time.time() - start_time) * 1000
        logger.info(f"→ {request.method} {request.url} finished in {duration:.2f}ms")


# ==== Root route ====
@app.get("/")
async def root():
    """Welcomes requests and prevents ugly 404 console logs on startup."""
    return {
        "status": "online",
        "service": app.title,
        "version": app.version,
        "docs_url": "/docs",
        "health_check_url": "/health",
        "agent_activated": app.state.activated,
    }


# ==== Activate & Deactivate ====
@app.post("/activate")
async def activate_ai():
    app.state.activated = True
    logger.info("✅ AI agent ACTIVATED.")
    return {"status": "activated", "message": "AI agent is active."}


@app.post("/deactivate")
async def deactivate_ai():
    app.state.activated = False
    logger.info("🛑 AI agent DEACTIVATED.")
    return {"status": "deactivated", "message": "AI agent is inactive."}


# ==== Health ====
@app.get("/health")
async def health():
    try:
        client = get_ollama_client()
        models = await client.list()
        return {
            "status": "healthy",
            "models": parse_ollama_models_response(models),
        }
    except Exception as e:
        logger.error(f"⚠️ Health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}


# ==== Models list ====
@app.get("/models")
async def models():
    try:
        client = get_ollama_client()
        mlist = await client.list()
        return {"models": parse_ollama_models_response(mlist)}
    except Exception as e:
        logger.error(f"❌ Model list retrieval failed: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ==== Generate code ====
@app.post("/generate-code", response_model=CodeResponse)
async def generate_code(request: CodeRequest):
    if not app.state.activated:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="AI Agent inactive. Use /activate.")
    if not request.prompt or not request.prompt.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Prompt cannot be empty.")
    try:
        client = get_ollama_client()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Ollama client not initialized: {e}")

    selection = select_best_model(request.prompt, request.language)
    chosen_model = request.model or selection["model"]

    task_prompt = (
        "You are a brutal, expert-level AI programmer.\n"
        f"Generate clean, optimized {request.language or '[AUTO DETECTED]'} code for:\n{request.prompt}\n"
        "Return only code. Do not include explanations or markdown fences."
    )

    start = time.time()
    try:
        response = await client.generate(
            model=chosen_model,
            prompt=task_prompt,
            options={"temperature": 0.1, "top_p": 0.9, "top_k": 40},
        )
    except Exception as ex:
        logger.exception("💥 Code generation failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Code generation failed: {ex}")

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
@app.post("/fix-code", response_model=CodeResponse)
async def fix_code(req: FixRequest):
    file_code = req.file_code
    instructions = req.instructions

    if not app.state.activated:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="AI Agent inactive. Use /activate.")
    if not file_code or not file_code.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Code cannot be empty.")
    try:
        client = get_ollama_client()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Ollama client not initialized: {e}")

    prompt = (
        "You are an expert senior developer.\n"
        f"Given this code:\n{file_code}\n\n"
        f"Instructions: {instructions or 'Fix all bugs and optimize for best practices.'}\n"
        "Return only the fixed code. Do not include explanations or markdown fences."
    )

    selection = select_best_model(file_code, None)
    chosen_model = selection["model"]

    start = time.time()
    try:
        response = await client.generate(
            model=chosen_model,
            prompt=prompt,
            options={"temperature": 0.1, "top_p": 0.9, "top_k": 40},
        )
    except Exception as e:
        logger.exception("💥 Code fix failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Code fixing failed: {str(e)}")

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


# ==== Run server ====
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)