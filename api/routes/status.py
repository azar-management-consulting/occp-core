"""Status endpoint – health check, version info, and LLM provider health."""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import text

from api.deps import AppState, get_state
from api.models import HealthCheck, HealthResponse, StatusResponse

router = APIRouter(tags=["status"])

_VERSION = "0.10.1"


@router.get("/status", response_model=StatusResponse)
async def get_status(state: AppState = Depends(get_state)) -> StatusResponse:
    return StatusResponse(
        version=_VERSION,
        tasks_count=await state.task_count(),
        audit_entries=len(state.policy_engine.audit_log),
    )


@router.get("/health", response_model=HealthResponse)
async def health_check(state: AppState = Depends(get_state)) -> HealthResponse:
    """Readiness probe — verifies database connectivity and core subsystems."""
    checks: list[HealthCheck] = []

    # 1. Database ping
    db_check = await _check_database(state)
    checks.append(db_check)

    # 2. Policy engine
    pe_status = "ok" if state.policy_engine is not None else "error"
    checks.append(HealthCheck(name="policy_engine", status=pe_status))

    # 3. Pipeline
    pl_status = "ok" if state.pipeline is not None else "error"
    checks.append(HealthCheck(name="pipeline", status=pl_status))

    # Overall status
    all_ok = all(c.status == "ok" for c in checks)
    any_ok = any(c.status == "ok" for c in checks)
    if all_ok:
        overall = "healthy"
    elif any_ok:
        overall = "degraded"
    else:
        overall = "unhealthy"

    return HealthResponse(status=overall, version=_VERSION, checks=checks)


async def _check_database(state: AppState) -> HealthCheck:
    """Execute ``SELECT 1`` to verify database connectivity."""
    if state.db is None:
        return HealthCheck(name="database", status="error", detail="no_connection")
    try:
        start = time.monotonic()
        async with state.db.session_factory() as session:
            await session.execute(text("SELECT 1"))
        latency = round((time.monotonic() - start) * 1000, 2)
        return HealthCheck(name="database", status="ok", latency_ms=latency)
    except Exception as exc:
        return HealthCheck(
            name="database", status="error", detail=str(exc)[:200]
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
