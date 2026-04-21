"""Managed Agents API — deep-web-research PoC.

Endpoints:
    POST /managed-agents/research         - spawn a session, stream SSE back
    GET  /managed-agents/status/{sid}     - poll session state

Safety guards:
    * Kill switch must be INACTIVE (hard stop)
    * BudgetPolicy.check() must pass before session open
    * Requires OCCP_ANTHROPIC_API_KEY (NotConfigured → 503)
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any, Literal

import yaml
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from adapters.managed_agents_client import (
    AnthropicManagedAgentsClient,
    ManagedAgentsAPIError,
    NotConfigured,
    SessionHandle,
)
from api.auth import get_current_user_payload
from api.rbac import PermissionChecker
from evaluation import get_kill_switch
from policy_engine.budget_policy import BudgetPolicy

logger = logging.getLogger(__name__)

router = APIRouter(tags=["managed-agents"])

# Cost heuristic per depth tier (USD) — sized to the Opus-4.7 budget
_DEPTH_BUDGET_USD: dict[str, float] = {
    "shallow": 0.15,
    "deep": 0.75,
}
_DEPTH_TOKEN_ESTIMATE: dict[str, int] = {
    "shallow": 8_000,
    "deep": 32_000,
}

_AGENT_CONFIG_PATH = (
    Path(__file__).resolve().parents[2]
    / "managed_agents"
    / "deep_web_research.yaml"
)

# Module-scoped singletons (lazy)
_client: AnthropicManagedAgentsClient | None = None
_budget_policy: BudgetPolicy | None = None
# In-process session registry — PoC-only; production should persist
_session_registry: dict[str, dict[str, Any]] = {}


def _get_client() -> AnthropicManagedAgentsClient:
    global _client
    if _client is None:
        _client = AnthropicManagedAgentsClient()
    return _client


def _get_budget_policy() -> BudgetPolicy:
    global _budget_policy
    if _budget_policy is None:
        _budget_policy = BudgetPolicy()
    return _budget_policy


def require_kill_switch_inactive() -> None:
    """Refuse to proceed while the kill switch is ACTIVE."""
    ks = get_kill_switch()
    if ks.is_active():
        reason = (
            ks.current_activation.reason
            if ks.current_activation is not None
            else "unknown"
        )
        raise HTTPException(
            status_code=503,
            detail=f"kill switch ACTIVE: {reason}",
        )


def _load_agent_config() -> dict[str, Any]:
    try:
        return yaml.safe_load(_AGENT_CONFIG_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"agent config missing: {_AGENT_CONFIG_PATH}",
        ) from exc


# ── Request models ────────────────────────────────────────────


class ResearchRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=2000)
    depth: Literal["shallow", "deep"] = "deep"


# ── Endpoints ─────────────────────────────────────────────────


@router.post(
    "/managed-agents/research",
    dependencies=[Depends(PermissionChecker("managed_agents", "dispatch"))],
)
async def research(
    body: ResearchRequest,
    current_user: dict = Depends(get_current_user_payload),
) -> StreamingResponse:
    """Spawn a deep-web-research session and stream tokens back as SSE."""
    require_kill_switch_inactive()

    depth = body.depth
    # UUID-based task_id: collision-safe (was: hash() % 10M — too small to resist forced collisions).
    task_id = f"managed-agents-{depth}-{uuid.uuid4().hex[:16]}"
    budget = _get_budget_policy()
    budget.set_task_budget(task_id, _DEPTH_BUDGET_USD[depth])
    passed, reason = budget.check(
        task_id=task_id,
        estimated_tokens=_DEPTH_TOKEN_ESTIMATE[depth],
        model="claude-opus-4-7",
    )
    if not passed:
        raise HTTPException(status_code=429, detail=f"budget check failed: {reason}")

    try:
        client = _get_client()
    except NotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    agent_config = _load_agent_config()
    try:
        handle: SessionHandle = await client.create_session(agent_config)
    except ManagedAgentsAPIError as exc:
        # Log verbatim upstream body server-side; return generic detail to client to avoid prompt/body leak.
        logger.warning("managed-agents upstream error: %s", exc)
        raise HTTPException(status_code=502, detail="upstream managed-agents error") from exc

    _session_registry[handle.session_id] = {
        "state": "running",
        "agent": handle.agent_name,
        "created_at": handle.created_at,
        "query": body.query,
        "depth": depth,
        "task_id": task_id,
    }
    logger.info(
        "managed-agents: session %s opened (depth=%s, task=%s)",
        handle.session_id,
        depth,
        task_id,
    )

    async def _event_stream():
        yield (
            f"event: session\n"
            f"data: {{\"session_id\": \"{handle.session_id}\"}}\n\n"
        )
        try:
            async for token in client.send_message(handle.session_id, body.query):
                # SSE framing: escape newlines inside the data field
                safe = token.replace("\r", "").replace("\n", "\\n")
                yield f"data: {safe}\n\n"
        except ManagedAgentsAPIError as exc:
            logger.error("managed-agents stream failed: %s", exc)
            yield f"event: error\ndata: {exc!s}\n\n"
            _session_registry[handle.session_id]["state"] = "failed"
            return
        finally:
            await client.end_session(handle.session_id)
            if _session_registry.get(handle.session_id, {}).get("state") == "running":
                _session_registry[handle.session_id]["state"] = "completed"

        yield "event: done\ndata: [DONE]\n\n"

    return StreamingResponse(_event_stream(), media_type="text/event-stream")


@router.get(
    "/managed-agents/status/{session_id}",
    dependencies=[Depends(PermissionChecker("managed_agents", "read"))],
)
async def status(
    session_id: str,
    current_user: dict = Depends(get_current_user_payload),
) -> dict[str, Any]:
    record = _session_registry.get(session_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"session {session_id} not found")
    return {"session_id": session_id, **record}
