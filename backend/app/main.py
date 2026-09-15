import logging
import uuid
import warnings
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .routes.control import router as control_router
from .routes.generation import router as generation_router
from .routes.health import router as health_router
from .routes.mcp import router as mcp_router
from .services.ollama_service import close_ollama_client
from database.db import get_state

warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", message=".*protected namespace.*")

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(asctime)s [%(name)s] %(message)s",
)
logger = logging.getLogger("codemaster-ai")

OPEN_PATHS = {"/", "/health", "/docs", "/openapi.json", "/redoc"}


def set_app_state_from_db() -> None:
    """Synchronize the in-memory app state with the persisted database state."""
    app.state.activated = get_state().get("activated", False)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load persisted activation state and release provider clients on shutdown."""
    app.state.activated = get_state().get("activated", False)
    yield
    await close_ollama_client()


app = FastAPI(
    title="Codemaster-AI Ultra Boss",
    description="Brutal AI code agent with full safety & zero crash tolerance",
    version="9.9.9",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.ALLOWED_ORIGINS.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all HTTP requests with unique request ID and execution time."""
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id

    if settings.API_KEY and request.url.path not in OPEN_PATHS:
        provided = request.headers.get("x-api-key", "")
        authorization = request.headers.get("authorization", "")
        bearer = authorization[7:] if authorization.lower().startswith("bearer ") else ""
        if provided != settings.API_KEY and bearer != settings.API_KEY:
            return JSONResponse(status_code=401, content={"detail": "Invalid or missing API key"})

    logger.info(f"[{request_id}] {request.method} {request.url}")
    try:
        return await call_next(request)
    except Exception:
        logger.exception(f"[{request_id}] Unhandled error in request")
        raise


app.include_router(health_router)
app.include_router(control_router)
app.include_router(generation_router)
app.include_router(mcp_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=settings.HOST,
        port=settings.PORT,
    )
