"""Dashboard API — real-time Brain status for dashboard and Telegram.

Endpoints:
    GET /dashboard/overview       — Full Brain status overview
    GET /dashboard/agent/{id}     — Detailed agent view
    GET /dashboard/timeline       — Activity timeline (last 24h)
    GET /dashboard/metrics        — Performance metrics (charts data)
    GET /dashboard/telegram       — Telegram-formatted status message
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from api.auth import get_current_user_payload
from api.deps import AppState, get_state
from api.rbac import PermissionChecker

from orchestrator.brain_stats import BrainStats, BRAIN_AGENT_IDS
from orchestrator.telegram_formatter import format_telegram_status

logger = logging.getLogger(__name__)

router = APIRouter(tags=["dashboard"])


# ---------------------------------------------------------------------------
# Module-level singleton (shared with app lifespan)
# ---------------------------------------------------------------------------

_brain_stats: BrainStats | None = None


def get_brain_stats() -> BrainStats:
    """Get or create the BrainStats singleton."""
    global _brain_stats
    if _brain_stats is None:
        _brain_stats = BrainStats()
    return _brain_stats


def set_brain_stats(stats: BrainStats) -> None:
    """Set the BrainStats singleton (for testing or lifespan injection)."""
    global _brain_stats
    _brain_stats = stats


# ---------------------------------------------------------------------------
# Helper: get quality gate and feedback loop from quality module
# ---------------------------------------------------------------------------

def _get_quality_gate() -> Any:
    from api.routes.quality import get_quality_gate
    return get_quality_gate()


def _get_feedback_loop() -> Any:
    from api.routes.quality import get_feedback_loop
    return get_feedback_loop()


# ---------------------------------------------------------------------------
# GET /dashboard/overview
# ---------------------------------------------------------------------------


@router.get(
    "/dashboard/overview",
    dependencies=[Depends(PermissionChecker("brain", "read"))],
)
async def dashboard_overview(
    state: AppState = Depends(get_state),
) -> dict[str, Any]:
    """Full Brain status overview.

    Returns brain status, all 8 agents with current state,
    active projects, recent activity stream, and aggregate stats.
    """
    stats = get_brain_stats()
    project_manager = state.project_manager
    quality_gate = _get_quality_gate()
    feedback_loop = _get_feedback_loop()

    return stats.get_overview(
        project_manager=project_manager,
        quality_gate=quality_gate,
        feedback_loop=feedback_loop,
    )


# ---------------------------------------------------------------------------
# GET /dashboard/agent/{agent_id}
# ---------------------------------------------------------------------------


@router.get(
    "/dashboard/agent/{agent_id}",
    dependencies=[Depends(PermissionChecker("brain", "read"))],
)
async def dashboard_agent_detail(agent_id: str) -> dict[str, Any]:
    """Detailed view for a single agent.

    Shows capabilities, current task, today's stats, feedback scores,
    and recent activity for the specified agent.
    """
    if agent_id not in BRAIN_AGENT_IDS:
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{agent_id}' not found. Valid agents: {sorted(BRAIN_AGENT_IDS)}",
        )

    stats = get_brain_stats()
    feedback_loop = _get_feedback_loop()

    return stats.get_agent_detail(agent_id, feedback_loop=feedback_loop)


# ---------------------------------------------------------------------------
# GET /dashboard/timeline
# ---------------------------------------------------------------------------


@router.get(
    "/dashboard/timeline",
    dependencies=[Depends(PermissionChecker("brain", "read"))],
)
async def dashboard_timeline(
    hours: int = Query(default=24, ge=1, le=168, description="Hours to look back"),
) -> dict[str, Any]:
    """Activity timeline for the last N hours (default 24).

    Returns chronologically ordered activity events with type,
    agent, project, and description.
    """
    stats = get_brain_stats()
    activities = stats.get_timeline(hours=hours)

    return {
        "hours": hours,
        "total": len(activities),
        "activities": activities,
    }


# ---------------------------------------------------------------------------
# GET /dashboard/metrics
# ---------------------------------------------------------------------------


@router.get(
    "/dashboard/metrics",
    dependencies=[Depends(PermissionChecker("brain", "read"))],
)
async def dashboard_metrics() -> dict[str, Any]:
    """Performance metrics for dashboard charts.

    Returns per-agent performance, completion time distribution,
    quality distribution, and total task counts.
    """
    stats = get_brain_stats()
    quality_gate = _get_quality_gate()
    feedback_loop = _get_feedback_loop()

    return stats.get_metrics(
        quality_gate=quality_gate,
        feedback_loop=feedback_loop,
    )


# ---------------------------------------------------------------------------
# GET /dashboard/telegram
# ---------------------------------------------------------------------------


@router.get(
    "/dashboard/telegram",
    dependencies=[Depends(PermissionChecker("brain", "read"))],
)
async def dashboard_telegram(
    state: AppState = Depends(get_state),
) -> dict[str, str]:
    """Telegram-formatted status message.

    Returns the compact status message suitable for Telegram delivery
    when Henry sends "staatusz", "status", or "mi a helyzet".
    """
    stats = get_brain_stats()
    project_manager = state.project_manager
    quality_gate = _get_quality_gate()
    feedback_loop = _get_feedback_loop()

    overview = stats.get_overview(
        project_manager=project_manager,
        quality_gate=quality_gate,
        feedback_loop=feedback_loop,
    )

    message = format_telegram_status(overview)
    return {"message": message}
