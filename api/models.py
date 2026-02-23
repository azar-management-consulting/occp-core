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
