"""Status endpoint – health check, version info, and LLM provider health."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from api.deps import AppState, get_state
from api.models import StatusResponse

router = APIRouter(tags=["status"])


@router.get("/status", response_model=StatusResponse)
async def get_status(state: AppState = Depends(get_state)) -> StatusResponse:
    return StatusResponse(
        version="0.6.0",
        tasks_count=await state.task_count(),
        audit_entries=len(state.policy_engine.audit_log),
    )


@router.get("/llm/health")
async def llm_health(state: AppState = Depends(get_state)) -> dict[str, Any]:
    """Return per-provider health metrics from the MultiLLMPlanner.

    Includes circuit breaker state, success rates, latency, and call counts.
    """
    if state.multi_planner is None:
        return {"providers": {}, "status": "no_planner_configured"}

    providers = state.multi_planner.get_health()
    all_healthy = all(p["healthy"] for p in providers.values())
    return {
        "status": "healthy" if all_healthy else "degraded",
        "providers": providers,
    }
