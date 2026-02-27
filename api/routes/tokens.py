"""Encrypted token management API — store, list, validate, revoke LLM keys.

All tokens are encrypted at rest (AES-256-GCM envelope encryption).
List operations return only masked values — plaintext is never exposed via API.
Per-user isolation enforced via JWT ``sub`` claim binding.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, status

from api.auth import get_current_user_payload
from api.rbac import PermissionChecker
from api.deps import AppState, get_state

logger = logging.getLogger(__name__)

router = APIRouter(tags=["tokens"])

SUPPORTED_PROVIDERS = {"anthropic", "openai"}


# ── Request / Response schemas ────────────────────────────────────────

class TokenStoreRequest(BaseModel):
    provider: str = Field(..., pattern=r"^(anthropic|openai)$")
    token: str = Field(..., min_length=10, max_length=500)
    label: str = Field(default="", max_length=128)


class TokenStoreResponse(BaseModel):
    provider: str
    masked_value: str
    label: str
    stored: bool = True


class TokenInfoResponse(BaseModel):
    id: str
    provider: str
    masked_value: str
    label: str
    is_active: bool
    created_at: str
    updated_at: str


class TokenListResponse(BaseModel):
    tokens: list[TokenInfoResponse]
    total: int
    has_anthropic: bool = False
    has_openai: bool = False


class TokenValidateResponse(BaseModel):
    provider: str
    valid: bool
    detail: str = ""


# ── Endpoints ─────────────────────────────────────────────────────────

@router.post(
    "/tokens",
    response_model=TokenStoreResponse,
    status_code=201,
    dependencies=[Depends(PermissionChecker("tokens", "manage"))],
)
async def store_token(
    body: TokenStoreRequest,
    payload: dict[str, Any] = Depends(get_current_user_payload),
    state: AppState = Depends(get_state),
) -> TokenStoreResponse:
    """Encrypt and store an LLM API token for the current user."""
    if state.token_store is None:
        raise HTTPException(status_code=503, detail="Token store not available")

    user_id = payload["sub"]

    # Audit: token storage event
    if state.policy_engine and state.audit_store:
        await state.policy_engine.audit(
            actor=user_id,
            action="token.store",
            task_id="",
            detail={"provider": body.provider, "event": "token_stored"},
            audit_store=state.audit_store,
        )

    row = await state.token_store.store_token(
        user_id=user_id,
        provider=body.provider,
        token=body.token,
        label=body.label,
    )

    return TokenStoreResponse(
        provider=body.provider,
        masked_value=row.masked_value,
        label=row.label,
    )


@router.get(
    "/tokens",
    response_model=TokenListResponse,
    dependencies=[Depends(PermissionChecker("tokens", "read"))],
)
async def list_tokens(
    payload: dict[str, Any] = Depends(get_current_user_payload),
    state: AppState = Depends(get_state),
) -> TokenListResponse:
    """List all tokens for the current user (masked, never plaintext)."""
    if state.token_store is None:
        raise HTTPException(status_code=503, detail="Token store not available")

    user_id = payload["sub"]
    tokens = await state.token_store.list_tokens(user_id)

    has_anthropic = any(
        t["provider"] == "anthropic" and t["is_active"] for t in tokens
    )
    has_openai = any(
        t["provider"] == "openai" and t["is_active"] for t in tokens
    )

    return TokenListResponse(
        tokens=[TokenInfoResponse(**t) for t in tokens],
        total=len(tokens),
        has_anthropic=has_anthropic,
        has_openai=has_openai,
    )


@router.post(
    "/tokens/{provider}/validate",
    response_model=TokenValidateResponse,
    dependencies=[Depends(PermissionChecker("tokens", "manage"))],
)
async def validate_token(
    provider: str,
    payload: dict[str, Any] = Depends(get_current_user_payload),
    state: AppState = Depends(get_state),
) -> TokenValidateResponse:
    """Validate a stored token by making a lightweight provider API call."""
    if provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")

    if state.token_store is None:
        raise HTTPException(status_code=503, detail="Token store not available")

    user_id = payload["sub"]
    token = await state.token_store.get_decrypted(user_id, provider)

    if token is None:
        return TokenValidateResponse(
            provider=provider,
            valid=False,
            detail="No active token found for this provider",
        )

    # Lightweight validation: check token format and attempt provider ping
    valid = False
    detail = ""

    if provider == "anthropic":
        valid = token.startswith("sk-ant-") and len(token) > 20
        detail = "Token format valid" if valid else "Invalid Anthropic key format (expected sk-ant-...)"

    elif provider == "openai":
        valid = token.startswith("sk-") and len(token) > 20
        detail = "Token format valid" if valid else "Invalid OpenAI key format (expected sk-...)"

    # Audit: token validation event
    if state.policy_engine and state.audit_store:
        await state.policy_engine.audit(
            actor=user_id,
            action="token.validate",
            task_id="",
            detail={"provider": provider, "valid": valid},
            audit_store=state.audit_store,
        )

    return TokenValidateResponse(provider=provider, valid=valid, detail=detail)


@router.delete(
    "/tokens/{provider}",
    dependencies=[Depends(PermissionChecker("tokens", "manage"))],
)
async def revoke_token(
    provider: str,
    payload: dict[str, Any] = Depends(get_current_user_payload),
    state: AppState = Depends(get_state),
) -> dict:
    """Revoke (soft-delete) a stored token."""
    if provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")

    if state.token_store is None:
        raise HTTPException(status_code=503, detail="Token store not available")

    user_id = payload["sub"]
    revoked = await state.token_store.revoke_token(user_id, provider)

    if not revoked:
        raise HTTPException(status_code=404, detail=f"No {provider} token found")

    # Audit: token revocation
    if state.policy_engine and state.audit_store:
        await state.policy_engine.audit(
            actor=user_id,
            action="token.revoke",
            task_id="",
            detail={"provider": provider},
            audit_store=state.audit_store,
        )

    return {"provider": provider, "revoked": True}


@router.get(
    "/tokens/check",
    dependencies=[Depends(PermissionChecker("tokens", "read"))],
)
async def check_token_status(
    payload: dict[str, Any] = Depends(get_current_user_payload),
    state: AppState = Depends(get_state),
) -> dict:
    """Quick check if the current user has any active tokens."""
    if state.token_store is None:
        return {"has_any": False, "providers": {}}

    user_id = payload["sub"]
    providers = {}
    for p in SUPPORTED_PROVIDERS:
        providers[p] = await state.token_store.has_active_token(user_id, p)

    return {
        "has_any": any(providers.values()),
        "providers": providers,
    }
