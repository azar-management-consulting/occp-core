"""MCP Bridge REST API — dispatch server-side tool calls."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth import get_current_user_payload
from api.deps import AppState, get_state
from api.rbac import PermissionChecker
from adapters.mcp_bridge import MCPBridge, ToolCall, build_default_bridge

logger = logging.getLogger(__name__)
router = APIRouter(tags=["mcp-bridge"])

# Process-level singleton
_bridge: MCPBridge | None = None


def _get_bridge(state: AppState) -> MCPBridge:
    global _bridge
    if _bridge is None:
        _bridge = build_default_bridge(
            agent_tool_guard=getattr(state, "agent_tool_guard", None),
            input_sanitizer=None,
            audit_store=state.audit_store,
        )
    return _bridge


class MCPDispatchRequest(BaseModel):
    tool: str = Field(..., min_length=1, max_length=100)
    params: dict[str, Any] = Field(default_factory=dict)
    agent_id: str = Field(default="brain", max_length=50)
    timeout_seconds: float = Field(default=30.0, gt=0, le=300)


class MCPDispatchResponse(BaseModel):
    call_id: str
    tool: str
    status: str
    result: Any = None
    error: str | None = None
    duration_ms: float
    timestamp: str


class MCPBatchRequest(BaseModel):
    calls: list[MCPDispatchRequest] = Field(..., min_length=1, max_length=32)


class MCPBatchResponse(BaseModel):
    results: list[MCPDispatchResponse]
    total: int
    ok_count: int
    error_count: int


class MCPToolListResponse(BaseModel):
    tools: list[str]
    stats: dict[str, Any]


@router.get(
    "/mcp-bridge/tools",
    response_model=MCPToolListResponse,
    dependencies=[Depends(PermissionChecker("brain", "read"))],
)
async def list_mcp_tools(state: AppState = Depends(get_state)) -> MCPToolListResponse:
    """List all registered MCP tools + stats."""
    bridge = _get_bridge(state)
    return MCPToolListResponse(tools=bridge.list_tools(), stats=bridge.stats())


@router.post(
    "/mcp-bridge/dispatch",
    response_model=MCPDispatchResponse,
    dependencies=[Depends(PermissionChecker("brain", "dispatch"))],
)
async def dispatch_tool(
    body: MCPDispatchRequest,
    state: AppState = Depends(get_state),
) -> MCPDispatchResponse:
    """Dispatch a single MCP tool call."""
    bridge = _get_bridge(state)
    call = ToolCall(
        tool=body.tool,
        params=body.params,
        agent_id=body.agent_id,
        timeout_seconds=body.timeout_seconds,
    )
    result = await bridge.dispatch(call)
    return MCPDispatchResponse(
        call_id=result.call_id,
        tool=result.tool,
        status=result.status,
        result=result.result,
        error=result.error,
        duration_ms=round(result.duration_ms, 2),
        timestamp=result.timestamp,
    )


@router.post(
    "/mcp-bridge/batch",
    response_model=MCPBatchResponse,
    dependencies=[Depends(PermissionChecker("brain", "dispatch"))],
)
async def dispatch_batch(
    body: MCPBatchRequest,
    state: AppState = Depends(get_state),
) -> MCPBatchResponse:
    """Dispatch multiple tool calls in parallel."""
    bridge = _get_bridge(state)
    calls = [
        ToolCall(
            tool=c.tool,
            params=c.params,
            agent_id=c.agent_id,
            timeout_seconds=c.timeout_seconds,
        )
        for c in body.calls
    ]
    results = await bridge.dispatch_many(calls)
    ok = sum(1 for r in results if r.status == "ok")
    err = sum(1 for r in results if r.status != "ok")
    return MCPBatchResponse(
        results=[
            MCPDispatchResponse(
                call_id=r.call_id,
                tool=r.tool,
                status=r.status,
                result=r.result,
                error=r.error,
                duration_ms=round(r.duration_ms, 2),
                timestamp=r.timestamp,
            )
            for r in results
        ],
        total=len(results),
        ok_count=ok,
        error_count=err,
    )
