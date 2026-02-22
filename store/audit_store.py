"""Async SQLite audit entry persistence."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from policy_engine.models import AuditEntry
from store.database import Database


class AuditStore:
    """Persist and retrieve tamper-evident audit entries."""

    def __init__(self, db: Database) -> None:
        self._db = db

    async def append(self, entry: AuditEntry) -> None:
        """Insert a new audit entry."""
        await self._db.conn.execute(
            """INSERT INTO audit_entries
               (id, timestamp, actor, action, task_id, detail, prev_hash, hash)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                entry.id,
                entry.timestamp.isoformat(),
                entry.actor,
                entry.action,
                entry.task_id,
                json.dumps(entry.detail),
                entry.prev_hash,
                entry.hash,
            ),
        )
        await self._db.conn.commit()

    async def list_all(self) -> list[AuditEntry]:
        """Return all audit entries ordered by timestamp."""
        cursor = await self._db.conn.execute(
            "SELECT * FROM audit_entries ORDER BY timestamp ASC"
        )
        rows = await cursor.fetchall()
        return [self._row_to_entry(r) for r in rows]

    async def count(self) -> int:
        """Total audit entry count."""
        cursor = await self._db.conn.execute(
            "SELECT COUNT(*) FROM audit_entries"
        )
        row = await cursor.fetchone()
        return row[0]

    async def get_last(self) -> AuditEntry | None:
        """Get the last audit entry (for hash chaining)."""
        cursor = await self._db.conn.execute(
            "SELECT * FROM audit_entries ORDER BY rowid DESC LIMIT 1"
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return self._row_to_entry(row)

    @staticmethod
    def _row_to_entry(row: Any) -> AuditEntry:
        """Convert sqlite Row to AuditEntry."""
        entry = AuditEntry(
            actor=row["actor"],
            action=row["action"],
            task_id=row["task_id"],
            detail=json.loads(row["detail"]) if row["detail"] else {},
        )
        object.__setattr__(entry, "id", row["id"])
        entry.timestamp = datetime.fromisoformat(row["timestamp"])
        entry.prev_hash = row["prev_hash"]
        entry.hash = row["hash"]
        return entry
