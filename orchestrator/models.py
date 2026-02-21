"""Core data models for the Orchestrator module."""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, ClassVar


class TaskStatus(enum.Enum):
    """Lifecycle states of a pipeline task."""

    PENDING = "pending"
    PLANNING = "planning"
    GATED = "gated"
    EXECUTING = "executing"
    VALIDATING = "validating"
    SHIPPING = "shipping"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"


class RiskLevel(enum.Enum):
    """Risk classification for tasks entering the Gate stage."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AgentConfig:
    """Configuration for a registered agent adapter."""

    agent_type: str
    display_name: str
    capabilities: list[str] = field(default_factory=list)
    max_concurrent: int = 1
    timeout_seconds: int = 300
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Task:
    """Represents a unit of work flowing through the VAP pipeline."""

    name: str
    description: str
    agent_type: str
    risk_level: RiskLevel = RiskLevel.LOW
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    plan: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    # Valid state transitions for the VAP pipeline
    _VALID_TRANSITIONS: ClassVar[dict[TaskStatus, set[TaskStatus]]] = {
        TaskStatus.PENDING: {TaskStatus.PLANNING, TaskStatus.FAILED},
        TaskStatus.PLANNING: {TaskStatus.GATED, TaskStatus.FAILED},
        TaskStatus.GATED: {TaskStatus.EXECUTING, TaskStatus.REJECTED, TaskStatus.FAILED},
        TaskStatus.EXECUTING: {TaskStatus.VALIDATING, TaskStatus.FAILED},
        TaskStatus.VALIDATING: {TaskStatus.SHIPPING, TaskStatus.FAILED},
        TaskStatus.SHIPPING: {TaskStatus.COMPLETED, TaskStatus.FAILED},
        TaskStatus.COMPLETED: set(),
        TaskStatus.FAILED: set(),
        TaskStatus.REJECTED: set(),
    }

    def transition(self, new_status: TaskStatus) -> None:
        """Move task to *new_status* and bump *updated_at*.

        Raises :class:`ValueError` if the transition is not allowed.
        """
        allowed = self._VALID_TRANSITIONS.get(self.status, set())
        if new_status not in allowed:
            raise ValueError(
                f"Invalid transition: {self.status.value} → {new_status.value}"
            )
        self.status = new_status
        self.updated_at = datetime.now(timezone.utc)


@dataclass
class PipelineResult:
    """Outcome of a full VAP pipeline run."""

    task_id: str
    success: bool
    status: TaskStatus
    started_at: datetime
    finished_at: datetime
    evidence: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
