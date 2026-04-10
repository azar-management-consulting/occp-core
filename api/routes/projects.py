"""Project management endpoints — 10-project concurrent routing.

Endpoints:
    POST   /projects                      — Create project
    GET    /projects                      — List all (filter by status)
    GET    /projects/{id}                 — Get project details
    PUT    /projects/{id}                 — Update project
    DELETE /projects/{id}                 — Archive project
    POST   /projects/{id}/dispatch        — Dispatch task within project
    GET    /projects/{id}/status          — Full project status dashboard
    POST   /projects/{id}/agents          — Assign agent to project
    DELETE /projects/{id}/agents/{agent_id} — Remove agent from project
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from api.auth import get_current_user_payload
from api.deps import AppState, get_state
from api.models import (
    ProjectAgentAssign,
    ProjectCreate,
    ProjectDispatchRequest,
    ProjectDispatchResponse,
    ProjectListResponse,
    ProjectResponse,
    ProjectStatusResponse,
    ProjectUpdate,
)
from api.rbac import PermissionChecker
from orchestrator.project_manager import (
    ProjectLimitError,
    ProjectManagerError,
    ProjectNotFoundError,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["projects"])


def _project_to_response(project) -> ProjectResponse:
    """Convert a Project dataclass to a ProjectResponse model."""
    d = project.to_dict()
    return ProjectResponse(**d)


# ---------------------------------------------------------------------------
# POST /projects
# ---------------------------------------------------------------------------


@router.post(
    "/projects",
    response_model=ProjectResponse,
    status_code=201,
    dependencies=[Depends(PermissionChecker("projects", "create"))],
)
async def create_project(
    body: ProjectCreate,
    state: AppState = Depends(get_state),
) -> ProjectResponse:
    """Create a new project with agent assignments."""
    pm = state.project_manager
    if pm is None:
        raise HTTPException(status_code=503, detail="Project manager not initialized")

    try:
        project = await pm.create_project(
            name=body.name,
            description=body.description,
            agents=body.agents,
            priority=body.priority,
            metadata=body.metadata,
        )
    except ProjectLimitError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return _project_to_response(project)


# ---------------------------------------------------------------------------
# GET /projects
# ---------------------------------------------------------------------------


@router.get(
    "/projects",
    response_model=ProjectListResponse,
    dependencies=[Depends(PermissionChecker("projects", "read"))],
)
async def list_projects(
    status: str | None = Query(default=None, pattern=r"^(active|paused|completed|archived)$"),
    state: AppState = Depends(get_state),
) -> ProjectListResponse:
    """List all projects, optionally filtered by status."""
    pm = state.project_manager
    if pm is None:
        raise HTTPException(status_code=503, detail="Project manager not initialized")

    projects = await pm.list_projects(status=status)
    return ProjectListResponse(
        projects=[_project_to_response(p) for p in projects],
        total=len(projects),
    )


# ---------------------------------------------------------------------------
# GET /projects/{project_id}
# ---------------------------------------------------------------------------


@router.get(
    "/projects/{project_id}",
    response_model=ProjectResponse,
    dependencies=[Depends(PermissionChecker("projects", "read"))],
)
async def get_project(
    project_id: str,
    state: AppState = Depends(get_state),
) -> ProjectResponse:
    """Get project details including agent assignments."""
    pm = state.project_manager
    if pm is None:
        raise HTTPException(status_code=503, detail="Project manager not initialized")

    project = await pm.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    return _project_to_response(project)


# ---------------------------------------------------------------------------
# PUT /projects/{project_id}
# ---------------------------------------------------------------------------


@router.put(
    "/projects/{project_id}",
    response_model=ProjectResponse,
    dependencies=[Depends(PermissionChecker("projects", "update"))],
)
async def update_project(
    project_id: str,
    body: ProjectUpdate,
    state: AppState = Depends(get_state),
) -> ProjectResponse:
    """Update project fields."""
    pm = state.project_manager
    if pm is None:
        raise HTTPException(status_code=503, detail="Project manager not initialized")

    update_fields = body.model_dump(exclude_unset=True)
    if not update_fields:
        raise HTTPException(status_code=422, detail="No fields to update")

    try:
        project = await pm.update_project(project_id, **update_fields)
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return _project_to_response(project)


# ---------------------------------------------------------------------------
# DELETE /projects/{project_id}
# ---------------------------------------------------------------------------


@router.delete(
    "/projects/{project_id}",
    status_code=204,
    dependencies=[Depends(PermissionChecker("projects", "delete"))],
)
async def archive_project(
    project_id: str,
    state: AppState = Depends(get_state),
) -> None:
    """Archive a project (soft delete)."""
    pm = state.project_manager
    if pm is None:
        raise HTTPException(status_code=503, detail="Project manager not initialized")

    try:
        await pm.archive_project(project_id)
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


# ---------------------------------------------------------------------------
# POST /projects/{project_id}/dispatch
# ---------------------------------------------------------------------------


@router.post(
    "/projects/{project_id}/dispatch",
    response_model=ProjectDispatchResponse,
    dependencies=[Depends(PermissionChecker("projects", "dispatch"))],
)
async def dispatch_to_project(
    project_id: str,
    body: ProjectDispatchRequest,
    state: AppState = Depends(get_state),
) -> ProjectDispatchResponse:
    """Dispatch a task within a project context."""
    pm = state.project_manager
    if pm is None:
        raise HTTPException(status_code=503, detail="Project manager not initialized")

    try:
        task_id = await pm.dispatch_to_project(project_id, body.task_input)
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ProjectManagerError as e:
        raise HTTPException(status_code=409, detail=str(e))

    return ProjectDispatchResponse(
        task_id=task_id,
        project_id=project_id,
        status="dispatched",
    )


# ---------------------------------------------------------------------------
# GET /projects/{project_id}/status
# ---------------------------------------------------------------------------


@router.get(
    "/projects/{project_id}/status",
    response_model=ProjectStatusResponse,
    dependencies=[Depends(PermissionChecker("projects", "read"))],
)
async def get_project_status(
    project_id: str,
    state: AppState = Depends(get_state),
) -> ProjectStatusResponse:
    """Get full project status dashboard data."""
    pm = state.project_manager
    if pm is None:
        raise HTTPException(status_code=503, detail="Project manager not initialized")

    try:
        status_data = await pm.get_project_status(project_id)
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    return ProjectStatusResponse(
        project=ProjectResponse(**status_data["project"]),
        agents=status_data["agents"],
        agent_count=status_data["agent_count"],
        workflow_ids=status_data["workflow_ids"],
        workflow_count=status_data["workflow_count"],
        task_ids=status_data["task_ids"],
        task_count=status_data["task_count"],
    )


# ---------------------------------------------------------------------------
# POST /projects/{project_id}/agents
# ---------------------------------------------------------------------------


@router.post(
    "/projects/{project_id}/agents",
    response_model=ProjectResponse,
    dependencies=[Depends(PermissionChecker("projects", "update"))],
)
async def assign_agent_to_project(
    project_id: str,
    body: ProjectAgentAssign,
    state: AppState = Depends(get_state),
) -> ProjectResponse:
    """Assign an agent to a project."""
    pm = state.project_manager
    if pm is None:
        raise HTTPException(status_code=503, detail="Project manager not initialized")

    try:
        await pm.assign_agent(project_id, body.agent_id)
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    project = await pm.get_project(project_id)
    return _project_to_response(project)


# ---------------------------------------------------------------------------
# DELETE /projects/{project_id}/agents/{agent_id}
# ---------------------------------------------------------------------------


@router.delete(
    "/projects/{project_id}/agents/{agent_id}",
    response_model=ProjectResponse,
    dependencies=[Depends(PermissionChecker("projects", "update"))],
)
async def remove_agent_from_project(
    project_id: str,
    agent_id: str,
    state: AppState = Depends(get_state),
) -> ProjectResponse:
    """Remove an agent from a project."""
    pm = state.project_manager
    if pm is None:
        raise HTTPException(status_code=503, detail="Project manager not initialized")

    try:
        await pm.remove_agent(project_id, agent_id)
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    project = await pm.get_project(project_id)
    return _project_to_response(project)
