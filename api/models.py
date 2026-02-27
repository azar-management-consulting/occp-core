"""Pydantic v2 request/response schemas for the OCCP REST API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

class TaskCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1, max_length=5000)
    agent_type: str = Field(default="default", max_length=100)
    risk_level: str = Field(default="low")
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaskResponse(BaseModel):
    id: str
    name: str
    description: str
    agent_type: str
    status: str
    risk_level: str
    created_at: datetime
    updated_at: datetime
    plan: dict[str, Any] | None = None
    error: str | None = None

    model_config = {"from_attributes": True}


class TaskListResponse(BaseModel):
    tasks: list[TaskResponse]
    total: int


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

class PipelineRunResponse(BaseModel):
    task_id: str
    success: bool
    status: str
    started_at: datetime
    finished_at: datetime
    evidence: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------

class PolicyEvaluateRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=10000)


class GuardResultResponse(BaseModel):
    guard: str
    passed: bool
    detail: str = ""


class PolicyEvaluateResponse(BaseModel):
    approved: bool
    results: list[GuardResultResponse]


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------

class AuditEntryResponse(BaseModel):
    id: str
    timestamp: datetime
    actor: str
    action: str
    task_id: str
    detail: dict[str, Any] = Field(default_factory=dict)
    prev_hash: str = ""
    hash: str = ""


class AuditLogResponse(BaseModel):
    entries: list[AuditEntryResponse]
    chain_valid: bool
    total: int


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------

class AgentRegistrationRequest(BaseModel):
    agent_type: str = Field(..., min_length=1, max_length=100)
    display_name: str = Field(..., min_length=1, max_length=200)
    capabilities: list[str] = Field(default_factory=list)
    max_concurrent: int = Field(default=1, ge=1, le=100)
    timeout_seconds: int = Field(default=300, ge=1, le=3600)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentResponse(BaseModel):
    agent_type: str
    display_name: str
    capabilities: list[str]
    max_concurrent: int
    timeout_seconds: int
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentListResponse(BaseModel):
    agents: list[AgentResponse]
    total: int


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

class StatusResponse(BaseModel):
    platform: str = "OCCP"
    version: str
    status: str = "running"
    tasks_count: int = 0
    audit_entries: int = 0


class HealthCheck(BaseModel):
    name: str
    status: str  # "ok" | "error"
    latency_ms: float = 0.0
    detail: str = ""


class HealthResponse(BaseModel):
    status: str  # "healthy" | "degraded" | "unhealthy"
    version: str
    checks: list[HealthCheck] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Onboarding (10-step enterprise wizard)
# ---------------------------------------------------------------------------

class OnboardingStatusResponse(BaseModel):
    user_id: str = ""
    token_present: bool
    wizard_state: str  # landing | token_present | running | done
    current_step: int = 0
    current_step_name: str = "landing_cta"
    completed_steps: list[str] = Field(default_factory=list)
    total_steps: int = 10
    steps: list[str] = Field(default_factory=list)
    step_descriptions: dict[str, str] = Field(default_factory=dict)
    run_id: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class OnboardingStartResponse(BaseModel):
    run_id: str
    wizard_state: str
    current_step: int = 0
    current_step_name: str = ""
    completed_steps: list[str] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)


class OnboardingStepResponse(BaseModel):
    step: str
    step_index: int = 0
    completed: bool = True
    wizard_state: str = "running"
    next_step: str | None = None
    completed_steps: list[str] = Field(default_factory=list)
    progress_pct: int = 0


class VerificationCheckResponse(BaseModel):
    all_passed: bool
    checks: list[dict[str, Any]] = Field(default_factory=list)
    total_checks: int = 0
    passed_count: int = 0


# ---------------------------------------------------------------------------
# MCP Connectors
# ---------------------------------------------------------------------------

class MCPConnectorInfo(BaseModel):
    id: str
    name: str
    description: str
    package: str = ""
    category: str = "integration"


class MCPCatalogResponse(BaseModel):
    connectors: list[MCPConnectorInfo]
    total: int


class MCPInstallRequest(BaseModel):
    connector_id: str = Field(..., min_length=1, max_length=100)
    env_vars: dict[str, str] = Field(default_factory=dict)


class MCPInstallResponse(BaseModel):
    connector_id: str
    connector_name: str
    mcp_json: dict[str, Any]
    instructions: str = ""


# ---------------------------------------------------------------------------
# Skills
# ---------------------------------------------------------------------------

class SkillInfo(BaseModel):
    id: str
    name: str
    description: str
    category: str = "general"
    enabled: bool = False
    trusted: bool = True
    token_impact_chars: int = 0
    token_impact_tokens: int = 0


class SkillsListResponse(BaseModel):
    skills: list[SkillInfo]
    total: int
    total_enabled_token_impact: int = 0


# ---------------------------------------------------------------------------
# LLM Health
# ---------------------------------------------------------------------------

class LLMProviderStatus(BaseModel):
    provider: str
    configured: bool
    model: str = ""
    status: str = "not_configured"  # ok | not_configured | error


class LLMHealthResponse(BaseModel):
    status: str  # ok | fallback | error
    active_provider: str = "echo"
    providers: list[LLMProviderStatus] = Field(default_factory=list)
    token_present: bool = False
