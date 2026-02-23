"""Audit entry persistence — SQLAlchemy 2.0 ORM backend.

The hash-chain logic remains in ``PolicyEngine``; this store only
persists and retrieves entries.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from policy_engine.models import AuditEntry
from store.models import AuditEntryRow


class AuditStore:
    """Persist and retrieve tamper-evident audit entries."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(self, entry: AuditEntry) -> None:
        """Insert a new audit entry."""
        row = AuditEntryRow(
            id=entry.id,
            timestamp=entry.timestamp.isoformat(),
            actor=entry.actor,
            action=entry.action,
            task_id=entry.task_id,
            detail=entry.detail,
            prev_hash=entry.prev_hash,
            hash=entry.hash,
        )
        self._session.add(row)
        await self._session.commit()

    async def list_all(self) -> list[AuditEntry]:
        """Return all audit entries ordered by timestamp."""
        stmt = select(AuditEntryRow).order_by(AuditEntryRow.timestamp.asc())
        result = await self._session.execute(stmt)
        return [self._row_to_entry(r) for r in result.scalars().all()]

    async def count(self) -> int:
        """Total audit entry count."""
        stmt = select(func.count()).select_from(AuditEntryRow)
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def get_last(self) -> AuditEntry | None:
        """Get the last audit entry (for hash chaining)."""
        stmt = (
            select(AuditEntryRow)
            .order_by(AuditEntryRow.timestamp.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self._row_to_entry(row)

    @staticmethod
    def _row_to_entry(row: AuditEntryRow) -> AuditEntry:
        """Convert ORM row to domain AuditEntry model."""
        entry = AuditEntry(
            actor=row.actor,
            action=row.action,
            task_id=row.task_id or "",
            detail=row.detail if row.detail else {},
        )
        object.__setattr__(entry, "id", row.id)
        entry.timestamp = datetime.fromisoformat(row.timestamp)
        entry.prev_hash = row.prev_hash
        entry.hash = row.hash
        return entry
