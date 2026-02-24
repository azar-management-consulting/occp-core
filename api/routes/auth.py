"""Authentication routes – login and token refresh.

Login authenticates against the UserStore (argon2). On fresh deployments
the admin user is auto-seeded from OCCP_ADMIN_USER / OCCP_ADMIN_PASSWORD
environment variables (see ``api/app.py`` lifespan).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, HTTPException, status

from api.auth import create_access_token, decode_token
from api.rbac import PermissionChecker
from api.deps import AppState, get_state

router = APIRouter(tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=200)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    role: str = "viewer"


class RefreshRequest(BaseModel):
    token: str


@router.post("/auth/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    state: AppState = Depends(get_state),
) -> TokenResponse:
    """Authenticate with credentials and receive a JWT with role claim."""
    settings = state.settings
    user = None

    # Primary path: UserStore authentication (argon2)
    if state.user_store:
        user = await state.user_store.authenticate(body.username, body.password)

    # Fallback: env-var admin credentials (bootstrap / tests only — disabled in production)
    if user is None and not settings.is_production:
        if body.username == settings.admin_user and body.password == settings.admin_password:
            # Synthetic admin for backward compat
            from store.user_store import User
            user = User(
                username=settings.admin_user,
                role="system_admin",
                display_name="Admin",
            )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    token = create_access_token(
        user.username,
        settings,
        extra={"role": user.role},
    )
    return TokenResponse(
        access_token=token,
        expires_in=settings.jwt_expire_minutes * 60,
        role=user.role,
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
    role = payload.get("role", "viewer")

    new_token = create_access_token(
        sub,
        settings,
        extra={"role": role},
    )
    return TokenResponse(
        access_token=new_token,
        expires_in=settings.jwt_expire_minutes * 60,
        role=role,
    )


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=8, max_length=200)
    role: str = Field(default="viewer", pattern=r"^(viewer|operator|org_admin|system_admin)$")
    display_name: str = ""


@router.post("/auth/register", response_model=TokenResponse, status_code=201,
             dependencies=[Depends(PermissionChecker("users", "create"))])
async def register_user(
    body: RegisterRequest,
    state: AppState = Depends(get_state),
) -> TokenResponse:
    """Create a new user (requires users:create permission)."""
    if state.user_store is None:
        raise HTTPException(status_code=503, detail="User store not available")

    existing = await state.user_store.get_by_username(body.username)
    if existing:
        raise HTTPException(status_code=409, detail="Username already exists")

    user = await state.user_store.create(
        username=body.username,
        password=body.password,
        role=body.role,
        display_name=body.display_name or body.username,
    )
    token = create_access_token(
        user.username,
        state.settings,
        extra={"role": user.role},
    )
    return TokenResponse(
        access_token=token,
        expires_in=state.settings.jwt_expire_minutes * 60,
        role=user.role,
    )
