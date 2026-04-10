"""Add encrypted_tokens table for per-user LLM API key storage.

Revision ID: 003
Revises: 002
Create Date: 2026-02-27

Adds the encrypted_tokens table with AES-256-GCM envelope encryption.
Tokens are encrypted at rest — only masked values in API responses.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "encrypted_tokens",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("encrypted_value", sa.Text(), nullable=False),
        sa.Column("masked_value", sa.String(32), server_default="***"),
        sa.Column("label", sa.String(128), server_default=""),
        sa.Column("is_active", sa.Boolean(), server_default="1"),
        sa.Column("created_at", sa.String(64), nullable=False),
        sa.Column("updated_at", sa.String(64), nullable=False),
    )
    op.create_index(
        "idx_tokens_user_provider",
        "encrypted_tokens",
        ["user_id", "provider"],
    )
    op.create_index(
        "idx_tokens_user_active",
        "encrypted_tokens",
        ["user_id", "is_active"],
    )


def downgrade() -> None:
    op.drop_table("encrypted_tokens")
