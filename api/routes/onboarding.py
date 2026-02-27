"""Onboarding wizard API — 10-step enterprise flow with per-user binding.

Steps 0–9:
  0. landing_cta     — Visitor clicks CTA → redirected to auth
  1. auth_check      — JWT authenticated, user bound
  2. llm_token       — Encrypted LLM key stored via TokenStore
  3. agent_init      — Agent configs verified, pipeline validated
  4. skills_config   — Skill allowlist configured, token budget checked
  5. gsd_init        — GSD runtime initialized (future: workspace scaffold)
  6. mcp_config      — MCP connectors selected and configured
  7. policy_config   — Session policy + tool governance configured
  8. verification    — Full-stack verification (DB, LLM, pipeline, audit)
  9. first_task      — Demo task launched through verified pipeline
"""

from __future__ import annotations

import uuid
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from api.auth import get_current_user_payload
from api.rbac import PermissionChecker
from api.deps import AppState, get_state

logger = logging.getLogger(__name__)

router = APIRouter(tags=["onboarding"])

# 10-step wizard definition
WIZARD_STEPS = [
    "landing_cta",
    "auth_check",
    "llm_token",
    "agent_init",
    "skills_config",
    "gsd_init",
    "mcp_config",
    "policy_config",
    "verification",
    "first_task",
]

STEP_DESCRIPTIONS = {
    "landing_cta": "Landing page CTA — visitor engagement",
    "auth_check": "Authentication verified — JWT bound",
    "llm_token": "LLM API token encrypted and stored",
    "agent_init": "Agent configs loaded, pipeline validated",
    "skills_config": "Skill allowlist configured",
    "gsd_init": "GSD runtime initialized",
    "mcp_config": "MCP connectors configured",
    "policy_config": "Session & tool policies set",
    "verification": "Full-stack verification passed",
    "first_task": "First autonomous task completed",
}


@router.get(
    "/onboarding/status",
    dependencies=[Depends(PermissionChecker("onboarding", "read"))],
)
async def get_onboarding_status(
    payload: dict[str, Any] = Depends(get_current_user_payload),
    state: AppState = Depends(get_state),
) -> dict:
    """Return current onboarding wizard state for the authenticated user."""
    user_id = payload["sub"]

    # Check if user has stored tokens
    has_token = False
    if state.token_store:
        has_token = await state.token_store.has_active_token(user_id)

    # Fallback: env-var tokens (legacy/bootstrap)
    if not has_token:
        has_token = state.settings.has_anthropic or state.settings.has_openai

    # Check DB for progress
    if state.onboarding_store:
        row = await state.onboarding_store.get(user_id)
        if row:
            return {
                "user_id": user_id,
                "token_present": has_token,
                "wizard_state": row.state,
                "current_step": row.current_step,
                "current_step_name": WIZARD_STEPS[row.current_step] if row.current_step < len(WIZARD_STEPS) else "done",
                "completed_steps": row.completed_steps or [],
                "total_steps": len(WIZARD_STEPS),
                "steps": WIZARD_STEPS,
                "step_descriptions": STEP_DESCRIPTIONS,
                "run_id": row.run_id,
                "metadata": row.metadata_ or {},
            }

    # No progress record — determine initial state
    wizard_state = "landing" if not has_token else "token_present"
    return {
        "user_id": user_id,
        "token_present": has_token,
        "wizard_state": wizard_state,
        "current_step": 0,
        "current_step_name": "landing_cta",
        "completed_steps": [],
        "total_steps": len(WIZARD_STEPS),
        "steps": WIZARD_STEPS,
        "step_descriptions": STEP_DESCRIPTIONS,
        "run_id": "",
        "metadata": {},
    }


@router.post(
    "/onboarding/start",
    dependencies=[Depends(PermissionChecker("onboarding", "start"))],
)
async def start_onboarding(
    payload: dict[str, Any] = Depends(get_current_user_payload),
    state: AppState = Depends(get_state),
) -> dict:
    """Start or restart the onboarding wizard for the authenticated user.

    Step 0 (landing_cta) and Step 1 (auth_check) are auto-completed
    since the user is already authenticated.
    """
    user_id = payload["sub"]
    run_id = uuid.uuid4().hex[:16]

    # Auto-complete steps 0 and 1 (CTA + auth already happened)
    auto_completed = ["landing_cta", "auth_check"]
    initial_step = 2  # Start at llm_token

    if state.onboarding_store:
        await state.onboarding_store.upsert(
            user_id,
            state="running",
            current_step=initial_step,
            completed_steps=auto_completed,
            run_id=run_id,
        )

    # Audit: onboarding started
    if state.policy_engine and state.audit_store:
        await state.policy_engine.audit(
            actor=user_id,
            action="onboarding.start",
            detail={"run_id": run_id, "auto_completed": auto_completed},
            audit_store=state.audit_store,
        )

    logger.info("Onboarding started for user=%s run_id=%s", user_id, run_id)

    return {
        "run_id": run_id,
        "wizard_state": "running",
        "current_step": initial_step,
        "current_step_name": WIZARD_STEPS[initial_step],
        "completed_steps": auto_completed,
        "steps": WIZARD_STEPS,
    }


@router.post(
    "/onboarding/step/{step_name}",
    dependencies=[Depends(PermissionChecker("onboarding", "start"))],
)
async def complete_step(
    step_name: str,
    payload: dict[str, Any] = Depends(get_current_user_payload),
    state: AppState = Depends(get_state),
) -> dict:
    """Mark a wizard step as complete for the authenticated user.

    Validates step prerequisites before marking complete.
    """
    if step_name not in WIZARD_STEPS:
        raise HTTPException(status_code=400, detail=f"Unknown step: {step_name}")

    user_id = payload["sub"]
    step_idx = WIZARD_STEPS.index(step_name)

    # Validate step-specific prerequisites
    await _validate_step_prereqs(step_name, user_id, state)

    if state.onboarding_store:
        row = await state.onboarding_store.get(user_id)
        if row is None:
            raise HTTPException(status_code=400, detail="Wizard not started — call POST /onboarding/start first")

        completed = list(row.completed_steps or [])
        if step_name not in completed:
            completed.append(step_name)

        next_step = step_idx + 1
        new_state = "done" if next_step >= len(WIZARD_STEPS) else "running"

        await state.onboarding_store.upsert(
            user_id,
            state=new_state,
            current_step=next_step,
            completed_steps=completed,
        )

        # Audit: step completed
        if state.policy_engine and state.audit_store:
            await state.policy_engine.audit(
                actor=user_id,
                action="onboarding.step_complete",
                detail={
                    "step": step_name,
                    "step_index": step_idx,
                    "wizard_state": new_state,
                    "run_id": row.run_id,
                },
                audit_store=state.audit_store,
            )

        return {
            "step": step_name,
            "step_index": step_idx,
            "completed": True,
            "wizard_state": new_state,
            "next_step": WIZARD_STEPS[next_step] if next_step < len(WIZARD_STEPS) else None,
            "completed_steps": completed,
            "progress_pct": int(len(completed) / len(WIZARD_STEPS) * 100),
        }

    return {"step": step_name, "completed": True, "wizard_state": "running"}


@router.post(
    "/onboarding/verify",
    dependencies=[Depends(PermissionChecker("onboarding", "start"))],
)
async def run_verification(
    payload: dict[str, Any] = Depends(get_current_user_payload),
    state: AppState = Depends(get_state),
) -> dict:
    """Step 8 — Run full-stack verification checks.

    Validates: DB connectivity, LLM provider health, pipeline readiness,
    audit chain integrity, and encryption subsystem.
    """
    user_id = payload["sub"]
    checks: list[dict] = []

    # 1. Database
    db_ok = state.db is not None
    checks.append({"name": "database", "passed": db_ok, "detail": "Connected" if db_ok else "Not connected"})

    # 2. LLM provider
    has_token = False
    if state.token_store:
        has_token = await state.token_store.has_active_token(user_id)
    if not has_token:
        has_token = state.settings.has_anthropic or state.settings.has_openai
    checks.append({"name": "llm_token", "passed": has_token, "detail": "Token available" if has_token else "No token"})

    # 3. Pipeline
    pipeline_ok = state.pipeline is not None
    checks.append({"name": "pipeline", "passed": pipeline_ok, "detail": "Ready" if pipeline_ok else "Not initialized"})

    # 4. Audit chain
    chain_ok = True
    if state.policy_engine:
        chain_ok = state.policy_engine.verify_audit_chain()
    checks.append({"name": "audit_chain", "passed": chain_ok, "detail": "Intact" if chain_ok else "Broken"})

    # 5. Encryption
    enc_ok = state.token_encryptor is not None
    checks.append({"name": "encryption", "passed": enc_ok, "detail": "Active" if enc_ok else "Not initialized"})

    # 6. Agent configs
    agent_count = await state.agent_count()
    agents_ok = agent_count > 0
    checks.append({"name": "agents", "passed": agents_ok, "detail": f"{agent_count} registered"})

    all_passed = all(c["passed"] for c in checks)

    # Audit verification result
    if state.policy_engine and state.audit_store:
        await state.policy_engine.audit(
            actor=user_id,
            action="onboarding.verification",
            detail={"all_passed": all_passed, "checks": checks},
            audit_store=state.audit_store,
        )

    return {
        "all_passed": all_passed,
        "checks": checks,
        "total_checks": len(checks),
        "passed_count": sum(1 for c in checks if c["passed"]),
    }


@router.post(
    "/onboarding/first-task",
    dependencies=[Depends(PermissionChecker("onboarding", "start"))],
)
async def launch_first_task(
    payload: dict[str, Any] = Depends(get_current_user_payload),
    state: AppState = Depends(get_state),
) -> dict:
    """Step 9 — Launch a demo task through the verified autonomy pipeline.

    Creates a lightweight task to prove end-to-end pipeline functionality:
    Plan → Gate → Execute → Validate → Ship.
    """
    from orchestrator.models import Task

    user_id = payload["sub"]

    task = Task(
        name="Onboarding Verification Task",
        description="Automated first-task: verify the full pipeline (plan → gate → execute → validate → ship).",
        agent_type="demo",
        risk_level="low",
        metadata={"source": "onboarding", "user_id": user_id},
    )

    await state.add_task(task)

    # Run through pipeline if available
    result_data: dict[str, Any] = {"task_id": task.id, "status": "created"}

    if state.pipeline:
        try:
            result = await state.pipeline.run(task)
            task.status = "completed" if result.success else "failed"
            result_data = {
                "task_id": task.id,
                "success": result.success,
                "status": task.status,
                "evidence": result.evidence if hasattr(result, "evidence") else {},
            }
        except Exception as e:
            task.status = "failed"
            task.error = str(e)
            result_data = {"task_id": task.id, "success": False, "status": "failed", "error": str(e)}
    else:
        task.status = "completed"
        result_data = {"task_id": task.id, "success": True, "status": "completed", "note": "Pipeline not available — mock success"}

    await state.update_task(task)

    # Audit: first task
    if state.policy_engine and state.audit_store:
        await state.policy_engine.audit(
            actor=user_id,
            action="onboarding.first_task",
            task_id=task.id,
            detail=result_data,
            audit_store=state.audit_store,
        )

    return result_data


# ---------------------------------------------------------------------------
# Step prerequisite validation
# ---------------------------------------------------------------------------

async def _validate_step_prereqs(
    step_name: str, user_id: str, state: AppState
) -> None:
    """Validate that prerequisites for a step are met."""
    if step_name == "llm_token":
        # Token must be stored before marking this step complete
        has_token = False
        if state.token_store:
            has_token = await state.token_store.has_active_token(user_id)
        if not has_token:
            has_token = state.settings.has_anthropic or state.settings.has_openai
        if not has_token:
            raise HTTPException(
                status_code=400,
                detail="LLM token required. Store a token via POST /api/v1/tokens first.",
            )

    elif step_name == "agent_init":
        # At least one agent must be registered
        count = await state.agent_count()
        if count == 0:
            raise HTTPException(status_code=400, detail="No agent configs registered")

    elif step_name == "verification":
        # Previous steps must be completed
        if state.onboarding_store:
            row = await state.onboarding_store.get(user_id)
            if row:
                required = {"llm_token", "agent_init", "skills_config"}
                completed = set(row.completed_steps or [])
                missing = required - completed
                if missing:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Required steps not completed: {', '.join(sorted(missing))}",
                    )
