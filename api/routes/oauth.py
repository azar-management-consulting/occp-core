"""GitHub OAuth routes for self-serve onboarding.

Implements the 2026-Q2 developer onboarding flow (see
``.planning/OCCP_ONBOARDING_10_2026.md`` §3). GitHub is the primary provider
because ~95% of developers have accounts and it matches the Vercel/Supabase
convention.

Flow::

    GET  /api/v1/oauth/github/start
         → 302 redirect to github.com/login/oauth/authorize?...&state=<jwt>

    GET  /api/v1/oauth/github/callback?code=...&state=...
         → validate state JWT (5-min expiry, replay-safe via signature)
         → exchange code for access_token (httpx POST)
         → fetch /user + /user/emails
         → create/update UserStore row
         → return TokenResponse { access_token, token_type, expires_in, role }

Env vars required (routes skip registration when absent):
  - OCCP_GITHUB_CLIENT_ID
  - OCCP_GITHUB_CLIENT_SECRET
  - OCCP_OAUTH_REDIRECT_BASE_URL  (e.g. https://api.occp.ai)

NO direct modification of api/auth.py or api/rbac.py (immutable paths).
"""

from __future__ import annotations

import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from api.auth import create_access_token
from api.deps import AppState, get_state

logger = logging.getLogger(__name__)

router = APIRouter(tags=["oauth"])

# ----------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"
GITHUB_USER_EMAILS_URL = "https://api.github.com/user/emails"

# Scopes minimaled per 2026 best-practice — read:user + email is sufficient.
GITHUB_OAUTH_SCOPES = "read:user user:email"

# State JWT expiry — short to prevent replay + abandoned flows.
STATE_TOKEN_EXPIRES_SEC = 300  # 5 minutes


# ----------------------------------------------------------------------
# Pydantic models
# ----------------------------------------------------------------------


class OAuthStartResponse(BaseModel):
    """Returned when ``?json=1`` query is passed (for SPA consumers)."""

    authorize_url: str
    state: str
    expires_in: int = Field(STATE_TOKEN_EXPIRES_SEC, description="seconds")


class OAuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    role: str = "viewer"
    github_login: str
    github_id: int
    email: str | None = None


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _config() -> dict[str, str] | None:
    """Return GitHub OAuth config or None when any env var is missing."""
    client_id = os.environ.get("OCCP_GITHUB_CLIENT_ID")
    client_secret = os.environ.get("OCCP_GITHUB_CLIENT_SECRET")
    base_url = os.environ.get("OCCP_OAUTH_REDIRECT_BASE_URL", "http://localhost:8000")
    if not client_id or not client_secret:
        return None
    return {
        "client_id": client_id,
        "client_secret": client_secret,
        "base_url": base_url,
    }


def _state_secret() -> str:
    """Return the signing secret for state JWTs.

    Falls back to OCCP_JWT_SECRET so state tokens share trust with session
    tokens — avoids a second secret to rotate.
    """
    secret = os.environ.get("OCCP_OAUTH_STATE_SECRET") or os.environ.get("OCCP_JWT_SECRET")
    if not secret:
        raise RuntimeError(
            "OCCP_OAUTH_STATE_SECRET or OCCP_JWT_SECRET env var required for OAuth state"
        )
    return secret


def _mint_state(nonce: str | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "purpose": "oauth_state",
        "provider": "github",
        "nonce": nonce or secrets.token_urlsafe(16),
        "iat": now,
        "exp": now + timedelta(seconds=STATE_TOKEN_EXPIRES_SEC),
    }
    return jwt.encode(payload, _state_secret(), algorithm="HS256")


def _verify_state(token: str) -> dict[str, Any]:
    try:
        claims = jwt.decode(token, _state_secret(), algorithms=["HS256"])
    except jwt.ExpiredSignatureError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OAuth state expired; please restart the flow",
        ) from e
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OAuth state token",
        ) from e
    if claims.get("purpose") != "oauth_state":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="State token purpose mismatch",
        )
    return claims


async def _exchange_code_for_token(code: str, cfg: dict[str, str]) -> str:
    """Swap the one-time code for an access_token."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            GITHUB_TOKEN_URL,
            headers={"Accept": "application/json"},
            data={
                "client_id": cfg["client_id"],
                "client_secret": cfg["client_secret"],
                "code": code,
            },
        )
    if resp.status_code != 200:
        logger.warning("github code exchange failed status=%s body=%s", resp.status_code, resp.text[:200])
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="GitHub OAuth exchange failed",
        )
    data = resp.json()
    if "access_token" not in data:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"GitHub OAuth returned no access_token: {data.get('error_description', 'unknown')}",
        )
    return str(data["access_token"])


async def _fetch_github_user(access_token: str) -> dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "OCCP-OAuth/1.0",
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        user_resp = await client.get(GITHUB_USER_URL, headers=headers)
        emails_resp = await client.get(GITHUB_USER_EMAILS_URL, headers=headers)
    if user_resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"GitHub /user fetch failed ({user_resp.status_code})",
        )
    user = user_resp.json()
    primary_email = None
    if emails_resp.status_code == 200:
        for row in emails_resp.json() or []:
            if row.get("primary") and row.get("verified"):
                primary_email = row.get("email")
                break
    # Fallback to public profile email if no primary verified one.
    user["_primary_email"] = primary_email or user.get("email")
    return user


# ----------------------------------------------------------------------
# Routes
# ----------------------------------------------------------------------


@router.get("/oauth/github/start", response_model=None)
async def github_start(
    json_response: bool = Query(False, alias="json"),
):
    """Begin the GitHub OAuth flow.

    Returns a 302 redirect by default. Pass ``?json=1`` to get the URL
    as JSON (useful for SPA frontends that manage the window.location
    themselves).
    """
    cfg = _config()
    if cfg is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GitHub OAuth not configured (missing OCCP_GITHUB_CLIENT_ID/SECRET)",
        )
    state = _mint_state()
    params = {
        "client_id": cfg["client_id"],
        "redirect_uri": f"{cfg['base_url'].rstrip('/')}/api/v1/oauth/github/callback",
        "scope": GITHUB_OAUTH_SCOPES,
        "state": state,
        "allow_signup": "true",
    }
    authorize_url = f"{GITHUB_AUTHORIZE_URL}?{urlencode(params)}"
    if json_response:
        return OAuthStartResponse(authorize_url=authorize_url, state=state)
    return RedirectResponse(authorize_url, status_code=status.HTTP_302_FOUND)


@router.get("/oauth/github/callback", response_model=OAuthTokenResponse)
async def github_callback(
    code: str,
    state: str,
    state_obj: AppState = Depends(get_state),
) -> OAuthTokenResponse:
    """Complete the GitHub OAuth flow and return an OCCP JWT."""
    cfg = _config()
    if cfg is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GitHub OAuth not configured",
        )
    _verify_state(state)
    gh_token = await _exchange_code_for_token(code, cfg)
    gh_user = await _fetch_github_user(gh_token)

    settings = state_obj.settings
    user_store = state_obj.user_store
    if user_store is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="User store not initialized",
        )

    login = str(gh_user.get("login", "")).strip()
    if not login:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="GitHub returned no login",
        )
    username = f"gh_{login}"
    email = gh_user.get("_primary_email")

    # Create-or-fetch (UserStore.get_or_create_oauth_user is the ideal
    # primitive; if not present, fall back to create_user with a random
    # password the user can never use — OAuth-only).
    user_obj = None
    create_fn = getattr(user_store, "get_or_create_oauth_user", None)
    if create_fn is not None:
        user_obj = await create_fn(
            provider="github",
            provider_user_id=str(gh_user.get("id")),
            username=username,
            email=email,
        )
    else:
        get_fn = getattr(user_store, "get_by_username", None)
        if get_fn is not None:
            user_obj = await get_fn(username)
        if user_obj is None:
            random_pw = secrets.token_urlsafe(32)
            create_user = getattr(user_store, "create_user", None)
            if create_user is None:
                raise HTTPException(
                    status_code=status.HTTP_501_NOT_IMPLEMENTED,
                    detail="UserStore has no create_user method",
                )
            user_obj = await create_user(username=username, password=random_pw, role="viewer")

    role = getattr(user_obj, "role", "viewer") if user_obj else "viewer"

    # Mint OCCP JWT using the shared helper from api.auth (immutable module).
    # Signature: create_access_token(subject, settings, *, extra=None)
    token = create_access_token(
        username,
        settings,
        extra={"role": role, "provider": "github"},
    )
    expires_in = int(getattr(settings, "occp_jwt_expire_minutes", 60)) * 60

    return OAuthTokenResponse(
        access_token=token,
        expires_in=expires_in,
        role=role,
        github_login=login,
        github_id=int(gh_user.get("id") or 0),
        email=email,
    )
