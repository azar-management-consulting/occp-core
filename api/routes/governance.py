"""Governance API routes (L6 completion).

Exposes the self-modifier runtime validator and proposal generator as
read-only endpoints. These are the operator-facing views of OCCP's
governance layer.

Endpoints:
    POST /governance/check           - Validate a file path against boundaries
    POST /governance/check_many      - Validate multiple paths
    GET  /governance/stats           - Self-modifier statistics
    GET  /governance/recent          - Recent verdict history
    GET  /governance/boundaries      - Current boundary rules
    GET  /governance/proposals       - Ranked proposal candidates
    GET  /governance/issues          - Issue registry contents
"""

from __future__ import annotations

import logging
import pathlib
from typing import Any

import yaml
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth import get_current_user_payload
from api.rbac import PermissionChecker
from evaluation import (
    KillSwitchTrigger,
    get_canary_engine,
    get_drift_detector,
    get_flag_store,
    get_kill_switch,
    get_proposal_generator,
    get_self_modifier,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["governance"])

_ARCHITECTURE_DIR = pathlib.Path(__file__).parent.parent.parent / "architecture"


# ── Request models ────────────────────────────────────────────

class GovernanceCheckRequest(BaseModel):
    path: str = Field(..., min_length=1, max_length=500)


class GovernanceCheckManyRequest(BaseModel):
    paths: list[str] = Field(..., min_length=1, max_length=100)


class KillSwitchActivateRequest(BaseModel):
    trigger: str = Field(..., min_length=1, max_length=32)
    reason: str = Field(..., min_length=1, max_length=500)
    evidence: dict[str, Any] = Field(default_factory=dict)


class KillSwitchDrillRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)


class KillSwitchDeactivateRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)


class FeatureFlagUpdateRequest(BaseModel):
    key: str = Field(..., min_length=1, max_length=128)
    enabled: bool
    description: str | None = Field(default=None, max_length=500)
    rollout_percent: int | None = Field(default=None, ge=0, le=100)


# ── Routes ────────────────────────────────────────────────────

@router.post("/governance/check")
async def check_path(
    body: GovernanceCheckRequest,
    current_user: dict = Depends(get_current_user_payload),
) -> dict[str, Any]:
    """Validate a single path against boundaries.yaml."""
    modifier = get_self_modifier()
    verdict = modifier.check(body.path)
    return verdict.to_dict()


@router.post("/governance/check_many")
async def check_many_paths(
    body: GovernanceCheckManyRequest,
    current_user: dict = Depends(get_current_user_payload),
) -> dict[str, Any]:
    """Validate multiple paths in one call."""
    modifier = get_self_modifier()
    verdicts = modifier.check_many(body.paths)
    return {
        "all_allowed": all(v.allowed for v in verdicts.values()),
        "verdicts": {p: v.to_dict() for p, v in verdicts.items()},
    }


@router.get("/governance/stats")
async def get_governance_stats(
    current_user: dict = Depends(get_current_user_payload),
) -> dict[str, Any]:
    """Return self-modifier statistics."""
    modifier = get_self_modifier()
    return {
        "stats": modifier.stats,
        "immutable_paths_count": len(modifier.list_immutable_globs()),
        "autonomous_safe_count": len(modifier.list_autonomous_safe_globs()),
        "human_review_count": len(modifier.list_human_review_globs()),
    }


@router.get("/governance/recent")
async def get_recent_verdicts(
    current_user: dict = Depends(get_current_user_payload),
) -> dict[str, Any]:
    """Last 50 verdicts made by the self-modifier."""
    modifier = get_self_modifier()
    return {
        "count": len(modifier.recent_verdicts),
        "verdicts": [v.to_dict() for v in modifier.recent_verdicts],
    }


@router.get("/governance/boundaries")
async def get_boundaries(
    current_user: dict = Depends(get_current_user_payload),
) -> dict[str, Any]:
    """Return current boundary rules (read-only)."""
    path = _ARCHITECTURE_DIR / "boundaries.yaml"
    if not path.exists():
        raise HTTPException(status_code=404, detail="boundaries.yaml not found")
    with path.open() as f:
        data = yaml.safe_load(f) or {}
    return {
        "immutable_count": len(data.get("immutable", [])),
        "human_review_count": len(data.get("human_review_required", [])),
        "autonomous_safe_count": len(data.get("autonomous_safe", [])),
        "rules": data,
    }


@router.get("/governance/proposals")
async def get_proposals(
    current_user: dict = Depends(get_current_user_payload),
    include_anomalies: bool = True,
    include_resolved: bool = False,
) -> dict[str, Any]:
    """Return ranked proposal candidates (read-only)."""
    gen = get_proposal_generator()
    candidates = gen.generate(
        include_anomalies=include_anomalies,
        include_resolved=include_resolved,
    )
    return {
        "count": len(candidates),
        "top_score": candidates[0].score if candidates else 0.0,
        "candidates": [c.to_dict() for c in candidates],
    }


@router.get("/governance/issues")
async def get_issues(
    current_user: dict = Depends(get_current_user_payload),
) -> dict[str, Any]:
    """Return the architectural issue registry."""
    path = _ARCHITECTURE_DIR / "issue_registry.yaml"
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail="issue_registry.yaml not found",
        )
    with path.open() as f:
        data = yaml.safe_load(f) or {}

    issues = data.get("issues", [])
    by_status: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    for issue in issues:
        by_status[issue.get("status", "?")] = by_status.get(issue.get("status", "?"), 0) + 1
        by_severity[issue.get("severity", "?")] = by_severity.get(issue.get("severity", "?"), 0) + 1

    return {
        "total": len(issues),
        "by_status": by_status,
        "by_severity": by_severity,
        "issues": issues,
    }


# ── Kill switch (maximum-state hard-stop) ────────────────────

@router.get("/governance/kill_switch/status")
async def kill_switch_status(
    current_user: dict = Depends(get_current_user_payload),
) -> dict[str, Any]:
    """Return current kill switch state and recent history."""
    return get_kill_switch().status()


@router.get("/governance/kill_switch/stats")
async def kill_switch_stats(
    current_user: dict = Depends(get_current_user_payload),
) -> dict[str, Any]:
    return get_kill_switch().stats()


@router.post(
    "/governance/kill_switch/activate",
    dependencies=[Depends(PermissionChecker("governance", "manage"))],
)
async def kill_switch_activate(
    body: KillSwitchActivateRequest,
    current_user: dict = Depends(get_current_user_payload),
) -> dict[str, Any]:
    """Hard-stop: refuse all autonomous actions until deactivated.

    Admin-only. Requires explicit trigger and reason for audit.
    """
    try:
        trigger = KillSwitchTrigger(body.trigger)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=(
                f"invalid trigger: {body.trigger}. "
                f"Allowed: {[t.value for t in KillSwitchTrigger]}"
            ),
        )

    actor = current_user.get("sub", "admin")
    record = get_kill_switch().activate(
        trigger=trigger,
        actor=actor,
        reason=body.reason,
        evidence=body.evidence,
    )
    return {
        "status": "activated",
        "record": record.to_dict(),
    }


@router.post(
    "/governance/kill_switch/drill",
    dependencies=[Depends(PermissionChecker("governance", "manage"))],
)
async def kill_switch_drill(
    body: KillSwitchDrillRequest,
    current_user: dict = Depends(get_current_user_payload),
) -> dict[str, Any]:
    """Simulate kill switch activation. Logs but does not block operations."""
    actor = current_user.get("sub", "admin")
    record = get_kill_switch().drill(actor=actor, reason=body.reason)
    return {
        "status": "drill",
        "record": record.to_dict(),
    }


@router.post(
    "/governance/kill_switch/deactivate",
    dependencies=[Depends(PermissionChecker("governance", "manage"))],
)
async def kill_switch_deactivate(
    body: KillSwitchDeactivateRequest,
    current_user: dict = Depends(get_current_user_payload),
) -> dict[str, Any]:
    """Clear the kill switch. Requires explicit reason for audit."""
    actor = current_user.get("sub", "admin")
    record = get_kill_switch().deactivate(actor=actor, reason=body.reason)
    return {
        "status": "deactivated",
        "previous": record.to_dict() if record else None,
    }


# ── Canary verdict history ───────────────────────────────────

@router.get("/governance/canary/recent")
async def canary_recent(
    current_user: dict = Depends(get_current_user_payload),
) -> dict[str, Any]:
    """Return recent canary verdicts."""
    engine = get_canary_engine()
    return {
        "stats": engine.stats,
        "recent": [v.to_dict() for v in engine.recent_verdicts],
    }


# ── Drift detector ───────────────────────────────────────────

@router.get("/governance/drift")
async def governance_drift(
    current_user: dict = Depends(get_current_user_payload),
) -> dict[str, Any]:
    """Return architecture-vs-code drift report."""
    return get_drift_detector().detect().to_dict()


# ── Feature flags ────────────────────────────────────────────

@router.get("/governance/flags")
async def list_flags(
    current_user: dict = Depends(get_current_user_payload),
) -> dict[str, Any]:
    """List all feature flags."""
    flags = get_flag_store().list_all()
    return {
        "total": len(flags),
        "flags": [f.to_dict() for f in flags],
    }


@router.put(
    "/governance/flags",
    dependencies=[Depends(PermissionChecker("governance", "manage"))],
)
async def update_flag(
    body: FeatureFlagUpdateRequest,
    current_user: dict = Depends(get_current_user_payload),
) -> dict[str, Any]:
    """Set or update a feature flag. Persists to disk."""
    store = get_flag_store()
    flag = store.set(
        key=body.key,
        enabled=body.enabled,
        description=body.description,
        rollout_percent=body.rollout_percent,
    )
    return {"status": "updated", "flag": flag.to_dict()}
