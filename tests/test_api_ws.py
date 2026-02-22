"""Tests for the WebSocket pipeline event stream."""

from __future__ import annotations

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
    async def test_pipeline_events_via_api(self) -> None:
        app = create_app()
        async with app.router.lifespan_context(app):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post("/api/v1/tasks", json={
                    "name": "ws-test",
                    "description": "WebSocket integration test",
                    "agent_type": "demo",
                    "risk_level": "low",
                })
                assert resp.status_code == 201
                task_id = resp.json()["id"]

                resp2 = await client.post(f"/api/v1/pipeline/run/{task_id}")
                assert resp2.status_code == 200
                assert resp2.json()["success"] is True
