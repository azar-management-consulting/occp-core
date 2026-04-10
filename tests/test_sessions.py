"""Tests for SessionManager — REQ-CORE-02: Session Tiers, Lifecycle, Persistence.

Covers:
- SessionTier / SessionState enum values
- TierConstraints for all 3 tiers
- Session creation (defaults, owner_id validation)
- Session lifecycle: created → active → suspended → terminated
- Invalid state transitions
- Message management: add, eviction, get_history
- Cannot add messages to non-active session
- Participant management (add, remove, capacity)
- Task registration and completion (concurrent task limits)
- Idle session cleanup
- Terminated session cleanup
- Stage checking per tier
- Session stats
- Session.to_dict serialization
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from orchestrator.sessions import (
    Session,
    SessionCapacityError,
    SessionError,
    SessionManager,
    SessionNotFoundError,
    SessionState,
    SessionStateError,
    SessionTier,
    TIER_CONSTRAINTS,
    TierConstraints,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TestEnums:
    def test_session_tier_values(self) -> None:
        assert SessionTier.MAIN == "main"
        assert SessionTier.DM == "dm"
        assert SessionTier.GROUP == "group"

    def test_session_state_values(self) -> None:
        assert SessionState.CREATED == "created"
        assert SessionState.ACTIVE == "active"
        assert SessionState.SUSPENDED == "suspended"
        assert SessionState.TERMINATED == "terminated"

    def test_four_tiers(self) -> None:
        assert len(SessionTier) == 4

    def test_four_states(self) -> None:
        assert len(SessionState) == 4


# ---------------------------------------------------------------------------
# Tier constraints
# ---------------------------------------------------------------------------


class TestTierConstraints:
    def test_main_full_access(self) -> None:
        c = TIER_CONSTRAINTS[SessionTier.MAIN]
        assert c.can_execute is True
        assert c.can_ship is True
        assert "execute" in c.allowed_stages
        assert "ship" in c.allowed_stages
        assert c.max_participants == 1

    def test_dm_restricted(self) -> None:
        c = TIER_CONSTRAINTS[SessionTier.DM]
        assert c.can_execute is False
        assert c.can_ship is False
        assert "execute" not in c.allowed_stages
        assert "ship" not in c.allowed_stages
        assert c.max_participants == 2

    def test_group_multi_user(self) -> None:
        c = TIER_CONSTRAINTS[SessionTier.GROUP]
        assert c.can_execute is True
        assert c.max_participants == 50
        assert c.max_history_messages == 2000

    def test_all_tiers_have_constraints(self) -> None:
        for tier in SessionTier:
            assert tier in TIER_CONSTRAINTS


# ---------------------------------------------------------------------------
# Session creation
# ---------------------------------------------------------------------------


class TestSessionCreation:
    def test_create_basic(self) -> None:
        mgr = SessionManager()
        s = mgr.create("user-1")
        assert s.owner_id == "user-1"
        assert s.tier == SessionTier.MAIN
        assert s.state == SessionState.CREATED
        assert len(s.session_id) == 16
        assert s.participants == ["user-1"]

    def test_create_dm(self) -> None:
        mgr = SessionManager()
        s = mgr.create("user-1", tier=SessionTier.DM)
        assert s.tier == SessionTier.DM

    def test_create_group(self) -> None:
        mgr = SessionManager()
        s = mgr.create("user-1", tier=SessionTier.GROUP, context={"project": "x"})
        assert s.tier == SessionTier.GROUP
        assert s.context["project"] == "x"

    def test_create_empty_owner_raises(self) -> None:
        mgr = SessionManager()
        with pytest.raises(SessionError, match="owner_id must not be empty"):
            mgr.create("")

    def test_create_whitespace_owner_raises(self) -> None:
        mgr = SessionManager()
        with pytest.raises(SessionError, match="owner_id must not be empty"):
            mgr.create("   ")

    def test_get_existing(self) -> None:
        mgr = SessionManager()
        s = mgr.create("user-1")
        assert mgr.get(s.session_id) is s

    def test_get_missing_raises(self) -> None:
        mgr = SessionManager()
        with pytest.raises(SessionNotFoundError):
            mgr.get("nonexistent")

    def test_session_count(self) -> None:
        mgr = SessionManager()
        mgr.create("u1")
        mgr.create("u2")
        assert mgr.session_count == 2


# ---------------------------------------------------------------------------
# Lifecycle transitions
# ---------------------------------------------------------------------------


class TestLifecycle:
    def test_created_to_active(self) -> None:
        mgr = SessionManager()
        s = mgr.create("u1")
        mgr.activate(s.session_id)
        assert s.state == SessionState.ACTIVE
        assert s.is_active

    def test_active_to_suspended(self) -> None:
        mgr = SessionManager()
        s = mgr.create("u1")
        mgr.activate(s.session_id)
        mgr.suspend(s.session_id)
        assert s.state == SessionState.SUSPENDED
        assert s.suspended_at is not None

    def test_suspended_to_active(self) -> None:
        mgr = SessionManager()
        s = mgr.create("u1")
        mgr.activate(s.session_id)
        mgr.suspend(s.session_id)
        mgr.activate(s.session_id)
        assert s.state == SessionState.ACTIVE

    def test_terminate_from_active(self) -> None:
        mgr = SessionManager()
        s = mgr.create("u1")
        mgr.activate(s.session_id)
        mgr.terminate(s.session_id)
        assert s.state == SessionState.TERMINATED
        assert s.terminated_at is not None

    def test_terminate_from_created(self) -> None:
        mgr = SessionManager()
        s = mgr.create("u1")
        mgr.terminate(s.session_id)
        assert s.state == SessionState.TERMINATED

    def test_invalid_transition_raises(self) -> None:
        mgr = SessionManager()
        s = mgr.create("u1")
        with pytest.raises(SessionStateError):
            mgr.suspend(s.session_id)  # CREATED → SUSPENDED invalid

    def test_terminated_is_final(self) -> None:
        mgr = SessionManager()
        s = mgr.create("u1")
        mgr.terminate(s.session_id)
        with pytest.raises(SessionStateError):
            mgr.activate(s.session_id)

    def test_active_sessions(self) -> None:
        mgr = SessionManager()
        s1 = mgr.create("u1")
        s2 = mgr.create("u2")
        mgr.activate(s1.session_id)
        assert len(mgr.active_sessions()) == 1
        mgr.activate(s2.session_id)
        assert len(mgr.active_sessions()) == 2


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------


class TestMessages:
    def test_add_message(self) -> None:
        mgr = SessionManager()
        s = mgr.create("u1")
        mgr.activate(s.session_id)
        msg = mgr.add_message(s.session_id, "user", "hello")
        assert msg.role == "user"
        assert msg.content == "hello"
        assert s.message_count == 1

    def test_add_message_non_active_raises(self) -> None:
        mgr = SessionManager()
        s = mgr.create("u1")
        with pytest.raises(SessionStateError, match="Cannot add messages"):
            mgr.add_message(s.session_id, "user", "hi")

    def test_message_eviction(self) -> None:
        """Messages beyond max_history_messages are evicted (oldest first)."""
        mgr = SessionManager()
        s = mgr.create("u1", tier=SessionTier.DM)  # max 500
        mgr.activate(s.session_id)

        # Fill to capacity
        for i in range(500):
            mgr.add_message(s.session_id, "user", f"msg-{i}")
        assert s.message_count == 500

        # Add one more — oldest should be evicted
        mgr.add_message(s.session_id, "user", "msg-500")
        assert s.message_count == 500
        assert s.messages[0].content == "msg-1"

    def test_get_history(self) -> None:
        mgr = SessionManager()
        s = mgr.create("u1")
        mgr.activate(s.session_id)
        for i in range(5):
            mgr.add_message(s.session_id, "user", f"m{i}")
        history = mgr.get_history(s.session_id, limit=2)
        assert len(history) == 2
        assert history[0].content == "m3"
        assert history[1].content == "m4"

    def test_get_full_history(self) -> None:
        mgr = SessionManager()
        s = mgr.create("u1")
        mgr.activate(s.session_id)
        mgr.add_message(s.session_id, "user", "a")
        mgr.add_message(s.session_id, "assistant", "b")
        history = mgr.get_history(s.session_id)
        assert len(history) == 2

    def test_message_to_dict(self) -> None:
        mgr = SessionManager()
        s = mgr.create("u1")
        mgr.activate(s.session_id)
        msg = mgr.add_message(s.session_id, "user", "hello", sender_id="u1")
        d = msg.to_dict()
        assert d["role"] == "user"
        assert d["sender_id"] == "u1"
        assert "timestamp" in d


# ---------------------------------------------------------------------------
# Participants
# ---------------------------------------------------------------------------


class TestParticipants:
    def test_add_participant(self) -> None:
        mgr = SessionManager()
        s = mgr.create("u1", tier=SessionTier.GROUP)
        mgr.add_participant(s.session_id, "u2")
        assert "u2" in s.participants
        assert len(s.participants) == 2

    def test_no_duplicate_participants(self) -> None:
        mgr = SessionManager()
        s = mgr.create("u1", tier=SessionTier.GROUP)
        mgr.add_participant(s.session_id, "u2")
        mgr.add_participant(s.session_id, "u2")
        assert s.participants.count("u2") == 1

    def test_remove_participant(self) -> None:
        mgr = SessionManager()
        s = mgr.create("u1", tier=SessionTier.GROUP)
        mgr.add_participant(s.session_id, "u2")
        mgr.remove_participant(s.session_id, "u2")
        assert "u2" not in s.participants

    def test_participant_capacity(self) -> None:
        """MAIN tier allows only 1 participant (the owner)."""
        mgr = SessionManager()
        s = mgr.create("u1", tier=SessionTier.MAIN)
        with pytest.raises(SessionCapacityError, match="max participants"):
            mgr.add_participant(s.session_id, "u2")


# ---------------------------------------------------------------------------
# Task tracking
# ---------------------------------------------------------------------------


class TestTaskTracking:
    def test_register_task(self) -> None:
        mgr = SessionManager()
        s = mgr.create("u1")
        mgr.register_task(s.session_id, "task-1")
        assert "task-1" in s.active_tasks

    def test_complete_task(self) -> None:
        mgr = SessionManager()
        s = mgr.create("u1")
        mgr.register_task(s.session_id, "task-1")
        mgr.complete_task(s.session_id, "task-1")
        assert "task-1" not in s.active_tasks

    def test_task_capacity(self) -> None:
        mgr = SessionManager()
        s = mgr.create("u1", tier=SessionTier.DM)  # max 2 concurrent
        mgr.register_task(s.session_id, "t1")
        mgr.register_task(s.session_id, "t2")
        with pytest.raises(SessionCapacityError, match="max concurrent tasks"):
            mgr.register_task(s.session_id, "t3")

    def test_no_duplicate_tasks(self) -> None:
        mgr = SessionManager()
        s = mgr.create("u1")
        mgr.register_task(s.session_id, "t1")
        mgr.register_task(s.session_id, "t1")  # no dup
        assert s.active_tasks.count("t1") == 1


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------


class TestCleanup:
    def test_cleanup_idle(self) -> None:
        mgr = SessionManager(idle_timeout_minutes=30)
        s = mgr.create("u1")
        mgr.activate(s.session_id)

        # Simulate idle session
        s.updated_at = datetime.now(timezone.utc) - timedelta(minutes=31)

        count = mgr.cleanup_idle()
        assert count == 1
        assert s.state == SessionState.SUSPENDED

    def test_cleanup_idle_skips_recent(self) -> None:
        mgr = SessionManager(idle_timeout_minutes=30)
        s = mgr.create("u1")
        mgr.activate(s.session_id)

        count = mgr.cleanup_idle()
        assert count == 0
        assert s.state == SessionState.ACTIVE

    def test_cleanup_terminated(self) -> None:
        mgr = SessionManager()
        s = mgr.create("u1")
        mgr.terminate(s.session_id)
        assert mgr.session_count == 1
        removed = mgr.cleanup_terminated()
        assert removed == 1
        assert mgr.session_count == 0


# ---------------------------------------------------------------------------
# Tier checks
# ---------------------------------------------------------------------------


class TestTierChecks:
    def test_main_all_stages(self) -> None:
        mgr = SessionManager()
        s = mgr.create("u1", tier=SessionTier.MAIN)
        for stage in ("plan", "gate", "execute", "validate", "ship"):
            assert mgr.check_stage_allowed(s.session_id, stage)

    def test_dm_no_execute_ship(self) -> None:
        mgr = SessionManager()
        s = mgr.create("u1", tier=SessionTier.DM)
        assert mgr.check_stage_allowed(s.session_id, "plan") is True
        assert mgr.check_stage_allowed(s.session_id, "execute") is False
        assert mgr.check_stage_allowed(s.session_id, "ship") is False


# ---------------------------------------------------------------------------
# Serialization & Stats
# ---------------------------------------------------------------------------


class TestSerialization:
    def test_session_to_dict(self) -> None:
        mgr = SessionManager()
        s = mgr.create("u1")
        d = s.to_dict()
        assert d["owner_id"] == "u1"
        assert d["tier"] == "main"
        assert d["state"] == "created"
        assert "session_id" in d

    def test_get_stats(self) -> None:
        mgr = SessionManager()
        mgr.create("u1")
        s2 = mgr.create("u2")
        mgr.activate(s2.session_id)
        stats = mgr.get_stats()
        assert stats["total_sessions"] == 2
        assert stats["by_state"]["created"] == 1
        assert stats["by_state"]["active"] == 1
        assert stats["by_tier"]["main"] == 2

    def test_constraints_property(self) -> None:
        mgr = SessionManager()
        s = mgr.create("u1", tier=SessionTier.GROUP)
        assert s.constraints.max_participants == 50
