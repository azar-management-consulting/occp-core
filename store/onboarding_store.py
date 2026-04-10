"""Store for onboarding wizard progress persistence."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from store.models import OnboardingProgressRow


class OnboardingStore:
    """CRUD for onboarding_progress table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, user_id: str) -> OnboardingProgressRow | None:
        result = await self._session.execute(
            select(OnboardingProgressRow).where(
                OnboardingProgressRow.user_id == user_id
            )
        )
        return result.scalar_one_or_none()

    async def upsert(
        self,
        user_id: str,
        *,
        state: str = "landing",
        current_step: int = 0,
        completed_steps: list[str] | None = None,
        run_id: str = "",
        org_id: str = "",
        completed_flag: bool = False,
        audit_linkage: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> OnboardingProgressRow:
        now = datetime.now(timezone.utc).isoformat()
        row = await self.get(user_id)
        if row is None:
            row = OnboardingProgressRow(
                user_id=user_id,
                org_id=org_id,
                state=state,
                current_step=current_step,
                completed_steps=completed_steps or [],
                completed_flag=completed_flag,
                run_id=run_id,
                audit_linkage=audit_linkage,
                metadata_=metadata or {},
                created_at=now,
                updated_at=now,
            )
            self._session.add(row)
        else:
            row.state = state
            row.current_step = current_step
            row.completed_steps = completed_steps or row.completed_steps
            row.run_id = run_id or row.run_id
            if org_id:
                row.org_id = org_id
            if completed_flag:
                row.completed_flag = True
            if audit_linkage:
                row.audit_linkage = audit_linkage
            row.metadata_ = metadata if metadata is not None else row.metadata_
            row.updated_at = now
            if state == "done":
                row.completed_at = now
        await self._session.flush()
        return row

    async def list_all(self) -> list[dict[str, Any]]:
        """Return all onboarding progress rows as dicts (for funnel stats)."""
        result = await self._session.execute(select(OnboardingProgressRow))
        rows = result.scalars().all()
        return [
            {"user_id": r.user_id, "wizard_state": r.state, "current_step": r.current_step}
            for r in rows
        ]

    async def mark_complete(self, user_id: str) -> OnboardingProgressRow | None:
        row = await self.get(user_id)
        if row is None:
            return None
        now = datetime.now(timezone.utc).isoformat()
        row.state = "done"
        row.completed_at = now
        row.updated_at = now
        await self._session.flush()
        return row
