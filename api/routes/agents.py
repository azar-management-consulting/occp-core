"""Agent registry CRUD endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from orchestrator.models import AgentConfig

from api.auth import get_current_user
from api.deps import AppState, get_state
from api.models import (
    AgentListResponse,
    AgentRegistrationRequest,
    AgentResponse,
)

router = APIRouter(tags=["agents"])


def _agent_to_response(cfg: AgentConfig) -> AgentResponse:
    return AgentResponse(
        agent_type=cfg.agent_type,
        display_name=cfg.display_name,
        capabilities=cfg.capabilities,
        max_concurrent=cfg.max_concurrent,
        timeout_seconds=cfg.timeout_seconds,
        metadata=cfg.metadata,
    )


@router.get("/agents", response_model=AgentListResponse)
async def list_agents(
    state: AppState = Depends(get_state),
) -> AgentListResponse:
    agents = state.scheduler.list_agents()
    return AgentListResponse(
        agents=[_agent_to_response(a) for a in agents],
        total=len(agents),
    )


@router.get("/agents/{agent_type}", response_model=AgentResponse)
async def get_agent(
    agent_type: str,
    state: AppState = Depends(get_state),
) -> AgentResponse:
    cfg = state.scheduler.get_agent(agent_type)
    if cfg is None:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_type}' not found")
    return _agent_to_response(cfg)


@router.post("/agents", response_model=AgentResponse, status_code=201)
async def register_agent(
    body: AgentRegistrationRequest,
    _user: str = Depends(get_current_user),
    state: AppState = Depends(get_state),
) -> AgentResponse:
    """Register or update an agent type in the scheduler."""
    config = AgentConfig(
        agent_type=body.agent_type,
        display_name=body.display_name,
        capabilities=body.capabilities,
        max_concurrent=body.max_concurrent,
        timeout_seconds=body.timeout_seconds,
        metadata=body.metadata,
    )

    # Provide a no-op factory for API-registered agents
    async def _noop_factory(_cfg: AgentConfig, _task: Any = None):  # type: ignore[no-untyped-def]
        return {"status": "ok", "agent_type": _cfg.agent_type}

    state.scheduler.register(config, _noop_factory)
    return _agent_to_response(config)


@router.delete("/agents/{agent_type}", status_code=204)
async def unregister_agent(
    agent_type: str,
    _user: str = Depends(get_current_user),
    state: AppState = Depends(get_state),
) -> None:
    cfg = state.scheduler.get_agent(agent_type)
    if cfg is None:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_type}' not found")
    state.scheduler.unregister(agent_type)
