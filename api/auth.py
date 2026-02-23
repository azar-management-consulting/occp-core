"""JWT authentication helpers for OCCP API.

Provides token creation/verification and FastAPI dependencies:
- ``get_current_user`` — returns username string (backward compat)
- ``get_current_user_payload`` — returns dict with sub, role (RBAC-aware)
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config.settings import Settings

logger = logging.getLogger(__name__)

_bearer_scheme = HTTPBearer(auto_error=False)


def create_access_token(
    subject: str,
    settings: Settings,
    *,
    extra: dict[str, Any] | None = None,
) -> str:
    """Mint a new JWT for *subject* (usually the username)."""
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str, settings: Settings) -> dict[str, Any]:
    """Decode and verify a JWT.  Raises HTTPException on failure."""
    try:
        return jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
        )
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
        )


def _extract_payload(
    credentials: HTTPAuthorizationCredentials | None,
) -> dict[str, Any]:
    """Shared extraction logic for both dependency variants."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    from api.deps import get_state

    settings = get_state().settings
    payload = decode_token(credentials.credentials, settings)
    sub: str | None = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing 'sub' claim",
        )
    return payload


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> str:
    """FastAPI dependency – returns the username (``sub`` claim).

    Backward-compatible: existing endpoints keep using this.
    """
    payload = _extract_payload(credentials)
    return payload["sub"]


async def get_current_user_payload(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> dict[str, Any]:
    """FastAPI dependency – returns full token payload (sub, role, etc.).

    Use this for RBAC-aware endpoints via ``PermissionChecker``.
    """
    payload = _extract_payload(credentials)
    # Ensure role is always present (default viewer for legacy tokens)
    if "role" not in payload:
        payload["role"] = "viewer"
    return payload
