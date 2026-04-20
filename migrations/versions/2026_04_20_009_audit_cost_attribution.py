"""Add cost-attribution columns to audit_entries.

Revision ID: 009
Revises: 008
Create Date: 2026-04-20

Adds nullable columns that mirror the full Anthropic ``response.usage``
payload plus two derived values (``computed_usd``, ``cache_hit_ratio``).

All columns are nullable so existing rows remain valid and the migration
is safe to run against a populated production database.  The operation
is idempotent: if a column already exists (e.g. because
``Base.metadata.create_all`` ran earlier) it is skipped.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_NEW_COLUMNS: list[sa.Column] = [
    sa.Column("input_tokens", sa.Integer(), nullable=True),
    sa.Column("output_tokens", sa.Integer(), nullable=True),
    sa.Column("cache_read_input_tokens", sa.Integer(), nullable=True),
    sa.Column("cache_creation_input_tokens", sa.Integer(), nullable=True),
    sa.Column("ephemeral_5m_input_tokens", sa.Integer(), nullable=True),
    sa.Column("ephemeral_1h_input_tokens", sa.Integer(), nullable=True),
    sa.Column("model_id", sa.String(64), nullable=True),
    sa.Column("computed_usd", sa.Float(), nullable=True),
    sa.Column("cache_hit_ratio", sa.Float(), nullable=True),
]


def _existing_columns(bind: sa.engine.Connection, table: str) -> set[str]:
    return {c["name"] for c in inspect(bind).get_columns(table)}


def _existing_indexes(bind: sa.engine.Connection, table: str) -> set[str]:
    return {i["name"] for i in inspect(bind).get_indexes(table)}


def upgrade() -> None:
    bind = op.get_bind()
    existing = _existing_columns(bind, "audit_entries")

    with op.batch_alter_table("audit_entries") as batch:
        for col in _NEW_COLUMNS:
            if col.name not in existing:
                batch.add_column(
                    sa.Column(col.name, col.type, nullable=True)
                )

    # Re-bind after batch operation (SQLite recreates the table).
    bind = op.get_bind()
    if "idx_audit_model" not in _existing_indexes(bind, "audit_entries"):
        op.create_index(
            "idx_audit_model", "audit_entries", ["model_id"]
        )


def downgrade() -> None:
    bind = op.get_bind()
    if "idx_audit_model" in _existing_indexes(bind, "audit_entries"):
        op.drop_index("idx_audit_model", table_name="audit_entries")

    existing = _existing_columns(bind, "audit_entries")
    with op.batch_alter_table("audit_entries") as batch:
        for col in reversed(_NEW_COLUMNS):
            if col.name in existing:
                batch.drop_column(col.name)
