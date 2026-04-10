"""PROGRESS event streaming — central event emitter for OCCP Brain protocol.

Protocol requirement P1: Event-driven progress streaming with 6 event types.
Protocol requirement P2: correlation_id on every event.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    STATUS = "STATUS"
    PROGRESS = "PROGRESS"
    COMPLETION = "COMPLETION"
    QUESTION = "QUESTION"
    APPROVAL = "APPROVAL"
    ERROR = "ERROR"


@dataclass
class BrainEvent:
    event_type: EventType
    task_id: str
    correlation_id: str  # groups related events
    data: dict = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "event_type": self.event_type.value,
            "task_id": self.task_id,
            "correlation_id": self.correlation_id,
            "data": self.data,
            "timestamp": self.timestamp,
        }


class EventEmitter:
    """Central event emitter for OCCP Brain protocol."""

    def __init__(self) -> None:
        self._listeners: list[Callable] = []
        self._event_log: list[BrainEvent] = []  # ring buffer
        self._max_log = 1000

    def on(self, callback: Callable[[BrainEvent], None]) -> None:
        self._listeners.append(callback)

    def emit(self, event: BrainEvent) -> None:
        self._event_log.append(event)
        if len(self._event_log) > self._max_log:
            self._event_log.pop(0)
        for listener in self._listeners:
            try:
                listener(event)
            except Exception as exc:
                logger.error("Event listener error: %s", exc)

    def emit_progress(
        self,
        task_id: str,
        correlation_id: str,
        stage: str,
        detail: str,
        pct: int = 0,
    ) -> None:
        self.emit(BrainEvent(
            event_type=EventType.PROGRESS,
            task_id=task_id,
            correlation_id=correlation_id,
            data={"stage": stage, "detail": detail, "percent": pct},
        ))

    def emit_status(self, task_id: str, correlation_id: str, status: str) -> None:
        self.emit(BrainEvent(
            event_type=EventType.STATUS,
            task_id=task_id,
            correlation_id=correlation_id,
            data={"status": status},
        ))

    def emit_completion(
        self,
        task_id: str,
        correlation_id: str,
        result: Any = None,
    ) -> None:
        self.emit(BrainEvent(
            event_type=EventType.COMPLETION,
            task_id=task_id,
            correlation_id=correlation_id,
            data={"result": str(result)[:500] if result else ""},
        ))

    def emit_error(self, task_id: str, correlation_id: str, error: str) -> None:
        self.emit(BrainEvent(
            event_type=EventType.ERROR,
            task_id=task_id,
            correlation_id=correlation_id,
            data={"error": error},
        ))

    def emit_question(self, task_id: str, correlation_id: str, question: str) -> None:
        self.emit(BrainEvent(
            event_type=EventType.QUESTION,
            task_id=task_id,
            correlation_id=correlation_id,
            data={"question": question},
        ))

    def emit_approval(self, task_id: str, correlation_id: str, action: str) -> None:
        self.emit(BrainEvent(
            event_type=EventType.APPROVAL,
            task_id=task_id,
            correlation_id=correlation_id,
            data={"action": action, "status": "pending"},
        ))

    def get_events(self, task_id: str | None = None, limit: int = 50) -> list[dict]:
        events = self._event_log
        if task_id:
            events = [e for e in events if e.task_id == task_id]
        return [e.to_dict() for e in events[-limit:]]
