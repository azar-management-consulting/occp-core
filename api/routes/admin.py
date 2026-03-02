"""Admin statistics routes — dashboard analytics for org_admin+.

Provides aggregated stats: user counts, role distribution,
onboarding funnel, and recent user activity.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException

from api.rbac import PermissionChecker
from api.deps import AppState, get_state
from api.models import (
    AdminStatsResponse,
    OnboardingFunnel,
    UserActivity,
)

router = APIRouter(tags=["admin"])


@router.get(
    "/admin/stats",
    response_model=AdminStatsResponse,
    dependencies=[Depends(PermissionChecker("users", "read"))],
)
async def admin_stats(state: AppState = Depends(get_state)) -> AdminStatsResponse:
    """Aggregated admin statistics for the dashboard."""
    if state.user_store is None:
        raise HTTPException(status_code=503, detail="User store not available")

    users = await state.user_store.list_all()
    users_total = len(users)

    # Role distribution
    role_counter: Counter[str] = Counter()
    for u in users:
        role_counter[u.role] += 1
    users_by_role = dict(role_counter)

    # Registrations in last 7 days
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    registrations_last_7_days = sum(
        1 for u in users if u.created_at >= cutoff
    )

    # Onboarding funnel (best-effort — store may be None)
    funnel = OnboardingFunnel()
    if state.onboarding_store is not None:
        try:
            all_progress = await state.onboarding_store.list_all()
            for p in all_progress:
                ws = p.get("wizard_state", "landing")
                if ws == "done":
                    funnel.done += 1
                elif ws == "running":
                    funnel.running += 1
                else:
                    funnel.landing += 1
        except Exception:
            pass  # stats must not fail if store is degraded

    # User activity — last audit action per user
    activity: list[UserActivity] = []
    for u in users:
        ua = UserActivity(
            username=u.username,
            role=u.role,
            last_seen=u.updated_at.isoformat() if u.updated_at else "",
        )
        activity.append(ua)

    return AdminStatsResponse(
        users_total=users_total,
        users_by_role=users_by_role,
        registrations_last_7_days=registrations_last_7_days,
        onboarding_funnel=funnel,
        user_activity=activity,
    )
