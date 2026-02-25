"""Onboarding wizard API endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from api.rbac import PermissionChecker
from api.deps import AppState, get_state
from api.models import (
    OnboardingStatusResponse,
    OnboardingStartResponse,
)

router = APIRouter(tags=["onboarding"])

WIZARD_STEPS = [
    "llm_health",
    "mcp_install",
    "skills_install",
    "tool_policies",
    "session_scope",
    "verification",
]


@router.get(
    "/onboarding/status",
    response_model=OnboardingStatusResponse,
    dependencies=[Depends(PermissionChecker("onboarding", "read"))],
)
async def get_onboarding_status(
    state: AppState = Depends(get_state),
) -> OnboardingStatusResponse:
    """Return current onboarding wizard state."""
    settings = state.settings
    token_present = settings.has_anthropic or settings.has_openai

    # Check DB for progress
    if state.onboarding_store:
        # Use a default user_id for single-user mode
        row = await state.onboarding_store.get("default")
        if row:
            return OnboardingStatusResponse(
                token_present=token_present,
                wizard_state=row.state,
                current_step=row.current_step,
                completed_steps=row.completed_steps or [],
                total_steps=len(WIZARD_STEPS),
                run_id=row.run_id,
            )

    # No progress record — determine initial state
    wizard_state = "token_present" if token_present else "token_missing"
    return OnboardingStatusResponse(
        token_present=token_present,
        wizard_state=wizard_state,
        current_step=0,
        completed_steps=[],
        total_steps=len(WIZARD_STEPS),
        run_id="",
    )


@router.post(
    "/onboarding/start",
    response_model=OnboardingStartResponse,
    dependencies=[Depends(PermissionChecker("onboarding", "start"))],
)
async def start_onboarding(
    state: AppState = Depends(get_state),
) -> OnboardingStartResponse:
    """Start or restart the onboarding wizard."""
    settings = state.settings
    token_present = settings.has_anthropic or settings.has_openai

    if not token_present:
        raise HTTPException(
            status_code=400,
            detail="LLM token required before starting the wizard. "
            "Set OCCP_ANTHROPIC_API_KEY or OCCP_OPENAI_API_KEY.",
        )

    run_id = uuid.uuid4().hex[:16]

    if state.onboarding_store:
        await state.onboarding_store.upsert(
            "default",
            state="running",
            current_step=0,
            completed_steps=[],
            run_id=run_id,
        )

    return OnboardingStartResponse(
        run_id=run_id,
        wizard_state="running",
        current_step=0,
        steps=WIZARD_STEPS,
    )


@router.post(
    "/onboarding/step/{step_name}",
    dependencies=[Depends(PermissionChecker("onboarding", "start"))],
)
async def complete_step(
    step_name: str,
    state: AppState = Depends(get_state),
) -> dict:
    """Mark a wizard step as complete."""
    if step_name not in WIZARD_STEPS:
        raise HTTPException(status_code=400, detail=f"Unknown step: {step_name}")

    step_idx = WIZARD_STEPS.index(step_name)

    if state.onboarding_store:
        row = await state.onboarding_store.get("default")
        if row is None:
            raise HTTPException(status_code=400, detail="Wizard not started")

        completed = list(row.completed_steps or [])
        if step_name not in completed:
            completed.append(step_name)

        next_step = step_idx + 1
        new_state = "done" if next_step >= len(WIZARD_STEPS) else "running"

        await state.onboarding_store.upsert(
            "default",
            state=new_state,
            current_step=next_step,
            completed_steps=completed,
        )

        return {
            "step": step_name,
            "completed": True,
            "wizard_state": new_state,
            "next_step": WIZARD_STEPS[next_step] if next_step < len(WIZARD_STEPS) else None,
        }

    return {"step": step_name, "completed": True, "wizard_state": "running"}
