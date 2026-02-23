"""Tests for Agent Registry – Scheduler methods + API CRUD."""

from __future__ import annotations

import os

import pytest
from httpx import ASGITransport, AsyncClient

from orchestrator.models import AgentConfig
from orchestrator.scheduler import Scheduler

from api.app import create_app


# ---------------------------------------------------------------------------
# Scheduler unit tests
# ---------------------------------------------------------------------------


class TestSchedulerRegistry:
    def test_list_agents_empty(self) -> None:
        s = Scheduler()
        assert s.list_agents() == []

    def test_register_and_list(self) -> None:
        s = Scheduler()
        cfg = AgentConfig(agent_type="test", display_name="Test Agent")

        async def factory(_cfg, _task=None):
            return {}

        s.register(cfg, factory)
        agents = s.list_agents()
        assert len(agents) == 1
        assert agents[0].agent_type == "test"

    def test_get_agent(self) -> None:
        s = Scheduler()
        cfg = AgentConfig(agent_type="finder", display_name="Finder")

        async def factory(_cfg, _task=None):
            return {}

        s.register(cfg, factory)
        assert s.get_agent("finder") is not None
        assert s.get_agent("finder").display_name == "Finder"
        assert s.get_agent("missing") is None

    def test_unregister(self) -> None:
        s = Scheduler()
        cfg = AgentConfig(agent_type="temp", display_name="Temp")

        async def factory(_cfg, _task=None):
            return {}

        s.register(cfg, factory)
        assert len(s.list_agents()) == 1
        s.unregister("temp")
        assert len(s.list_agents()) == 0


# ---------------------------------------------------------------------------
# API integration tests
# ---------------------------------------------------------------------------


@pytest.fixture
async def client(tmp_path):
    db_path = tmp_path / "test_agents.db"
    os.environ["OCCP_DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"
    os.environ["OCCP_ADMIN_USER"] = "agentadmin"
    os.environ["OCCP_ADMIN_PASSWORD"] = "agentpass"
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


async def _get_token(client: AsyncClient) -> str:
    resp = await client.post("/api/v1/auth/login", json={
        "username": "agentadmin",
        "password": "agentpass",
    })
    return resp.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class TestAgentsAPI:
    @pytest.mark.asyncio
    async def test_list_empty(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/agents")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["agents"] == []

    @pytest.mark.asyncio
    async def test_register_and_get(self, client: AsyncClient) -> None:
        token = await _get_token(client)
        resp = await client.post("/api/v1/agents", json={
            "agent_type": "coder",
            "display_name": "Code Agent",
            "capabilities": ["python", "js"],
            "max_concurrent": 3,
        }, headers=_auth(token))
        assert resp.status_code == 201
        data = resp.json()
        assert data["agent_type"] == "coder"
        assert data["max_concurrent"] == 3

        resp2 = await client.get("/api/v1/agents/coder")
        assert resp2.status_code == 200
        assert resp2.json()["display_name"] == "Code Agent"

    @pytest.mark.asyncio
    async def test_register_requires_auth(self, client: AsyncClient) -> None:
        resp = await client.post("/api/v1/agents", json={
            "agent_type": "test",
            "display_name": "Test",
        })
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_get_missing_agent(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/agents/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_agent(self, client: AsyncClient) -> None:
        token = await _get_token(client)
        await client.post("/api/v1/agents", json={
            "agent_type": "deleteme",
            "display_name": "Delete Me",
        }, headers=_auth(token))

        resp = await client.delete("/api/v1/agents/deleteme", headers=_auth(token))
        assert resp.status_code == 204

        resp2 = await client.get("/api/v1/agents/deleteme")
        assert resp2.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_missing_agent(self, client: AsyncClient) -> None:
        token = await _get_token(client)
        resp = await client.delete("/api/v1/agents/ghost", headers=_auth(token))
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_list_after_registration(self, client: AsyncClient) -> None:
        token = await _get_token(client)
        await client.post("/api/v1/agents", json={
            "agent_type": "a1",
            "display_name": "Agent 1",
        }, headers=_auth(token))
        await client.post("/api/v1/agents", json={
            "agent_type": "a2",
            "display_name": "Agent 2",
        }, headers=_auth(token))

        resp = await client.get("/api/v1/agents")
        assert resp.json()["total"] == 2
