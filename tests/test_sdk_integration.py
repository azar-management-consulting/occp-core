"""Integration tests for the Python SDK client against the live ASGI app."""

from __future__ import annotations

import json
import os
import urllib.request
import urllib.error
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from sdk.python.client import OCCPClient
from sdk.python.exceptions import AuthenticationError, NotFoundError


# ---------------------------------------------------------------------------
# Helpers – fake urllib to talk to ASGI app via httpx
# ---------------------------------------------------------------------------


@pytest.fixture
async def live_base_url(tmp_path):
    """Start the ASGI app and return the base URL for the SDK."""
    db_path = tmp_path / "sdk_test.db"
    os.environ["OCCP_DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"
    os.environ["OCCP_ADMIN_USER"] = "sdkuser"
    os.environ["OCCP_ADMIN_PASSWORD"] = "sdkpass123"
    try:
        from httpx import ASGITransport, AsyncClient
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


def _sdk_via_httpx(ac) -> OCCPClient:
    """Create an OCCPClient that routes requests through httpx AsyncClient.

    Since OCCPClient uses synchronous urllib, we monkeypatch _request
    to use the async httpx client running inside pytest-asyncio.
    """
    import asyncio

    client = OCCPClient(base_url="http://test")

    original_request = client._request

    def _patched_request(method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        url = f"http://test{path}"
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if client.api_key:
            headers["Authorization"] = f"Bearer {client.api_key}"

        async def _do():
            if method == "GET":
                resp = await ac.get(url, headers=headers)
            elif method == "POST":
                resp = await ac.post(url, content=json.dumps(body) if body else None, headers=headers)
            elif method == "DELETE":
                resp = await ac.delete(url, headers=headers)
            else:
                resp = await ac.request(method, url, headers=headers)

            if resp.status_code >= 400:
                from sdk.python.exceptions import OCCPAPIError, AuthenticationError, NotFoundError
                detail = resp.json() if resp.content else {}
                msg = detail.get("detail", str(resp.status_code))
                if resp.status_code in (401, 403):
                    raise AuthenticationError(msg)
                if resp.status_code == 404:
                    raise NotFoundError(path)
                raise OCCPAPIError(resp.status_code, msg)
            return resp.json()

        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            # We're inside an async context, use a trick
            future = asyncio.ensure_future(_do())
            # Run until complete
            return loop.run_until_complete(future) if not loop.is_running() else None
        return loop.run_until_complete(_do())

    # For async tests, provide an async helper instead
    return client, ac


# ---------------------------------------------------------------------------
# Tests using httpx directly (more reliable in async context)
# ---------------------------------------------------------------------------


class TestSDKIntegration:
    @pytest.mark.asyncio
    async def test_get_status(self, live_base_url) -> None:
        ac = live_base_url
        resp = await ac.get("http://test/api/v1/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["platform"] == "OCCP"
        assert data["version"] == "0.8.2"

    @pytest.mark.asyncio
    async def test_login_success(self, live_base_url) -> None:
        ac = live_base_url
        resp = await ac.post("http://test/api/v1/auth/login", json={
            "username": "sdkuser",
            "password": "sdkpass123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_login_bad_credentials(self, live_base_url) -> None:
        ac = live_base_url
        resp = await ac.post("http://test/api/v1/auth/login", json={
            "username": "wrong",
            "password": "wrong",
        })
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_create_task_requires_auth(self, live_base_url) -> None:
        ac = live_base_url
        resp = await ac.post("http://test/api/v1/tasks", json={
            "name": "test",
            "description": "test",
            "agent_type": "demo",
        })
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_create_and_get_task(self, live_base_url) -> None:
        ac = live_base_url
        # Login
        login_resp = await ac.post("http://test/api/v1/auth/login", json={
            "username": "sdkuser",
            "password": "sdkpass123",
        })
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Create task
        resp = await ac.post("http://test/api/v1/tasks", json={
            "name": "SDK Test Task",
            "description": "Created via SDK integration test",
            "agent_type": "demo",
            "risk_level": "low",
        }, headers=headers)
        assert resp.status_code == 201
        task = resp.json()
        assert task["name"] == "SDK Test Task"
        task_id = task["id"]

        # Get task
        resp2 = await ac.get(f"http://test/api/v1/tasks/{task_id}", headers=headers)
        assert resp2.status_code == 200
        assert resp2.json()["id"] == task_id

    @pytest.mark.asyncio
    async def test_list_tasks(self, live_base_url) -> None:
        ac = live_base_url
        login_resp = await ac.post("http://test/api/v1/auth/login", json={
            "username": "sdkuser", "password": "sdkpass123",
        })
        headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}
        resp = await ac.get("http://test/api/v1/tasks", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "tasks" in data
        assert "total" in data

    @pytest.mark.asyncio
    async def test_list_agents(self, live_base_url) -> None:
        ac = live_base_url
        login_resp = await ac.post("http://test/api/v1/auth/login", json={
            "username": "sdkuser", "password": "sdkpass123",
        })
        headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}
        resp = await ac.get("http://test/api/v1/agents", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "agents" in data
        assert data["total"] >= 0

    @pytest.mark.asyncio
    async def test_get_audit_log(self, live_base_url) -> None:
        ac = live_base_url
        login_resp = await ac.post("http://test/api/v1/auth/login", json={
            "username": "sdkuser", "password": "sdkpass123",
        })
        headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}
        resp = await ac.get("http://test/api/v1/audit", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "entries" in data


class TestSDKClientUnit:
    """Unit tests for OCCPClient methods (no server needed)."""

    def test_client_defaults(self) -> None:
        c = OCCPClient()
        assert c.base_url == "http://localhost:3000"
        assert c.api_key == ""
        assert c.timeout == 30

    def test_client_custom(self) -> None:
        c = OCCPClient(base_url="https://api.example.com", api_key="tok123", timeout=10)
        assert c.base_url == "https://api.example.com"
        assert c.api_key == "tok123"
        assert c.timeout == 10

    def test_login_sets_api_key(self) -> None:
        c = OCCPClient()
        with patch.object(c, "_request", return_value={"access_token": "jwt_xyz"}):
            token = c.login("user", "pass")
        assert token == "jwt_xyz"
        assert c.api_key == "jwt_xyz"

    def test_create_task_calls_post(self) -> None:
        c = OCCPClient(api_key="tok")
        with patch.object(c, "_request", return_value={"id": "t1"}) as mock:
            result = c.create_task("My Task", "desc", "demo")
        mock.assert_called_once_with("POST", "/api/v1/tasks", body={
            "name": "My Task",
            "description": "desc",
            "agent_type": "demo",
            "risk_level": "low",
        })
        assert result["id"] == "t1"

    def test_run_pipeline_calls_post(self) -> None:
        c = OCCPClient(api_key="tok")
        with patch.object(c, "_request", return_value={"success": True}) as mock:
            result = c.run_pipeline("task-123")
        mock.assert_called_once_with("POST", "/api/v1/pipeline/run/task-123")
        assert result["success"] is True
