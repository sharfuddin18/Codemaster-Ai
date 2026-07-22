import logging
import re
from typing import Dict, Optional

import ollama

from app.config import settings
from app.utils.retry_handler import retry_on_transient_error

logger = logging.getLogger("codemaster-ai")

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


@retry_on_transient_error(retries=3, base_delay=0.5, max_delay=4.0)
async def generate_with_retry(client, **kwargs):
    """Generate text via Ollama with exponential backoff for transient failures."""
    return await client.generate(**kwargs)


def select_best_model(prompt: str, language: Optional[str]) -> Dict[str, str]:
    """Dynamically routes code tasks to specific models using clean word boundaries."""
    p = (prompt or "").lower()
    lang = (language or "").lower()

    def matches_boundary(keyword: str, text: str) -> bool:
        """Helper to check for exact word boundaries, resolving substring collision errors."""
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
        ("codellama:7b-instruct", "Python detected", lambda: matches_boundary("python", lang) or matches_boundary("python", p)),
        (
            "qwen2.5-coder:1.5b",
            "JavaScript/Web detected",
            lambda: matches_boundary("javascript", lang)
            or matches_boundary("js", lang)
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
        ("mistral:7b-instruct", "Java detected", lambda: matches_boundary("java", lang) or matches_boundary("java", p)),
        (
            "mistral:7b-instruct",
            "C/C++ detected",
            lambda: any(matches_boundary(x, lang) for x in ["c++", "cpp", "c language"])
            or any(matches_boundary(x, p) for x in ["c++", "cpp"]),
        ),
        ("mistral:7b-instruct", "C# detected", lambda: matches_boundary("c#", lang) or matches_boundary("c#", p)),
        (
            "mistral:7b-instruct",
            "Go detected",
            lambda: matches_boundary("go", lang) or matches_boundary("golang", lang) or matches_boundary("go lang", p),
        ),
        ("mistral:7b-instruct", "Rust detected", lambda: matches_boundary("rust", lang) or matches_boundary("rust", p)),
        ("mistral:7b-instruct", "Ruby detected", lambda: matches_boundary("ruby", lang) or matches_boundary("ruby", p)),
        (
            "mistral:7b-instruct",
            "TypeScript detected",
            lambda: matches_boundary("typescript", lang) or matches_boundary("typescript", p),
        ),
        (
            "mistral:7b-instruct",
            "Swift/Kotlin detected",
            lambda: any(matches_boundary(x, lang) for x in ["swift", "kotlin"])
            or any(matches_boundary(x, p) for x in ["swift", "kotlin", "android", "ios"]),
        ),
        (
            "qwen2.5-coder:1.5b",
            "SQL/Database detected",
            lambda: matches_boundary("sql", lang)
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
            "qwen2.5-coder:1.5b",
            "Shell/Bash detected",
            lambda: any(matches_boundary(x, lang) for x in ["bash", "shell", "sh"])
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
        ("qwen2.5-coder:1.5b", "PHP detected", lambda: matches_boundary("php", lang) or matches_boundary("php", p)),
        (
            "qwen2.5-coder:1.5b",
            "DevOps detected",
            lambda: any(matches_boundary(x, lang) for x in ["yaml", "docker", "compose"])
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
            "qwen2.5-coder:1.5b",
            "Frontend/UI/UX detected",
            lambda: any(matches_boundary(x, lang) for x in ["html", "css"])
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
            lambda: any(matches_boundary(x, lang) for x in ["matlab", "r", "sas"])
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
        except Exception:  # nosec B112
            continue

    logger.info("Model selected: qwen2.5-coder:1.5b | Reason: Default fallback")
    return {"model": "qwen2.5-coder:1.5b", "reason": "Default fallback"}
