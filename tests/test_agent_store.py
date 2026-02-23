"""Tests for AgentStore persistence layer."""

from __future__ import annotations

import pytest

from orchestrator.models import AgentConfig
from store.database import Database
from store.agent_store import AgentStore


@pytest.fixture
async def agent_store(tmp_path):
    db_path = tmp_path / "test_agents.db"
    db = Database(url=f"sqlite+aiosqlite:///{db_path}")
    await db.connect()
    store = AgentStore(db.session())
    yield store
    await db.close()


class TestAgentStore:
    @pytest.mark.asyncio
    async def test_upsert_and_get(self, agent_store: AgentStore) -> None:
        cfg = AgentConfig(
            agent_type="test-agent",
            display_name="Test Agent",
            capabilities=["plan", "execute"],
            max_concurrent=2,
            timeout_seconds=120,
        )
        await agent_store.upsert(cfg)
        result = await agent_store.get("test-agent")
        assert result is not None
        assert result.agent_type == "test-agent"
        assert result.display_name == "Test Agent"
        assert result.capabilities == ["plan", "execute"]
        assert result.max_concurrent == 2
        assert result.timeout_seconds == 120

    @pytest.mark.asyncio
    async def test_upsert_overwrites(self, agent_store: AgentStore) -> None:
        cfg1 = AgentConfig(agent_type="x", display_name="Version 1")
        await agent_store.upsert(cfg1)
        cfg2 = AgentConfig(agent_type="x", display_name="Version 2", max_concurrent=5)
        await agent_store.upsert(cfg2)
        result = await agent_store.get("x")
        assert result is not None
        assert result.display_name == "Version 2"
        assert result.max_concurrent == 5

    @pytest.mark.asyncio
    async def test_get_missing(self, agent_store: AgentStore) -> None:
        result = await agent_store.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_all(self, agent_store: AgentStore) -> None:
        await agent_store.upsert(AgentConfig(agent_type="b-agent", display_name="B Agent"))
        await agent_store.upsert(AgentConfig(agent_type="a-agent", display_name="A Agent"))
        agents = await agent_store.list_all()
        assert len(agents) == 2
        # Sorted by display_name
        assert agents[0].display_name == "A Agent"
        assert agents[1].display_name == "B Agent"

    @pytest.mark.asyncio
    async def test_delete(self, agent_store: AgentStore) -> None:
        await agent_store.upsert(AgentConfig(agent_type="del-me", display_name="Delete Me"))
        assert await agent_store.count() == 1
        deleted = await agent_store.delete("del-me")
        assert deleted is True
        assert await agent_store.count() == 0

    @pytest.mark.asyncio
    async def test_delete_missing(self, agent_store: AgentStore) -> None:
        deleted = await agent_store.delete("nope")
        assert deleted is False

    @pytest.mark.asyncio
    async def test_count(self, agent_store: AgentStore) -> None:
        assert await agent_store.count() == 0
        await agent_store.upsert(AgentConfig(agent_type="one", display_name="One"))
        await agent_store.upsert(AgentConfig(agent_type="two", display_name="Two"))
        assert await agent_store.count() == 2

    @pytest.mark.asyncio
    async def test_metadata_round_trip(self, agent_store: AgentStore) -> None:
        cfg = AgentConfig(
            agent_type="meta-test",
            display_name="Meta Test",
            metadata={"model": "gpt-4o", "temperature": 0.7},
        )
        await agent_store.upsert(cfg)
        result = await agent_store.get("meta-test")
        assert result is not None
        assert result.metadata == {"model": "gpt-4o", "temperature": 0.7}
