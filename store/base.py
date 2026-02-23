"""SQLAlchemy 2.0 declarative base with cross-dialect support.

Provides:
- ``Base`` — DeclarativeBase with naming convention for Alembic
- ``GUID`` — UUID on PostgreSQL, CHAR(32) on SQLite
- ``JSONBText`` — JSONB on PostgreSQL, JSON-as-TEXT on SQLite
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import MetaData, Text, types
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase

# ── Naming Convention ─────────────────────────────────────────────────
# Ensures Alembic auto-generates consistent constraint names across
# dialects, which is required for batch operations on SQLite.
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Shared declarative base for all OCCP ORM models."""

    metadata = MetaData(naming_convention=convention)


# ── TypeDecorators ────────────────────────────────────────────────────


class GUID(types.TypeDecorator[uuid.UUID]):
    """Platform-independent UUID type.

    Uses PostgreSQL ``UUID`` when available, stores as ``CHAR(32)``
    (hex without dashes) on other dialects.
    """

    impl = types.CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(UUID(as_uuid=True))
        return dialect.type_descriptor(types.CHAR(32))

    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
        if value is None:
            return None
        if dialect.name == "postgresql":
            return str(value)
        if isinstance(value, uuid.UUID):
            return value.hex
        return uuid.UUID(value).hex

    def process_result_value(self, value: Any, dialect: Any) -> uuid.UUID | None:
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(value)


class JSONBText(types.TypeDecorator[dict[str, Any] | list[Any]]):
    """Platform-independent JSON type.

    Uses PostgreSQL ``JSONB`` for indexing/querying when available,
    falls back to ``TEXT`` with JSON serialisation on SQLite.
    """

    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value  # asyncpg handles dict → JSONB
        return json.dumps(value, default=str)

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str):
            return json.loads(value)
        return value
