"""Tests for Casbin RBAC enforcement and PermissionChecker."""

from __future__ import annotations

import os

import pytest
from httpx import ASGITransport, AsyncClient

from api.rbac import check_permission, get_enforcer


class TestCasbinPolicy:
    """Direct policy checks without HTTP — pure Casbin enforcer tests."""

    def test_enforcer_loads(self) -> None:
        get_enforcer.cache_clear()
        e = get_enforcer()
        assert e is not None

    # ── Viewer ──────────────────────────────────────────────────────

    def test_viewer_can_read_tasks(self) -> None:
        assert check_permission("viewer", "tasks", "read") is True

    def test_viewer_can_read_agents(self) -> None:
        assert check_permission("viewer", "agents", "read") is True

    def test_viewer_can_read_audit(self) -> None:
        assert check_permission("viewer", "audit", "read") is True

    def test_viewer_can_read_status(self) -> None:
        assert check_permission("viewer", "status", "read") is True

    def test_viewer_can_evaluate_policy(self) -> None:
        assert check_permission("viewer", "policy", "evaluate") is True

    def test_viewer_cannot_create_tasks(self) -> None:
        assert check_permission("viewer", "tasks", "create") is False

    def test_viewer_cannot_delete_tasks(self) -> None:
        assert check_permission("viewer", "tasks", "delete") is False

    def test_viewer_cannot_manage_users(self) -> None:
        assert check_permission("viewer", "users", "read") is False
        assert check_permission("viewer", "users", "create") is False

    # ── Operator ────────────────────────────────────────────────────

    def test_operator_inherits_viewer(self) -> None:
        assert check_permission("operator", "tasks", "read") is True
        assert check_permission("operator", "agents", "read") is True

    def test_operator_can_create_tasks(self) -> None:
        assert check_permission("operator", "tasks", "create") is True

    def test_operator_can_update_tasks(self) -> None:
        assert check_permission("operator", "tasks", "update") is True

    def test_operator_can_execute_tasks(self) -> None:
        assert check_permission("operator", "tasks", "execute") is True

    def test_operator_can_run_pipeline(self) -> None:
        assert check_permission("operator", "pipeline", "run") is True

    def test_operator_cannot_delete_tasks(self) -> None:
        assert check_permission("operator", "tasks", "delete") is False

    def test_operator_cannot_manage_agents(self) -> None:
        assert check_permission("operator", "agents", "create") is False

    # ── Org Admin ───────────────────────────────────────────────────

    def test_org_admin_inherits_operator(self) -> None:
        assert check_permission("org_admin", "tasks", "create") is True
        assert check_permission("org_admin", "tasks", "read") is True
        assert check_permission("org_admin", "pipeline", "run") is True

    def test_org_admin_can_delete_tasks(self) -> None:
        assert check_permission("org_admin", "tasks", "delete") is True

    def test_org_admin_can_manage_agents(self) -> None:
        assert check_permission("org_admin", "agents", "create") is True
        assert check_permission("org_admin", "agents", "update") is True
        assert check_permission("org_admin", "agents", "delete") is True

    def test_org_admin_can_manage_users(self) -> None:
        assert check_permission("org_admin", "users", "read") is True
        assert check_permission("org_admin", "users", "create") is True
        assert check_permission("org_admin", "users", "update") is True

    def test_org_admin_cannot_delete_users(self) -> None:
        assert check_permission("org_admin", "users", "delete") is False

    def test_org_admin_cannot_update_policy(self) -> None:
        assert check_permission("org_admin", "policy", "update") is False

    # ── System Admin ────────────────────────────────────────────────

    def test_system_admin_inherits_all(self) -> None:
        assert check_permission("system_admin", "tasks", "read") is True
        assert check_permission("system_admin", "tasks", "create") is True
        assert check_permission("system_admin", "tasks", "delete") is True
        assert check_permission("system_admin", "agents", "create") is True
        assert check_permission("system_admin", "users", "read") is True

    def test_system_admin_can_delete_users(self) -> None:
        assert check_permission("system_admin", "users", "delete") is True

    def test_system_admin_can_update_policy(self) -> None:
        assert check_permission("system_admin", "policy", "update") is True

    def test_system_admin_can_manage_system(self) -> None:
        assert check_permission("system_admin", "system", "manage") is True

    # ── Edge cases ──────────────────────────────────────────────────

    def test_unknown_role_denied(self) -> None:
        assert check_permission("hacker", "tasks", "read") is False

    def test_unknown_resource_denied(self) -> None:
        assert check_permission("system_admin", "nuclear_codes", "launch") is False


class TestLoginWithRole:
    """Integration: login returns JWT with role claim."""

    @pytest.fixture
    async def client(self, tmp_path):
        db_path = tmp_path / "test_rbac.db"
        os.environ["OCCP_DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"
        os.environ["OCCP_ADMIN_USER"] = "rbac_admin"
        os.environ["OCCP_ADMIN_PASSWORD"] = "rbac_pass_123"
        try:
            from api.app import create_app
            app = create_app()
            async with app.router.lifespan_context(app):
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as ac:
                    yield ac
        finally:
            os.environ.pop("OCCP_DATABASE_URL", None)
            os.environ.pop("OCCP_ADMIN_USER", None)
            os.environ.pop("OCCP_ADMIN_PASSWORD", None)
            # Reset cached enforcer
            get_enforcer.cache_clear()

    async def test_login_returns_role(self, client: AsyncClient) -> None:
        resp = await client.post("/api/v1/auth/login", json={
            "username": "rbac_admin",
            "password": "rbac_pass_123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "system_admin"

    async def test_token_contains_role_claim(self, client: AsyncClient) -> None:
        import jwt as pyjwt
        resp = await client.post("/api/v1/auth/login", json={
            "username": "rbac_admin",
            "password": "rbac_pass_123",
        })
        token = resp.json()["access_token"]
        payload = pyjwt.decode(token, options={"verify_signature": False})
        assert payload["role"] == "system_admin"
        assert payload["sub"] == "rbac_admin"

    async def test_refresh_preserves_role(self, client: AsyncClient) -> None:
        resp = await client.post("/api/v1/auth/login", json={
            "username": "rbac_admin",
            "password": "rbac_pass_123",
        })
        token = resp.json()["access_token"]

        resp2 = await client.post("/api/v1/auth/refresh", json={"token": token})
        assert resp2.status_code == 200
        assert resp2.json()["role"] == "system_admin"

    async def test_admin_user_seeded_on_boot(self, client: AsyncClient) -> None:
        """Verify the admin user was auto-seeded from env vars."""
        resp = await client.post("/api/v1/auth/login", json={
            "username": "rbac_admin",
            "password": "rbac_pass_123",
        })
        assert resp.status_code == 200
        assert resp.json()["role"] == "system_admin"
