"""Task CRUD endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from orchestrator.models import RiskLevel, Task

from api.rbac import PermissionChecker
from api.deps import AppState, get_state
from api.models import TaskCreate, TaskListResponse, TaskResponse

router = APIRouter(tags=["tasks"])


def _task_to_response(task: Task) -> TaskResponse:
    return TaskResponse(
        id=task.id,
        name=task.name,
        description=task.description,
        agent_type=task.agent_type,
        status=task.status.value,
        risk_level=task.risk_level.value,
        created_at=task.created_at,
        updated_at=task.updated_at,
        plan=task.plan,
        error=task.error,
    )


@router.post("/tasks", response_model=TaskResponse, status_code=201)
async def create_task(
    body: TaskCreate,
    user: dict = Depends(PermissionChecker("tasks", "create")),
    state: AppState = Depends(get_state),
) -> TaskResponse:
    task = Task(
        name=body.name,
        description=body.description,
        agent_type=body.agent_type,
        risk_level=RiskLevel(body.risk_level),
        metadata=body.metadata,
    )
    await state.add_task(task)
    return _task_to_response(task)


@router.get("/tasks", response_model=TaskListResponse,
            dependencies=[Depends(PermissionChecker("tasks", "read"))])
async def list_tasks(state: AppState = Depends(get_state)) -> TaskListResponse:
    all_tasks = await state.list_tasks()
    return TaskListResponse(
        tasks=[_task_to_response(t) for t in all_tasks],
        total=len(all_tasks),
    )


@router.get("/tasks/{task_id}", response_model=TaskResponse,
            dependencies=[Depends(PermissionChecker("tasks", "read"))])
async def get_task(
    task_id: str,
    state: AppState = Depends(get_state),
) -> TaskResponse:
    task = await state.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return _task_to_response(task)
