"""Add users table for RBAC authentication.

Revision ID: 002
Revises: 001
Create Date: 2026-02-23

Adds the users table with argon2 password hashing, hierarchical
roles (system_admin > org_admin > operator > viewer), and indexes
on username and role.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("username", sa.String(128), unique=True, nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(32), nullable=False, server_default="viewer"),
        sa.Column("is_active", sa.Boolean(), server_default="1"),
        sa.Column("display_name", sa.String(128), server_default=""),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("metadata", sa.Text(), server_default="{}"),
        sa.Column("created_at", sa.String(64), nullable=False),
        sa.Column("updated_at", sa.String(64), nullable=False),
    )
    op.create_index("idx_users_username", "users", ["username"])
    op.create_index("idx_users_role", "users", ["role"])


def downgrade() -> None:
    op.drop_table("users")
