"""Tests for store – async SQLite persistence for tasks and audit entries."""

from __future__ import annotations

import pytest

from orchestrator.models import Task, TaskStatus, RiskLevel
from policy_engine.models import AuditEntry
from store.database import Database
from store.task_store import TaskStore
from store.audit_store import AuditStore


@pytest.fixture
async def db(tmp_path):
    """Create an in-memory database for testing."""
    d = Database(url=f"sqlite+aiosqlite:///{tmp_path}/test.db")
    await d.connect()
    yield d
    await d.close()


@pytest.fixture
async def task_store(db):
    return TaskStore(db.session())


@pytest.fixture
async def audit_store(db):
    return AuditStore(db.session())


def _make_task(name: str = "test-task") -> Task:
    return Task(name=name, description=f"Test: {name}", agent_type="default")


# ── TaskStore Tests ──────────────────────────────────────────────────


class TestTaskStore:
    async def test_add_and_get(self, task_store: TaskStore) -> None:
        task = _make_task()
        await task_store.add(task)
        loaded = await task_store.get(task.id)
        assert loaded is not None
        assert loaded.id == task.id
        assert loaded.name == "test-task"

    async def test_get_missing(self, task_store: TaskStore) -> None:
        result = await task_store.get("nonexistent")
        assert result is None

    async def test_list_all(self, task_store: TaskStore) -> None:
        for i in range(3):
            await task_store.add(_make_task(f"task-{i}"))
        tasks = await task_store.list_all()
        assert len(tasks) == 3

    async def test_update(self, task_store: TaskStore) -> None:
        task = _make_task()
        await task_store.add(task)
        task.transition(TaskStatus.PLANNING)
        task.plan = {"steps": ["analyze"]}
        await task_store.update(task)
        loaded = await task_store.get(task.id)
        assert loaded is not None
        assert loaded.status == TaskStatus.PLANNING
        assert loaded.plan == {"steps": ["analyze"]}

    async def test_delete(self, task_store: TaskStore) -> None:
        task = _make_task()
        await task_store.add(task)
        deleted = await task_store.delete(task.id)
        assert deleted is True
        assert await task_store.get(task.id) is None

    async def test_delete_missing(self, task_store: TaskStore) -> None:
        deleted = await task_store.delete("nonexistent")
        assert deleted is False

    async def test_count(self, task_store: TaskStore) -> None:
        assert await task_store.count() == 0
        await task_store.add(_make_task("a"))
        await task_store.add(_make_task("b"))
        assert await task_store.count() == 2

    async def test_risk_level_persisted(self, task_store: TaskStore) -> None:
        task = Task(name="risky", description="high risk", agent_type="default", risk_level=RiskLevel.HIGH)
        await task_store.add(task)
        loaded = await task_store.get(task.id)
        assert loaded is not None
        assert loaded.risk_level == RiskLevel.HIGH

    async def test_metadata_persisted(self, task_store: TaskStore) -> None:
        task = _make_task()
        task.metadata = {"key": "value", "count": 42}
        await task_store.add(task)
        loaded = await task_store.get(task.id)
        assert loaded is not None
        assert loaded.metadata == {"key": "value", "count": 42}


# ── AuditStore Tests ─────────────────────────────────────────────────


class TestAuditStore:
    async def test_append_and_list(self, audit_store: AuditStore) -> None:
        entry = AuditEntry(actor="system", action="test", task_id="t1")
        entry.prev_hash = "0" * 64
        entry.hash = entry.compute_hash(entry.prev_hash)
        await audit_store.append(entry)
        entries = await audit_store.list_all()
        assert len(entries) == 1
        assert entries[0].id == entry.id

    async def test_count(self, audit_store: AuditStore) -> None:
        assert await audit_store.count() == 0
        entry = AuditEntry(actor="system", action="test")
        entry.prev_hash = "0" * 64
        entry.hash = entry.compute_hash(entry.prev_hash)
        await audit_store.append(entry)
        assert await audit_store.count() == 1

    async def test_get_last(self, audit_store: AuditStore) -> None:
        for i in range(3):
            entry = AuditEntry(actor="system", action=f"action-{i}")
            entry.prev_hash = "0" * 64
            entry.hash = entry.compute_hash(entry.prev_hash)
            await audit_store.append(entry)
        last = await audit_store.get_last()
        assert last is not None
        assert last.action == "action-2"


# ── Database Tests ───────────────────────────────────────────────────


class TestDatabase:
    async def test_connect_creates_tables(self, tmp_path) -> None:
        from sqlalchemy import inspect as sa_inspect

        db = Database(url=f"sqlite+aiosqlite:///{tmp_path}/fresh.db")
        await db.connect()
        async with db.engine.connect() as conn:
            tables = await conn.run_sync(
                lambda sync_conn: sa_inspect(sync_conn).get_table_names()
            )
        assert "tasks" in tables
        assert "audit_entries" in tables
        assert "agent_configs" in tables
        await db.close()
