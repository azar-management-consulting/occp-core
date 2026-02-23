"""Alembic environment — async-capable with dual-backend support.

Supports both SQLite (render_as_batch) and PostgreSQL (online DDL).
Database URL resolved from OCCP_DATABASE_URL or config/settings.py.
"""

from __future__ import annotations

import asyncio
import logging
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from store.base import Base
from store.engine import is_sqlite

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


def _get_url() -> str:
    """Resolve database URL from settings or environment."""
    # Prefer explicit sqlalchemy.url from alembic.ini (e.g., via -x or direct edit)
    url = config.get_main_option("sqlalchemy.url")
    if url:
        return url

    # Fall back to OCCP settings
    try:
        from config.settings import Settings
        return Settings().database_url
    except Exception:
        return "sqlite+aiosqlite:///data/occp.db"


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode — emit SQL as script output."""
    url = _get_url()
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

    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = url

    # Engine configuration per dialect
    engine_kwargs: dict = {}
    if is_sqlite(url):
        engine_kwargs["poolclass"] = pool.StaticPool
        engine_kwargs["connect_args"] = {"check_same_thread": False}

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
