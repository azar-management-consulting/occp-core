"""Skills management endpoints — Phase 1 curated allowlist."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from api.rbac import PermissionChecker
from api.deps import AppState, get_state
from api.models import SkillInfo, SkillsListResponse

router = APIRouter(tags=["skills"])

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
    dependencies=[Depends(PermissionChecker("skills", "manage"))],
)
async def enable_skill(skill_id: str) -> dict:
    """Enable a skill by ID."""
    skill = next((s for s in _BASELINE_SKILLS if s["id"] == skill_id), None)
    if skill is None:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found")
    if not skill.get("trusted", False):
        raise HTTPException(status_code=403, detail=f"Skill '{skill_id}' is not in trusted allowlist")
    skill["enabled"] = True
    return {"skill_id": skill_id, "enabled": True}


@router.post(
    "/skills/{skill_id}/disable",
    dependencies=[Depends(PermissionChecker("skills", "manage"))],
)
async def disable_skill(skill_id: str) -> dict:
    """Disable a skill by ID."""
    skill = next((s for s in _BASELINE_SKILLS if s["id"] == skill_id), None)
    if skill is None:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found")
    skill["enabled"] = False
    return {"skill_id": skill_id, "enabled": False}
