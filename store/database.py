"""Async database connection manager — SQLAlchemy 2.0 backend.

The ``Database`` class preserves the legacy API used by tests and lifespan
bootstrap while delegating to the new ``engine.py`` async engine factory.
Table creation now uses ``Base.metadata.create_all`` instead of inline DDL.

Resolution of the backend URL follows a three-tier fallback order:

1. **Explicit kwarg** — ``Database(url="...")`` passed by the caller.
2. **Environment variable** — ``OCCP_DATABASE_URL`` (covers both local
   SQLite and production Postgres/Supabase deployments).
3. **SQLite default** — ``sqlite+aiosqlite:///data/occp.db`` for local dev.

Modes
-----
- SQLite (aiosqlite): file-based, local-only, zero-config. Default.
- PostgreSQL direct (asyncpg, port 5432): standard pool semantics.
- PostgreSQL via PgBouncer/Supabase pooler (port 6543): asyncpg prepared
  statement cache must be disabled — handled transparently by
  ``store.engine._create_pg_engine``.
"""

from __future__ import annotations

import logging
import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from store.base import Base
from store.engine import create_engine_and_session, is_sqlite

# Ensure all ORM models are imported so their tables register on Base.metadata
import store.models  # noqa: F401

logger = logging.getLogger(__name__)

# Default URL used when neither an explicit kwarg nor OCCP_DATABASE_URL is set.
_SQLITE_DEFAULT_URL = "sqlite+aiosqlite:///data/occp.db"


def _resolve_url(explicit: str | None) -> str:
    """Resolve the backend URL from kwarg → env var → SQLite default."""
    if explicit:
        return explicit
    env_url = os.environ.get("OCCP_DATABASE_URL")
    if env_url:
        return env_url
    return _SQLITE_DEFAULT_URL


class Database:
    """Async database wrapper with ORM-based schema initialisation.

    This class exists for backward compatibility with existing tests
    and the ``api.app`` lifespan.  New code should use ``engine.py``
    and ``async_sessionmaker`` directly.

    Backend URL resolution (first non-empty wins):

    1. ``url`` kwarg passed to ``__init__``.
    2. ``OCCP_DATABASE_URL`` environment variable.
    3. Built-in SQLite default (``sqlite+aiosqlite:///data/occp.db``).

    Supported backends
    ------------------
    - ``sqlite+aiosqlite://...`` — default, local file or ``:memory:``.
    - ``postgresql+asyncpg://...`` — direct Postgres or Supabase (5432).
    - ``postgresql+asyncpg://...:6543/...`` — Supabase transaction pooler;
      prepared-statement cache is automatically disabled.
    """

    def __init__(self, url: str | None = None) -> None:
        self._url = _resolve_url(url)
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None

    async def connect(self) -> None:
        """Create engine, initialise tables, configure session factory."""
        engine, session_factory = create_engine_and_session(self._url)
        self._engine = engine
        self._session_factory = session_factory

        # Create tables if they don't exist (replaces inline DDL)
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

            # SQLite-specific pragmas
            if is_sqlite(self._url):
                await conn.execute(text("PRAGMA journal_mode=WAL"))
                await conn.execute(text("PRAGMA foreign_keys=ON"))

        logger.info("Database connected: %s", self._url)

    async def close(self) -> None:
        """Dispose of the engine and release all pooled connections."""
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None

    @property
    def engine(self) -> AsyncEngine:
        """The underlying SQLAlchemy async engine."""
        assert self._engine is not None, "Database not connected"
        return self._engine

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        """Session factory — use ``async with db.session_factory() as s:``."""
        assert self._session_factory is not None, "Database not connected"
        return self._session_factory

    def session(self) -> AsyncSession:
        """Create a new AsyncSession (caller must manage commit/close)."""
        return self.session_factory()
