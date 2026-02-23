"""Task persistence — SQLAlchemy 2.0 ORM backend.

Public API is identical to the legacy raw-SQL version, so all existing
tests and route handlers work without modification.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.models import Task, TaskStatus, RiskLevel
from store.models import TaskRow


class TaskStore:
    """CRUD operations for tasks backed by SQLAlchemy."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── Write ──────────────────────────────────────────────────────────

    async def add(self, task: Task) -> None:
        """Insert a new task."""
        row = TaskRow(
            id=task.id,
            name=task.name,
            description=task.description,
            agent_type=task.agent_type,
            risk_level=task.risk_level.value,
            status=task.status.value,
            plan=task.plan,
            result=task.result,
            error=task.error,
            metadata_=task.metadata,
            created_at=task.created_at.isoformat(),
            updated_at=task.updated_at.isoformat(),
        )
        self._session.add(row)
        await self._session.commit()

    async def update(self, task: Task) -> None:
        """Persist current task state."""
        task.updated_at = datetime.now(timezone.utc)
        stmt = (
            update(TaskRow)
            .where(TaskRow.id == task.id)
            .values(
                status=task.status.value,
                plan=task.plan,
                result=task.result,
                error=task.error,
                metadata_=task.metadata,
                updated_at=task.updated_at.isoformat(),
            )
        )
        await self._session.execute(stmt)
        await self._session.commit()

    async def delete(self, task_id: str) -> bool:
        """Delete a task. Returns True if deleted."""
        stmt = delete(TaskRow).where(TaskRow.id == task_id)
        result = await self._session.execute(stmt)
        await self._session.commit()
        return result.rowcount > 0

    # ── Read ───────────────────────────────────────────────────────────

    async def get(self, task_id: str) -> Task | None:
        """Fetch a single task by ID."""
        stmt = select(TaskRow).where(TaskRow.id == task_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self._row_to_task(row)

    async def list_all(self) -> list[Task]:
        """Return all tasks ordered by created_at desc."""
        stmt = select(TaskRow).order_by(TaskRow.created_at.desc())
        result = await self._session.execute(stmt)
        return [self._row_to_task(r) for r in result.scalars().all()]

    async def count(self) -> int:
        """Total task count."""
        stmt = select(func.count()).select_from(TaskRow)
        result = await self._session.execute(stmt)
        return result.scalar_one()

    # ── Conversion ─────────────────────────────────────────────────────

    @staticmethod
    def _row_to_task(row: TaskRow) -> Task:
        """Convert ORM row to domain Task model."""
        task = Task(
            name=row.name,
            description=row.description or "",
            agent_type=row.agent_type or "default",
            risk_level=RiskLevel(row.risk_level),
            metadata=row.metadata_ if row.metadata_ else {},
        )
        # Override auto-generated fields from persistence
        object.__setattr__(task, "id", row.id)
        task.status = TaskStatus(row.status)
        task.plan = row.plan
        task.result = row.result
        task.error = row.error
        task.created_at = datetime.fromisoformat(row.created_at)
        task.updated_at = datetime.fromisoformat(row.updated_at)
        return task
