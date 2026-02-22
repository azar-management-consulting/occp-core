"""Async SQLite task persistence – replaces in-memory dict."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from orchestrator.models import Task, TaskStatus, RiskLevel
from store.database import Database


class TaskStore:
    """CRUD operations for tasks backed by SQLite."""

    def __init__(self, db: Database) -> None:
        self._db = db

    async def add(self, task: Task) -> None:
        """Insert a new task."""
        await self._db.conn.execute(
            """INSERT INTO tasks
               (id, name, description, agent_type, risk_level, status,
                plan, result, error, metadata, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                task.id,
                task.name,
                task.description,
                task.agent_type,
                task.risk_level.value,
                task.status.value,
                json.dumps(task.plan) if task.plan else None,
                json.dumps(task.result) if task.result else None,
                task.error,
                json.dumps(task.metadata),
                task.created_at.isoformat(),
                task.updated_at.isoformat(),
            ),
        )
        await self._db.conn.commit()

    async def get(self, task_id: str) -> Task | None:
        """Fetch a single task by ID."""
        cursor = await self._db.conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return self._row_to_task(row)

    async def list_all(self) -> list[Task]:
        """Return all tasks ordered by created_at desc."""
        cursor = await self._db.conn.execute(
            "SELECT * FROM tasks ORDER BY created_at DESC"
        )
        rows = await cursor.fetchall()
        return [self._row_to_task(r) for r in rows]

    async def update(self, task: Task) -> None:
        """Persist current task state."""
        task.updated_at = datetime.now(timezone.utc)
        await self._db.conn.execute(
            """UPDATE tasks SET
               status=?, plan=?, result=?, error=?, metadata=?, updated_at=?
               WHERE id=?""",
            (
                task.status.value,
                json.dumps(task.plan) if task.plan else None,
                json.dumps(task.result) if task.result else None,
                task.error,
                json.dumps(task.metadata),
                task.updated_at.isoformat(),
                task.id,
            ),
        )
        await self._db.conn.commit()

    async def delete(self, task_id: str) -> bool:
        """Delete a task. Returns True if deleted."""
        cursor = await self._db.conn.execute(
            "DELETE FROM tasks WHERE id = ?", (task_id,)
        )
        await self._db.conn.commit()
        return cursor.rowcount > 0

    async def count(self) -> int:
        """Total task count."""
        cursor = await self._db.conn.execute("SELECT COUNT(*) FROM tasks")
        row = await cursor.fetchone()
        return row[0]

    @staticmethod
    def _row_to_task(row: Any) -> Task:
        """Convert sqlite Row to Task model."""
        task = Task(
            name=row["name"],
            description=row["description"],
            agent_type=row["agent_type"],
            risk_level=RiskLevel(row["risk_level"]),
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
        )
        # Override auto-generated fields
        object.__setattr__(task, "id", row["id"])
        task.status = TaskStatus(row["status"])
        task.plan = json.loads(row["plan"]) if row["plan"] else None
        task.result = json.loads(row["result"]) if row["result"] else None
        task.error = row["error"]
        task.created_at = datetime.fromisoformat(row["created_at"])
        task.updated_at = datetime.fromisoformat(row["updated_at"])
        return task
