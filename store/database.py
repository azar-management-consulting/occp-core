"""Async database connection manager — SQLAlchemy 2.0 backend.

The ``Database`` class preserves the legacy API used by tests and lifespan
bootstrap while delegating to the new ``engine.py`` async engine factory.
Table creation now uses ``Base.metadata.create_all`` instead of inline DDL.
"""

from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from store.base import Base
from store.engine import create_engine_and_session, is_sqlite

# Ensure all ORM models are imported so their tables register on Base.metadata
import store.models  # noqa: F401

logger = logging.getLogger(__name__)


class Database:
    """Async database wrapper with ORM-based schema initialisation.

    This class exists for backward compatibility with existing tests
    and the ``api.app`` lifespan.  New code should use ``engine.py``
    and ``async_sessionmaker`` directly.
    """

    def __init__(self, url: str = "sqlite+aiosqlite:///data/occp.db") -> None:
        self._url = url
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
