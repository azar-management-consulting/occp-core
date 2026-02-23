"""FastAPI dependency injection – provides pipeline, task store, and policy engine."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from orchestrator.models import Task
from orchestrator.pipeline import Pipeline
from orchestrator.scheduler import Scheduler
from policy_engine.engine import PolicyEngine

from api.ws_manager import ConnectionManager
from config.settings import Settings

if TYPE_CHECKING:
    from store.database import Database
    from store.task_store import TaskStore
    from store.audit_store import AuditStore


class AppState:
    """Shared application state created during lifespan."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings: Settings = settings or Settings()
        self._tasks: dict[str, Task] = {}  # fallback when no DB
        self.db: Database | None = None
        self.task_store: TaskStore | None = None
        self.audit_store: AuditStore | None = None
        self.pipeline: Pipeline | None = None
        self.policy_engine: PolicyEngine = PolicyEngine()
        self.scheduler: Scheduler = Scheduler()
        self.ws_manager: ConnectionManager = ConnectionManager()
        self.multi_planner: Any = None  # MultiLLMPlanner (set in lifespan)

    # -- Task helpers (async, with store-or-dict fallback) --

    async def add_task(self, task: Task) -> None:
        if self.task_store:
            await self.task_store.add(task)
        else:
            self._tasks[task.id] = task

    async def get_task(self, task_id: str) -> Task | None:
        if self.task_store:
            return await self.task_store.get(task_id)
        return self._tasks.get(task_id)

    async def list_tasks(self) -> list[Task]:
        if self.task_store:
            return await self.task_store.list_all()
        return list(self._tasks.values())

    async def update_task(self, task: Task) -> None:
        if self.task_store:
            await self.task_store.update(task)
        else:
            self._tasks[task.id] = task

    async def task_count(self) -> int:
        if self.task_store:
            return await self.task_store.count()
        return len(self._tasks)


# Global singleton – set during lifespan
_state: AppState | None = None


def get_state() -> AppState:
    assert _state is not None, "AppState not initialized"
    return _state


def set_state(state: AppState) -> None:
    global _state
    _state = state
