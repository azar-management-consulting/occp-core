"""Quality & Feedback API endpoints.

Endpoints:
    GET  /quality/{task_id}         — Quality check results for a task
    POST /feedback                  — Submit Henry's feedback on a task
    GET  /agents/{agent_id}/stats   — Agent performance statistics
    GET  /quality/stats             — Global quality gate statistics
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from api.auth import get_current_user_payload
from api.deps import AppState, get_state
from api.rbac import PermissionChecker

logger = logging.getLogger(__name__)

router = APIRouter(tags=["quality"])


# ---------------------------------------------------------------------------
# In-memory stores (production: persist to DB)
# ---------------------------------------------------------------------------

# Shared QualityGate and FeedbackLoop instances are attached to AppState.
# For now we use module-level singletons if not on AppState.

from orchestrator.quality_gate import QualityGate
from orchestrator.feedback_loop import FeedbackLoop

_quality_gate: QualityGate | None = None
_feedback_loop: FeedbackLoop | None = None


def get_quality_gate() -> QualityGate:
    global _quality_gate
    if _quality_gate is None:
        _quality_gate = QualityGate()
    return _quality_gate


def get_feedback_loop() -> FeedbackLoop:
    global _feedback_loop
    if _feedback_loop is None:
        _feedback_loop = FeedbackLoop()
    return _feedback_loop


def set_quality_gate(gate: QualityGate) -> None:
    global _quality_gate
    _quality_gate = gate


def set_feedback_loop(loop: FeedbackLoop) -> None:
    global _feedback_loop
    _feedback_loop = loop


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

from pydantic import BaseModel, Field


class QualityCheckResponse(BaseModel):
    check_id: str
    agent_id: str
    task_id: str
    check_type: str
    status: str
    score: float
    feedback: str
    reviewer: str
    timestamp: str


class QualityResultResponse(BaseModel):
    task_id: str
    checks: list[QualityCheckResponse]
    total: int
    passed: int
    failed: int


class FeedbackRequest(BaseModel):
    task_id: str = Field(..., min_length=1)
    agent_id: str = Field(..., min_length=1)
    rating: int = Field(..., ge=1, le=5)
    comment: str = Field(default="", max_length=2000)


class FeedbackResponse(BaseModel):
    feedback_id: str
    status: str = "recorded"


class AgentStatsResponse(BaseModel):
    agent_id: str
    tasks_completed: int = 0
    avg_score: float = 0.0
    revision_rate: float = 0.0
    total_feedback: int = 0
    total_revisions: int = 0
    recent_trend: list[int] = Field(default_factory=list)
    recommendation: str = "continue"
    degradation_detected: bool = False


class QualityStatsResponse(BaseModel):
    total_checks: int = 0
    total_passed: int = 0
    total_failed: int = 0
    tasks_tracked: int = 0


# ---------------------------------------------------------------------------
# GET /quality/{task_id}
# ---------------------------------------------------------------------------


@router.get(
    "/quality/stats",
    response_model=QualityStatsResponse,
    dependencies=[Depends(PermissionChecker("brain", "read"))],
)
async def get_quality_stats() -> QualityStatsResponse:
    """Get global quality gate statistics.

    NOTE: This route MUST be declared before ``/quality/{task_id}`` to
    prevent FastAPI from matching ``stats`` as a task_id path param.
    """
    gate = get_quality_gate()
    stats = gate.get_stats()
    return QualityStatsResponse(**stats)


@router.get(
    "/quality/{task_id}",
    response_model=QualityResultResponse,
    dependencies=[Depends(PermissionChecker("brain", "read"))],
)
async def get_quality_checks(task_id: str) -> QualityResultResponse:
    """Get quality check results for a specific task."""
    gate = get_quality_gate()
    checks = gate.get_checks(task_id)

    if not checks:
        raise HTTPException(
            status_code=404,
            detail=f"No quality checks found for task '{task_id}'",
        )

    passed = sum(1 for c in checks if c.status == "passed")
    failed = sum(1 for c in checks if c.status == "failed")

    return QualityResultResponse(
        task_id=task_id,
        checks=[
            QualityCheckResponse(
                check_id=c.check_id,
                agent_id=c.agent_id,
                task_id=c.task_id,
                check_type=c.check_type,
                status=c.status,
                score=c.score,
                feedback=c.feedback,
                reviewer=c.reviewer,
                timestamp=c.timestamp.isoformat(),
            )
            for c in checks
        ],
        total=len(checks),
        passed=passed,
        failed=failed,
    )


# ---------------------------------------------------------------------------
# POST /feedback
# ---------------------------------------------------------------------------


@router.post(
    "/feedback",
    response_model=FeedbackResponse,
    dependencies=[Depends(PermissionChecker("brain", "dispatch"))],
)
async def submit_feedback(body: FeedbackRequest) -> FeedbackResponse:
    """Submit Henry's feedback on a completed task."""
    loop = get_feedback_loop()

    fb = await loop.record_feedback(
        task_id=body.task_id,
        agent_id=body.agent_id,
        rating=body.rating,
        comment=body.comment,
        source="human",
    )

    logger.info(
        "Feedback recorded: task=%s agent=%s rating=%d",
        body.task_id,
        body.agent_id,
        body.rating,
    )

    return FeedbackResponse(feedback_id=fb.feedback_id)


# ---------------------------------------------------------------------------
# GET /agents/{agent_id}/stats
# ---------------------------------------------------------------------------


@router.get(
    "/agents/{agent_id}/stats",
    response_model=AgentStatsResponse,
    dependencies=[Depends(PermissionChecker("brain", "read"))],
)
async def get_agent_stats(agent_id: str) -> AgentStatsResponse:
    """Get agent performance statistics."""
    loop = get_feedback_loop()
    stats = await loop.get_agent_stats(agent_id)
    recommendation = await loop.recommend_action(agent_id)
    degradation = await loop.detect_degradation(agent_id)

    return AgentStatsResponse(
        agent_id=agent_id,
        tasks_completed=stats["tasks_completed"],
        avg_score=stats["avg_score"],
        revision_rate=stats["revision_rate"],
        total_feedback=stats["total_feedback"],
        total_revisions=stats["total_revisions"],
        recent_trend=stats["recent_trend"],
        recommendation=recommendation,
        degradation_detected=degradation,
    )


# (Removed duplicate /quality/stats — moved above /quality/{task_id} to fix route shadowing)
