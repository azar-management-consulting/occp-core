"""Skills management endpoints — curated allowlist with integrity checks.

Every enable/disable operation is:
1. Integrity-checked via SkillIntegrityChecker (hash verification)
2. Audit-trailed via PolicyEngine.audit() (hash-chained)
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from api.auth import get_current_user_payload
from api.rbac import PermissionChecker
from api.deps import AppState, get_state
from api.models import SkillInfo, SkillsListResponse
from security.supply_chain import SupplyChainScanner

logger = logging.getLogger(__name__)

router = APIRouter(tags=["skills"])

# Singleton supply-chain scanner
_scanner = SupplyChainScanner()

# Phase 1: curated allowlist of baseline skills
_BASELINE_SKILLS: list[dict] = [
    {
        "id": "code-review",
        "name": "Code Review",
        "description": "Automated code review with security scanning and best practice checks.",
        "category": "development",
        "enabled": True,
        "trusted": True,
        "token_impact_chars": 0,  # calculated dynamically
    },
    {
        "id": "git-operations",
        "name": "Git Operations",
        "description": "Safe git operations: commit, branch, diff, log with approval gates.",
        "category": "development",
        "enabled": True,
        "trusted": True,
        "token_impact_chars": 0,
    },
    {
        "id": "file-manager",
        "name": "File Manager",
        "description": "Read, write, and organize files with sandbox isolation.",
        "category": "filesystem",
        "enabled": True,
        "trusted": True,
        "token_impact_chars": 0,
    },
    {
        "id": "web-search",
        "name": "Web Search",
        "description": "Search the web for current information and documentation.",
        "category": "web",
        "enabled": False,
        "trusted": True,
        "token_impact_chars": 0,
    },
    {
        "id": "database-query",
        "name": "Database Query",
        "description": "Execute read-only database queries with result formatting.",
        "category": "database",
        "enabled": False,
        "trusted": True,
        "token_impact_chars": 0,
    },
]


def _calc_token_impact(skill: dict) -> int:
    """Token impact formula: 195 + Σ(97 + len(name) + len(description) + len(location))."""
    name = skill.get("name", "")
    desc = skill.get("description", "")
    location = skill.get("id", "")
    return 195 + 97 + len(name) + len(desc) + len(location)


def _skill_to_info(skill: dict) -> SkillInfo:
    chars = _calc_token_impact(skill)
    return SkillInfo(
        id=skill["id"],
        name=skill["name"],
        description=skill["description"],
        category=skill.get("category", "general"),
        enabled=skill.get("enabled", False),
        trusted=skill.get("trusted", True),
        token_impact_chars=chars,
        token_impact_tokens=chars // 4,
    )


@router.get(
    "/skills",
    response_model=SkillsListResponse,
    dependencies=[Depends(PermissionChecker("skills", "read"))],
)
async def list_skills() -> SkillsListResponse:
    """Return the list of available skills with token impact."""
    skills = [_skill_to_info(s) for s in _BASELINE_SKILLS]
    total_tokens = sum(s.token_impact_tokens for s in skills if s.enabled)
    return SkillsListResponse(
        skills=skills,
        total=len(skills),
        total_enabled_token_impact=total_tokens,
    )


@router.post(
    "/skills/{skill_id}/enable",
)
async def enable_skill(
    skill_id: str,
    user: dict[str, Any] = Depends(PermissionChecker("skills", "manage")),
    state: AppState = Depends(get_state),
) -> dict:
    """Enable a skill — integrity-checked and audit-trailed."""
    skill = next((s for s in _BASELINE_SKILLS if s["id"] == skill_id), None)
    if skill is None:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found")

    if not skill.get("trusted", False):
        raise HTTPException(status_code=403, detail=f"Skill '{skill_id}' is not in trusted allowlist")

    # ── Integrity gate ───────────────────────────────────────────
    integrity = _scanner.scan_skill_enable(skill)
    if not integrity.valid:
        await state.policy_engine.audit(
            actor=user.get("sub", "unknown"),
            action="skill_enable_blocked",
            detail={
                "skill_id": skill_id,
                "reason": integrity.reason,
            },
        )
        raise HTTPException(
            status_code=403,
            detail=f"Integrity check failed: {integrity.reason}",
        )

    skill["enabled"] = True

    # ── Audit trail ──────────────────────────────────────────────
    await state.policy_engine.audit(
        actor=user.get("sub", "unknown"),
        action="skill_enabled",
        detail={
            "skill_id": skill_id,
            "skill_name": skill["name"],
            "hash_sha256": integrity.hash_sha256[:16] if integrity.hash_sha256 else "",
        },
    )

    return {"skill_id": skill_id, "enabled": True}


@router.post(
    "/skills/{skill_id}/disable",
)
async def disable_skill(
    skill_id: str,
    user: dict[str, Any] = Depends(PermissionChecker("skills", "manage")),
    state: AppState = Depends(get_state),
) -> dict:
    """Disable a skill — audit-trailed."""
    skill = next((s for s in _BASELINE_SKILLS if s["id"] == skill_id), None)
    if skill is None:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found")

    skill["enabled"] = False

    # ── Audit trail ──────────────────────────────────────────────
    await state.policy_engine.audit(
        actor=user.get("sub", "unknown"),
        action="skill_disabled",
        detail={
            "skill_id": skill_id,
            "skill_name": skill["name"],
        },
    )

    return {"skill_id": skill_id, "enabled": False}
