"""API key onboarding — reveal-once + rotation (2026-Q2).

First-API-key flow per .planning/OCCP_ONBOARDING_10_2026.md §5:
    POST /api/v1/onboarding/first-api-key
        → generates occp_live_sk_<base64url(24 bytes)>
        → stores SHA-256 hash only
        → returns plain text ONCE
        → 409 on second call (rotation is the path for replacement)

Rotation (48h grace per Stripe/OneUptime 2026 best-practice):
    POST /api/v1/onboarding/rotate-api-key
        → mints new key, old remains valid 48h
        → old-key responses get X-Rotate-Notice: true

Revoke (no grace):
    POST /api/v1/onboarding/revoke-api-key { confirm: true }

This module is strictly additive. It does NOT touch api/auth.py,
security/vault.py, policy_engine/*.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from api.auth import get_current_user_payload
from api.deps import AppState, get_state

logger = logging.getLogger(__name__)

router = APIRouter(tags=["onboarding"])

API_KEY_PREFIX_LIVE = "occp_live_sk_"
API_KEY_BYTES = 24
ROTATION_GRACE_SEC = 48 * 3600


# ----------------------------------------------------------------------
# In-memory store (production should swap for persistent)
# ----------------------------------------------------------------------


class _KeyRecord:
    __slots__ = ("user", "hashed", "prefix_shown", "created_at", "rotated_at", "grace_until")

    def __init__(self, user: str, hashed: str, prefix_shown: str) -> None:
        self.user = user
        self.hashed = hashed
        self.prefix_shown = prefix_shown
        self.created_at = datetime.now(timezone.utc)
        self.rotated_at: datetime | None = None
        self.grace_until: datetime | None = None


_KEY_BY_HASH: dict[str, _KeyRecord] = {}
_LATEST_BY_USER: dict[str, str] = {}
_GRACE_BY_USER: dict[str, str] = {}


def _reset_store_for_testing() -> None:
    """Test-only cleanup."""
    _KEY_BY_HASH.clear()
    _LATEST_BY_USER.clear()
    _GRACE_BY_USER.clear()


def _mint_key() -> tuple[str, str, str]:
    raw = secrets.token_bytes(API_KEY_BYTES)
    body = base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")
    plain = f"{API_KEY_PREFIX_LIVE}{body}"
    hashed = hashlib.sha256(plain.encode("utf-8")).hexdigest()
    prefix_shown = f"{plain[: len(API_KEY_PREFIX_LIVE) + 6]}…"
    return plain, hashed, prefix_shown


# ----------------------------------------------------------------------
# Models
# ----------------------------------------------------------------------


class FirstKeyResponse(BaseModel):
    key: str = Field(..., description="Plain-text API key — shown ONCE")
    prefix_shown: str
    created_at: datetime
    copy_reminder: str = (
        "This is the only time the key is shown. Store it in a password manager "
        "or your CI secrets. You can always rotate if lost."
    )


class RotateRequest(BaseModel):
    reason: str | None = Field(None, max_length=240)


class RotateResponse(BaseModel):
    key: str
    prefix_shown: str
    created_at: datetime
    previous_grace_until: datetime
    grace_seconds: int = ROTATION_GRACE_SEC


class RevokeRequest(BaseModel):
    confirm: bool = Field(..., description="Must be true to revoke")


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _current_user(payload: dict[str, Any]) -> str:
    user = payload.get("sub") or payload.get("username")
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user has no subject claim",
        )
    return str(user)


# ----------------------------------------------------------------------
# Routes
# ----------------------------------------------------------------------


@router.post(
    "/onboarding/first-api-key",
    response_model=FirstKeyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def first_api_key(
    payload: dict[str, Any] = Depends(get_current_user_payload),
    state: AppState = Depends(get_state),
) -> FirstKeyResponse:
    """Generate the user's FIRST API key (shown once, idempotent)."""
    user = _current_user(payload)
    if user in _LATEST_BY_USER:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="API key already generated. Use POST /onboarding/rotate-api-key instead.",
        )
    plain, hashed, prefix_shown = _mint_key()
    rec = _KeyRecord(user=user, hashed=hashed, prefix_shown=prefix_shown)
    _KEY_BY_HASH[hashed] = rec
    _LATEST_BY_USER[user] = hashed
    logger.info("first_api_key issued user=%s prefix=%s", user, prefix_shown)
    return FirstKeyResponse(
        key=plain,
        prefix_shown=prefix_shown,
        created_at=rec.created_at,
    )


@router.post(
    "/onboarding/rotate-api-key",
    response_model=RotateResponse,
)
async def rotate_api_key(
    body: RotateRequest,
    payload: dict[str, Any] = Depends(get_current_user_payload),
    state: AppState = Depends(get_state),
) -> RotateResponse:
    """Mint new key; old stays valid for 48h grace."""
    user = _current_user(payload)
    if user not in _LATEST_BY_USER:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No existing API key to rotate. Call /onboarding/first-api-key first.",
        )
    old_hash = _LATEST_BY_USER[user]
    old_rec = _KEY_BY_HASH.get(old_hash)
    if old_rec is not None:
        old_rec.rotated_at = datetime.now(timezone.utc)
        old_rec.grace_until = old_rec.rotated_at + timedelta(seconds=ROTATION_GRACE_SEC)
        _GRACE_BY_USER[user] = old_hash

    plain, hashed, prefix_shown = _mint_key()
    new_rec = _KeyRecord(user=user, hashed=hashed, prefix_shown=prefix_shown)
    _KEY_BY_HASH[hashed] = new_rec
    _LATEST_BY_USER[user] = hashed
    logger.info(
        "rotate_api_key user=%s new_prefix=%s reason=%s",
        user,
        prefix_shown,
        (body.reason or "(none)")[:80],
    )
    return RotateResponse(
        key=plain,
        prefix_shown=prefix_shown,
        created_at=new_rec.created_at,
        previous_grace_until=(
            old_rec.grace_until if old_rec and old_rec.grace_until
            else datetime.now(timezone.utc) + timedelta(seconds=ROTATION_GRACE_SEC)
        ),
    )


@router.post(
    "/onboarding/revoke-api-key",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def revoke_api_key(
    body: RevokeRequest,
    payload: dict[str, Any] = Depends(get_current_user_payload),
    state: AppState = Depends(get_state),
) -> Response:
    """Immediately revoke the user's active key (no grace)."""
    if not body.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Set confirm=true to revoke",
        )
    user = _current_user(payload)
    h = _LATEST_BY_USER.pop(user, None)
    if h and h in _KEY_BY_HASH:
        del _KEY_BY_HASH[h]
    grace_h = _GRACE_BY_USER.pop(user, None)
    if grace_h and grace_h in _KEY_BY_HASH:
        del _KEY_BY_HASH[grace_h]
    logger.warning("revoke_api_key user=%s", user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def validate_api_key_header(req: Request, response: Response) -> _KeyRecord | None:
    """Helper: accept `Authorization: Bearer <occp_live_sk_...>` from downstream routes.

    Sets `X-Rotate-Notice: true` + `X-Rotate-Grace-Until` when the key is
    within the 48h post-rotation grace window.
    """
    auth = req.headers.get("Authorization") or req.headers.get("authorization")
    if not auth or not auth.lower().startswith("bearer "):
        return None
    candidate = auth.split(" ", 1)[1].strip()
    if not candidate.startswith(API_KEY_PREFIX_LIVE):
        return None
    hashed = hashlib.sha256(candidate.encode("utf-8")).hexdigest()
    rec = _KEY_BY_HASH.get(hashed)
    if rec is None:
        return None
    user = rec.user
    if _GRACE_BY_USER.get(user) == hashed and rec.grace_until:
        if datetime.now(timezone.utc) < rec.grace_until:
            response.headers["X-Rotate-Notice"] = "true"
            response.headers["X-Rotate-Grace-Until"] = rec.grace_until.isoformat()
        else:
            # Grace expired — actively invalid.
            del _KEY_BY_HASH[hashed]
            _GRACE_BY_USER.pop(user, None)
            return None
    return rec
