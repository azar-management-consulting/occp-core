"""Voice pipeline status and history routes for the OCCP Brain."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from api.deps import AppState, get_state

router = APIRouter(tags=["voice"])


@router.get("/voice/status")
async def voice_status(
    state: AppState = Depends(get_state),
) -> dict[str, Any]:
    """Voice pipeline status: bot connected, last command, stats."""
    handler = getattr(state, "voice_handler", None)

    if handler is None:
        return {
            "enabled": False,
            "bot_connected": False,
            "detail": "Voice pipeline not configured",
        }

    return handler.get_status()


@router.get("/voice/history")
async def voice_history(
    state: AppState = Depends(get_state),
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    """Recent voice commands with transcription + task status."""
    handler = getattr(state, "voice_handler", None)

    if handler is None:
        return {"commands": [], "total": 0}

    commands = handler.get_history(limit=limit)
    return {
        "commands": commands,
        "total": len(commands),
    }
