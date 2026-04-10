"""Tests for store.conversation_store — BrainConversation persistence.

Covers:
  - Save new conversation [1]
  - Get conversation by ID [1]
  - Get returns None for missing [1]
  - Update conversation phase [1]
  - Update with kwargs [1]
  - Get active by user (excludes completed/cancelled) [2]
  - Cleanup expired conversations [1]
  - Cleanup respects completed phase [1]
  - Multiple conversations per user [1]
  - Save idempotent (update existing) [1]
  - Round-trip JSON fields [1]
  - Plan_approved boolean persistence [1]
  - Feedback score persistence [1]
  - Cleanup with custom max_age [1]
  - Active ordering (newest first) [1]
Total: 16 tests
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta

import pytest
import pytest_asyncio

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from store.base import Base
from store.conversation_store import BrainConversationRow, ConversationStore


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
    cs = ConversationStore(factory)
    yield cs
    await engine.dispose()


# ---------------------------------------------------------------------------
# Save & Get
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_new_conversation(store: ConversationStore):
    await store.save("c1", "u1", "intake", original_message="hello")
    row = await store.get("c1")
    assert row is not None
    assert row["conversation_id"] == "c1"
    assert row["user_id"] == "u1"
    assert row["phase"] == "intake"
    assert row["original_message"] == "hello"


@pytest.mark.asyncio
async def test_get_by_id(store: ConversationStore):
    await store.save("c2", "u1", "plan")
    row = await store.get("c2")
    assert row is not None
    assert row["phase"] == "plan"


@pytest.mark.asyncio
async def test_get_missing_returns_none(store: ConversationStore):
    result = await store.get("nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_update_phase(store: ConversationStore):
    await store.save("c3", "u1", "intake")
    await store.save("c3", "u1", "confirm")
    row = await store.get("c3")
    assert row is not None
    assert row["phase"] == "confirm"


@pytest.mark.asyncio
async def test_update_with_kwargs(store: ConversationStore):
    await store.save("c4", "u1", "intake")
    await store.save("c4", "u1", "plan", execution_plan={"steps": [1, 2]})
    row = await store.get("c4")
    assert row is not None
    assert row["execution_plan"] == {"steps": [1, 2]}


# ---------------------------------------------------------------------------
# Active by user
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_active_excludes_completed(store: ConversationStore):
    await store.save("c5", "u2", "intake")
    await store.save("c6", "u2", "completed")
    await store.save("c7", "u2", "cancelled")
    active = await store.get_active_by_user("u2")
    ids = [a["conversation_id"] for a in active]
    assert "c5" in ids
    assert "c6" not in ids
    assert "c7" not in ids


@pytest.mark.asyncio
async def test_get_active_empty_for_unknown_user(store: ConversationStore):
    active = await store.get_active_by_user("nobody")
    assert active == []


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cleanup_expired(store: ConversationStore):
    old_ts = (datetime.now(timezone.utc) - timedelta(minutes=60)).isoformat()
    await store.save("c8", "u3", "intake")
    # Force old timestamp
    async with store._session_factory() as session:
        row = await session.get(BrainConversationRow, "c8")
        row.updated_at = old_ts
        await session.commit()
    deleted = await store.cleanup_expired(max_age_minutes=30)
    assert deleted == 1
    assert await store.get("c8") is None


@pytest.mark.asyncio
async def test_cleanup_respects_completed(store: ConversationStore):
    old_ts = (datetime.now(timezone.utc) - timedelta(minutes=60)).isoformat()
    await store.save("c9", "u3", "completed")
    async with store._session_factory() as session:
        row = await session.get(BrainConversationRow, "c9")
        row.updated_at = old_ts
        await session.commit()
    deleted = await store.cleanup_expired(max_age_minutes=30)
    assert deleted == 0
    assert await store.get("c9") is not None


@pytest.mark.asyncio
async def test_cleanup_custom_max_age(store: ConversationStore):
    ts_5min_ago = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    await store.save("c15", "u8", "monitor")
    async with store._session_factory() as session:
        row = await session.get(BrainConversationRow, "c15")
        row.updated_at = ts_5min_ago
        await session.commit()
    # 10 min cutoff — should NOT delete 5-min-old row
    assert await store.cleanup_expired(max_age_minutes=10) == 0
    # 3 min cutoff — should delete it
    assert await store.cleanup_expired(max_age_minutes=3) == 1


# ---------------------------------------------------------------------------
# Multiple / Idempotent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_multiple_conversations_per_user(store: ConversationStore):
    await store.save("c10", "u4", "intake")
    await store.save("c11", "u4", "plan")
    await store.save("c12", "u4", "confirm")
    active = await store.get_active_by_user("u4")
    assert len(active) == 3


@pytest.mark.asyncio
async def test_save_idempotent(store: ConversationStore):
    await store.save("c13", "u5", "intake", original_message="first")
    await store.save("c13", "u5", "intake", original_message="second")
    row = await store.get("c13")
    assert row is not None
    assert row["original_message"] == "second"


# ---------------------------------------------------------------------------
# JSON fields round-trip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_json_fields_roundtrip(store: ConversationStore):
    questions = ["Q1?", "Q2?"]
    answers = ["A1", "A2"]
    tasks = ["task-abc", "task-def"]
    results = [{"task_id": "task-abc", "status": "completed", "summary": "ok"}]
    await store.save(
        "c14", "u6", "deliver",
        clarifying_questions=questions,
        clarifying_answers=answers,
        dispatched_tasks=tasks,
        results=results,
    )
    row = await store.get("c14")
    assert row is not None
    assert row["clarifying_questions"] == questions
    assert row["clarifying_answers"] == answers
    assert row["dispatched_tasks"] == tasks
    assert row["results"] == results


# ---------------------------------------------------------------------------
# Boolean & Integer fields
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_plan_approved_persistence(store: ConversationStore):
    await store.save("c16", "u7", "confirm", plan_approved=True)
    row = await store.get("c16")
    assert row is not None
    assert row["plan_approved"] is True


@pytest.mark.asyncio
async def test_feedback_score_persistence(store: ConversationStore):
    await store.save("c17", "u7", "completed", feedback_score=4)
    row = await store.get("c17")
    assert row is not None
    assert row["feedback_score"] == 4


# ---------------------------------------------------------------------------
# Ordering
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_active_ordered_newest_first(store: ConversationStore):
    t1 = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    t2 = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    t3 = datetime.now(timezone.utc).isoformat()
    await store.save("old", "u9", "intake")
    await store.save("mid", "u9", "plan")
    await store.save("new", "u9", "confirm")
    # Force timestamps to ensure ordering
    async with store._session_factory() as session:
        for cid, ts in [("old", t1), ("mid", t2), ("new", t3)]:
            row = await session.get(BrainConversationRow, cid)
            row.updated_at = ts
        await session.commit()
    active = await store.get_active_by_user("u9")
    ids = [a["conversation_id"] for a in active]
    assert ids == ["new", "mid", "old"]
