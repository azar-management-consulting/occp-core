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
    environment: str = "production"
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
# Auth / Users / Admin
# ---------------------------------------------------------------------------


class MeResponse(BaseModel):
    username: str
    role: str
    display_name: str = ""


class UserListItem(BaseModel):
    id: str
    username: str
    role: str
    display_name: str = ""
    is_active: bool = True
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    users: list[UserListItem]
    total: int


class OnboardingFunnel(BaseModel):
    landing: int = 0
    running: int = 0
    done: int = 0


class UserActivity(BaseModel):
    username: str
    role: str
    last_action: str = ""
    last_seen: str = ""
    onboarding_state: str = ""


class AdminStatsResponse(BaseModel):
    users_total: int = 0
    users_by_role: dict[str, int] = Field(default_factory=dict)
    registrations_last_7_days: int = 0
    onboarding_funnel: OnboardingFunnel = Field(default_factory=OnboardingFunnel)
    user_activity: list[UserActivity] = Field(default_factory=list)


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


# ---------------------------------------------------------------------------
# Brain Webhook Gateway (Agent Dispatch / Callback / Workflows)
# ---------------------------------------------------------------------------

class TaskDispatchRequest(BaseModel):
    """Request body for dispatching a task to an OpenClaw agent."""

    task_name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1, max_length=5000)
    agent_type: str = Field(default="general", max_length=100)
    priority: str = Field(default="normal", pattern=r"^(low|normal|high|critical)$")
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaskDispatchResponse(BaseModel):
    """Response for a dispatched task."""

    task_id: str
    status: str = "dispatched"
    agent_id: str


class AgentCallbackRequest(BaseModel):
    """Incoming result from an OpenClaw agent callback."""

    task_id: str = Field(..., min_length=1)
    agent_id: str = Field(..., min_length=1)
    result: dict[str, Any] = Field(default_factory=dict)
    success: bool = True
    error: str | None = None
    workflow_id: str | None = None
    node_id: str | None = None


class AgentCallbackResponse(BaseModel):
    """Response to an agent callback."""

    status: str = "accepted"


class SubAgentInfo(BaseModel):
    """Sub-agent info within an agent registry entry."""

    id: str
    name: str
    skills: list[str] = Field(default_factory=list)


class AgentRegistryEntry(BaseModel):
    """Extended agent info for the registry endpoint."""

    agent_id: str
    name: str
    agent_type: str
    model: str = ""
    status: str = "offline"  # online | offline
    capabilities: list[str] = Field(default_factory=list)
    sub_agents: list[SubAgentInfo] = Field(default_factory=list)
    skill_count: int = 0
    max_concurrent: int = 1
    timeout_seconds: int = 300


class AgentRegistryResponse(BaseModel):
    """Response for the agent registry listing."""

    agents: list[AgentRegistryEntry]
    total: int


class BatchDispatchItem(BaseModel):
    """A single item within a batch dispatch request."""

    agent_id: str = Field(..., min_length=1, max_length=100)
    task_name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1, max_length=5000)
    agent_type: str = Field(default="general", max_length=100)
    priority: str = Field(default="normal", pattern=r"^(low|normal|high|critical)$")
    metadata: dict[str, Any] = Field(default_factory=dict)


class BatchDispatchRequest(BaseModel):
    """Request body for batch-dispatching tasks to multiple agents."""

    items: list[BatchDispatchItem] = Field(..., min_length=1, max_length=50)


class BatchDispatchResultItem(BaseModel):
    """Result for a single batch dispatch item."""

    agent_id: str
    task_id: str | None = None
    status: str  # "dispatched" | "error"
    error: str | None = None


class BatchDispatchResponse(BaseModel):
    """Response for batch dispatch."""

    results: list[BatchDispatchResultItem]
    total: int
    dispatched: int
    failed: int


class WorkflowTaskNode(BaseModel):
    """A task node within a workflow creation request."""

    node_id: str = Field(..., min_length=1, max_length=100)
    agent_type: str = Field(..., min_length=1, max_length=100)
    task_name: str = Field(default="", max_length=200)
    description: str = Field(default="", max_length=5000)
    depends_on: list[str] = Field(default_factory=list)
    timeout_seconds: int = Field(default=0, ge=0, le=3600)
    retry_count: int = Field(default=0, ge=0, le=5)
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkflowCreateRequest(BaseModel):
    """Request body for creating a multi-agent DAG workflow."""

    name: str = Field(..., min_length=1, max_length=200)
    tasks: list[WorkflowTaskNode] = Field(..., min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkflowCreateResponse(BaseModel):
    """Response for a created workflow."""

    workflow_id: str
    name: str
    node_count: int
    waves: list[list[str]]


class WorkflowNodeStatus(BaseModel):
    """Status of a single node in a workflow."""

    node_id: str
    agent_type: str
    status: str = "pending"  # pending | running | completed | failed
    result: dict[str, Any] | None = None
    error: str | None = None


class WorkflowStatusResponse(BaseModel):
    """Response for workflow progress."""

    workflow_id: str
    name: str
    status: str  # pending | running | completed | failed | killed
    nodes: list[WorkflowNodeStatus] = Field(default_factory=list)
    waves: list[list[str]] = Field(default_factory=list)
    wave_progress: int = 0
    total_waves: int = 0
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None


class WorkflowExecutionSummary(BaseModel):
    """Summary of a single workflow execution."""

    execution_id: str
    workflow_id: str
    status: str
    current_wave: int = 0
    node_results: dict[str, Any] = Field(default_factory=dict)
    checkpoints: list[dict[str, Any]] = Field(default_factory=list)
    started_at: str | None = None
    finished_at: str | None = None
    error_detail: str | None = None


class WorkflowExecutionListResponse(BaseModel):
    """Response for listing workflow executions."""

    executions: list[WorkflowExecutionSummary]
    total: int


class WorkflowResumeResponse(BaseModel):
    """Response for resuming an interrupted workflow."""

    execution_id: str
    workflow_id: str
    status: str
    resumed_from_wave: int = 0
    node_results: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Parallel Dispatch
# ---------------------------------------------------------------------------


class ParallelDispatchTaskItem(BaseModel):
    """A single task within a parallel dispatch request."""

    agent_id: str = Field(..., min_length=1, max_length=100)
    input: str = Field(..., min_length=1, max_length=10000)
    timeout: int | None = Field(default=None, ge=1, le=3600)


class ParallelDispatchRequest(BaseModel):
    """Request body for parallel dispatch to multiple agents."""

    tasks: list[ParallelDispatchTaskItem] = Field(..., min_length=1, max_length=50)


class ParallelDispatchTaskStatus(BaseModel):
    """Status of a single task in a parallel dispatch."""

    agent_id: str
    status: str  # dispatched | running | completed | failed | timeout
    result: dict[str, Any] | None = None
    error: str | None = None


class ParallelDispatchResponse(BaseModel):
    """Response for a parallel dispatch request."""

    dispatch_id: str
    tasks: list[ParallelDispatchTaskStatus]


class ParallelDispatchStatusResponse(BaseModel):
    """Response for checking parallel dispatch status."""

    dispatch_id: str
    total: int
    completed: int
    failed: int
    pending: int
    results: list[ParallelDispatchTaskStatus]


# ---------------------------------------------------------------------------
# Projects (10-project concurrent routing)
# ---------------------------------------------------------------------------


class ProjectCreate(BaseModel):
    """Request body for creating a project."""

    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)
    agents: list[str] = Field(default_factory=list)
    priority: int = Field(default=5, ge=1, le=10)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProjectUpdate(BaseModel):
    """Request body for updating a project."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    status: str | None = Field(default=None, pattern=r"^(active|paused|completed|archived)$")
    priority: int | None = Field(default=None, ge=1, le=10)
    metadata: dict[str, Any] | None = None


class ProjectResponse(BaseModel):
    """Response for a project."""

    project_id: str
    name: str
    description: str
    status: str
    assigned_agents: list[str] = Field(default_factory=list)
    priority: int = 5
    created_at: str
    updated_at: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProjectListResponse(BaseModel):
    """Response for listing projects."""

    projects: list[ProjectResponse]
    total: int


class ProjectStatusResponse(BaseModel):
    """Full project status dashboard data."""

    project: ProjectResponse
    agents: list[str] = Field(default_factory=list)
    agent_count: int = 0
    workflow_ids: list[str] = Field(default_factory=list)
    workflow_count: int = 0
    task_ids: list[str] = Field(default_factory=list)
    task_count: int = 0


class ProjectDispatchRequest(BaseModel):
    """Request body for dispatching a task within a project."""

    task_input: str = Field(..., min_length=1, max_length=10000)


class ProjectDispatchResponse(BaseModel):
    """Response for a dispatched project task."""

    task_id: str
    project_id: str
    status: str = "dispatched"


class ProjectAgentAssign(BaseModel):
    """Request body for assigning an agent to a project."""

    agent_id: str = Field(..., min_length=1, max_length=100)


# ---------------------------------------------------------------------------
# Brain Flow — direct conversation endpoint
# ---------------------------------------------------------------------------

class BrainMessageRequest(BaseModel):
    """Direct input to BrainFlowEngine from API (non-Telegram path)."""

    message: str = Field(..., min_length=1, max_length=5000)
    user_id: str = Field(default="api-user", max_length=100)
    conversation_id: str | None = Field(default=None, max_length=128)


class BrainMessageResponse(BaseModel):
    """BrainFlowEngine response — phase + text + optional actions."""

    text: str
    phase: str
    conversation_id: str
    actions: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
