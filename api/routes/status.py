"""Status endpoint – health check and version info."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from api.deps import AppState, get_state
from api.models import StatusResponse

router = APIRouter(tags=["status"])


@router.get("/status", response_model=StatusResponse)
async def get_status(state: AppState = Depends(get_state)) -> StatusResponse:
    return StatusResponse(
        version="0.5.0",
        tasks_count=await state.task_count(),
        audit_entries=len(state.policy_engine.audit_log),
    )
