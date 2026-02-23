"""Async SQLite connection manager with auto-migration."""

from __future__ import annotations

import logging
from pathlib import Path

import aiosqlite

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT DEFAULT '',
    agent_type  TEXT DEFAULT 'default',
    risk_level  TEXT DEFAULT 'low',
    status      TEXT DEFAULT 'pending',
    plan        TEXT,          -- JSON
    result      TEXT,          -- JSON
    error       TEXT,
    metadata    TEXT DEFAULT '{}',  -- JSON
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_entries (
    id          TEXT PRIMARY KEY,
    timestamp   TEXT NOT NULL,
    actor       TEXT NOT NULL,
    action      TEXT NOT NULL,
    task_id     TEXT,
    detail      TEXT DEFAULT '{}',  -- JSON
    prev_hash   TEXT NOT NULL,
    hash        TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_created ON tasks(created_at);
CREATE TABLE IF NOT EXISTS agent_configs (
    agent_type      TEXT PRIMARY KEY,
    display_name    TEXT NOT NULL,
    capabilities    TEXT DEFAULT '[]',  -- JSON array
    max_concurrent  INTEGER DEFAULT 1,
    timeout_seconds INTEGER DEFAULT 300,
    metadata        TEXT DEFAULT '{}',  -- JSON
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_task ON audit_entries(task_id);
CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_entries(timestamp);
"""


class Database:
    """Async SQLite wrapper with connection pooling and schema init."""

    def __init__(self, url: str = "sqlite+aiosqlite:///data/occp.db") -> None:
        # Strip driver prefix to get file path
        path = url.replace("sqlite+aiosqlite:///", "").replace("sqlite:///", "")
        self._path = path
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        """Open connection and ensure schema exists."""
        # Ensure parent directory exists
        db_path = Path(self._path)
        db_path.parent.mkdir(parents=True, exist_ok=True)

        self._conn = await aiosqlite.connect(self._path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")
        await self._conn.executescript(_SCHEMA)
        await self._conn.commit()
        logger.info("Database connected: %s", self._path)

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None

    @property
    def conn(self) -> aiosqlite.Connection:
        assert self._conn is not None, "Database not connected"
        return self._conn
