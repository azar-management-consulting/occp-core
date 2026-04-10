"""Add pending_approvals table for ConfirmationGate persistence.

Revision ID: 007
Revises: 006
Create Date: 2026-03-30

Stores pending human approvals so they survive server restarts.
Expired rows are cleaned up automatically by ApprovalStore.cleanup_expired().
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pending_approvals",
        sa.Column("task_id", sa.String(64), primary_key=True),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("plan_summary", sa.Text(), nullable=True, server_default=""),
        sa.Column("risk_level", sa.String(20), nullable=True, server_default="medium"),
        sa.Column("status", sa.String(20), nullable=True, server_default="pending"),
        sa.Column("agent_type", sa.String(64), nullable=True, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
    )
    op.create_index("idx_pending_approvals_chat", "pending_approvals", ["chat_id"])
    op.create_index("idx_pending_approvals_status", "pending_approvals", ["status"])
    op.create_index("idx_pending_approvals_expires", "pending_approvals", ["expires_at"])


def downgrade() -> None:
    op.drop_table("pending_approvals")
