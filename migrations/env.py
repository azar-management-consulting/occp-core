"""Alembic environment — async-capable with dual-backend support.

Supports both SQLite (render_as_batch) and PostgreSQL (online DDL).
Database URL resolution order:

1. ``-x url=...`` alembic command-line override (``config.get_main_option``).
2. ``OCCP_DATABASE_URL`` environment variable.
3. ``config.settings.Settings().database_url``.
4. Built-in SQLite default.

Safety
------
When the resolved URL targets a production-grade Postgres backend
(Supabase or any ``postgresql://`` scheme), destructive migrations require
the caller to explicitly opt in via ``-x env=migrate-production``. This
guard prevents accidental prod DB writes from developer shells.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from store.base import Base
from store.engine import _is_pgbouncer_url, is_sqlite

# Ensure all models are imported so their tables register on Base.metadata
import store.models  # noqa: F401

# Alembic Config object — gives access to alembic.ini values
config = context.config

# Set up logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

logger = logging.getLogger("alembic.env")

# Target metadata for 'autogenerate' support
target_metadata = Base.metadata

# Sentinel value callers pass via ``alembic -x env=migrate-production``
# to confirm they intend to mutate a production Postgres/Supabase DB.
_PROD_OVERRIDE_TOKEN = "migrate-production"


def _get_url() -> str:
    """Resolve database URL from CLI → env var → settings → default."""
    # 1. Explicit -x url=... or sqlalchemy.url set on the Config
    url = config.get_main_option("sqlalchemy.url")
    if url:
        return url

    # 2. Environment variable (preferred for CI / prod runners)
    env_url = os.environ.get("OCCP_DATABASE_URL")
    if env_url:
        return env_url

    # 3. OCCP settings (pydantic-settings reads .env too)
    try:
        from config.settings import Settings
        return Settings().database_url
    except Exception:
        return "sqlite+aiosqlite:///data/occp.db"


def _is_production_url(url: str) -> bool:
    """Heuristic: does this URL point at a prod Postgres/Supabase DB?"""
    lowered = url.lower()
    if lowered.startswith("sqlite"):
        return False
    return (
        "supabase" in lowered
        or lowered.startswith("postgresql")
        or lowered.startswith("postgres+")
        or _is_pgbouncer_url(lowered)
    )


def _guard_production(url: str) -> None:
    """Abort unless caller opted in to writing a production DB.

    Reads the ``env`` x-arg from the alembic command (``-x env=...``).
    Accepted override token: ``migrate-production``. Any other value
    (or a missing x-arg) causes the runner to print a warning and exit
    before any DDL is emitted.
    """
    if not _is_production_url(url):
        return

    x_args = context.get_x_argument(as_dictionary=True) or {}
    override = x_args.get("env")

    if override == _PROD_OVERRIDE_TOKEN:
        logger.warning(
            "Production migration explicitly authorised (env=%s) against %s",
            override,
            _redact(url),
        )
        return

    msg = (
        "REFUSING to run migrations against a production-grade database.\n"
        f"  URL: {_redact(url)}\n"
        f"  Re-run with: alembic -x env={_PROD_OVERRIDE_TOKEN} upgrade head\n"
        "  (Set OCCP_DATABASE_URL to a non-prod URL for local runs.)"
    )
    print(msg, file=sys.stderr)
    sys.exit(2)


def _redact(url: str) -> str:
    """Strip credentials before logging a URL."""
    if "@" not in url:
        return url
    prefix, rest = url.split("@", 1)
    if ":" in prefix.rsplit("/", 1)[-1]:
        safe = prefix.rsplit(":", 1)[0] + ":***"
        return f"{safe}@{rest}"
    return url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode — emit SQL as script output."""
    url = _get_url()
    _guard_production(url)
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=is_sqlite(url),
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Configure context and run migrations within a connection."""
    url = _get_url()
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=is_sqlite(url),
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with an async engine."""
    url = _get_url()
    _guard_production(url)

    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = url

    # Engine configuration per dialect
    engine_kwargs: dict = {}
    if is_sqlite(url):
        engine_kwargs["poolclass"] = pool.StaticPool
        engine_kwargs["connect_args"] = {"check_same_thread": False}
    elif _is_pgbouncer_url(url):
        # Same PgBouncer caveat as store.engine: disable prepared-statement
        # cache when routing through a transaction pooler.
        engine_kwargs["connect_args"] = {"statement_cache_size": 0}

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        **engine_kwargs,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for online migrations — delegates to async runner."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
