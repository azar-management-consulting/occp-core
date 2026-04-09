"""Approval queue — Human-in-the-loop approval for MEDIUM/HIGH/CRIT changes.

Design:
- LOW risk changes bypass approval (auto-approve after verification)
- MEDIUM+ risk requires explicit approval
- Approval requests can target Telegram (async notification)
- Each request has a TTL (default 24h)
- Approvals are logged to the hash chain
- Rejections are logged with reason
- Timeouts are treated as implicit rejection

Preservation: builds on existing ConfirmationGate pattern; does NOT
modify the confirmation_gate module.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ApprovalState(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    TIMEOUT = "timeout"
    AUTO_APPROVED = "auto_approved"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    def requires_approval(self) -> bool:
        return self != RiskLevel.LOW


@dataclass
class ApprovalRequest:
    """A single approval request."""

    request_id: str
    run_id: str
    risk_level: RiskLevel
    title: str
    summary: str
    affected_paths: list[str]
    diff_preview: str  # truncated
    residual_risk_score: float
    state: ApprovalState = ApprovalState.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None
    resolved_at: datetime | None = None
    resolved_by: str | None = None
    resolution_reason: str | None = None
    notification_sent: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "run_id": self.run_id,
            "risk_level": self.risk_level.value,
            "title": self.title,
            "summary": self.summary,
            "affected_paths": self.affected_paths,
            "diff_preview": self.diff_preview,
            "residual_risk_score": self.residual_risk_score,
            "state": self.state.value,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolved_by": self.resolved_by,
            "resolution_reason": self.resolution_reason,
            "notification_sent": self.notification_sent,
        }

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) >= self.expires_at

    def is_terminal(self) -> bool:
        return self.state in (
            ApprovalState.APPROVED,
            ApprovalState.AUTO_APPROVED,
            ApprovalState.REJECTED,
            ApprovalState.TIMEOUT,
        )


class ApprovalQueue:
    """In-memory queue of approval requests with TTL + state machine."""

    def __init__(self, default_ttl_hours: int = 24) -> None:
        self._lock = threading.Lock()
        self._requests: dict[str, ApprovalRequest] = {}
        self._default_ttl_hours = default_ttl_hours

    # ── Submit ────────────────────────────────────────────
    def submit(
        self,
        *,
        request_id: str,
        run_id: str,
        risk_level: RiskLevel | str,
        title: str,
        summary: str,
        affected_paths: list[str],
        diff_preview: str,
        residual_risk_score: float,
        ttl_hours: int | None = None,
    ) -> ApprovalRequest:
        """Submit a new approval request."""
        if isinstance(risk_level, str):
            risk_level = RiskLevel(risk_level)

        with self._lock:
            if request_id in self._requests:
                raise ValueError(f"duplicate request_id: {request_id}")

            # ttl_hours=0 means already expired (for test purposes); None means default
            effective_ttl = (
                self._default_ttl_hours if ttl_hours is None else ttl_hours
            )
            expires_at = datetime.now(timezone.utc) + timedelta(
                hours=effective_ttl
            )

            req = ApprovalRequest(
                request_id=request_id,
                run_id=run_id,
                risk_level=risk_level,
                title=title,
                summary=summary,
                affected_paths=affected_paths,
                diff_preview=diff_preview[:4000],  # cap for telegram
                residual_risk_score=residual_risk_score,
                expires_at=expires_at,
            )

            # LOW risk auto-approves immediately
            if not risk_level.requires_approval():
                req.state = ApprovalState.AUTO_APPROVED
                req.resolved_at = datetime.now(timezone.utc)
                req.resolved_by = "system"
                req.resolution_reason = "LOW risk auto-approved"

            self._requests[request_id] = req
            logger.info(
                "autodev.approval: submitted id=%s risk=%s state=%s",
                request_id,
                risk_level.value,
                req.state.value,
            )
            return req

    # ── Resolve ───────────────────────────────────────────
    def approve(
        self, request_id: str, actor: str, reason: str = ""
    ) -> ApprovalRequest:
        return self._resolve(
            request_id, ApprovalState.APPROVED, actor, reason
        )

    def reject(
        self, request_id: str, actor: str, reason: str = ""
    ) -> ApprovalRequest:
        return self._resolve(
            request_id, ApprovalState.REJECTED, actor, reason
        )

    def _resolve(
        self,
        request_id: str,
        new_state: ApprovalState,
        actor: str,
        reason: str,
    ) -> ApprovalRequest:
        with self._lock:
            req = self._requests.get(request_id)
            if req is None:
                raise KeyError(f"unknown request_id: {request_id}")
            if req.is_terminal():
                raise ValueError(
                    f"request {request_id} already in terminal state "
                    f"{req.state.value}"
                )
            req.state = new_state
            req.resolved_at = datetime.now(timezone.utc)
            req.resolved_by = actor
            req.resolution_reason = reason
            logger.info(
                "autodev.approval: %s id=%s actor=%s reason=%s",
                new_state.value,
                request_id,
                actor,
                reason[:100],
            )
            return req

    # ── Cleanup expired ───────────────────────────────────
    def cleanup_expired(self) -> int:
        """Mark expired pending requests as TIMEOUT. Returns count changed."""
        changed = 0
        with self._lock:
            for req in self._requests.values():
                if (
                    req.state == ApprovalState.PENDING
                    and req.is_expired()
                ):
                    req.state = ApprovalState.TIMEOUT
                    req.resolved_at = datetime.now(timezone.utc)
                    req.resolved_by = "system"
                    req.resolution_reason = "ttl_expired"
                    changed += 1
        if changed:
            logger.info("autodev.approval: %d requests timed out", changed)
        return changed

    # ── Query ─────────────────────────────────────────────
    def get(self, request_id: str) -> ApprovalRequest | None:
        with self._lock:
            return self._requests.get(request_id)

    def list_pending(self) -> list[ApprovalRequest]:
        with self._lock:
            return [
                r
                for r in self._requests.values()
                if r.state == ApprovalState.PENDING
            ]

    def list_all(self) -> list[ApprovalRequest]:
        with self._lock:
            return sorted(
                self._requests.values(),
                key=lambda r: r.created_at,
                reverse=True,
            )

    def mark_notification_sent(self, request_id: str) -> None:
        with self._lock:
            req = self._requests.get(request_id)
            if req:
                req.notification_sent = True

    # ── Stats ─────────────────────────────────────────────
    @property
    def stats(self) -> dict[str, Any]:
        with self._lock:
            total = len(self._requests)
            by_state: dict[str, int] = {}
            by_risk: dict[str, int] = {}
            for r in self._requests.values():
                by_state[r.state.value] = by_state.get(r.state.value, 0) + 1
                by_risk[r.risk_level.value] = by_risk.get(r.risk_level.value, 0) + 1
            return {
                "total": total,
                "by_state": by_state,
                "by_risk": by_risk,
            }

    def reset(self) -> None:
        """Test-only: clear all requests."""
        with self._lock:
            self._requests.clear()


# ── Singleton accessor ────────────────────────────────────────
_global_queue: ApprovalQueue | None = None
_init_lock = threading.Lock()


def get_approval_queue() -> ApprovalQueue:
    global _global_queue
    if _global_queue is None:
        with _init_lock:
            if _global_queue is None:
                _global_queue = ApprovalQueue()
    return _global_queue
