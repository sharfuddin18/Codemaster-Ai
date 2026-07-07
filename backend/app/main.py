import logging
import warnings
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routes.control import router as control_router
from app.routes.generation import router as generation_router
from app.routes.health import router as health_router
from app.services.ollama_service import close_ollama_client
from database.db import get_state

warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", message=".*protected namespace.*")

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(asctime)s [%(name)s] %(message)s",
)
logger = logging.getLogger("codemaster-ai")

app = FastAPI(
    title="Codemaster-AI Ultra Boss",
    description="Brutal AI code agent with full safety & zero crash tolerance",
    version="9.9.9",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.ALLOWED_ORIGINS.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



@app.on_event("startup")
async def load_persisted_state():
    """Load the persisted activation state when the application starts."""
    set_app_state_from_db()


def set_app_state_from_db() -> None:
    """Synchronize the in-memory app state with the persisted database state."""
    app.state.activated = get_state().get("activated", False)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all HTTP requests with unique request ID and execution time."""
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id

    logger.info(f"[{request_id}] {request.method} {request.url}")
    try:
        return await call_next(request)
    except Exception:
        logger.exception(f"[{request_id}] 🔥 Unhandled error in request")
        raise


app.include_router(health_router)
app.include_router(control_router)
app.include_router(generation_router)


@app.on_event("shutdown")
async def shutdown_event():
    """Gracefully close connections on server shutdown."""
    await close_ollama_client()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=settings.HOST,
        port=settings.PORT,
    )
