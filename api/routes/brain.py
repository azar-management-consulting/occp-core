"""Brain Webhook Gateway — dispatch/callback/registry/workflow endpoints.

Implements the OCCP Brain control plane webhook gateway for communicating
with OpenClaw agent runtime via HMAC-SHA256 signed webhooks.

Endpoints:
    POST /agents/{agent_id}/dispatch — Dispatch task to OpenClaw agent
    POST /agents/callback — Receive result from OpenClaw agent
    GET  /agents/registry — List all registered agents + status
    POST /workflows — Create multi-agent DAG workflow
    GET  /workflows/{workflow_id}/status — Workflow progress
"""

from __future__ import annotations

from security.input_sanitizer import InputSanitizer

_input_sanitizer = InputSanitizer()

import hashlib
import hmac
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from api.auth import get_current_user_payload
from api.deps import AppState, get_state
from api.models import (
    AgentCallbackRequest,
    AgentCallbackResponse,
    AgentRegistryEntry,
    AgentRegistryResponse,
    BatchDispatchRequest,
    BatchDispatchResponse,
    BatchDispatchResultItem,
    BrainMessageRequest,
    BrainMessageResponse,
    ParallelDispatchRequest,
    ParallelDispatchResponse,
    ParallelDispatchStatusResponse,
    ParallelDispatchTaskStatus,
    SubAgentInfo,
    TaskDispatchRequest,
    TaskDispatchResponse,
    WorkflowCreateRequest,
    WorkflowCreateResponse,
    WorkflowExecutionListResponse,
    WorkflowExecutionSummary,
    WorkflowNodeStatus,
    WorkflowResumeResponse,
    WorkflowStatusResponse,
)
from api.rbac import PermissionChecker
from orchestrator.models import Task
from orchestrator.multi_agent import (
    AgentNode,
    ParallelDispatcher,
    WorkflowDefinition,
    WorkflowNotFoundError,
    WorkflowValidationError,
)
from adapters.openclaw_client import OpenClawClient, OpenClawTask
from config.openclaw_agents import AGENT_OPENCLAW_MAP, get_agent_workspace
from orchestrator.task_router import TaskRouter

logger = logging.getLogger(__name__)

router = APIRouter(tags=["brain"])

# Singleton TaskRouter instance
_task_router = TaskRouter()

# Singleton OpenClawClient (lazily initialised per-process)
_openclaw_client: OpenClawClient | None = None


def _get_openclaw_client(state: "AppState") -> OpenClawClient:
    """Return or create the process-level OpenClawClient."""
    global _openclaw_client
    if _openclaw_client is None:
        s = state.settings
        _openclaw_client = OpenClawClient(
            base_url=s.openclaw_base_url,
            auth_user=s.openclaw_auth_user or None,
            auth_pass=s.openclaw_auth_pass or None,
            webhook_secret=s.webhook_secret or None,
            callback_url=s.openclaw_callback_url or None,
            timeout=s.openclaw_timeout,
        )
    return _openclaw_client

# ---------------------------------------------------------------------------
# In-memory stores (production: persist to DB)
# ---------------------------------------------------------------------------

# task_id -> {agent_id, status, dispatched_at, result, ...}
_dispatch_store: dict[str, dict[str, Any]] = {}

# workflow_id -> WorkflowDefinition
_workflow_store: dict[str, WorkflowDefinition] = {}

# workflow_id -> execution state dict
_workflow_execution_store: dict[str, dict[str, Any]] = {}

# Agent sub-agent/skill registry (from BRAIN_AGENT_ARCHITECTURE.md)
_OPENCLAW_AGENTS: list[dict[str, Any]] = [
    {
        "agent_id": "eng-core",
        "name": "Engineering Agent",
        "model": "claude-sonnet-4-6",
        "sub_agents": [
            {"id": "frontend-ui", "name": "Frontend UI", "skills": ["nextjs-build", "react-component", "tailwind-layout"]},
            {"id": "backend-api", "name": "Backend API", "skills": ["fastapi-build", "api-contract-design", "pydantic-model"]},
            {"id": "database-data", "name": "Database", "skills": ["alembic-migration", "query-optimize", "schema-design"]},
            {"id": "qa-test", "name": "QA Test", "skills": ["pytest-generate", "coverage-check", "e2e-playwright"]},
            {"id": "code-review", "name": "Code Review", "skills": ["refactor-safe", "security-scan", "code-smell-detect"]},
        ],
    },
    {
        "agent_id": "wp-web",
        "name": "Web/WordPress Agent",
        "model": "claude-sonnet-4-6",
        "sub_agents": [
            {"id": "elementor-builder", "name": "Elementor Builder", "skills": ["elementor-section-build", "container-layout", "responsive-check"]},
            {"id": "wp-plugin-dev", "name": "WP Plugin Dev", "skills": ["wordpress-plugin-architecture", "hook-filter-design", "wp-rest-endpoint"]},
            {"id": "seo-page-optimizer", "name": "SEO Optimizer", "skills": ["yoast-optimize", "schema-markup", "meta-tag-audit"]},
            {"id": "conversion-page-builder", "name": "Conversion Builder", "skills": ["landing-page-conversion", "cta-placement", "ab-test-setup"]},
            {"id": "wp-debugger", "name": "WP Debugger", "skills": ["wp-debug-log", "plugin-conflict-isolate", "query-monitor"]},
        ],
    },
    {
        "agent_id": "infra-ops",
        "name": "Infra/Deploy Agent",
        "model": "claude-sonnet-4-6",
        "sub_agents": [
            {"id": "server-provision", "name": "Server Provision", "skills": ["hetzner-vps-setup", "ssh-hardening", "firewall-config"]},
            {"id": "docker-stack", "name": "Docker Stack", "skills": ["docker-compose-prod", "multi-stage-build", "volume-strategy"]},
            {"id": "apache-nginx-proxy", "name": "Proxy Config", "skills": ["apache-reverse-proxy", "nginx-config", "proxy-pass-websocket"]},
            {"id": "ssl-dns-mail", "name": "SSL/DNS/Mail", "skills": ["ssl-letsencrypt", "dns-cutover", "mailcow-config"]},
            {"id": "live-verifier", "name": "Live Verifier", "skills": ["deployment-verification", "health-check", "rollback-plan"]},
        ],
    },
    {
        "agent_id": "design-lab",
        "name": "Design/UI Agent",
        "model": "claude-sonnet-4-6",
        "sub_agents": [
            {"id": "ui-layout", "name": "UI Layout", "skills": ["premium-ui-system", "landing-wireframe", "grid-system"]},
            {"id": "brand-visual", "name": "Brand Visual", "skills": ["monochrome-executive-style", "color-system", "typography-scale"]},
            {"id": "ad-creative", "name": "Ad Creative", "skills": ["ad-visual-brief", "social-banner", "video-thumbnail"]},
            {"id": "presentation-visual", "name": "Presentation", "skills": ["slide-layout", "data-visualization", "executive-deck"]},
        ],
    },
    {
        "agent_id": "content-forge",
        "name": "Content/Copy Agent",
        "model": "claude-sonnet-4-6",
        "sub_agents": [
            {"id": "seo-copy", "name": "SEO Copy", "skills": ["hungarian-seo-copy", "keyword-density", "internal-linking"]},
            {"id": "sales-copy", "name": "Sales Copy", "skills": ["sales-copy-framework", "urgency-scarcity", "benefit-stack"]},
            {"id": "executive-copy", "name": "Executive Copy", "skills": ["authority-positioning", "trust-building-copy", "case-study"]},
            {"id": "email-copy", "name": "Email Copy", "skills": ["email-sequence", "subject-line-test", "drip-campaign"]},
        ],
    },
    {
        "agent_id": "social-growth",
        "name": "Social Media Agent",
        "model": "claude-sonnet-4-6",
        "sub_agents": [
            {"id": "facebook-ads", "name": "Facebook Ads", "skills": ["fb-ad-copy", "audience-targeting", "pixel-event"]},
            {"id": "instagram-ads", "name": "Instagram Ads", "skills": ["ig-carousel", "reel-script", "story-template"]},
            {"id": "tiktok-script", "name": "TikTok Script", "skills": ["short-video-script", "hook-first-3sec", "trend-adapt"]},
            {"id": "lead-magnet-social", "name": "Lead Magnet", "skills": ["engagement-post-design", "cta-optimizer", "lead-form"]},
        ],
    },
    {
        "agent_id": "intel-research",
        "name": "Research/Intelligence Agent",
        "model": "claude-opus-4-6",
        "sub_agents": [
            {"id": "market-research", "name": "Market Research", "skills": ["deep-web-research", "citation-first-analysis", "market-sizing"]},
            {"id": "competitor-scan", "name": "Competitor Scan", "skills": ["competitor-mapping", "feature-matrix", "pricing-compare"]},
            {"id": "tech-radar", "name": "Tech Radar", "skills": ["trend-watch", "framework-evaluate", "migration-risk"]},
            {"id": "fact-check", "name": "Fact Check", "skills": ["source-verify", "claim-validate", "bias-detect"]},
            {"id": "procurement-scan", "name": "Procurement Scan", "skills": ["procurement-scan", "tender-match", "deadline-track"]},
        ],
    },
    {
        "agent_id": "biz-strategy",
        "name": "Business/Proposal Agent",
        "model": "claude-opus-4-6",
        "sub_agents": [
            {"id": "proposal-writer", "name": "Proposal Writer", "skills": ["b2b-offer-design", "scope-define", "deliverable-matrix"]},
            {"id": "pricing-architect", "name": "Pricing Architect", "skills": ["premium-pricing", "tier-structure", "roi-framing"]},
            {"id": "pitch-structurer", "name": "Pitch Structurer", "skills": ["executive-deck-logic", "problem-solution-fit", "investor-narrative"]},
            {"id": "partnership-mapper", "name": "Partnership Mapper", "skills": ["partnership-fit-analysis", "synergy-map", "deal-structure"]},
        ],
    },
]


# ---------------------------------------------------------------------------
# HMAC helpers
# ---------------------------------------------------------------------------


def _compute_hmac(payload: dict[str, Any], secret: str) -> str:
    """Compute HMAC-SHA256 signature for a JSON payload."""
    body = json.dumps(payload, sort_keys=True, default=str)
    return hmac.new(
        secret.encode(),
        body.encode(),
        hashlib.sha256,
    ).hexdigest()


def _verify_hmac(body: bytes, signature: str, secret: str) -> bool:
    """Verify HMAC-SHA256 signature. Expects 'sha256=<hex>' format."""
    if not secret:
        return False
    expected = hmac.new(
        secret.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    received = signature
    if received.startswith("sha256="):
        received = received[7:]
    return hmac.compare_digest(expected, received)


# ---------------------------------------------------------------------------
# 1. POST /agents/{agent_id}/dispatch
# ---------------------------------------------------------------------------


@router.post(
    "/agents/{agent_id}/dispatch",
    response_model=TaskDispatchResponse,
    dependencies=[Depends(PermissionChecker("brain", "dispatch"))],
)
async def dispatch_to_agent(
    agent_id: str,
    body: TaskDispatchRequest,
    state: AppState = Depends(get_state),
) -> TaskDispatchResponse:
    """Dispatch a task to an OpenClaw agent via webhook.

    1. Verify agent_id exists in registry
    2. Policy gate check on task content
    3. HMAC-SHA256 sign the payload
    4. Store task_id -> agent mapping
    5. Return dispatched status
    """
    # Input sanitization (OWASP ASI01)
    san = _input_sanitizer.sanitize(body.description, channel="api")
    if not san.safe:
        raise HTTPException(status_code=422, detail=f"Input blocked: {san.threats_detected}")
    body.description = san.sanitized

    # Verify agent exists in OCCP agent store
    known_agent_ids = {a["agent_id"] for a in _OPENCLAW_AGENTS}
    cfg = await state.get_agent(agent_id)
    if cfg is None and agent_id not in known_agent_ids:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

    # Policy gate check on task content
    if state.policy_engine:
        task_obj = Task(
            name=body.task_name,
            description=body.description,
            agent_type=body.agent_type,
            metadata=body.metadata,
        )
        gate = await state.policy_engine.evaluate(task_obj)
        if not gate.approved:
            raise HTTPException(
                status_code=403,
                detail=f"Policy gate rejected: {gate.reason}",
            )

    # Generate task ID
    task_id = uuid.uuid4().hex[:16]

    # Build webhook payload
    webhook_payload = {
        "task_id": task_id,
        "agent_id": agent_id,
        "task_name": body.task_name,
        "description": body.description,
        "agent_type": body.agent_type,
        "priority": body.priority,
        "metadata": body.metadata,
        "dispatched_at": datetime.now(timezone.utc).isoformat(),
    }

    # HMAC-SHA256 sign
    secret = state.settings.webhook_secret
    signature = ""
    if secret:
        signature = f"sha256={_compute_hmac(webhook_payload, secret)}"

    # ── Dispatch to OpenClaw agent runtime ──────────────────────────
    openclaw = _get_openclaw_client(state)
    workspace = get_agent_workspace(agent_id)
    openclaw_task: OpenClawTask | None = None
    if workspace:
        openclaw_task = await openclaw.dispatch_task(
            agent_id=agent_id,
            input_text=body.description,
            task_id=task_id,
            metadata={
                "task_name": body.task_name,
                "priority": body.priority,
                "workspace": workspace,
                **(body.metadata or {}),
            },
        )

    # Determine dispatch status from OpenClaw result
    dispatch_status = "dispatched"
    openclaw_session = None
    openclaw_error = None
    if openclaw_task:
        if openclaw_task.status == "running":
            dispatch_status = "dispatched"
            openclaw_session = openclaw_task.session_key
        elif openclaw_task.status == "failed":
            # HTTP dispatch failed — not critical, WebSocket bridge is the primary path
            dispatch_status = "queued_for_pipeline"
            openclaw_error = f"HTTP dispatch unavailable (use pipeline/run for WebSocket execution): {openclaw_task.error or ''}"

    # Store dispatch record
    _dispatch_store[task_id] = {
        "task_id": task_id,
        "agent_id": agent_id,
        "status": dispatch_status,
        "payload": webhook_payload,
        "signature": signature,
        "dispatched_at": datetime.now(timezone.utc).isoformat(),
        "result": None,
        "openclaw_session": openclaw_session,
        "openclaw_error": openclaw_error,
    }

    # Audit log
    if state.policy_engine:
        await state.policy_engine.audit(
            actor="brain",
            action="task_dispatch",
            task_id=task_id,
            detail={
                "agent_id": agent_id,
                "task_name": body.task_name,
                "priority": body.priority,
                "openclaw_status": dispatch_status,
                "openclaw_session": openclaw_session,
            },
        )

    logger.info(
        "Task dispatched: task_id=%s agent_id=%s task_name=%s openclaw=%s",
        task_id,
        agent_id,
        body.task_name,
        dispatch_status,
    )

    return TaskDispatchResponse(
        task_id=task_id,
        status=dispatch_status,
        agent_id=agent_id,
    )


# ---------------------------------------------------------------------------
# 1a. POST /agents/dispatch (auto-routing — no agent_id needed)
# ---------------------------------------------------------------------------


@router.post(
    "/agents/dispatch",
    response_model=TaskDispatchResponse,
    dependencies=[Depends(PermissionChecker("brain", "dispatch"))],
)
async def dispatch_auto_route(
    body: TaskDispatchRequest,
    state: AppState = Depends(get_state),
) -> TaskDispatchResponse:
    """Auto-route a task to the best agent via TaskRouter.

    Uses keyword + pattern analysis to determine the primary agent.
    Falls back to eng-core if no confident match.
    """
    # Input sanitization (OWASP ASI01)
    san = _input_sanitizer.sanitize(body.description, channel="api")
    if not san.safe:
        raise HTTPException(status_code=422, detail=f"Input blocked: {san.threats_detected}")
    body.description = san.sanitized

    # Route the task
    decision = _task_router.route(
        body.description,
        context={"task_name": body.task_name, "metadata": body.metadata},
    )

    agent_id = decision.primary_agent

    # Policy gate check on task content
    if state.policy_engine:
        task_obj = Task(
            name=body.task_name,
            description=body.description,
            agent_type=body.agent_type,
            metadata=body.metadata,
        )
        gate = await state.policy_engine.evaluate(task_obj)
        if not gate.approved:
            raise HTTPException(
                status_code=403,
                detail=f"Policy gate rejected: {gate.reason}",
            )

    # Generate task ID
    task_id = uuid.uuid4().hex[:16]

    # Build webhook payload
    webhook_payload = {
        "task_id": task_id,
        "agent_id": agent_id,
        "task_name": body.task_name,
        "description": body.description,
        "agent_type": body.agent_type,
        "priority": body.priority,
        "metadata": {
            **body.metadata,
            "route_decision": decision.to_dict(),
        },
        "dispatched_at": datetime.now(timezone.utc).isoformat(),
    }

    # HMAC-SHA256 sign
    secret = state.settings.webhook_secret
    signature = ""
    if secret:
        signature = f"sha256={_compute_hmac(webhook_payload, secret)}"

    # ── Dispatch to OpenClaw agent runtime ──────────────────────────
    openclaw = _get_openclaw_client(state)
    workspace = get_agent_workspace(agent_id)
    openclaw_task: OpenClawTask | None = None
    if workspace:
        openclaw_task = await openclaw.dispatch_task(
            agent_id=agent_id,
            input_text=body.description,
            task_id=task_id,
            metadata={
                "task_name": body.task_name,
                "priority": body.priority,
                "workspace": workspace,
                "route_decision": decision.to_dict(),
                **(body.metadata or {}),
            },
        )

    dispatch_status = "dispatched"
    openclaw_session = None
    openclaw_error = None
    if openclaw_task:
        if openclaw_task.status == "running":
            dispatch_status = "dispatched"
            openclaw_session = openclaw_task.session_key
        elif openclaw_task.status == "failed":
            # HTTP dispatch failed — not critical, WebSocket bridge is the primary path
            dispatch_status = "queued_for_pipeline"
            openclaw_error = f"HTTP dispatch unavailable (use pipeline/run for WebSocket execution): {openclaw_task.error or ''}"

    # Store dispatch record
    _dispatch_store[task_id] = {
        "task_id": task_id,
        "agent_id": agent_id,
        "status": dispatch_status,
        "payload": webhook_payload,
        "signature": signature,
        "dispatched_at": datetime.now(timezone.utc).isoformat(),
        "result": None,
        "route_decision": decision.to_dict(),
        "openclaw_session": openclaw_session,
        "openclaw_error": openclaw_error,
    }

    # Audit log
    if state.policy_engine:
        await state.policy_engine.audit(
            actor="brain",
            action="task_auto_dispatch",
            task_id=task_id,
            detail={
                "agent_id": agent_id,
                "task_name": body.task_name,
                "priority": body.priority,
                "route_decision": decision.to_dict(),
                "openclaw_status": dispatch_status,
                "openclaw_session": openclaw_session,
            },
        )

    logger.info(
        "Task auto-dispatched: task_id=%s agent_id=%s confidence=%.3f openclaw=%s",
        task_id,
        agent_id,
        decision.confidence,
        dispatch_status,
    )

    return TaskDispatchResponse(
        task_id=task_id,
        status=dispatch_status,
        agent_id=agent_id,
    )


# ---------------------------------------------------------------------------
# 1b. POST /agents/batch-dispatch
# ---------------------------------------------------------------------------


@router.post(
    "/agents/batch-dispatch",
    response_model=BatchDispatchResponse,
    dependencies=[Depends(PermissionChecker("brain", "dispatch"))],
)
async def batch_dispatch(
    body: BatchDispatchRequest,
    state: AppState = Depends(get_state),
) -> BatchDispatchResponse:
    """Batch-dispatch tasks to multiple agents in parallel.

    Each item is dispatched independently.  Failures in one dispatch
    do not affect others.
    """
    known_agent_ids = {a["agent_id"] for a in _OPENCLAW_AGENTS}
    results: list[BatchDispatchResultItem] = []
    dispatched_count = 0
    failed_count = 0

    async def _dispatch_one(item: "BatchDispatchRequest.items") -> BatchDispatchResultItem:
        """Dispatch a single item — returns result, never raises."""
        try:
            # Input sanitization
            san = _input_sanitizer.sanitize(item.description, channel="api")
            if not san.safe:
                return BatchDispatchResultItem(
                    agent_id=item.agent_id,
                    status="error",
                    error=f"Input blocked: {san.threats_detected}",
                )
            item.description = san.sanitized

            # Verify agent exists
            cfg = await state.get_agent(item.agent_id)
            if cfg is None and item.agent_id not in known_agent_ids:
                return BatchDispatchResultItem(
                    agent_id=item.agent_id,
                    status="error",
                    error=f"Agent '{item.agent_id}' not found",
                )

            # Policy gate
            if state.policy_engine:
                task_obj = Task(
                    name=item.task_name,
                    description=item.description,
                    agent_type=item.agent_type,
                    metadata=item.metadata,
                )
                gate = await state.policy_engine.evaluate(task_obj)
                if not gate.approved:
                    return BatchDispatchResultItem(
                        agent_id=item.agent_id,
                        status="error",
                        error=f"Policy gate rejected: {gate.reason}",
                    )

            task_id = uuid.uuid4().hex[:16]

            webhook_payload = {
                "task_id": task_id,
                "agent_id": item.agent_id,
                "task_name": item.task_name,
                "description": item.description,
                "agent_type": item.agent_type,
                "priority": item.priority,
                "metadata": item.metadata,
                "dispatched_at": datetime.now(timezone.utc).isoformat(),
            }

            secret = state.settings.webhook_secret
            signature = ""
            if secret:
                signature = f"sha256={_compute_hmac(webhook_payload, secret)}"

            _dispatch_store[task_id] = {
                "task_id": task_id,
                "agent_id": item.agent_id,
                "status": "dispatched",
                "payload": webhook_payload,
                "signature": signature,
                "dispatched_at": datetime.now(timezone.utc).isoformat(),
                "result": None,
            }

            logger.info(
                "Batch dispatch: task_id=%s agent_id=%s task_name=%s",
                task_id,
                item.agent_id,
                item.task_name,
            )

            return BatchDispatchResultItem(
                agent_id=item.agent_id,
                task_id=task_id,
                status="dispatched",
            )
        except Exception as exc:
            logger.error(
                "Batch dispatch failed for agent=%s: %s", item.agent_id, exc
            )
            return BatchDispatchResultItem(
                agent_id=item.agent_id,
                status="error",
                error=str(exc),
            )

    # Run all dispatches in parallel
    import asyncio as _asyncio

    raw_results = await _asyncio.gather(
        *[_dispatch_one(item) for item in body.items],
        return_exceptions=False,
    )

    for r in raw_results:
        results.append(r)
        if r.status == "dispatched":
            dispatched_count += 1
        else:
            failed_count += 1

    # Audit
    if state.policy_engine:
        await state.policy_engine.audit(
            actor="brain",
            action="batch_dispatch",
            task_id="batch",
            detail={
                "total": len(body.items),
                "dispatched": dispatched_count,
                "failed": failed_count,
            },
        )

    return BatchDispatchResponse(
        results=results,
        total=len(body.items),
        dispatched=dispatched_count,
        failed=failed_count,
    )


# ---------------------------------------------------------------------------
# 2. POST /agents/callback
# ---------------------------------------------------------------------------


@router.post(
    "/agents/callback",
    response_model=AgentCallbackResponse,
)
async def agent_callback(
    request: Request,
    body: AgentCallbackRequest,
    x_occp_signature: str | None = Header(default=None, alias="X-OCCP-Signature"),
    state: AppState = Depends(get_state),
) -> AgentCallbackResponse:
    """Receive completed result from an OpenClaw agent.

    1. Verify HMAC signature (if webhook_secret configured)
    2. Run PolicyEngine output guard on result
    3. Create audit log entry
    4. Update workflow state if part of DAG
    """
    secret = state.settings.webhook_secret

    # Verify HMAC signature
    if secret:
        if not x_occp_signature:
            raise HTTPException(
                status_code=401,
                detail="Missing X-OCCP-Signature header",
            )
        raw_body = await request.body()
        if not _verify_hmac(raw_body, x_occp_signature, secret):
            raise HTTPException(
                status_code=401,
                detail="Invalid HMAC signature",
            )

    # Verify task_id is known
    dispatch_record = _dispatch_store.get(body.task_id)
    if dispatch_record is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown task_id: {body.task_id}",
        )

    # Policy engine output guard on the result content
    if state.policy_engine and body.result:
        result_text = json.dumps(body.result, default=str)
        # Build a lightweight task-like dict for policy evaluation
        output_check = {
            "name": f"callback-{body.task_id}",
            "description": result_text[:5000],
            "agent_type": body.agent_id,
            "metadata": {"source": "agent_callback", "task_id": body.task_id},
        }
        gate = await state.policy_engine.evaluate(output_check)
        if not gate.approved:
            logger.warning(
                "Callback output rejected by policy: task_id=%s reason=%s",
                body.task_id,
                gate.reason,
            )
            # Update dispatch record but mark as rejected
            dispatch_record["status"] = "rejected"
            dispatch_record["result"] = {
                "rejected": True,
                "reason": gate.reason,
            }
            raise HTTPException(
                status_code=403,
                detail=f"Output policy gate rejected: {gate.reason}",
            )

    # Update dispatch record
    status_val = "completed" if body.success else "failed"
    dispatch_record["status"] = status_val
    dispatch_record["result"] = body.result
    dispatch_record["completed_at"] = datetime.now(timezone.utc).isoformat()

    # Audit log entry
    if state.policy_engine:
        await state.policy_engine.audit(
            actor=body.agent_id,
            action="agent_callback",
            task_id=body.task_id,
            detail={
                "success": body.success,
                "agent_id": body.agent_id,
                "error": body.error,
            },
        )

    # Update workflow state if part of DAG
    if body.workflow_id and body.node_id:
        wf_exec = _workflow_execution_store.get(body.workflow_id)
        if wf_exec is not None:
            wf_exec["node_results"][body.node_id] = {
                "status": status_val,
                "result": body.result,
                "error": body.error,
            }
            # Check if all nodes are complete
            wf_def = _workflow_store.get(body.workflow_id)
            if wf_def:
                all_node_ids = {n.node_id for n in wf_def.nodes}
                completed_nodes = {
                    nid
                    for nid, nr in wf_exec["node_results"].items()
                    if nr.get("status") in ("completed", "failed")
                }
                if all_node_ids == completed_nodes:
                    has_failures = any(
                        nr.get("status") == "failed"
                        for nr in wf_exec["node_results"].values()
                    )
                    wf_exec["status"] = "failed" if has_failures else "completed"
                    wf_exec["finished_at"] = datetime.now(timezone.utc).isoformat()

    logger.info(
        "Callback received: task_id=%s agent_id=%s success=%s",
        body.task_id,
        body.agent_id,
        body.success,
    )

    return AgentCallbackResponse(status="accepted")


# ---------------------------------------------------------------------------
# 3. GET /agents/registry
# ---------------------------------------------------------------------------


@router.get(
    "/agents/registry",
    response_model=AgentRegistryResponse,
    dependencies=[Depends(PermissionChecker("brain", "read"))],
)
async def list_agent_registry(
    state: AppState = Depends(get_state),
) -> AgentRegistryResponse:
    """List all 8 registered OpenClaw agents with status, sub-agents, and skill counts."""
    # Merge OCCP agent store with OpenClaw registry
    registered_agents = await state.list_agents()
    registered_types = {a.agent_type for a in registered_agents}

    entries: list[AgentRegistryEntry] = []
    for agent_def in _OPENCLAW_AGENTS:
        agent_id = agent_def["agent_id"]
        sub_agents = [
            SubAgentInfo(
                id=sa["id"],
                name=sa["name"],
                skills=sa["skills"],
            )
            for sa in agent_def.get("sub_agents", [])
        ]
        total_skills = sum(len(sa.skills) for sa in sub_agents)

        # Check if agent is registered in OCCP store (= "online")
        is_registered = agent_id in registered_types
        agent_status = "online" if is_registered else "offline"

        # Get capabilities from OCCP store if available
        capabilities: list[str] = []
        max_concurrent = 1
        timeout_seconds = 300
        for reg in registered_agents:
            if reg.agent_type == agent_id:
                capabilities = reg.capabilities
                max_concurrent = reg.max_concurrent
                timeout_seconds = reg.timeout_seconds
                break

        entries.append(
            AgentRegistryEntry(
                agent_id=agent_id,
                name=agent_def["name"],
                agent_type=agent_id,
                model=agent_def.get("model", ""),
                status=agent_status,
                capabilities=capabilities,
                sub_agents=sub_agents,
                skill_count=total_skills,
                max_concurrent=max_concurrent,
                timeout_seconds=timeout_seconds,
            )
        )

    return AgentRegistryResponse(agents=entries, total=len(entries))


# ---------------------------------------------------------------------------
# 4. POST /workflows
# ---------------------------------------------------------------------------


@router.post(
    "/workflows",
    response_model=WorkflowCreateResponse,
    status_code=201,
    dependencies=[Depends(PermissionChecker("workflows", "create"))],
)
async def create_workflow(
    body: WorkflowCreateRequest,
    state: AppState = Depends(get_state),
) -> WorkflowCreateResponse:
    """Create a multi-agent DAG workflow.

    Validates the DAG has no cycles and returns the workflow_id with
    computed execution waves.
    """
    workflow_id = uuid.uuid4().hex[:16]

    # Build WorkflowDefinition from request
    nodes = [
        AgentNode(
            node_id=t.node_id,
            agent_type=t.agent_type,
            task_template={
                "name": t.task_name or t.node_id,
                "description": t.description,
                "metadata": t.metadata,
            },
            depends_on=t.depends_on,
            timeout_seconds=t.timeout_seconds,
            retry_count=t.retry_count,
        )
        for t in body.tasks
    ]

    definition = WorkflowDefinition(
        workflow_id=workflow_id,
        name=body.name,
        nodes=nodes,
        metadata=body.metadata,
    )

    # Validate (no cycles, valid references)
    issues = definition.validate()
    if issues:
        raise HTTPException(
            status_code=422,
            detail=f"Workflow validation failed: {'; '.join(issues)}",
        )

    # Compute waves
    waves = definition.topological_sort()

    # Store (in-memory)
    _workflow_store[workflow_id] = definition
    _workflow_execution_store[workflow_id] = {
        "workflow_id": workflow_id,
        "name": body.name,
        "status": "pending",
        "node_results": {},
        "started_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": None,
        "waves": waves,
    }

    # Persist to DB (workflow_executions table) using db.session_factory
    db = getattr(state, "db", None)
    if db is not None:
        try:
            from store.models import WorkflowExecutionRow
            execution_id = uuid.uuid4().hex[:16]
            async with db.session_factory() as session:
                row = WorkflowExecutionRow(
                    execution_id=execution_id,
                    workflow_id=workflow_id,
                    status="pending",
                    dag_definition={"nodes": [n.__dict__ for n in nodes], "waves": waves, "name": body.name},
                    node_results={},
                    checkpoints=[],
                    current_wave=0,
                    started_at=datetime.now(timezone.utc),
                )
                session.add(row)
                await session.commit()
            logger.info("Workflow execution persisted: %s", execution_id)
        except Exception as exc:
            logger.warning("Workflow DB persistence failed: %s", exc)

    # Audit
    if state.policy_engine:
        await state.policy_engine.audit(
            actor="brain",
            action="workflow_create",
            task_id=workflow_id,
            detail={
                "name": body.name,
                "node_count": len(nodes),
                "wave_count": len(waves),
            },
        )

    logger.info(
        "Workflow created: id=%s name=%s nodes=%d waves=%d",
        workflow_id,
        body.name,
        len(nodes),
        len(waves),
    )

    return WorkflowCreateResponse(
        workflow_id=workflow_id,
        name=body.name,
        node_count=len(nodes),
        waves=waves,
    )


# ---------------------------------------------------------------------------
# 5. GET /workflows/{workflow_id}/status
# ---------------------------------------------------------------------------


@router.get(
    "/workflows/{workflow_id}/status",
    response_model=WorkflowStatusResponse,
    dependencies=[Depends(PermissionChecker("workflows", "read"))],
)
async def get_workflow_status(
    workflow_id: str,
    state: AppState = Depends(get_state),
) -> WorkflowStatusResponse:
    """Get workflow progress with per-node status and wave progress."""
    definition = _workflow_store.get(workflow_id)
    if definition is None:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found")

    execution = _workflow_execution_store.get(workflow_id, {})

    # Build per-node status
    node_statuses: list[WorkflowNodeStatus] = []
    node_results = execution.get("node_results", {})
    for node in definition.nodes:
        nr = node_results.get(node.node_id)
        if nr is None:
            node_status = "pending"
            result = None
            error = None
        else:
            node_status = nr.get("status", "pending")
            result = nr.get("result")
            error = nr.get("error")

        node_statuses.append(
            WorkflowNodeStatus(
                node_id=node.node_id,
                agent_type=node.agent_type,
                status=node_status,
                result=result,
                error=error,
            )
        )

    # Compute wave progress
    waves = execution.get("waves", [])
    completed_nodes = {
        nid
        for nid, nr in node_results.items()
        if nr.get("status") in ("completed", "failed")
    }
    wave_progress = 0
    for wave in waves:
        if all(nid in completed_nodes for nid in wave):
            wave_progress += 1
        else:
            break

    return WorkflowStatusResponse(
        workflow_id=workflow_id,
        name=definition.name,
        status=execution.get("status", "pending"),
        nodes=node_statuses,
        waves=waves,
        wave_progress=wave_progress,
        total_waves=len(waves),
        started_at=execution.get("started_at"),
        finished_at=execution.get("finished_at"),
        error=execution.get("error"),
    )


# ---------------------------------------------------------------------------
# 6. GET /workflows/{workflow_id}/executions
# ---------------------------------------------------------------------------


@router.get(
    "/workflows/{workflow_id}/executions",
    response_model=WorkflowExecutionListResponse,
    dependencies=[Depends(PermissionChecker("workflows", "read"))],
)
async def list_workflow_executions(
    workflow_id: str,
    state: AppState = Depends(get_state),
) -> WorkflowExecutionListResponse:
    """List all executions for a workflow (from persistent store)."""
    if not hasattr(state, "workflow_store") or state.workflow_store is None:
        # Fallback to in-memory store
        wf_exec = _workflow_execution_store.get(workflow_id)
        if wf_exec is None:
            return WorkflowExecutionListResponse(executions=[], total=0)
        summary = WorkflowExecutionSummary(
            execution_id=wf_exec.get("workflow_id", workflow_id),
            workflow_id=workflow_id,
            status=wf_exec.get("status", "pending"),
            current_wave=0,
            node_results=wf_exec.get("node_results", {}),
            started_at=wf_exec.get("started_at"),
            finished_at=wf_exec.get("finished_at"),
        )
        return WorkflowExecutionListResponse(executions=[summary], total=1)

    rows = await state.workflow_store.list_workflow_executions(workflow_id)
    executions = [
        WorkflowExecutionSummary(
            execution_id=r.execution_id,
            workflow_id=r.workflow_id,
            status=r.status,
            current_wave=r.current_wave,
            node_results=r.node_results or {},
            checkpoints=r.checkpoints or [],
            started_at=r.started_at,
            finished_at=r.finished_at,
            error_detail=r.error_detail,
        )
        for r in rows
    ]
    return WorkflowExecutionListResponse(executions=executions, total=len(executions))


# ---------------------------------------------------------------------------
# 7. POST /workflows/{workflow_id}/resume
# ---------------------------------------------------------------------------


@router.post(
    "/workflows/{workflow_id}/resume",
    response_model=WorkflowResumeResponse,
    dependencies=[Depends(PermissionChecker("workflows", "create"))],
)
async def resume_workflow(
    workflow_id: str,
    state: AppState = Depends(get_state),
) -> WorkflowResumeResponse:
    """Resume an interrupted workflow execution.

    Finds the most recent interrupted execution for the given workflow_id
    and resumes it from the last checkpoint.
    """
    if not hasattr(state, "workflow_store") or state.workflow_store is None:
        raise HTTPException(
            status_code=501,
            detail="Workflow persistence not configured — cannot resume",
        )

    # Find the most recent interrupted execution for this workflow
    rows = await state.workflow_store.list_workflow_executions(workflow_id)
    interrupted = [
        r for r in rows if r.status in ("running", "paused")
    ]
    if not interrupted:
        raise HTTPException(
            status_code=404,
            detail=f"No interrupted executions found for workflow '{workflow_id}'",
        )

    target = interrupted[0]  # Most recent (ordered by started_at desc)

    # Use the orchestrator to resume if available
    from orchestrator.multi_agent import MultiAgentOrchestrator, WorkflowDefinition

    # Build a minimal orchestrator with the workflow store
    orchestrator = MultiAgentOrchestrator(
        state.scheduler,
        workflow_store=state.workflow_store,
    )

    # Register the workflow from the persisted DAG definition
    definition = WorkflowDefinition.from_dict(target.dag_definition)
    orchestrator.register_workflow(definition)

    try:
        execution = await orchestrator.resume_execution(target.execution_id)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Resume failed: {exc}",
        )

    return WorkflowResumeResponse(
        execution_id=execution.execution_id,
        workflow_id=execution.workflow_id,
        status=execution.status.value,
        resumed_from_wave=target.current_wave,
        node_results=execution.node_results,
    )


# ---------------------------------------------------------------------------
# Parallel Dispatch (singleton dispatcher per process)
# ---------------------------------------------------------------------------

_parallel_dispatcher: ParallelDispatcher | None = None


def _get_parallel_dispatcher(state: AppState) -> ParallelDispatcher:
    """Return or create the process-level ParallelDispatcher."""
    global _parallel_dispatcher
    if _parallel_dispatcher is None:
        _parallel_dispatcher = ParallelDispatcher(
            max_concurrent=state.settings.parallel_dispatch_max_concurrent,
            default_timeout=state.settings.parallel_dispatch_default_timeout,
        )
    return _parallel_dispatcher


# ---------------------------------------------------------------------------
# POST /agents/parallel-dispatch
# ---------------------------------------------------------------------------


@router.post(
    "/agents/parallel-dispatch",
    response_model=ParallelDispatchResponse,
    dependencies=[Depends(PermissionChecker("brain", "dispatch"))],
)
async def parallel_dispatch(
    body: ParallelDispatchRequest,
    state: AppState = Depends(get_state),
) -> ParallelDispatchResponse:
    """Dispatch tasks to multiple agents simultaneously.

    Each task is dispatched in parallel with concurrency control.
    Failed tasks do not block other tasks (partial failure tolerance).
    """
    dispatcher = _get_parallel_dispatcher(state)

    # Validate agent IDs
    known_agent_ids = {a["agent_id"] for a in _OPENCLAW_AGENTS}

    task_defs: list[dict[str, Any]] = []
    for task_item in body.tasks:
        if task_item.agent_id not in known_agent_ids:
            cfg = await state.get_agent(task_item.agent_id)
            if cfg is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Agent '{task_item.agent_id}' not found",
                )
        task_def: dict[str, Any] = {
            "agent_id": task_item.agent_id,
            "input": task_item.input,
        }
        if task_item.timeout is not None:
            task_def["timeout"] = task_item.timeout
        task_defs.append(task_def)

    dispatch_state = await dispatcher.dispatch(task_defs)

    task_statuses = [
        ParallelDispatchTaskStatus(
            agent_id=t.agent_id,
            status=t.status.value,
            result=t.result if isinstance(t.result, dict) else None,
            error=t.error,
        )
        for t in dispatch_state.tasks
    ]

    if state.policy_engine:
        await state.policy_engine.audit(
            actor="brain",
            action="parallel_dispatch",
            task_id=dispatch_state.dispatch_id,
            detail={
                "total": dispatch_state.total,
                "completed": dispatch_state.completed,
                "failed": dispatch_state.failed,
            },
        )

    logger.info(
        "Parallel dispatch: id=%s total=%d completed=%d failed=%d",
        dispatch_state.dispatch_id,
        dispatch_state.total,
        dispatch_state.completed,
        dispatch_state.failed,
    )

    return ParallelDispatchResponse(
        dispatch_id=dispatch_state.dispatch_id,
        tasks=task_statuses,
    )


# ---------------------------------------------------------------------------
# GET /agents/parallel-dispatch/{dispatch_id}
# ---------------------------------------------------------------------------


@router.get(
    "/agents/parallel-dispatch/{dispatch_id}",
    response_model=ParallelDispatchStatusResponse,
    dependencies=[Depends(PermissionChecker("brain", "read"))],
)
async def get_parallel_dispatch_status(
    dispatch_id: str,
    state: AppState = Depends(get_state),
) -> ParallelDispatchStatusResponse:
    """Check the status of a parallel dispatch batch."""
    dispatcher = _get_parallel_dispatcher(state)
    dispatch_state = dispatcher.get_dispatch(dispatch_id)

    if dispatch_state is None:
        raise HTTPException(
            status_code=404,
            detail=f"Parallel dispatch '{dispatch_id}' not found",
        )

    results = [
        ParallelDispatchTaskStatus(
            agent_id=t.agent_id,
            status=t.status.value,
            result=t.result if isinstance(t.result, dict) else None,
            error=t.error,
        )
        for t in dispatch_state.tasks
    ]

    return ParallelDispatchStatusResponse(
        dispatch_id=dispatch_state.dispatch_id,
        total=dispatch_state.total,
        completed=dispatch_state.completed,
        failed=dispatch_state.failed,
        pending=dispatch_state.pending,
        results=results,
    )


# ---------------------------------------------------------------------------
# POST /brain/message — direct BrainFlowEngine invocation (non-Telegram path)
# ---------------------------------------------------------------------------


@router.post(
    "/brain/message",
    response_model=BrainMessageResponse,
    dependencies=[Depends(PermissionChecker("brain", "dispatch"))],
)
async def brain_message(
    body: BrainMessageRequest,
    state: AppState = Depends(get_state),
) -> BrainMessageResponse:
    """Direct BrainFlow invocation — bypasses Telegram channel.

    Allows API-authenticated clients (CloudCode, dashboard, CI) to push
    messages directly to Brian the Brain, exercising the full 7-phase
    conversation flow and persistence layer.

    Persistence: brain_conversations table fills automatically via
    BrainFlowEngine._persist_conversation on phase transitions.
    """
    brain_flow = getattr(state, "brain_flow", None)
    if brain_flow is None:
        raise HTTPException(
            status_code=503,
            detail="BrainFlowEngine not initialized",
        )

    # Input sanitization (OWASP ASI01)
    san = _input_sanitizer.sanitize(body.message, channel="api")
    if not san.safe:
        raise HTTPException(
            status_code=422,
            detail=f"Input blocked: {san.threats_detected}",
        )

    try:
        response = await brain_flow.process_message(
            user_id=body.user_id,
            message=san.sanitized,
            conversation_id=body.conversation_id,
        )
    except Exception as exc:
        logger.error("BrainFlow error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"BrainFlow error: {exc}")

    return BrainMessageResponse(
        text=response.get("text", ""),
        phase=response.get("phase", "unknown"),
        conversation_id=response.get("conversation_id", ""),
        actions=response.get("actions", []),
        metadata=response.get("metadata", {}),
    )


# ---------------------------------------------------------------------------
# Module-level helpers for testing
# ---------------------------------------------------------------------------


def get_dispatch_store() -> dict[str, dict[str, Any]]:
    """Return the dispatch store (for testing)."""
    return _dispatch_store


def get_workflow_store() -> dict[str, WorkflowDefinition]:
    """Return the workflow store (for testing)."""
    return _workflow_store


def get_workflow_execution_store() -> dict[str, dict[str, Any]]:
    """Return the workflow execution store (for testing)."""
    return _workflow_execution_store


def get_parallel_dispatcher() -> ParallelDispatcher | None:
    """Return the parallel dispatcher (for testing)."""
    return _parallel_dispatcher


def clear_stores() -> None:
    """Clear all in-memory stores (for testing)."""
    global _parallel_dispatcher, _openclaw_client
    _dispatch_store.clear()
    _workflow_store.clear()
    _workflow_execution_store.clear()
    _parallel_dispatcher = None
    _openclaw_client = None


def set_openclaw_client(client: OpenClawClient | None) -> None:
    """Override the OpenClaw client (for testing)."""
    global _openclaw_client
    _openclaw_client = client
