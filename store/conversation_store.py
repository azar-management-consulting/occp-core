"""Persistent storage for BrainConversation objects.

Survives server restarts. Uses SQLAlchemy async with the existing Database.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import Boolean, Index, Integer, String, Text, delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import Mapped, mapped_column

from store.base import Base, JSONBText

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class BrainConversationRow(Base):
    """Persisted brain conversation — maps to ``brain_conversations`` table."""

    __tablename__ = "brain_conversations"

    conversation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    phase: Mapped[str] = mapped_column(String(20), nullable=False, default="intake")
    original_message: Mapped[str] = mapped_column(Text, default="")
    clarifying_questions: Mapped[list] = mapped_column(JSONBText(), default=list)
    clarifying_answers: Mapped[list] = mapped_column(JSONBText(), default=list)
    execution_plan: Mapped[Optional[dict]] = mapped_column(JSONBText(), nullable=True)
    plan_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    dispatched_tasks: Mapped[list] = mapped_column(JSONBText(), default=list)
    results: Mapped[list] = mapped_column(JSONBText(), default=list)
    feedback_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    project_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        Index("idx_brain_conv_user", "user_id"),
        Index("idx_brain_conv_phase", "phase"),
        Index("idx_brain_conv_updated", "updated_at"),
    )


class ConversationStore:
    """CRUD operations for BrainConversation persistence.

    Args:
        session_factory: An ``async_sessionmaker[AsyncSession]`` from
            ``Database.session_factory`` or ``create_engine_and_session``.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def save(
        self,
        conv_id: str,
        user_id: str,
        phase: str,
        **kwargs: object,
    ) -> None:
        """Upsert a conversation row. Creates if missing, updates if exists."""
        now = _utcnow_iso()
        async with self._session_factory() as session:
            row = await session.get(BrainConversationRow, conv_id)
            if row is not None:
                row.phase = phase
                row.updated_at = now
                for k, v in kwargs.items():
                    if hasattr(BrainConversationRow, k):
                        setattr(row, k, v)
            else:
                filtered = {k: v for k, v in kwargs.items() if hasattr(BrainConversationRow, k)}
                row = BrainConversationRow(
                    conversation_id=conv_id,
                    user_id=user_id,
                    phase=phase,
                    created_at=now,
                    updated_at=now,
                    **filtered,
                )
                session.add(row)
            await session.commit()

    async def get(self, conv_id: str) -> Optional[dict]:
        """Return conversation dict or None."""
        async with self._session_factory() as session:
            row = await session.get(BrainConversationRow, conv_id)
            if row is None:
                return None
            return self._row_to_dict(row)

    async def get_active_by_user(self, user_id: str) -> list[dict]:
        """Return non-terminal conversations for a user, newest first."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(BrainConversationRow)
                .where(BrainConversationRow.user_id == user_id)
                .where(BrainConversationRow.phase.notin_(["completed", "cancelled"]))
                .order_by(BrainConversationRow.updated_at.desc())
            )
            return [self._row_to_dict(r) for r in result.scalars().all()]

    async def cleanup_expired(self, max_age_minutes: int = 30) -> int:
        """Delete stale non-completed conversations older than *max_age_minutes*.

        Returns the number of deleted rows.
        """
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=max_age_minutes)).isoformat()
        async with self._session_factory() as session:
            result = await session.execute(
                delete(BrainConversationRow)
                .where(BrainConversationRow.updated_at < cutoff)
                .where(BrainConversationRow.phase.notin_(["completed"]))
            )
            await session.commit()
            return result.rowcount  # type: ignore[return-value]

    @staticmethod
    def _row_to_dict(row: BrainConversationRow) -> dict:
        return {
            "conversation_id": row.conversation_id,
            "user_id": row.user_id,
            "phase": row.phase,
            "original_message": row.original_message or "",
            "clarifying_questions": row.clarifying_questions or [],
            "clarifying_answers": row.clarifying_answers or [],
            "execution_plan": row.execution_plan,
            "plan_approved": row.plan_approved,
            "dispatched_tasks": row.dispatched_tasks or [],
            "results": row.results or [],
            "feedback_score": row.feedback_score,
            "project_id": row.project_id,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }
