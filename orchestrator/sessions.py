"""Session Management — REQ-CORE-02: Session Tiers, Lifecycle, Persistence.

Manages conversation sessions with tier-based capabilities:
- main: Full VAP pipeline access (all stages, all tools)
- dm: Restricted access (no execute, no ship)
- group: Multi-user sessions with shared context
- brain: Brain orchestrator with high concurrency (20 tasks, 5000 messages)

Usage::

    manager = SessionManager()
    session = manager.create("user-1", tier=SessionTier.MAIN)
    manager.activate(session.session_id)
    manager.add_message(session.session_id, "user", "Deploy staging")
    manager.suspend(session.session_id)
    manager.terminate(session.session_id)
"""

from __future__ import annotations

import enum
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, ClassVar

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Session tiers
# ---------------------------------------------------------------------------


class SessionTier(str, enum.Enum):
    """Session capability tiers."""

    MAIN = "main"        # Full VAP access
    DM = "dm"            # Restricted (no execute/ship)
    GROUP = "group"      # Multi-user, shared context
    BRAIN = "brain"      # Brain orchestrator: high concurrency, full access


class SessionState(str, enum.Enum):
    """Session lifecycle states."""

    CREATED = "created"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    TERMINATED = "terminated"


# ---------------------------------------------------------------------------
# Tier constraints
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TierConstraints:
    """Defines what a session tier is allowed to do."""

    allowed_stages: tuple[str, ...]
    max_concurrent_tasks: int
    max_history_messages: int
    can_execute: bool
    can_ship: bool
    max_participants: int


TIER_CONSTRAINTS: dict[SessionTier, TierConstraints] = {
    SessionTier.MAIN: TierConstraints(
        allowed_stages=("plan", "gate", "execute", "validate", "ship"),
        max_concurrent_tasks=5,
        max_history_messages=1000,
        can_execute=True,
        can_ship=True,
        max_participants=1,
    ),
    SessionTier.DM: TierConstraints(
        allowed_stages=("plan", "gate", "validate"),
        max_concurrent_tasks=2,
        max_history_messages=500,
        can_execute=False,
        can_ship=False,
        max_participants=2,
    ),
    SessionTier.GROUP: TierConstraints(
        allowed_stages=("plan", "gate", "execute", "validate", "ship"),
        max_concurrent_tasks=3,
        max_history_messages=2000,
        can_execute=True,
        can_ship=True,
        max_participants=50,
    ),
    SessionTier.BRAIN: TierConstraints(
        allowed_stages=("plan", "gate", "execute", "validate", "ship"),
        max_concurrent_tasks=20,
        max_history_messages=5000,
        can_execute=True,
        can_ship=True,
        max_participants=1,
    ),
}


# ---------------------------------------------------------------------------
# Session message
# ---------------------------------------------------------------------------


@dataclass
class SessionMessage:
    """A single message within a session."""

    role: str  # "user", "assistant", "system"
    content: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    sender_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "sender_id": self.sender_id,
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------


@dataclass
class Session:
    """A conversation session with tier-based capabilities."""

    session_id: str
    owner_id: str
    tier: SessionTier
    state: SessionState = SessionState.CREATED
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    suspended_at: datetime | None = None
    terminated_at: datetime | None = None
    participants: list[str] = field(default_factory=list)
    messages: list[SessionMessage] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    active_tasks: list[str] = field(default_factory=list)

    # Valid state transitions (ClassVar — not a dataclass field)
    _VALID_TRANSITIONS: ClassVar[dict[SessionState, set[SessionState]]] = {
        SessionState.CREATED: {SessionState.ACTIVE, SessionState.TERMINATED},
        SessionState.ACTIVE: {SessionState.SUSPENDED, SessionState.TERMINATED},
        SessionState.SUSPENDED: {SessionState.ACTIVE, SessionState.TERMINATED},
        SessionState.TERMINATED: set(),
    }

    @property
    def constraints(self) -> TierConstraints:
        """Tier constraints for this session."""
        return TIER_CONSTRAINTS[self.tier]

    @property
    def is_active(self) -> bool:
        return self.state == SessionState.ACTIVE

    @property
    def message_count(self) -> int:
        return len(self.messages)

    def transition(self, new_state: SessionState) -> None:
        """Transition session to new state with validation."""
        allowed = self._VALID_TRANSITIONS.get(self.state, set())
        if new_state not in allowed:
            raise SessionStateError(
                f"Invalid transition: {self.state.value} → {new_state.value}"
            )
        self.state = new_state
        self.updated_at = datetime.now(timezone.utc)
        if new_state == SessionState.SUSPENDED:
            self.suspended_at = self.updated_at
        elif new_state == SessionState.TERMINATED:
            self.terminated_at = self.updated_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "owner_id": self.owner_id,
            "tier": self.tier.value,
            "state": self.state.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "participant_count": len(self.participants),
            "message_count": self.message_count,
            "active_tasks": self.active_tasks,
        }


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class SessionError(Exception):
    """Base session error."""


class SessionNotFoundError(SessionError):
    """Session not found."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        super().__init__(f"Session not found: {session_id}")


class SessionStateError(SessionError):
    """Invalid session state transition."""


class SessionCapacityError(SessionError):
    """Session capacity limit reached."""


# ---------------------------------------------------------------------------
# Session Manager
# ---------------------------------------------------------------------------


class SessionManager:
    """Manages session lifecycle — REQ-CORE-02.

    Features:
    - Four session tiers: main, dm, group, brain
    - State machine: created → active → suspended → terminated
    - Participant management (group sessions)
    - Message history with tier-based limits
    - Session context persistence
    - Idle session cleanup
    """

    def __init__(
        self,
        *,
        idle_timeout_minutes: int = 60,
    ) -> None:
        self._sessions: dict[str, Session] = {}
        self._idle_timeout = timedelta(minutes=idle_timeout_minutes)

    @property
    def session_count(self) -> int:
        """Total number of sessions (all states)."""
        return len(self._sessions)

    def active_sessions(self) -> list[Session]:
        """Return all active sessions."""
        return [s for s in self._sessions.values() if s.is_active]

    # -- Lifecycle --

    def create(
        self,
        owner_id: str,
        *,
        tier: SessionTier = SessionTier.MAIN,
        context: dict[str, Any] | None = None,
    ) -> Session:
        """Create a new session."""
        if not owner_id or not owner_id.strip():
            raise SessionError("owner_id must not be empty")

        session = Session(
            session_id=uuid.uuid4().hex[:16],
            owner_id=owner_id,
            tier=tier,
            participants=[owner_id],
            context=context or {},
        )
        self._sessions[session.session_id] = session
        logger.info(
            "Session created: id=%s owner=%s tier=%s",
            session.session_id,
            owner_id,
            tier.value,
        )
        return session

    def get(self, session_id: str) -> Session:
        """Get session by ID. Raises SessionNotFoundError if not found."""
        session = self._sessions.get(session_id)
        if session is None:
            raise SessionNotFoundError(session_id)
        return session

    def activate(self, session_id: str) -> Session:
        """Transition session to active state."""
        session = self.get(session_id)
        session.transition(SessionState.ACTIVE)
        logger.info("Session activated: id=%s", session_id)
        return session

    def suspend(self, session_id: str) -> Session:
        """Suspend an active session."""
        session = self.get(session_id)
        session.transition(SessionState.SUSPENDED)
        logger.info("Session suspended: id=%s", session_id)
        return session

    def terminate(self, session_id: str) -> Session:
        """Terminate a session."""
        session = self.get(session_id)
        session.transition(SessionState.TERMINATED)
        logger.info("Session terminated: id=%s", session_id)
        return session

    # -- Messages --

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        *,
        sender_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> SessionMessage:
        """Add a message to the session history."""
        session = self.get(session_id)
        if not session.is_active:
            raise SessionStateError(
                f"Cannot add messages to session in state: {session.state.value}"
            )

        constraints = session.constraints
        if len(session.messages) >= constraints.max_history_messages:
            # Evict oldest messages to stay within limit
            excess = len(session.messages) - constraints.max_history_messages + 1
            session.messages = session.messages[excess:]

        msg = SessionMessage(
            role=role,
            content=content,
            sender_id=sender_id,
            metadata=metadata or {},
        )
        session.messages.append(msg)
        session.updated_at = datetime.now(timezone.utc)
        return msg

    def get_history(
        self,
        session_id: str,
        *,
        limit: int | None = None,
    ) -> list[SessionMessage]:
        """Get message history for a session."""
        session = self.get(session_id)
        if limit is not None:
            return session.messages[-limit:]
        return list(session.messages)

    # -- Participants (group sessions) --

    def add_participant(self, session_id: str, user_id: str) -> None:
        """Add a participant to a session."""
        session = self.get(session_id)
        constraints = session.constraints

        if len(session.participants) >= constraints.max_participants:
            raise SessionCapacityError(
                f"Session {session_id} has reached max participants "
                f"({constraints.max_participants})"
            )

        if user_id not in session.participants:
            session.participants.append(user_id)
            session.updated_at = datetime.now(timezone.utc)

    def remove_participant(self, session_id: str, user_id: str) -> None:
        """Remove a participant from a session."""
        session = self.get(session_id)
        if user_id in session.participants:
            session.participants.remove(user_id)
            session.updated_at = datetime.now(timezone.utc)

    # -- Task tracking --

    def register_task(self, session_id: str, task_id: str) -> None:
        """Register an active task in the session."""
        session = self.get(session_id)
        constraints = session.constraints

        active_count = len(session.active_tasks)
        if active_count >= constraints.max_concurrent_tasks:
            raise SessionCapacityError(
                f"Session {session_id} has reached max concurrent tasks "
                f"({constraints.max_concurrent_tasks})"
            )

        if task_id not in session.active_tasks:
            session.active_tasks.append(task_id)

    def complete_task(self, session_id: str, task_id: str) -> None:
        """Mark a task as completed and remove from active list."""
        session = self.get(session_id)
        if task_id in session.active_tasks:
            session.active_tasks.remove(task_id)

    # -- Cleanup --

    def cleanup_idle(self) -> int:
        """Suspend sessions that have been idle beyond the timeout.

        Returns the number of sessions suspended.
        """
        now = datetime.now(timezone.utc)
        count = 0
        for session in list(self._sessions.values()):
            if session.state != SessionState.ACTIVE:
                continue
            if now - session.updated_at > self._idle_timeout:
                session.transition(SessionState.SUSPENDED)
                count += 1
                logger.info(
                    "Auto-suspended idle session: id=%s idle=%s",
                    session.session_id,
                    now - session.updated_at,
                )
        return count

    def cleanup_terminated(self) -> int:
        """Remove terminated sessions from memory.

        Returns the number of sessions removed.
        """
        to_remove = [
            sid
            for sid, s in self._sessions.items()
            if s.state == SessionState.TERMINATED
        ]
        for sid in to_remove:
            del self._sessions[sid]
        return len(to_remove)

    # -- Tier checking --

    def check_stage_allowed(self, session_id: str, stage: str) -> bool:
        """Check if a pipeline stage is allowed for this session's tier."""
        session = self.get(session_id)
        return stage in session.constraints.allowed_stages

    def get_stats(self) -> dict[str, Any]:
        """Return session manager statistics."""
        by_state: dict[str, int] = {}
        by_tier: dict[str, int] = {}
        for s in self._sessions.values():
            by_state[s.state.value] = by_state.get(s.state.value, 0) + 1
            by_tier[s.tier.value] = by_tier.get(s.tier.value, 0) + 1
        return {
            "total_sessions": self.session_count,
            "by_state": by_state,
            "by_tier": by_tier,
        }
