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

from sqlalchemy import event
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
_PG_POOL_RECYCLE = 3600  # seconds


def is_sqlite(url: str) -> bool:
    """Detect if the database URL targets SQLite."""
    return url.startswith("sqlite")


def _is_pgbouncer_url(url: str) -> bool:
    """Detect if the Postgres URL targets a PgBouncer/transaction-pool endpoint.

    Triggers:
    - Explicit ``:6543/`` port (Supabase pooler convention).
    - Substring ``pgbouncer`` anywhere in the URL (host/query/alias).

    When true, asyncpg's prepared-statement cache must be disabled because
    PgBouncer in transaction-pooling mode does not support prepared
    statements reliably across pooled connections.
    """
    lowered = url.lower()
    return ":6543/" in lowered or "pgbouncer" in lowered


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
        - ``postgresql+asyncpg://user:pass@host:6543/occp`` (pooler)
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
    """Configure engine for PostgreSQL (asyncpg driver).

    Pool configuration:
    - ``pool_size=5``, ``max_overflow=10`` — sensible defaults for
      moderate-traffic services; tune via env if needed.
    - ``pool_pre_ping=True`` — verify connection liveness before checkout.
    - ``pool_recycle=3600`` — recycle connections every hour to avoid
      server-side idle timeouts (Supabase defaults to 60s idle disconnects
      on the pooler, but the recycle covers long-lived direct connections).

    PgBouncer / Supabase transaction pooler (port 6543) caveat:
    asyncpg uses prepared statements by default and caches them per
    connection. Transaction-pool mode multiplexes connections across
    sessions, which breaks the cache. When ``_is_pgbouncer_url`` detects
    this, ``statement_cache_size=0`` is passed via ``connect_args``.

    A post-connect hook issues ``SELECT 1`` on each new connection to
    verify end-to-end connectivity early (fails fast on auth/DNS issues).
    """
    connect_args: dict = {}
    if _is_pgbouncer_url(url):
        # Critical for PgBouncer transaction mode — prepared statement cache
        # must be disabled to avoid "prepared statement does not exist" errors.
        connect_args["statement_cache_size"] = 0
        logger.info("PgBouncer/pooler URL detected — asyncpg statement cache disabled")

    engine = create_async_engine(
        url,
        echo=echo,
        pool_size=_PG_POOL_SIZE,
        max_overflow=_PG_MAX_OVERFLOW,
        pool_pre_ping=True,
        pool_recycle=_PG_POOL_RECYCLE,
        connect_args=connect_args,
    )

    # Post-connect hook: run SELECT 1 on every new DBAPI connection to
    # verify connectivity early. Fails fast on auth/DNS problems and
    # primes the connection before the first real query.
    _register_pg_connect_probe(engine)

    return engine


def _register_pg_connect_probe(engine: AsyncEngine) -> None:
    """Attach a ``connect`` event listener that runs ``SELECT 1``.

    The listener runs on the underlying sync engine (inside the async
    wrapper) because SQLAlchemy fires DBAPI-level events synchronously.
    Any failure propagates as a connection-time error so callers see it
    immediately instead of on the first query.
    """

    @event.listens_for(engine.sync_engine, "connect")
    def _probe_connection(dbapi_connection, _connection_record):  # type: ignore[no-untyped-def]
        try:
            cursor = dbapi_connection.cursor()
            try:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            finally:
                cursor.close()
            logger.debug("Postgres post-connect probe OK")
        except Exception as exc:  # pragma: no cover - surfaced to caller
            logger.error("Postgres post-connect probe failed: %s", exc)
            raise


def _sanitise_url(url: str) -> str:
    """Remove credentials from URL for logging."""
    if "@" in url:
        prefix, rest = url.split("@", 1)
        # Remove password from prefix  (e.g. driver://user:pass → driver://user:***)
        if ":" in prefix.rsplit("/", 1)[-1]:
            safe = prefix.rsplit(":", 1)[0] + ":***"
            return f"{safe}@{rest}"
    return url


# Re-export for test/migration-runner introspection
__all__ = [
    "create_engine_and_session",
    "is_sqlite",
    "_is_pgbouncer_url",
]
