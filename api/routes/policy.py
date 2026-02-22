"""Policy evaluation endpoint – check content against guards."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from adapters.policy_gate import PolicyGate

from api.auth import get_current_user
from api.deps import AppState, get_state
from api.models import (
    GuardResultResponse,
    PolicyEvaluateRequest,
    PolicyEvaluateResponse,
)

router = APIRouter(tags=["policy"])


@router.post("/policy/evaluate", response_model=PolicyEvaluateResponse)
async def evaluate_policy(
    body: PolicyEvaluateRequest,
    _user: str = Depends(get_current_user),
    state: AppState = Depends(get_state),
) -> PolicyEvaluateResponse:
    gate = PolicyGate(engine=state.policy_engine)
    results = gate.check_content(body.content)

    all_passed = all(r["passed"] for r in results)

    return PolicyEvaluateResponse(
        approved=all_passed,
        results=[
            GuardResultResponse(
                guard=r["guard"],
                passed=r["passed"],
                detail=r["detail"],
            )
            for r in results
        ],
    )
