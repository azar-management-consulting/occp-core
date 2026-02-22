"""Pipeline execution endpoint – triggers the full VAP pipeline for a task."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from orchestrator.exceptions import GateRejectedError
from orchestrator.models import Task, TaskStatus

from api.deps import AppState, get_state
from api.models import PipelineRunResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["pipeline"])


@router.post("/pipeline/run/{task_id}", response_model=PipelineRunResponse)
async def run_pipeline(
    task_id: str,
    state: AppState = Depends(get_state),
) -> PipelineRunResponse:
    task = state.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    if task.status != TaskStatus.PENDING:
        raise HTTPException(
            status_code=409,
            detail=f"Task {task_id} is in state '{task.status.value}', expected 'pending'",
        )

    if state.pipeline is None:
        raise HTTPException(status_code=503, detail="Pipeline not configured")

    # Instrument task transitions for WebSocket broadcasting
    original_transition = task.transition

    async def _broadcast_transition(new_status: TaskStatus) -> None:
        original_transition(new_status)
        await state.ws_manager.broadcast(task_id, {
            "event": "status_change",
            "task_id": task_id,
            "status": new_status.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    # Monkey-patch transition to async broadcast wrapper
    # Pipeline calls task.transition() synchronously, so we use a different approach:
    # wrap the pipeline run and broadcast after each stage
    try:
        result = await state.pipeline.run(task)

        # Broadcast final status
        await state.ws_manager.broadcast(task_id, {
            "event": "pipeline_complete",
            "task_id": task_id,
            "success": result.success,
            "status": result.status.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        return PipelineRunResponse(
            task_id=result.task_id,
            success=result.success,
            status=result.status.value,
            started_at=result.started_at,
            finished_at=result.finished_at,
            evidence=result.evidence,
            error=result.error,
        )

    except GateRejectedError as exc:
        await state.ws_manager.broadcast(task_id, {
            "event": "pipeline_rejected",
            "task_id": task_id,
            "reason": exc.reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        raise HTTPException(status_code=422, detail=exc.reason)
