"""Agent registry CRUD endpoints with persistent storage."""

from __future__ import annotations

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
    agents = await state.list_agents()
    return AgentListResponse(
        agents=[_agent_to_response(a) for a in agents],
        total=len(agents),
    )


@router.get("/agents/{agent_type}", response_model=AgentResponse)
async def get_agent(
    agent_type: str,
    state: AppState = Depends(get_state),
) -> AgentResponse:
    cfg = await state.get_agent(agent_type)
    if cfg is None:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_type}' not found")
    return _agent_to_response(cfg)


@router.post("/agents", response_model=AgentResponse, status_code=201)
async def register_agent(
    body: AgentRegistrationRequest,
    _user: str = Depends(get_current_user),
    state: AppState = Depends(get_state),
) -> AgentResponse:
    """Register or update an agent type (persisted to DB)."""
    config = AgentConfig(
        agent_type=body.agent_type,
        display_name=body.display_name,
        capabilities=body.capabilities,
        max_concurrent=body.max_concurrent,
        timeout_seconds=body.timeout_seconds,
        metadata=body.metadata,
    )
    await state.upsert_agent(config)
    return _agent_to_response(config)


@router.delete("/agents/{agent_type}", status_code=204)
async def unregister_agent(
    agent_type: str,
    _user: str = Depends(get_current_user),
    state: AppState = Depends(get_state),
) -> None:
    cfg = await state.get_agent(agent_type)
    if cfg is None:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_type}' not found")
    await state.delete_agent(agent_type)


@router.get("/agents/{agent_type}/routing")
async def get_agent_routing(
    agent_type: str,
    state: AppState = Depends(get_state),
) -> dict[str, str]:
    """Return which adapter source (default/override) is used per pipeline stage."""
    cfg = await state.get_agent(agent_type)
    if cfg is None:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_type}' not found")
    if state.adapter_registry:
        return state.adapter_registry.get_routing_info(agent_type)
    return {"planner": "default", "executor": "default", "validator": "default", "shipper": "default"}
