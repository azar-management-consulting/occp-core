"""Add org_id, completed_flag, audit_linkage to onboarding_progress.

Revision ID: 008
Revises: 007
Create Date: 2026-04-08

Fixes schema drift: the OnboardingProgressRow model has three columns
(org_id, completed_flag, audit_linkage) that were never migrated into the
SQLite database, causing ``GET /onboarding/status`` to return 500.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("onboarding_progress") as batch:
        batch.add_column(
            sa.Column("org_id", sa.String(64), nullable=False, server_default="")
        )
        batch.add_column(
            sa.Column("completed_flag", sa.Boolean(), nullable=False, server_default="0")
        )
        batch.add_column(
            sa.Column("audit_linkage", sa.String(64), nullable=False, server_default="")
        )
    op.create_index(
        "idx_onboarding_org",
        "onboarding_progress",
        ["org_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_onboarding_org", table_name="onboarding_progress")
    with op.batch_alter_table("onboarding_progress") as batch:
        batch.drop_column("audit_linkage")
        batch.drop_column("completed_flag")
        batch.drop_column("org_id")
