"""Auto-dev API routes — SAFE self-improvement pipeline.

Endpoints:
    POST /autodev/propose          - submit a proposal (title + rationale + diff)
    POST /autodev/run/{run_id}     - execute build + verify (synchronous)
    POST /autodev/run/{run_id}/approve  - approve (HITL)
    POST /autodev/run/{run_id}/reject   - reject (HITL)
    POST /autodev/run/{run_id}/merge    - finalize (branch kept for human PR)
    POST /autodev/run/{run_id}/cancel   - cancel + cleanup
    GET  /autodev/runs             - list all runs
    GET  /autodev/runs/{run_id}    - run detail
    GET  /autodev/budget           - current budget state
    GET  /autodev/approvals        - pending approval queue
    GET  /autodev/stats            - overall stats
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth import get_current_user_payload
from api.rbac import PermissionChecker
from autodev import (
    BudgetExhausted,
    get_approval_queue,
    get_orchestrator,
    get_rate_budget_tracker,
    get_sandbox_worktree,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["autodev"])


# ── Request models ────────────────────────────────────────────

class ProposeRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    rationale: str = Field(..., min_length=10, max_length=4000)
    proposed_diff: str = Field(..., min_length=1, max_length=100_000)


class ApprovalDecisionRequest(BaseModel):
    actor: str = Field(..., min_length=1, max_length=64)
    reason: str = Field(default="", max_length=500)


class CancelRequest(BaseModel):
    reason: str = Field(default="manual", max_length=200)


# ── Endpoints ─────────────────────────────────────────────────

@router.post(
    "/autodev/propose",
    dependencies=[Depends(PermissionChecker("governance", "manage"))],
)
async def propose(
    body: ProposeRequest,
    current_user: dict = Depends(get_current_user_payload),
) -> dict[str, Any]:
    """Submit a new auto-dev proposal. Admin only."""
    try:
        run = get_orchestrator().propose(
            title=body.title,
            rationale=body.rationale,
            proposed_diff=body.proposed_diff,
        )
    except BudgetExhausted as exc:
        raise HTTPException(status_code=429, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"propose failed: {exc}")
    return {"status": "proposed", "run": run.to_dict()}


@router.post(
    "/autodev/run/{run_id}/execute",
    dependencies=[Depends(PermissionChecker("governance", "manage"))],
)
async def execute(
    run_id: str,
    current_user: dict = Depends(get_current_user_payload),
) -> dict[str, Any]:
    """Run BUILD + VERIFY stages synchronously.

    State transitions: PROPOSED → BUILDING → VERIFYING → AWAITING_APPROVAL
    (or REJECTED / FAILED).
    """
    orch = get_orchestrator()
    if orch.get(run_id) is None:
        raise HTTPException(status_code=404, detail=f"run {run_id} not found")
    try:
        run = orch.execute_build_and_verify(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"execute failed: {exc}")
    return {"status": run.state.value, "run": run.to_dict()}


@router.post(
    "/autodev/run/{run_id}/approve",
    dependencies=[Depends(PermissionChecker("governance", "manage"))],
)
async def approve(
    run_id: str,
    body: ApprovalDecisionRequest,
    current_user: dict = Depends(get_current_user_payload),
) -> dict[str, Any]:
    """Approve an AWAITING_APPROVAL run. Admin only."""
    orch = get_orchestrator()
    try:
        run = orch.resolve_approval(run_id, approved=True, actor=body.actor, reason=body.reason)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"status": run.state.value, "run": run.to_dict()}


@router.post(
    "/autodev/run/{run_id}/reject",
    dependencies=[Depends(PermissionChecker("governance", "manage"))],
)
async def reject(
    run_id: str,
    body: ApprovalDecisionRequest,
    current_user: dict = Depends(get_current_user_payload),
) -> dict[str, Any]:
    orch = get_orchestrator()
    try:
        run = orch.resolve_approval(run_id, approved=False, actor=body.actor, reason=body.reason)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"status": run.state.value, "run": run.to_dict()}


@router.post(
    "/autodev/run/{run_id}/merge",
    dependencies=[Depends(PermissionChecker("governance", "manage"))],
)
async def merge(
    run_id: str,
    current_user: dict = Depends(get_current_user_payload),
) -> dict[str, Any]:
    """Finalize an APPROVED run. Branch is kept for human PR creation.

    OCCP preservation contract: the orchestrator NEVER pushes to main.
    It only prepares the branch. Human creates the PR + merges manually.
    """
    orch = get_orchestrator()
    try:
        run = orch.finalize_merge(run_id)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"status": run.state.value, "run": run.to_dict()}


@router.post(
    "/autodev/run/{run_id}/cancel",
    dependencies=[Depends(PermissionChecker("governance", "manage"))],
)
async def cancel(
    run_id: str,
    body: CancelRequest,
    current_user: dict = Depends(get_current_user_payload),
) -> dict[str, Any]:
    orch = get_orchestrator()
    try:
        run = orch.cancel(run_id, reason=body.reason)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"status": run.state.value, "run": run.to_dict()}


# ── Read-only endpoints ───────────────────────────────────────

@router.get("/autodev/runs")
async def list_runs(
    current_user: dict = Depends(get_current_user_payload),
) -> dict[str, Any]:
    runs = get_orchestrator().list_all()
    return {
        "count": len(runs),
        "runs": [r.to_dict() for r in runs],
    }


@router.get("/autodev/runs/{run_id}")
async def get_run(
    run_id: str,
    current_user: dict = Depends(get_current_user_payload),
) -> dict[str, Any]:
    run = get_orchestrator().get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"run {run_id} not found")
    return run.to_dict()


@router.get("/autodev/budget")
async def budget(
    current_user: dict = Depends(get_current_user_payload),
) -> dict[str, Any]:
    return get_rate_budget_tracker().snapshot()


@router.get("/autodev/approvals")
async def approvals(
    current_user: dict = Depends(get_current_user_payload),
) -> dict[str, Any]:
    q = get_approval_queue()
    pending = q.list_pending()
    return {
        "pending_count": len(pending),
        "pending": [r.to_dict() for r in pending],
        "stats": q.stats,
    }


@router.get("/autodev/stats")
async def stats(
    current_user: dict = Depends(get_current_user_payload),
) -> dict[str, Any]:
    runs = get_orchestrator().list_all()
    by_state: dict[str, int] = {}
    for r in runs:
        by_state[r.state.value] = by_state.get(r.state.value, 0) + 1
    return {
        "total_runs": len(runs),
        "by_state": by_state,
        "sandbox": get_sandbox_worktree().stats,
        "budget": get_rate_budget_tracker().snapshot(),
        "approvals": get_approval_queue().stats,
    }
