"""User management routes — admin-only user listing.

Requires ``users:read`` permission (org_admin+ via Casbin RBAC).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from api.rbac import PermissionChecker
from api.deps import AppState, get_state
from api.models import UserListItem, UserListResponse

router = APIRouter(tags=["users"])


@router.get(
    "/users",
    response_model=UserListResponse,
    dependencies=[Depends(PermissionChecker("users", "read"))],
)
async def list_users(state: AppState = Depends(get_state)) -> UserListResponse:
    """Return all users (admin-only)."""
    if state.user_store is None:
        raise HTTPException(status_code=503, detail="User store not available")

    users = await state.user_store.list_all()
    items = [
        UserListItem(
            id=u.id,
            username=u.username,
            role=u.role,
            display_name=u.display_name,
            is_active=u.is_active,
            created_at=u.created_at,
            updated_at=u.updated_at,
        )
        for u in users
    ]
    return UserListResponse(users=items, total=len(items))
