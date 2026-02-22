"""Tests for the WebSocket pipeline event stream."""

from __future__ import annotations

import os

import pytest
from httpx import ASGITransport, AsyncClient

from api.app import create_app
from api.ws_manager import ConnectionManager


class TestConnectionManager:
    @pytest.mark.asyncio
    async def test_manager_initializes_empty(self) -> None:
        mgr = ConnectionManager()
        assert len(mgr._connections) == 0

    @pytest.mark.asyncio
    async def test_broadcast_no_connections(self) -> None:
        mgr = ConnectionManager()
        # Should not raise
        await mgr.broadcast("task-1", {"event": "test"})


class TestWSEndpoint:
    @pytest.mark.asyncio
    async def test_pipeline_events_via_api(self, tmp_path) -> None:
        db_path = tmp_path / "test_ws.db"
        os.environ["OCCP_DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"
        os.environ["OCCP_ADMIN_USER"] = "wsadmin"
        os.environ["OCCP_ADMIN_PASSWORD"] = "wspass123"
        try:
            app = create_app()
            async with app.router.lifespan_context(app):
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    # Login first
                    login_resp = await client.post("/api/v1/auth/login", json={
                        "username": "wsadmin",
                        "password": "wspass123",
                    })
                    token = login_resp.json()["access_token"]
                    headers = {"Authorization": f"Bearer {token}"}

                    resp = await client.post("/api/v1/tasks", json={
                        "name": "ws-test",
                        "description": "WebSocket integration test",
                        "agent_type": "demo",
                        "risk_level": "low",
                    }, headers=headers)
                    assert resp.status_code == 201
                    task_id = resp.json()["id"]

                    resp2 = await client.post(
                        f"/api/v1/pipeline/run/{task_id}",
                        headers=headers,
                    )
                    assert resp2.status_code == 200
                    assert resp2.json()["success"] is True
        finally:
            os.environ.pop("OCCP_DATABASE_URL", None)
            os.environ.pop("OCCP_ADMIN_USER", None)
            os.environ.pop("OCCP_ADMIN_PASSWORD", None)
