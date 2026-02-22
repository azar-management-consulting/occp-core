"""Authentication routes – login and token refresh."""

from __future__ import annotations

from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, HTTPException, status

from api.auth import create_access_token, decode_token
from api.deps import AppState, get_state

router = APIRouter(tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=200)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class RefreshRequest(BaseModel):
    token: str


@router.post("/auth/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    state: AppState = Depends(get_state),
) -> TokenResponse:
    """Authenticate with admin credentials and receive a JWT."""
    settings = state.settings
    if body.username != settings.admin_user or body.password != settings.admin_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    token = create_access_token(body.username, settings)
    return TokenResponse(
        access_token=token,
        expires_in=settings.jwt_expire_minutes * 60,
    )


@router.post("/auth/refresh", response_model=TokenResponse)
async def refresh_token(
    body: RefreshRequest,
    state: AppState = Depends(get_state),
) -> TokenResponse:
    """Exchange a valid (non-expired) token for a fresh one."""
    settings = state.settings
    payload = decode_token(body.token, settings)
    sub = payload.get("sub", "")

    new_token = create_access_token(sub, settings)
    return TokenResponse(
        access_token=new_token,
        expires_in=settings.jwt_expire_minutes * 60,
    )
