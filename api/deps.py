"""FastAPI dependency injection – provides pipeline, task store, and policy engine."""

from __future__ import annotations

from typing import Any

from orchestrator.models import Task
from orchestrator.pipeline import Pipeline
from policy_engine.engine import PolicyEngine

from api.ws_manager import ConnectionManager


class AppState:
    """Shared application state created during lifespan."""

    def __init__(self) -> None:
        self.tasks: dict[str, Task] = {}
        self.pipeline: Pipeline | None = None
        self.policy_engine: PolicyEngine = PolicyEngine()
        self.ws_manager: ConnectionManager = ConnectionManager()

    def add_task(self, task: Task) -> None:
        self.tasks[task.id] = task

    def get_task(self, task_id: str) -> Task | None:
        return self.tasks.get(task_id)

    def list_tasks(self) -> list[Task]:
        return list(self.tasks.values())


# Global singleton – set during lifespan
_state: AppState | None = None


def get_state() -> AppState:
    assert _state is not None, "AppState not initialized"
    return _state


def set_state(state: AppState) -> None:
    global _state
    _state = state
