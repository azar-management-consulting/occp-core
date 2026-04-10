"""Tests for store.approval_store — ConfirmationGate persistence.

Covers:
  - Save pending approval [1]
  - Get by task_id [1]
  - Get returns None for missing [1]
  - Get pending for chat_id (excludes expired) [1]
  - Get pending for chat_id (excludes non-pending) [1]
  - Update status to approved [1]
  - Update status to rejected [1]
  - Update status to timeout [1]
  - Update returns False for missing [1]
  - Cleanup expired [1]
  - Cleanup skips non-pending [1]
  - Multiple approvals per chat [1]
  - Save idempotent (merge/upsert) [1]
  - Custom timeout_seconds [1]
  - Pending ordered newest first [1]
  - Row dict contains all fields [1]
Total: 16 tests
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta

import pytest
import pytest_asyncio

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from store.base import Base
from store.approval_store import ApprovalStore, PendingApprovalRow


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def store():
    """In-memory SQLite store, fresh per test."""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    s = ApprovalStore(factory)
    yield s
    await engine.dispose()


# ---------------------------------------------------------------------------
# Save & Get
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_pending_approval(store: ApprovalStore):
    await store.save("t1", 100, "Deploy to prod", "high", "deploy-agent")
    row = await store.get("t1")
    assert row is not None
    assert row["task_id"] == "t1"
    assert row["chat_id"] == 100
    assert row["plan_summary"] == "Deploy to prod"
    assert row["risk_level"] == "high"
    assert row["status"] == "pending"
    assert row["agent_type"] == "deploy-agent"


@pytest.mark.asyncio
async def test_get_by_task_id(store: ApprovalStore):
    await store.save("t2", 200, "Run tests", "medium", "test-agent")
    row = await store.get("t2")
    assert row is not None
    assert row["plan_summary"] == "Run tests"


@pytest.mark.asyncio
async def test_get_missing_returns_none(store: ApprovalStore):
    result = await store.get("nonexistent")
    assert result is None


# ---------------------------------------------------------------------------
# Get pending for chat
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_pending_excludes_expired(store: ApprovalStore):
    await store.save("t3", 300, "Plan A", "medium", timeout_seconds=300)
    # Force expiry in the past
    async with store._session_factory() as session:
        row = await session.get(PendingApprovalRow, "t3")
        row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        await session.commit()
    pending = await store.get_pending_for_chat(300)
    assert len(pending) == 0


@pytest.mark.asyncio
async def test_get_pending_excludes_non_pending(store: ApprovalStore):
    await store.save("t4", 400, "Plan B", "high")
    await store.update_status("t4", "approved")
    pending = await store.get_pending_for_chat(400)
    assert len(pending) == 0


# ---------------------------------------------------------------------------
# Update status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_status_approved(store: ApprovalStore):
    await store.save("t5", 500, "Plan C", "medium")
    result = await store.update_status("t5", "approved")
    assert result is True
    row = await store.get("t5")
    assert row is not None
    assert row["status"] == "approved"


@pytest.mark.asyncio
async def test_update_status_rejected(store: ApprovalStore):
    await store.save("t6", 600, "Plan D", "high")
    result = await store.update_status("t6", "rejected")
    assert result is True
    row = await store.get("t6")
    assert row is not None
    assert row["status"] == "rejected"


@pytest.mark.asyncio
async def test_update_status_timeout(store: ApprovalStore):
    await store.save("t7", 700, "Plan E", "critical")
    result = await store.update_status("t7", "timeout")
    assert result is True
    row = await store.get("t7")
    assert row is not None
    assert row["status"] == "timeout"


@pytest.mark.asyncio
async def test_update_returns_false_for_missing(store: ApprovalStore):
    result = await store.update_status("nonexistent", "approved")
    assert result is False


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cleanup_expired(store: ApprovalStore):
    await store.save("t8", 800, "Plan F", "medium", timeout_seconds=300)
    # Force expiry in the past
    async with store._session_factory() as session:
        row = await session.get(PendingApprovalRow, "t8")
        row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=10)
        await session.commit()
    deleted = await store.cleanup_expired()
    assert deleted == 1
    assert await store.get("t8") is None


@pytest.mark.asyncio
async def test_cleanup_skips_non_pending(store: ApprovalStore):
    await store.save("t9", 900, "Plan G", "high", timeout_seconds=300)
    await store.update_status("t9", "approved")
    # Force expiry in the past
    async with store._session_factory() as session:
        row = await session.get(PendingApprovalRow, "t9")
        row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=10)
        await session.commit()
    deleted = await store.cleanup_expired()
    assert deleted == 0
    assert await store.get("t9") is not None


# ---------------------------------------------------------------------------
# Multiple / Idempotent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_multiple_approvals_per_chat(store: ApprovalStore):
    await store.save("t10", 1000, "Plan H", "medium")
    await store.save("t11", 1000, "Plan I", "high")
    await store.save("t12", 1000, "Plan J", "critical")
    pending = await store.get_pending_for_chat(1000)
    assert len(pending) == 3


@pytest.mark.asyncio
async def test_save_idempotent(store: ApprovalStore):
    await store.save("t13", 1100, "Plan K v1", "medium")
    await store.save("t13", 1100, "Plan K v2", "high")
    row = await store.get("t13")
    assert row is not None
    assert row["plan_summary"] == "Plan K v2"
    assert row["risk_level"] == "high"
    # Only one row, not two
    pending = await store.get_pending_for_chat(1100)
    assert len(pending) == 1


# ---------------------------------------------------------------------------
# Custom timeout & ordering
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_custom_timeout_seconds(store: ApprovalStore):
    await store.save("t14", 1200, "Plan L", "medium", timeout_seconds=600)
    row = await store.get("t14")
    assert row is not None
    # expires_at should be ~600s from created_at
    created = datetime.fromisoformat(row["created_at"])
    expires = datetime.fromisoformat(row["expires_at"])
    diff = (expires - created).total_seconds()
    assert 598 <= diff <= 602  # allow small clock drift


@pytest.mark.asyncio
async def test_pending_ordered_newest_first(store: ApprovalStore):
    t1 = datetime.now(timezone.utc) - timedelta(minutes=10)
    t2 = datetime.now(timezone.utc) - timedelta(minutes=5)
    t3 = datetime.now(timezone.utc)
    future = datetime.now(timezone.utc) + timedelta(hours=1)

    await store.save("old", 1300, "Plan old", "medium")
    await store.save("mid", 1300, "Plan mid", "medium")
    await store.save("new", 1300, "Plan new", "medium")
    # Force created_at timestamps
    async with store._session_factory() as session:
        for tid, ts in [("old", t1), ("mid", t2), ("new", t3)]:
            row = await session.get(PendingApprovalRow, tid)
            row.created_at = ts
            row.expires_at = future
        await session.commit()
    pending = await store.get_pending_for_chat(1300)
    ids = [p["task_id"] for p in pending]
    assert ids == ["new", "mid", "old"]


# ---------------------------------------------------------------------------
# Dict completeness
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_row_dict_contains_all_fields(store: ApprovalStore):
    await store.save("t15", 1400, "Plan M", "critical", "seo-agent", 120)
    row = await store.get("t15")
    assert row is not None
    expected_keys = {
        "task_id", "chat_id", "plan_summary", "risk_level",
        "status", "agent_type", "created_at", "expires_at",
    }
    assert set(row.keys()) == expected_keys
    assert row["created_at"] is not None
    assert row["expires_at"] is not None
