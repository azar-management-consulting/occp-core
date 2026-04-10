"""Human approval gate for the VAP pipeline.

Implements the "Brian the Brain" confirmation flow:
  PLAN -> CONFIRM (Henry approves on Telegram) -> GATE -> EXECUTE ...

LOW risk tasks auto-approve. MEDIUM/HIGH/CRITICAL require explicit approval.

Pending confirmations are stored in-memory with asyncio.Event for synchronization.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from store.approval_store import ApprovalStore
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Protocol

logger = logging.getLogger(__name__)

# Approval keywords (case-insensitive, stripped)
_APPROVE_KEYWORDS = frozenset({
    "ok", "igen", "go", "yes", "jovahagyom",
    "approve", "proceed", "mehet", "rendben",
})

# Timeout for waiting on human confirmation (seconds)
DEFAULT_CONFIRMATION_TIMEOUT = 300  # 5 minutes


class ConfirmationStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    TIMEOUT = "timeout"
    AUTO_APPROVED = "auto_approved"


class ConfirmationSender(Protocol):
    """Sends a confirmation request message to the user."""

    async def send_confirmation_request(
        self, chat_id: int, message: str
    ) -> None: ...

    async def send_confirmation_result(
        self, chat_id: int, message: str
    ) -> None: ...


@dataclass
class PendingConfirmation:
    """Tracks a single pending confirmation."""

    task_id: str
    chat_id: int
    plan_summary: str
    risk_level: str
    agent_type: str
    event: asyncio.Event = field(default_factory=asyncio.Event)
    status: ConfirmationStatus = ConfirmationStatus.PENDING
    response_text: str = ""
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    resolved_at: datetime | None = None


class ConfirmationGate:
    """Human approval gate for the VAP pipeline.

    Usage::

        gate = ConfirmationGate(sender=telegram_adapter, timeout=300)

        # In pipeline (after PLAN):
        approved = await gate.request_confirmation(task, chat_id, plan_summary)
        if not approved:
            raise HumanRejectedError(...)

        # From Telegram callback (when user replies):
        gate.handle_response(chat_id, user_text)
    """

    def __init__(
        self,
        sender: ConfirmationSender | None = None,
        timeout: int = DEFAULT_CONFIRMATION_TIMEOUT,
        auto_approve_risk_levels: frozenset[str] | None = None,
        approval_store: ApprovalStore | None = None,
    ) -> None:
        self._sender = sender
        self._timeout = timeout
        self._auto_approve_risk_levels = auto_approve_risk_levels or frozenset(
            {"low"}
        )
        self._approval_store = approval_store

        # task_id -> PendingConfirmation
        self._pending: dict[str, PendingConfirmation] = {}
        # chat_id -> task_id (for routing Telegram replies)
        self._chat_to_task: dict[int, str] = {}
        # Stats
        self._total_requests: int = 0
        self._total_auto_approved: int = 0
        self._total_approved: int = 0
        self._total_rejected: int = 0
        self._total_timeouts: int = 0

    def set_sender(self, sender: ConfirmationSender) -> None:
        """Set/replace the sender (circular dep resolution)."""
        self._sender = sender

    async def load_pending_from_db(self) -> int:
        """Load non-expired pending approvals from DB on startup.

        Rebuilds _pending and _chat_to_task state.
        Returns count of loaded approvals.
        """
        if not self._approval_store:
            return 0
        try:
            # Cleanup expired first
            cleaned = await self._approval_store.cleanup_expired()
            if cleaned:
                logger.info("Cleaned %d expired approvals from DB", cleaned)

            # We can't easily load ALL pending without a list_all method,
            # but we can check known chat_ids. For startup, we skip rebuild
            # because asyncio.Event objects can't be persisted/restored.
            # Pending approvals that survive restart will timeout naturally.
            logger.info("ApprovalStore startup cleanup done (expired removed)")
            return 0
        except Exception as exc:
            logger.warning("Failed to load pending approvals: %s", exc)
            return 0

    async def cleanup_expired(self) -> int:
        """Clean up expired pending approvals in DB."""
        if not self._approval_store:
            return 0
        try:
            return await self._approval_store.cleanup_expired()
        except Exception as exc:
            logger.warning("Failed to cleanup expired approvals: %s", exc)
            return 0

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    def get_pending(self, task_id: str) -> PendingConfirmation | None:
        return self._pending.get(task_id)

    def get_pending_by_chat(self, chat_id: int) -> PendingConfirmation | None:
        task_id = self._chat_to_task.get(chat_id)
        if task_id:
            return self._pending.get(task_id)
        return None

    async def request_confirmation(
        self,
        task_id: str,
        chat_id: int,
        plan_summary: str,
        risk_level: str,
        agent_type: str,
    ) -> ConfirmationStatus:
        """Request human confirmation for a task.

        Returns ConfirmationStatus.APPROVED/AUTO_APPROVED on success,
        REJECTED/TIMEOUT on failure.

        For auto-approved risk levels, returns immediately without
        sending a Telegram message.
        """
        self._total_requests += 1

        # Auto-approve LOW risk
        if risk_level.lower() in self._auto_approve_risk_levels:
            self._total_auto_approved += 1
            logger.info(
                "Auto-approved task=%s risk=%s", task_id, risk_level
            )
            return ConfirmationStatus.AUTO_APPROVED

        # Create pending confirmation
        pending = PendingConfirmation(
            task_id=task_id,
            chat_id=chat_id,
            plan_summary=plan_summary,
            risk_level=risk_level,
            agent_type=agent_type,
        )
        self._pending[task_id] = pending
        self._chat_to_task[chat_id] = task_id

        # Persist to DB
        if self._approval_store:
            try:
                await self._approval_store.save(
                    task_id=task_id, chat_id=chat_id,
                    plan_summary=plan_summary, risk_level=risk_level,
                    agent_type=agent_type, timeout_seconds=self._timeout,
                )
            except Exception as exc:
                logger.warning("Failed to persist approval: %s", exc)

        # Send confirmation request via Telegram
        message = self._format_confirmation_message(
            plan_summary, risk_level, agent_type
        )
        if self._sender:
            await self._sender.send_confirmation_request(chat_id, message)
        else:
            logger.warning(
                "No sender configured — cannot send confirmation for task=%s",
                task_id,
            )

        # Wait for response with timeout
        try:
            await asyncio.wait_for(pending.event.wait(), timeout=self._timeout)
        except asyncio.TimeoutError:
            pending.status = ConfirmationStatus.TIMEOUT
            pending.resolved_at = datetime.now(timezone.utc)
            self._total_timeouts += 1
            logger.warning("Confirmation timeout for task=%s", task_id)
            self._cleanup(task_id, chat_id)

            if self._sender:
                await self._sender.send_confirmation_result(
                    chat_id,
                    "Lejart az ido, Henry. A feladatot kihagytam.",
                )
            return ConfirmationStatus.TIMEOUT

        result = pending.status
        self._cleanup(task_id, chat_id)
        return result

    def handle_response(self, chat_id: int, text: str) -> bool:
        """Handle a user response to a pending confirmation.

        Returns True if there was a pending confirmation for this chat_id
        and the response was processed, False otherwise.
        """
        task_id = self._chat_to_task.get(chat_id)
        if not task_id:
            return False

        pending = self._pending.get(task_id)
        if not pending or pending.status != ConfirmationStatus.PENDING:
            return False

        pending.response_text = text
        pending.resolved_at = datetime.now(timezone.utc)

        normalized = (
            text.strip()
            .lower()
            .replace("\u00e1", "a")  # a-acute -> a
            .replace("\u00e9", "e")  # e-acute -> e
            .replace("\u00f3", "o")  # o-acute -> o
        )

        if normalized in _APPROVE_KEYWORDS:
            pending.status = ConfirmationStatus.APPROVED
            self._total_approved += 1
            logger.info("Task=%s approved by user (chat=%d)", task_id, chat_id)
            if self._approval_store:
                asyncio.get_event_loop().create_task(
                    self._approval_store.update_status(task_id, "approved")
                )
        else:
            pending.status = ConfirmationStatus.REJECTED
            self._total_rejected += 1
            logger.info(
                "Task=%s rejected by user (chat=%d): %s",
                task_id,
                chat_id,
                text[:100],
            )
            if self._approval_store:
                asyncio.get_event_loop().create_task(
                    self._approval_store.update_status(task_id, "rejected")
                )

        # Wake up the waiting coroutine
        pending.event.set()
        return True

    def has_pending(self, chat_id: int) -> bool:
        """Check if there's a pending confirmation for this chat."""
        return chat_id in self._chat_to_task

    def _cleanup(self, task_id: str, chat_id: int) -> None:
        self._pending.pop(task_id, None)
        if self._chat_to_task.get(chat_id) == task_id:
            del self._chat_to_task[chat_id]

    @staticmethod
    def _format_confirmation_message(
        plan_summary: str, risk_level: str, agent_type: str
    ) -> str:
        risk_emoji = {
            "low": "LOW",
            "medium": "MEDIUM",
            "high": "HIGH",
            "critical": "CRITICAL",
        }
        risk_display = risk_emoji.get(risk_level.lower(), risk_level.upper())

        return (
            f"\U0001f9e0 *Brian the Brain*\n\n"
            f"Henry, itt a tervem:\n\n"
            f"{plan_summary}\n\n"
            f"\u26a1 Kockazat: {risk_display}\n"
            f"\U0001f916 Agent: {agent_type}\n\n"
            f"Jovahagyod? (igen/nem)"
        )

    @staticmethod
    def format_plan_summary(plan: dict[str, Any]) -> str:
        """Extract a human-readable summary from a plan dict.

        Tries common plan structures:
        - plan["steps"] -> bullet list
        - plan["summary"] -> direct text
        - plan["description"] -> direct text
        - fallback: first 3 keys as bullets
        """
        if not isinstance(plan, dict):
            return str(plan)[:500]

        # Direct summary field
        if "summary" in plan:
            return str(plan["summary"])[:500]

        if "description" in plan:
            return str(plan["description"])[:500]

        # Steps list
        steps = plan.get("steps", [])
        if isinstance(steps, list) and steps:
            lines = []
            for i, step in enumerate(steps[:5]):
                if isinstance(step, dict):
                    step_text = step.get("description", step.get("name", str(step)))
                else:
                    step_text = str(step)
                lines.append(f"  {i + 1}. {step_text}")
            return "\n".join(lines)

        # Fallback: stringify first 3 keys
        lines = []
        for key in list(plan.keys())[:3]:
            val = plan[key]
            if isinstance(val, str):
                lines.append(f"  - {key}: {val[:100]}")
            else:
                lines.append(f"  - {key}: {str(val)[:100]}")
        return "\n".join(lines) if lines else str(plan)[:500]

    def get_stats(self) -> dict[str, Any]:
        return {
            "total_requests": self._total_requests,
            "total_auto_approved": self._total_auto_approved,
            "total_approved": self._total_approved,
            "total_rejected": self._total_rejected,
            "total_timeouts": self._total_timeouts,
            "pending_count": self.pending_count,
        }


class HumanRejectedError(Exception):
    """Raised when a human rejects a task during confirmation."""

    def __init__(self, task_id: str, reason: str = "") -> None:
        self.task_id = task_id
        self.reason = reason
        super().__init__(
            f"Task {task_id} rejected by human: {reason or 'no reason given'}"
        )


class ConfirmationTimeoutError(Exception):
    """Raised when confirmation times out."""

    def __init__(self, task_id: str) -> None:
        self.task_id = task_id
        super().__init__(f"Confirmation timeout for task {task_id}")
