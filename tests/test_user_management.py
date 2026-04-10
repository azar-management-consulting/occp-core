"""Tests for user management endpoints – /auth/me, /auth/register, /users, /admin/stats.

Covers:
- GET /auth/me — profile retrieval
- POST /auth/register — public self-registration (viewer-only)
- POST /auth/register/admin — admin user creation with role
- GET /users — admin-only user listing
- GET /admin/stats — admin statistics
- Login audit logging
- RBAC enforcement (viewer cannot access admin-only endpoints)
"""

from __future__ import annotations

import os

import pytest
from httpx import ASGITransport, AsyncClient

from api.app import create_app


@pytest.fixture
async def client(tmp_path):
    db_path = tmp_path / "test_users.db"
    os.environ["OCCP_DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"
    os.environ["OCCP_ADMIN_USER"] = "testadmin"
    os.environ["OCCP_ADMIN_PASSWORD"] = "testpass123"
    try:
        app = create_app()
        async with app.router.lifespan_context(app):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                yield ac
    finally:
        os.environ.pop("OCCP_DATABASE_URL", None)
        os.environ.pop("OCCP_ADMIN_USER", None)
        os.environ.pop("OCCP_ADMIN_PASSWORD", None)


async def _admin_token(client: AsyncClient) -> str:
    """Login as seeded system_admin and return JWT."""
    resp = await client.post("/api/v1/auth/login", json={
        "username": "testadmin",
        "password": "testpass123",
    })
    assert resp.status_code == 200
    return resp.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# GET /auth/me
# ---------------------------------------------------------------------------


class TestAuthMe:
    @pytest.mark.asyncio
    async def test_me_returns_profile(self, client: AsyncClient) -> None:
        token = await _admin_token(client)
        resp = await client.get("/api/v1/auth/me", headers=_auth(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "testadmin"
        assert data["role"] == "system_admin"
        assert "display_name" in data

    @pytest.mark.asyncio
    async def test_me_unauthenticated(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_me_bad_token(self, client: AsyncClient) -> None:
        resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid.jwt.token"},
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /auth/register (public self-registration)
# ---------------------------------------------------------------------------


class TestSelfRegister:
    @pytest.mark.asyncio
    async def test_register_creates_viewer(self, client: AsyncClient) -> None:
        resp = await client.post("/api/v1/auth/register", json={
            "username": "newuser",
            "password": "securepass123",
            "display_name": "New User",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "access_token" in data
        assert data["role"] == "viewer"
        assert data["token_type"] == "bearer"
        assert data["expires_in"] > 0

    @pytest.mark.asyncio
    async def test_register_no_auth_required(self, client: AsyncClient) -> None:
        """Self-registration must work without any auth token."""
        resp = await client.post("/api/v1/auth/register", json={
            "username": "pubuser",
            "password": "securepass123",
        })
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_register_duplicate_username(self, client: AsyncClient) -> None:
        await client.post("/api/v1/auth/register", json={
            "username": "dupuser",
            "password": "securepass123",
        })
        resp = await client.post("/api/v1/auth/register", json={
            "username": "dupuser",
            "password": "differentpass1",
        })
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_register_password_too_short(self, client: AsyncClient) -> None:
        resp = await client.post("/api/v1/auth/register", json={
            "username": "shortpw",
            "password": "abc",
        })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_register_then_login(self, client: AsyncClient) -> None:
        """New user can login immediately after registration."""
        await client.post("/api/v1/auth/register", json={
            "username": "logintest",
            "password": "securepass123",
        })
        resp = await client.post("/api/v1/auth/login", json={
            "username": "logintest",
            "password": "securepass123",
        })
        assert resp.status_code == 200
        assert resp.json()["role"] == "viewer"

    @pytest.mark.asyncio
    async def test_register_default_display_name(self, client: AsyncClient) -> None:
        """When display_name omitted, defaults to username."""
        resp = await client.post("/api/v1/auth/register", json={
            "username": "noname",
            "password": "securepass123",
        })
        assert resp.status_code == 201
        # Verify via /auth/me
        token = resp.json()["access_token"]
        me = await client.get("/api/v1/auth/me", headers=_auth(token))
        assert me.json()["display_name"] == "noname"


# ---------------------------------------------------------------------------
# POST /auth/register/admin (admin-only user creation)
# ---------------------------------------------------------------------------


class TestAdminRegister:
    @pytest.mark.asyncio
    async def test_admin_creates_operator(self, client: AsyncClient) -> None:
        token = await _admin_token(client)
        resp = await client.post("/api/v1/auth/register/admin", json={
            "username": "opuser",
            "password": "securepass123",
            "role": "operator",
            "display_name": "Operator User",
        }, headers=_auth(token))
        assert resp.status_code == 201
        assert resp.json()["role"] == "operator"

    @pytest.mark.asyncio
    async def test_admin_creates_org_admin(self, client: AsyncClient) -> None:
        token = await _admin_token(client)
        resp = await client.post("/api/v1/auth/register/admin", json={
            "username": "orgadm",
            "password": "securepass123",
            "role": "org_admin",
        }, headers=_auth(token))
        assert resp.status_code == 201
        assert resp.json()["role"] == "org_admin"

    @pytest.mark.asyncio
    async def test_admin_register_requires_auth(self, client: AsyncClient) -> None:
        resp = await client.post("/api/v1/auth/register/admin", json={
            "username": "nope",
            "password": "securepass123",
            "role": "operator",
        })
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_viewer_cannot_admin_register(self, client: AsyncClient) -> None:
        """Viewer role lacks users:create — should get 403."""
        # Create a viewer via self-register
        reg = await client.post("/api/v1/auth/register", json={
            "username": "viewer1",
            "password": "securepass123",
        })
        viewer_token = reg.json()["access_token"]
        resp = await client.post("/api/v1/auth/register/admin", json={
            "username": "blocked",
            "password": "securepass123",
            "role": "operator",
        }, headers=_auth(viewer_token))
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_register_invalid_role(self, client: AsyncClient) -> None:
        token = await _admin_token(client)
        resp = await client.post("/api/v1/auth/register/admin", json={
            "username": "badrole",
            "password": "securepass123",
            "role": "superuser",
        }, headers=_auth(token))
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_admin_register_duplicate(self, client: AsyncClient) -> None:
        token = await _admin_token(client)
        await client.post("/api/v1/auth/register/admin", json={
            "username": "dup2",
            "password": "securepass123",
            "role": "viewer",
        }, headers=_auth(token))
        resp = await client.post("/api/v1/auth/register/admin", json={
            "username": "dup2",
            "password": "securepass123",
            "role": "operator",
        }, headers=_auth(token))
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# GET /users (admin-only user listing)
# ---------------------------------------------------------------------------


class TestUserList:
    @pytest.mark.asyncio
    async def test_admin_can_list_users(self, client: AsyncClient) -> None:
        token = await _admin_token(client)
        resp = await client.get("/api/v1/users", headers=_auth(token))
        assert resp.status_code == 200
        data = resp.json()
        assert "users" in data
        assert "total" in data
        assert data["total"] >= 1  # at least the seeded admin
        usernames = [u["username"] for u in data["users"]]
        assert "testadmin" in usernames

    @pytest.mark.asyncio
    async def test_viewer_cannot_list_users(self, client: AsyncClient) -> None:
        reg = await client.post("/api/v1/auth/register", json={
            "username": "viewer2",
            "password": "securepass123",
        })
        viewer_token = reg.json()["access_token"]
        resp = await client.get("/api/v1/users", headers=_auth(viewer_token))
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_unauthenticated_cannot_list_users(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/users")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_user_list_includes_registered_users(self, client: AsyncClient) -> None:
        # Register a new user
        await client.post("/api/v1/auth/register", json={
            "username": "listed_user",
            "password": "securepass123",
        })
        token = await _admin_token(client)
        resp = await client.get("/api/v1/users", headers=_auth(token))
        usernames = [u["username"] for u in resp.json()["users"]]
        assert "listed_user" in usernames


# ---------------------------------------------------------------------------
# GET /admin/stats
# ---------------------------------------------------------------------------


class TestAdminStats:
    @pytest.mark.asyncio
    async def test_admin_can_get_stats(self, client: AsyncClient) -> None:
        token = await _admin_token(client)
        resp = await client.get("/api/v1/admin/stats", headers=_auth(token))
        assert resp.status_code == 200
        data = resp.json()
        assert "users_total" in data
        assert "users_by_role" in data
        assert "registrations_last_7_days" in data
        assert "onboarding_funnel" in data
        assert "user_activity" in data
        assert data["users_total"] >= 1

    @pytest.mark.asyncio
    async def test_viewer_cannot_get_stats(self, client: AsyncClient) -> None:
        reg = await client.post("/api/v1/auth/register", json={
            "username": "viewer3",
            "password": "securepass123",
        })
        viewer_token = reg.json()["access_token"]
        resp = await client.get("/api/v1/admin/stats", headers=_auth(viewer_token))
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_unauthenticated_cannot_get_stats(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/admin/stats")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_stats_reflect_registrations(self, client: AsyncClient) -> None:
        """After registering users, stats should reflect the new count."""
        await client.post("/api/v1/auth/register", json={
            "username": "statsuser1",
            "password": "securepass123",
        })
        await client.post("/api/v1/auth/register", json={
            "username": "statsuser2",
            "password": "securepass123",
        })
        token = await _admin_token(client)
        resp = await client.get("/api/v1/admin/stats", headers=_auth(token))
        data = resp.json()
        # admin + 2 new users = at least 3
        assert data["users_total"] >= 3
        assert data["registrations_last_7_days"] >= 2

    @pytest.mark.asyncio
    async def test_stats_role_distribution(self, client: AsyncClient) -> None:
        token = await _admin_token(client)
        # Create users with different roles
        await client.post("/api/v1/auth/register/admin", json={
            "username": "op_stats",
            "password": "securepass123",
            "role": "operator",
        }, headers=_auth(token))
        resp = await client.get("/api/v1/admin/stats", headers=_auth(token))
        roles = resp.json()["users_by_role"]
        assert "system_admin" in roles
        assert "operator" in roles


# ---------------------------------------------------------------------------
# Login audit logging
# ---------------------------------------------------------------------------


class TestLoginAudit:
    @pytest.mark.asyncio
    async def test_login_creates_audit_entry(self, client: AsyncClient) -> None:
        """Successful login should produce an auth.login audit entry."""
        token = await _admin_token(client)
        resp = await client.get("/api/v1/audit", headers=_auth(token))
        assert resp.status_code == 200
        entries = resp.json()["entries"]
        login_entries = [e for e in entries if e["action"] == "auth.login"]
        assert len(login_entries) >= 1
        assert login_entries[0]["actor"] == "testadmin"
        assert login_entries[0]["detail"].get("role") == "system_admin"
