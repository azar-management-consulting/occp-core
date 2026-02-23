"""Async SQLite persistence for agent configurations."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from orchestrator.models import AgentConfig
from store.database import Database


class AgentStore:
    """CRUD operations for agent configs backed by SQLite."""

    def __init__(self, db: Database) -> None:
        self._db = db

    async def upsert(self, config: AgentConfig) -> None:
        """Insert or replace an agent configuration."""
        now = datetime.now(timezone.utc).isoformat()
        await self._db.conn.execute(
            """INSERT INTO agent_configs
               (agent_type, display_name, capabilities, max_concurrent,
                timeout_seconds, metadata, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(agent_type) DO UPDATE SET
                 display_name=excluded.display_name,
                 capabilities=excluded.capabilities,
                 max_concurrent=excluded.max_concurrent,
                 timeout_seconds=excluded.timeout_seconds,
                 metadata=excluded.metadata,
                 updated_at=excluded.updated_at""",
            (
                config.agent_type,
                config.display_name,
                json.dumps(config.capabilities),
                config.max_concurrent,
                config.timeout_seconds,
                json.dumps(config.metadata),
                now,
                now,
            ),
        )
        await self._db.conn.commit()

    async def get(self, agent_type: str) -> AgentConfig | None:
        """Fetch a single agent config."""
        cursor = await self._db.conn.execute(
            "SELECT * FROM agent_configs WHERE agent_type = ?", (agent_type,)
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return self._row_to_config(row)

    async def list_all(self) -> list[AgentConfig]:
        """Return all agent configs ordered by display_name."""
        cursor = await self._db.conn.execute(
            "SELECT * FROM agent_configs ORDER BY display_name"
        )
        rows = await cursor.fetchall()
        return [self._row_to_config(r) for r in rows]

    async def delete(self, agent_type: str) -> bool:
        """Delete an agent config. Returns True if deleted."""
        cursor = await self._db.conn.execute(
            "DELETE FROM agent_configs WHERE agent_type = ?", (agent_type,)
        )
        await self._db.conn.commit()
        return cursor.rowcount > 0

    async def count(self) -> int:
        """Total agent config count."""
        cursor = await self._db.conn.execute("SELECT COUNT(*) FROM agent_configs")
        row = await cursor.fetchone()
        return row[0]

    @staticmethod
    def _row_to_config(row: Any) -> AgentConfig:
        """Convert sqlite Row to AgentConfig."""
        return AgentConfig(
            agent_type=row["agent_type"],
            display_name=row["display_name"],
            capabilities=json.loads(row["capabilities"]) if row["capabilities"] else [],
            max_concurrent=row["max_concurrent"],
            timeout_seconds=row["timeout_seconds"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
        )
