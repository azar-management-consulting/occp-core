"""Persistent storage for pending approvals (ConfirmationGate).

Survives restarts. Expired approvals are cleaned up automatically.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import String, Text, BigInteger, DateTime, Index, select, delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import Mapped, mapped_column

from store.base import Base

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PendingApprovalRow(Base):
    """Persisted pending approval — maps to ``pending_approvals`` table."""

    __tablename__ = "pending_approvals"

    task_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    plan_summary: Mapped[str] = mapped_column(Text, default="")
    risk_level: Mapped[str] = mapped_column(String(20), default="medium")
    status: Mapped[str] = mapped_column(String(20), default="pending")
    agent_type: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_pending_approvals_chat", "chat_id"),
        Index("idx_pending_approvals_status", "status"),
        Index("idx_pending_approvals_expires", "expires_at"),
    )


class ApprovalStore:
    """CRUD for pending approval persistence.

    Args:
        session_factory: An ``async_sessionmaker[AsyncSession]`` from
            ``Database.session_factory`` or ``create_engine_and_session``.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def save(
        self,
        task_id: str,
        chat_id: int,
        plan_summary: str,
        risk_level: str,
        agent_type: str = "",
        timeout_seconds: int = 300,
    ) -> None:
        """Upsert a pending approval. Creates if missing, updates if exists."""
        now = _utcnow()
        async with self._session_factory() as session:
            row = await session.get(PendingApprovalRow, task_id)
            if row is not None:
                row.chat_id = chat_id
                row.plan_summary = plan_summary
                row.risk_level = risk_level
                row.agent_type = agent_type
                row.status = "pending"
                row.expires_at = now + timedelta(seconds=timeout_seconds)
            else:
                row = PendingApprovalRow(
                    task_id=task_id,
                    chat_id=chat_id,
                    plan_summary=plan_summary,
                    risk_level=risk_level,
                    agent_type=agent_type,
                    status="pending",
                    created_at=now,
                    expires_at=now + timedelta(seconds=timeout_seconds),
                )
                session.add(row)
            await session.commit()

    async def get(self, task_id: str) -> Optional[dict]:
        """Return approval dict or None."""
        async with self._session_factory() as session:
            row = await session.get(PendingApprovalRow, task_id)
            if row is None:
                return None
            return self._row_to_dict(row)

    async def get_pending_for_chat(self, chat_id: int) -> list[dict]:
        """Return non-expired pending approvals for a chat, newest first."""
        now = _utcnow()
        async with self._session_factory() as session:
            result = await session.execute(
                select(PendingApprovalRow)
                .where(PendingApprovalRow.chat_id == chat_id)
                .where(PendingApprovalRow.status == "pending")
                .where(PendingApprovalRow.expires_at > now)
                .order_by(PendingApprovalRow.created_at.desc())
            )
            return [self._row_to_dict(r) for r in result.scalars().all()]

    async def update_status(self, task_id: str, status: str) -> bool:
        """Update the status of a pending approval.

        Returns True if the row existed and was updated, False otherwise.
        """
        async with self._session_factory() as session:
            row = await session.get(PendingApprovalRow, task_id)
            if row is None:
                return False
            row.status = status
            await session.commit()
            return True

    async def cleanup_expired(self) -> int:
        """Delete expired pending approvals.

        Returns the number of deleted rows.
        """
        now = _utcnow()
        async with self._session_factory() as session:
            result = await session.execute(
                delete(PendingApprovalRow)
                .where(PendingApprovalRow.expires_at < now)
                .where(PendingApprovalRow.status == "pending")
            )
            await session.commit()
            return result.rowcount  # type: ignore[return-value]

    @staticmethod
    def _row_to_dict(row: PendingApprovalRow) -> dict:
        return {
            "task_id": row.task_id,
            "chat_id": row.chat_id,
            "plan_summary": row.plan_summary or "",
            "risk_level": row.risk_level or "medium",
            "status": row.status or "pending",
            "agent_type": row.agent_type or "",
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        }
