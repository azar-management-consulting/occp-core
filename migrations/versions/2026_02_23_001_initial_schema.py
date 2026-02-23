"""Initial schema — captures existing tasks, audit_entries, agent_configs tables.

Revision ID: 001
Revises: None
Create Date: 2026-02-23

This is a baseline migration. Existing databases already have these tables
created by Database.connect() → Base.metadata.create_all(). New databases
get them from this migration via ``alembic upgrade head``.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### tasks ###
    op.create_table(
        "tasks",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), server_default=""),
        sa.Column("agent_type", sa.String(64), server_default="default"),
        sa.Column("risk_level", sa.String(16), server_default="low"),
        sa.Column("status", sa.String(32), server_default="pending"),
        sa.Column("plan", sa.Text(), nullable=True),
        sa.Column("result", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("metadata", sa.Text(), server_default="{}"),
        sa.Column("created_at", sa.String(64), nullable=False),
        sa.Column("updated_at", sa.String(64), nullable=False),
    )
    op.create_index("idx_tasks_status", "tasks", ["status"])
    op.create_index("idx_tasks_created", "tasks", ["created_at"])

    # ### audit_entries ###
    op.create_table(
        "audit_entries",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("timestamp", sa.String(64), nullable=False),
        sa.Column("actor", sa.String(128), nullable=False),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("task_id", sa.String(32), nullable=True),
        sa.Column("detail", sa.Text(), server_default="{}"),
        sa.Column("prev_hash", sa.String(64), nullable=False),
        sa.Column("hash", sa.String(64), nullable=False),
    )
    op.create_index("idx_audit_task", "audit_entries", ["task_id"])
    op.create_index("idx_audit_ts", "audit_entries", ["timestamp"])

    # ### agent_configs ###
    op.create_table(
        "agent_configs",
        sa.Column("agent_type", sa.String(64), primary_key=True),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("capabilities", sa.Text(), server_default="[]"),
        sa.Column("max_concurrent", sa.Integer(), server_default="1"),
        sa.Column("timeout_seconds", sa.Integer(), server_default="300"),
        sa.Column("metadata", sa.Text(), server_default="{}"),
        sa.Column("created_at", sa.String(64), nullable=False),
        sa.Column("updated_at", sa.String(64), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("agent_configs")
    op.drop_table("audit_entries")
    op.drop_table("tasks")
