"""Add workflow_executions table for workflow state persistence.

Revision ID: 004
Revises: 003
Create Date: 2026-03-26

Stores DAG definition, per-node results, checkpoints, and wave progress
so that multi-agent workflow state survives process restarts.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workflow_executions",
        sa.Column("execution_id", sa.String(64), primary_key=True),
        sa.Column("workflow_id", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("dag_definition", sa.Text(), nullable=True),
        sa.Column("node_results", sa.Text(), nullable=True),
        sa.Column("checkpoints", sa.Text(), nullable=True),
        sa.Column("current_wave", sa.Integer(), server_default="0"),
        sa.Column("started_at", sa.String(64), nullable=False),
        sa.Column("finished_at", sa.String(64), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
    )
    op.create_index(
        "idx_wfexec_workflow_id",
        "workflow_executions",
        ["workflow_id"],
    )
    op.create_index(
        "idx_wfexec_status",
        "workflow_executions",
        ["status"],
    )


def downgrade() -> None:
    op.drop_table("workflow_executions")
