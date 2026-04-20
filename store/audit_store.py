"""Audit entry persistence — SQLAlchemy 2.0 ORM backend.

The hash-chain logic remains in ``PolicyEngine``; this store only
persists and retrieves entries.

Since v0.10 the store enriches each entry with cost-attribution metadata
(token counts from ``response.usage``, model id, computed USD, cache hit
ratio).  All new columns are nullable so legacy entries remain valid.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from policy_engine.models import AuditEntry
from store.cost_calculator import compute_cache_hit_ratio, compute_usd
from store.models import AuditEntryRow


class AuditStore:
    """Persist and retrieve tamper-evident audit entries."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(self, entry: AuditEntry) -> None:
        """Insert a new audit entry, auto-computing USD + cache ratio."""
        # Auto-populate derived fields if the caller didn't supply them.
        if entry.computed_usd is None and entry.model_id is not None:
            entry.computed_usd = compute_usd(
                model_id=entry.model_id,
                input_tokens=entry.input_tokens,
                output_tokens=entry.output_tokens,
                cache_read_input_tokens=entry.cache_read_input_tokens,
                cache_creation_input_tokens=entry.cache_creation_input_tokens,
                ephemeral_5m_input_tokens=entry.ephemeral_5m_input_tokens,
                ephemeral_1h_input_tokens=entry.ephemeral_1h_input_tokens,
            )

        if entry.cache_hit_ratio is None and entry.input_tokens is not None:
            entry.cache_hit_ratio = compute_cache_hit_ratio(
                input_tokens=entry.input_tokens,
                cache_read_input_tokens=entry.cache_read_input_tokens,
            )

        row = AuditEntryRow(
            id=entry.id,
            timestamp=entry.timestamp.isoformat(),
            actor=entry.actor,
            action=entry.action,
            task_id=entry.task_id,
            detail=entry.detail,
            prev_hash=entry.prev_hash,
            hash=entry.hash,
            input_tokens=entry.input_tokens,
            output_tokens=entry.output_tokens,
            cache_read_input_tokens=entry.cache_read_input_tokens,
            cache_creation_input_tokens=entry.cache_creation_input_tokens,
            ephemeral_5m_input_tokens=entry.ephemeral_5m_input_tokens,
            ephemeral_1h_input_tokens=entry.ephemeral_1h_input_tokens,
            model_id=entry.model_id,
            computed_usd=entry.computed_usd,
            cache_hit_ratio=entry.cache_hit_ratio,
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

    async def prune_before(self, cutoff_iso: str) -> int:
        """Delete audit entries older than *cutoff_iso* (ISO-8601 string).

        Safe & idempotent — returns the number of pruned rows.
        Uses string comparison on the ISO timestamp column which is
        lexicographically equivalent to chronological order.
        """
        stmt = (
            delete(AuditEntryRow)
            .where(AuditEntryRow.timestamp < cutoff_iso)
        )
        result = await self._session.execute(stmt)
        await self._session.commit()
        return result.rowcount  # type: ignore[return-value]

    @staticmethod
    def _row_to_entry(row: AuditEntryRow) -> AuditEntry:
        """Convert ORM row to domain AuditEntry model."""
        entry = AuditEntry(
            actor=row.actor,
            action=row.action,
            task_id=row.task_id or "",
            detail=row.detail if row.detail else {},
            input_tokens=row.input_tokens,
            output_tokens=row.output_tokens,
            cache_read_input_tokens=row.cache_read_input_tokens,
            cache_creation_input_tokens=row.cache_creation_input_tokens,
            ephemeral_5m_input_tokens=row.ephemeral_5m_input_tokens,
            ephemeral_1h_input_tokens=row.ephemeral_1h_input_tokens,
            model_id=row.model_id,
            computed_usd=row.computed_usd,
            cache_hit_ratio=row.cache_hit_ratio,
        )
        object.__setattr__(entry, "id", row.id)
        entry.timestamp = datetime.fromisoformat(row.timestamp)
        entry.prev_hash = row.prev_hash
        entry.hash = row.hash
        return entry
