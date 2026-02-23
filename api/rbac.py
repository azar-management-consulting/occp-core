"""Casbin-based RBAC enforcement for OCCP API.

Provides ``PermissionChecker`` — a reusable FastAPI dependency that
verifies the current user's role against the Casbin policy before
allowing access to an endpoint.

Role hierarchy: system_admin > org_admin > operator > viewer
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Any

import casbin
from fastapi import Depends, HTTPException, status

from api.auth import get_current_user_payload

logger = logging.getLogger(__name__)

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@lru_cache(maxsize=1)
def get_enforcer() -> casbin.Enforcer:
    """Cached Casbin enforcer loaded from config files."""
    model_path = os.path.join(_BASE_DIR, "config", "rbac_model.conf")
    policy_path = os.path.join(_BASE_DIR, "config", "rbac_policy.csv")
    enforcer = casbin.Enforcer(model_path, policy_path)
    logger.info("Casbin RBAC enforcer loaded (%s)", model_path)
    return enforcer


def check_permission(role: str, resource: str, action: str) -> bool:
    """Check if *role* can perform *action* on *resource*."""
    return get_enforcer().enforce(role, resource, action)


class PermissionChecker:
    """FastAPI dependency that enforces RBAC on an endpoint.

    Usage::

        @router.post("/tasks", dependencies=[Depends(PermissionChecker("tasks", "create"))])
        async def create_task(...): ...

    Or inject the user payload::

        @router.post("/tasks")
        async def create_task(user=Depends(PermissionChecker("tasks", "create"))): ...
    """

    def __init__(self, resource: str, action: str) -> None:
        self.resource = resource
        self.action = action

    async def __call__(
        self,
        current_user: dict[str, Any] = Depends(get_current_user_payload),
    ) -> dict[str, Any]:
        """Verify permission; return user payload on success."""
        role = current_user.get("role", "viewer")

        if not check_permission(role, self.resource, self.action):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {role} cannot {self.action} {self.resource}",
            )
        return current_user
