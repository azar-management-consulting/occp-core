"""CloudCode Hook Integration — Claude Code CLI to Brian the Brain gateway.

Enables Claude Code hooks (shell commands at lifecycle events) to send
commands to OCCP Brain via HTTP. Hook script POSTs here, Brain creates
a Task and runs it through the Verified Autonomy Pipeline.

Endpoints:
    POST /cloudcode/command — Receive command from CloudCode hook
    GET  /cloudcode/tasks/{task_id} — Poll task result
"""

from __future__ import annotations

import asyncio
import logging

from security.input_sanitizer import InputSanitizer
from security.channel_auth import ChannelAuthenticator

_input_sanitizer = InputSanitizer()
_channel_auth = ChannelAuthenticator()
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from api.deps import AppState, get_state
from orchestrator.models import RiskLevel, Task

router = APIRouter(prefix="/cloudcode", tags=["cloudcode"])
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class CloudCodeCommand(BaseModel):
    """Incoming command payload from a Claude Code hook script."""

    command: str = Field(..., min_length=1, description="Instruction for Brian")
    source: str = Field(default="cloudcode", description="Origin identifier")
    hook_type: str = Field(
        default="UserPromptSubmit",
        description="Claude Code hook lifecycle event",
    )
    priority: str = Field(default="high", description="Task priority")
    context: Optional[dict[str, Any]] = Field(
        default=None, description="Extra context from the hook"
    )
    cwd: Optional[str] = Field(
        default=None, description="Working directory of the hook caller"
    )


class CloudCodeResponse(BaseModel):
    """Acknowledgement returned after command intake."""

    task_id: str
    status: str  # accepted | rejected | queued
    message: str
    timestamp: str


class CloudCodeTaskResult(BaseModel):
    """Structured task result for polling."""

    task_id: str
    status: str
    name: str
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    plan: Optional[dict[str, Any]] = None
    created_at: Optional[str] = None


# ---------------------------------------------------------------------------
# Background pipeline runner
# ---------------------------------------------------------------------------


async def _run_pipeline_background(task: Task, state: AppState) -> None:
    """Run the Verified Autonomy Pipeline in background and update task."""
    try:
        if state.pipeline is None:
            logger.error("CloudCode task=%s: pipeline not initialized", task.id)
            return
        result = await state.pipeline.run(task)
        logger.info(
            "CloudCode task=%s completed success=%s", task.id, result.success
        )
    except Exception as exc:
        logger.error("CloudCode task=%s failed: %s", task.id, exc)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/command", response_model=CloudCodeResponse)
async def receive_cloudcode_command(
    body: CloudCodeCommand,
    request: Request,
    state: AppState = Depends(get_state),
) -> CloudCodeResponse:
    """Receive a command from Claude Code hooks.

    Flow: CloudCode hook -> curl POST /api/v1/cloudcode/command -> Brain intake -> pipeline
    """
    # HMAC auth — uses webhook_secret from settings
    import json
    webhook_secret = getattr(state.settings, "webhook_secret", "") if state.settings else ""
    auth = ChannelAuthenticator(webhook_secret=webhook_secret) if webhook_secret else _channel_auth
    signature = request.headers.get("X-OCCP-Signature", "")
    timestamp = int(request.headers.get("X-OCCP-Timestamp", "0") or "0")
    if webhook_secret:
        # Secret configured → signature REQUIRED
        if not signature:
            raise HTTPException(status_code=401, detail="Missing X-OCCP-Signature header")
        payload_str = json.dumps(body.model_dump(), sort_keys=True)
        identity = auth.authenticate_cloudcode(signature, payload_str, timestamp)
        if identity is None:
            raise HTTPException(status_code=401, detail="Invalid HMAC signature")
    elif signature:
        # No secret but signature provided — verify anyway
        payload_str = json.dumps(body.model_dump(), sort_keys=True)
        identity = auth.authenticate_cloudcode(signature, payload_str, timestamp)
        if identity is None:
            raise HTTPException(status_code=401, detail="Invalid HMAC signature")

    command_text = body.command.strip()
    if not command_text:
        raise HTTPException(status_code=400, detail="Empty command")

    # Input sanitization (OWASP ASI01)
    san = _input_sanitizer.sanitize(command_text, channel="cloudcode")
    if not san.safe:
        raise HTTPException(status_code=422, detail=f"Input blocked: {san.threats_detected}")
    command_text = san.sanitized

    # Create a Task for the pipeline
    task = Task(
        name=f"CloudCode: {command_text[:50]}",
        description=command_text,
        agent_type="general",
        risk_level=RiskLevel.LOW,
        metadata={
            "source": body.source,
            "hook_type": body.hook_type,
            "priority": body.priority,
            "cwd": body.cwd,
            "context": body.context or {},
        },
    )

    # Store the task
    await state.add_task(task)

    # Run pipeline in background (non-blocking)
    asyncio.create_task(_run_pipeline_background(task, state))

    return CloudCodeResponse(
        task_id=task.id,
        status="accepted",
        message=f"Brian received: {command_text[:100]}",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@router.get("/tasks/{task_id}", response_model=CloudCodeTaskResult)
async def get_cloudcode_task_result(
    task_id: str,
    state: AppState = Depends(get_state),
) -> CloudCodeTaskResult:
    """Poll for task result (CloudCode output format)."""
    task = await state.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return CloudCodeTaskResult(
        task_id=task.id,
        status=task.status.value,
        name=task.name,
        result=task.result,
        error=task.error,
        plan=task.plan,
        created_at=task.created_at.isoformat() if task.created_at else None,
    )
