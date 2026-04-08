"""SQLAlchemy 2.0 ORM models for OCCP persistent storage.

Maps to three existing tables (tasks, audit_entries, agent_configs)
with zero schema changes — backward-compatible with legacy raw-SQL stores.

All models use cross-dialect types (GUID, JSONBText) for seamless
SQLite ↔ PostgreSQL operation.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, DateTime, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from store.base import Base, JSONBText

from typing import Optional


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── Tasks ─────────────────────────────────────────────────────────────


class TaskRow(Base):
    """Persisted pipeline task — maps to ``tasks`` table."""

    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    agent_type: Mapped[str] = mapped_column(String(64), default="default")
    risk_level: Mapped[str] = mapped_column(String(16), default="low")
    status: Mapped[str] = mapped_column(String(32), default="pending")
    plan: Mapped[dict | None] = mapped_column(JSONBText(), nullable=True)
    result: Mapped[dict | None] = mapped_column(JSONBText(), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONBText(), default=dict
    )
    created_at: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        Index("idx_tasks_status", "status"),
        Index("idx_tasks_created", "created_at"),
    )


# ── Audit Log ─────────────────────────────────────────────────────────


class AuditEntryRow(Base):
    """Tamper-evident audit entry — maps to ``audit_entries`` table.

    The ``prev_hash`` / ``hash`` chain is managed by the PolicyEngine,
    not by the ORM layer.  The model merely persists the values.
    """

    __tablename__ = "audit_entries"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    timestamp: Mapped[str] = mapped_column(String(64), nullable=False)
    actor: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    task_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    detail: Mapped[dict] = mapped_column(JSONBText(), default=dict)
    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    hash: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        Index("idx_audit_task", "task_id"),
        Index("idx_audit_ts", "timestamp"),
    )


# ── Agent Configs ─────────────────────────────────────────────────────


class AgentConfigRow(Base):
    """Registered agent configuration — maps to ``agent_configs`` table."""

    __tablename__ = "agent_configs"

    agent_type: Mapped[str] = mapped_column(String(64), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    capabilities: Mapped[list] = mapped_column(JSONBText(), default=list)
    max_concurrent: Mapped[int] = mapped_column(Integer, default=1)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=300)
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONBText(), default=dict
    )
    created_at: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(64), nullable=False)


# ── Users ────────────────────────────────────────────────────────────


class UserRow(Base):
    """Registered user with hashed password and RBAC role."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    username: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="viewer")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    display_name: Mapped[str] = mapped_column(String(128), default="")
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONBText(), default=dict
    )
    created_at: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        Index("idx_users_username", "username"),
        Index("idx_users_role", "role"),
    )


# ── Onboarding Progress ─────────────────────────────────────────────


class OnboardingProgressRow(Base):
    """Onboarding wizard progress — maps to ``onboarding_progress`` table."""

    __tablename__ = "onboarding_progress"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    org_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    state: Mapped[str] = mapped_column(
        String(32), nullable=False, default="landing"
    )
    current_step: Mapped[int] = mapped_column(Integer, default=0)
    completed_steps: Mapped[list] = mapped_column(JSONBText(), default=list)
    completed_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    run_id: Mapped[str] = mapped_column(String(32), default="")
    audit_linkage: Mapped[str] = mapped_column(String(64), default="")
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONBText(), default=dict
    )
    completed_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        Index("idx_onboarding_org", "org_id"),
    )


# -- Encrypted Tokens -------------------------------------------------------


class EncryptedTokenRow(Base):
    """Encrypted LLM API token — maps to ``encrypted_tokens`` table.

    Tokens are stored as AES-256-GCM encrypted blobs.  Only masked
    values are ever returned via API; decryption happens server-side
    only when the pipeline needs to call an LLM provider.
    """

    __tablename__ = "encrypted_tokens"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    org_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    encrypted_value: Mapped[str] = mapped_column(Text, nullable=False)
    masked_value: Mapped[str] = mapped_column(String(32), default="***")
    label: Mapped[str] = mapped_column(String(128), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        Index("idx_tokens_user_provider", "user_id", "provider"),
        Index("idx_tokens_user_active", "user_id", "is_active"),
        Index("idx_tokens_org_provider", "org_id", "provider"),
    )


# ── Workflow Executions ──────────────────────────────────────────────


class WorkflowExecutionRow(Base):
    """Persisted workflow execution state — maps to ``workflow_executions`` table.

    Stores DAG definition, per-node results, checkpoints, and wave progress
    so that workflow state survives process restarts and can be resumed.
    """

    __tablename__ = "workflow_executions"

    execution_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workflow_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    dag_definition: Mapped[dict] = mapped_column(JSONBText(), default=dict)
    node_results: Mapped[dict] = mapped_column(JSONBText(), default=dict)
    checkpoints: Mapped[list] = mapped_column(JSONBText(), default=list)
    current_wave: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[str] = mapped_column(String(64), nullable=False)
    finished_at: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    error_detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("idx_wfexec_workflow_id", "workflow_id"),
        Index("idx_wfexec_status", "status"),
    )
