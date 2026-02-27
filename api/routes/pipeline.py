"""Pipeline execution endpoint – triggers the full Verified Autonomy Pipeline for a task."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from orchestrator.exceptions import GateRejectedError
from orchestrator.models import TaskStatus

from api.rbac import PermissionChecker
from api.deps import AppState, get_state
from api.models import PipelineRunResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["pipeline"])


@router.post("/pipeline/run/{task_id}", response_model=PipelineRunResponse)
async def run_pipeline(
    task_id: str,
    user: dict = Depends(PermissionChecker("pipeline", "run")),
    state: AppState = Depends(get_state),
) -> PipelineRunResponse:
    task = await state.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    if task.status != TaskStatus.PENDING:
        raise HTTPException(
            status_code=409,
            detail=f"Task {task_id} is in state '{task.status.value}', expected 'pending'",
        )

    if state.pipeline is None:
        raise HTTPException(status_code=503, detail="Pipeline not configured")

    try:
        result = await state.pipeline.run(task)

        # Persist updated task state after pipeline run
        await state.update_task(task)

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
        # Persist rejected state
        await state.update_task(task)

        await state.ws_manager.broadcast(task_id, {
            "event": "pipeline_rejected",
            "task_id": task_id,
            "reason": exc.reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        raise HTTPException(status_code=422, detail=exc.reason)
