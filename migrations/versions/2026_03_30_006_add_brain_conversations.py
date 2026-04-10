"""Add brain_conversations table for BrainConversation persistence.

Revision ID: 006
Revises: 004
Create Date: 2026-03-30

Stores the full BrainConversation state so that active conversations
survive server restarts.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "006"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "brain_conversations",
        sa.Column("conversation_id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("phase", sa.String(20), nullable=False, server_default="intake"),
        sa.Column("original_message", sa.Text(), nullable=True, server_default=""),
        sa.Column("clarifying_questions", sa.Text(), nullable=True),
        sa.Column("clarifying_answers", sa.Text(), nullable=True),
        sa.Column("execution_plan", sa.Text(), nullable=True),
        sa.Column("plan_approved", sa.Boolean(), server_default="0"),
        sa.Column("dispatched_tasks", sa.Text(), nullable=True),
        sa.Column("results", sa.Text(), nullable=True),
        sa.Column("feedback_score", sa.Integer(), nullable=True),
        sa.Column("project_id", sa.String(64), nullable=True),
        sa.Column("created_at", sa.String(64), nullable=False),
        sa.Column("updated_at", sa.String(64), nullable=False),
    )
    op.create_index("idx_brain_conv_user", "brain_conversations", ["user_id"])
    op.create_index("idx_brain_conv_phase", "brain_conversations", ["phase"])
    op.create_index("idx_brain_conv_updated", "brain_conversations", ["updated_at"])


def downgrade() -> None:
    op.drop_table("brain_conversations")
