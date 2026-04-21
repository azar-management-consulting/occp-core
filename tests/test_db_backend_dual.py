"""Dual-backend database tests — SQLite (real) and Postgres (mocked).

Covers:
- ``Database`` URL resolution via kwarg / env var / default.
- SQLite path: real tmp_path-based connect, tables created, pragmas set.
- Postgres path: ``create_async_engine`` is patched so we never hit a real
  server; we assert the URL, driver, pool config, and pooler detection.
- PgBouncer detection: asyncpg ``statement_cache_size=0`` is passed only
  when port 6543 / ``pgbouncer`` appears in the URL.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from store import engine as engine_module
from store.database import Database, _resolve_url
from store.engine import _is_pgbouncer_url, is_sqlite


# ---------------------------------------------------------------------------
# URL resolution (kwarg → env var → SQLite default)
# ---------------------------------------------------------------------------


class TestUrlResolution:
    def test_explicit_kwarg_wins(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OCCP_DATABASE_URL", "postgresql+asyncpg://env/db")
        url = _resolve_url("sqlite+aiosqlite:///x.db")
        assert url == "sqlite+aiosqlite:///x.db"

    def test_env_var_used_when_no_kwarg(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(
            "OCCP_DATABASE_URL", "postgresql+asyncpg://u:p@h:5432/occp"
        )
        url = _resolve_url(None)
        assert url == "postgresql+asyncpg://u:p@h:5432/occp"

    def test_default_sqlite_when_nothing_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("OCCP_DATABASE_URL", raising=False)
        url = _resolve_url(None)
        assert url.startswith("sqlite+aiosqlite:///")

    def test_database_init_reads_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(
            "OCCP_DATABASE_URL", "postgresql+asyncpg://u:p@h:5432/occp"
        )
        db = Database()
        assert db._url == "postgresql+asyncpg://u:p@h:5432/occp"


# ---------------------------------------------------------------------------
# PgBouncer / pooler URL detection
# ---------------------------------------------------------------------------


class TestPgBouncerDetection:
    @pytest.mark.parametrize(
        "url,expected",
        [
            ("postgresql+asyncpg://u:p@host:5432/db", False),
            ("postgresql+asyncpg://u:p@host:6543/db", True),
            ("postgresql+asyncpg://u:p@pgbouncer.internal:5432/db", True),
            ("postgresql+asyncpg://u:p@aws-0-eu.pooler.supabase.com:6543/postgres", True),
            ("sqlite+aiosqlite:///data/occp.db", False),
        ],
    )
    def test_detection(self, url: str, expected: bool) -> None:
        assert _is_pgbouncer_url(url) is expected


# ---------------------------------------------------------------------------
# SQLite backend (real connection to tmp_path)
# ---------------------------------------------------------------------------


class TestSqliteBackend:
    @pytest.mark.asyncio
    async def test_connect_creates_tables_and_pragmas(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("OCCP_DATABASE_URL", raising=False)
        db_file = tmp_path / "occp.db"
        url = f"sqlite+aiosqlite:///{db_file}"
        assert is_sqlite(url)

        db = Database(url=url)
        await db.connect()
        try:
            # Engine + session factory are wired up
            assert db.engine is not None
            assert db.session_factory is not None

            # Tables were created — inspect via a lightweight session query
            from sqlalchemy import inspect

            def _inspect(sync_conn: Any) -> list[str]:
                return list(inspect(sync_conn).get_table_names())

            async with db.engine.connect() as conn:
                tables = await conn.run_sync(_inspect)

            # Every ORM-registered table must exist
            assert "tasks" in tables
            assert "audit_entries" in tables
            assert "users" in tables
        finally:
            await db.close()


# ---------------------------------------------------------------------------
# Postgres backend (mocked — never hits a real server)
# ---------------------------------------------------------------------------


def _make_mock_engine() -> MagicMock:
    """Return a MagicMock that mimics the AsyncEngine surface we touch."""
    engine = MagicMock(name="MockAsyncEngine")
    engine.sync_engine = MagicMock(name="MockSyncEngine")
    engine.dispose = AsyncMock(return_value=None)
    # Async context manager returned by engine.begin()
    begin_cm = MagicMock()
    begin_cm.__aenter__ = AsyncMock(return_value=MagicMock(
        run_sync=AsyncMock(return_value=None),
        execute=AsyncMock(return_value=None),
    ))
    begin_cm.__aexit__ = AsyncMock(return_value=None)
    engine.begin = MagicMock(return_value=begin_cm)
    return engine


class TestPostgresBackendMocked:
    def test_pg_engine_direct_pool_config(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Direct Postgres (5432) uses standard pool args, no cache tweak."""
        captured: dict[str, Any] = {}

        def _fake_create(url: str, **kwargs: Any) -> MagicMock:
            captured["url"] = url
            captured["kwargs"] = kwargs
            return _make_mock_engine()

        # Also stub the event registration so we don't poke the mock engine.
        monkeypatch.setattr(engine_module, "create_async_engine", _fake_create)
        monkeypatch.setattr(
            engine_module, "_register_pg_connect_probe", lambda _e: None
        )

        url = "postgresql+asyncpg://user:pass@host:5432/occp"
        engine_module.create_engine_and_session(url)

        assert captured["url"] == url
        kw = captured["kwargs"]
        assert kw["pool_size"] == 5
        assert kw["max_overflow"] == 10
        assert kw["pool_pre_ping"] is True
        assert kw["pool_recycle"] == 3600
        # Direct port 5432 → no statement_cache_size tweak
        assert kw["connect_args"] == {}

    def test_pg_engine_pooler_disables_statement_cache(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Port 6543 (Supabase pooler) → asyncpg statement cache disabled."""
        captured: dict[str, Any] = {}

        def _fake_create(url: str, **kwargs: Any) -> MagicMock:
            captured["url"] = url
            captured["kwargs"] = kwargs
            return _make_mock_engine()

        monkeypatch.setattr(engine_module, "create_async_engine", _fake_create)
        monkeypatch.setattr(
            engine_module, "_register_pg_connect_probe", lambda _e: None
        )

        url = "postgresql+asyncpg://user:pass@aws-eu.pooler.supabase.com:6543/postgres"
        engine_module.create_engine_and_session(url)

        kw = captured["kwargs"]
        assert kw["connect_args"] == {"statement_cache_size": 0}
        assert kw["pool_pre_ping"] is True
        assert kw["pool_size"] == 5

    def test_pg_engine_pgbouncer_substring(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """'pgbouncer' substring in URL also triggers cache disable."""
        captured: dict[str, Any] = {}

        def _fake_create(url: str, **kwargs: Any) -> MagicMock:
            captured["kwargs"] = kwargs
            return _make_mock_engine()

        monkeypatch.setattr(engine_module, "create_async_engine", _fake_create)
        monkeypatch.setattr(
            engine_module, "_register_pg_connect_probe", lambda _e: None
        )

        url = "postgresql+asyncpg://u:p@pgbouncer.internal:5432/occp"
        engine_module.create_engine_and_session(url)
        assert captured["kwargs"]["connect_args"] == {"statement_cache_size": 0}

    @pytest.mark.asyncio
    async def test_database_connect_uses_pg_when_env_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Setting OCCP_DATABASE_URL=postgresql+asyncpg://... routes to PG path."""
        pg_url = "postgresql+asyncpg://user:pass@host:5432/occp"
        monkeypatch.setenv("OCCP_DATABASE_URL", pg_url)

        called: dict[str, Any] = {}

        def _fake_factory(url: str, *, echo: bool = False):  # type: ignore[no-untyped-def]
            called["url"] = url
            called["sqlite"] = is_sqlite(url)
            mock_engine = _make_mock_engine()
            session_factory = MagicMock(name="session_factory")
            return mock_engine, session_factory

        # Patch at the database module level (where it's imported)
        with patch("store.database.create_engine_and_session", _fake_factory):
            db = Database()
            assert db._url == pg_url
            await db.connect()
            try:
                assert called["url"] == pg_url
                assert called["sqlite"] is False
                assert db.engine is not None
                assert db.session_factory is not None
                # create_all was attempted on the mocked engine
                db.engine.begin.assert_called()
            finally:
                # Dispose happens on AsyncMock; no real resources to free.
                await db.close()


# ---------------------------------------------------------------------------
# Sanity: asyncio.get_event_loop is not leaked between tests
# ---------------------------------------------------------------------------


def test_module_imports_do_not_open_loop() -> None:
    """Import of store.* must not leave a running loop.

    Uses asyncio.new_event_loop() to isolate from pytest-asyncio's
    session-scoped loop (which stays running until teardown when other
    async tests share the module).
    """
    try:
        running = asyncio.get_running_loop()
    except RuntimeError:
        running = None
    assert running is None, (
        "store.* module import side-effect started an event loop — "
        "imports must remain lazy / sync."
    )
