"""Agent config persistence — SQLAlchemy 2.0 ORM backend."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.models import AgentConfig
from store.models import AgentConfigRow


class AgentStore:
    """CRUD operations for agent configs backed by SQLAlchemy."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(self, config: AgentConfig) -> None:
        """Insert or replace an agent configuration."""
        now = datetime.now(timezone.utc).isoformat()

        stmt = select(AgentConfigRow).where(
            AgentConfigRow.agent_type == config.agent_type
        )
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing is not None:
            existing.display_name = config.display_name
            existing.capabilities = config.capabilities
            existing.max_concurrent = config.max_concurrent
            existing.timeout_seconds = config.timeout_seconds
            existing.metadata_ = config.metadata
            existing.updated_at = now
        else:
            row = AgentConfigRow(
                agent_type=config.agent_type,
                display_name=config.display_name,
                capabilities=config.capabilities,
                max_concurrent=config.max_concurrent,
                timeout_seconds=config.timeout_seconds,
                metadata_=config.metadata,
                created_at=now,
                updated_at=now,
            )
            self._session.add(row)

        await self._session.commit()

    async def get(self, agent_type: str) -> AgentConfig | None:
        """Fetch a single agent config."""
        stmt = select(AgentConfigRow).where(
            AgentConfigRow.agent_type == agent_type
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self._row_to_config(row)

    async def list_all(self) -> list[AgentConfig]:
        """Return all agent configs ordered by display_name."""
        stmt = select(AgentConfigRow).order_by(AgentConfigRow.display_name)
        result = await self._session.execute(stmt)
        return [self._row_to_config(r) for r in result.scalars().all()]

    async def delete(self, agent_type: str) -> bool:
        """Delete an agent config. Returns True if deleted."""
        stmt = delete(AgentConfigRow).where(
            AgentConfigRow.agent_type == agent_type
        )
        result = await self._session.execute(stmt)
        await self._session.commit()
        return result.rowcount > 0

    async def count(self) -> int:
        """Total agent config count."""
        stmt = select(func.count()).select_from(AgentConfigRow)
        result = await self._session.execute(stmt)
        return result.scalar_one()

    @staticmethod
    def _row_to_config(row: AgentConfigRow) -> AgentConfig:
        """Convert ORM row to domain AgentConfig model."""
        return AgentConfig(
            agent_type=row.agent_type,
            display_name=row.display_name,
            capabilities=row.capabilities if row.capabilities else [],
            max_concurrent=row.max_concurrent,
            timeout_seconds=row.timeout_seconds,
            metadata=row.metadata_ if row.metadata_ else {},
        )
