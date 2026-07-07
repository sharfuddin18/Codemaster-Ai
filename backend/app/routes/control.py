import logging

from fastapi import APIRouter, Request

from database.db import set_state

logger = logging.getLogger("codemaster-ai")
router = APIRouter(tags=["Control"])


@router.post("/activate")
async def activate_ai(request: Request):
    """Activate the AI agent to enable code generation and fixing."""
    set_state(True)
    request.app.state.activated = True
    logger.info("✅ AI agent ACTIVATED.")
    return {"status": "activated", "message": "AI agent is active."}


@router.post("/deactivate")
async def deactivate_ai(request: Request):
    """Deactivate the AI agent to disable code generation and fixing."""
    set_state(False)
    request.app.state.activated = False
    logger.info("🛑 AI agent DEACTIVATED.")
    return {"status": "deactivated", "message": "AI agent is inactive."}
