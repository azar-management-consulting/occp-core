"""Workflow execution persistence — SQLAlchemy 2.0 ORM backend.

Provides CRUD operations for workflow execution state, enabling
state persistence across process restarts and workflow resume.
"""

from __future__ import annotations

import copy
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from store.models import WorkflowExecutionRow

logger = logging.getLogger(__name__)


class WorkflowStore:
    """CRUD operations for workflow executions backed by SQLAlchemy."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── Write ──────────────────────────────────────────────────────────

    async def save_workflow_execution(self, execution: WorkflowExecutionRow) -> None:
        """Insert or merge a workflow execution row."""
        merged = await self._session.merge(execution)
        await self._session.commit()
        logger.debug("Saved workflow execution: %s", merged.execution_id)

    async def update_workflow_status(
        self,
        execution_id: str,
        status: str,
        *,
        current_wave: int | None = None,
        finished_at: str | None = None,
        error_detail: str | None = None,
    ) -> None:
        """Update execution status and optional fields."""
        values: dict[str, Any] = {"status": status}
        if current_wave is not None:
            values["current_wave"] = current_wave
        if finished_at is not None:
            values["finished_at"] = finished_at
        if error_detail is not None:
            values["error_detail"] = error_detail
        stmt = (
            update(WorkflowExecutionRow)
            .where(WorkflowExecutionRow.execution_id == execution_id)
            .values(**values)
        )
        await self._session.execute(stmt)
        await self._session.commit()

    async def update_workflow_node_result(
        self,
        execution_id: str,
        node_id: str,
        result: dict[str, Any],
    ) -> None:
        """Persist a single node result into the execution's node_results JSON.

        Reads the current node_results, merges the new node result, and
        writes back the entire JSON blob (atomic at the row level).
        """
        row = await self.get_workflow_execution(execution_id)
        if row is None:
            logger.warning(
                "Cannot update node result: execution %s not found", execution_id
            )
            return
        node_results = copy.deepcopy(row.node_results) if row.node_results else {}
        node_results[node_id] = result
        stmt = (
            update(WorkflowExecutionRow)
            .where(WorkflowExecutionRow.execution_id == execution_id)
            .values(node_results=node_results)
        )
        await self._session.execute(stmt)
        await self._session.commit()

    async def add_workflow_checkpoint(
        self,
        execution_id: str,
        checkpoint: dict[str, Any],
    ) -> None:
        """Append a checkpoint dict to the execution's checkpoints list."""
        row = await self.get_workflow_execution(execution_id)
        if row is None:
            logger.warning(
                "Cannot add checkpoint: execution %s not found", execution_id
            )
            return
        checkpoints = copy.deepcopy(row.checkpoints) if row.checkpoints else []
        checkpoints.append(checkpoint)
        stmt = (
            update(WorkflowExecutionRow)
            .where(WorkflowExecutionRow.execution_id == execution_id)
            .values(checkpoints=checkpoints)
        )
        await self._session.execute(stmt)
        await self._session.commit()

    # ── Read ───────────────────────────────────────────────────────────

    async def get_workflow_execution(
        self, execution_id: str
    ) -> WorkflowExecutionRow | None:
        """Fetch a single workflow execution by ID."""
        stmt = select(WorkflowExecutionRow).where(
            WorkflowExecutionRow.execution_id == execution_id
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_workflow_executions(
        self, workflow_id: str
    ) -> list[WorkflowExecutionRow]:
        """Return all executions for a workflow, ordered by started_at desc."""
        stmt = (
            select(WorkflowExecutionRow)
            .where(WorkflowExecutionRow.workflow_id == workflow_id)
            .order_by(WorkflowExecutionRow.started_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_interrupted_executions(self) -> list[WorkflowExecutionRow]:
        """Return executions in 'running' or 'paused' status (interrupted by restart)."""
        stmt = (
            select(WorkflowExecutionRow)
            .where(
                WorkflowExecutionRow.status.in_(["running", "paused"])
            )
            .order_by(WorkflowExecutionRow.started_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
