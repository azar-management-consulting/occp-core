"""Async SQLAlchemy engine factory with dual-backend support.

Creates an ``AsyncEngine`` and ``async_sessionmaker`` configured for
either SQLite (aiosqlite) or PostgreSQL (asyncpg) based on the URL.

Usage::

    engine, SessionLocal = create_engine_and_session("sqlite+aiosqlite:///data/occp.db")
    async with SessionLocal() as session:
        ...
"""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

logger = logging.getLogger(__name__)

# ── Defaults ──────────────────────────────────────────────────────────
_SQLITE_PRAGMAS = "journal_mode=WAL&foreign_keys=ON"
_PG_POOL_SIZE = 5
_PG_MAX_OVERFLOW = 10


def is_sqlite(url: str) -> bool:
    """Detect if the database URL targets SQLite."""
    return url.startswith("sqlite")


def create_engine_and_session(
    url: str,
    *,
    echo: bool = False,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    """Build an async engine + session factory from a database URL.

    Parameters
    ----------
    url:
        SQLAlchemy async URL, e.g.:
        - ``sqlite+aiosqlite:///data/occp.db``
        - ``postgresql+asyncpg://user:pass@host:5432/occp``
    echo:
        If ``True``, emit SQL to the logger.

    Returns
    -------
    tuple of (AsyncEngine, async_sessionmaker)
    """
    if is_sqlite(url):
        engine = _create_sqlite_engine(url, echo=echo)
    else:
        engine = _create_pg_engine(url, echo=echo)

    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    logger.info("Database engine created: %s", _sanitise_url(url))
    return engine, session_factory


def _create_sqlite_engine(url: str, *, echo: bool) -> AsyncEngine:
    """Configure engine for SQLite (aiosqlite driver)."""
    # Ensure the parent directory exists for file-based SQLite
    path = url.replace("sqlite+aiosqlite:///", "").replace("sqlite:///", "")
    if path and path != ":memory:":
        db_path = Path(path)
        db_path.parent.mkdir(parents=True, exist_ok=True)

    # StaticPool: single connection shared across all coroutines.
    # aiosqlite serialises writes internally, so this is safe.
    return create_async_engine(
        url,
        echo=echo,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )


def _create_pg_engine(url: str, *, echo: bool) -> AsyncEngine:
    """Configure engine for PostgreSQL (asyncpg driver)."""
    return create_async_engine(
        url,
        echo=echo,
        pool_size=_PG_POOL_SIZE,
        max_overflow=_PG_MAX_OVERFLOW,
        pool_pre_ping=True,
    )


def _sanitise_url(url: str) -> str:
    """Remove credentials from URL for logging."""
    if "@" in url:
        prefix, rest = url.split("@", 1)
        # Remove password from prefix  (e.g. driver://user:pass → driver://user:***)
        if ":" in prefix.rsplit("/", 1)[-1]:
            safe = prefix.rsplit(":", 1)[0] + ":***"
            return f"{safe}@{rest}"
    return url
