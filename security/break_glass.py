"""Break-Glass Protocol — REQ-GOV-04.

Emergency override mechanism with multi-party approval, time-limited tokens,
auto-revocation, and immutable audit trail.

Usage::

    protocol = BreakGlassProtocol(required_approvals=2)
    token = protocol.request("admin-1", scope="deploy-override", duration_minutes=30)
    protocol.approve(token.token_id, "admin-2")
    protocol.approve(token.token_id, "admin-3")

    if protocol.is_active(token.token_id):
        # Emergency override permitted
        ...
"""

from __future__ import annotations

import hashlib
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


# ---------------------------------------------------------------------------
# Token model
# ---------------------------------------------------------------------------


@dataclass
class BreakGlassToken:
    """Time-limited emergency override token.

    Requires multi-party approval before activation.
    """

    token_id: str
    requested_by: str
    scope: str
    created_at: datetime
    expires_at: datetime
    duration_minutes: int
    required_approvals: int
    approved_by: list[str] = field(default_factory=list)
    revoked: bool = False
    revoked_at: datetime | None = None
    revoked_by: str = ""
    reason: str = ""
    audit_trail: list[dict[str, Any]] = field(default_factory=list)

    @property
    def is_approved(self) -> bool:
        """Token has received enough approvals."""
        return len(self.approved_by) >= self.required_approvals

    @property
    def is_expired(self) -> bool:
        """Token has passed its expiration time."""
        return datetime.now(timezone.utc) >= self.expires_at

    @property
    def is_active(self) -> bool:
        """Token is approved, not expired, and not revoked."""
        return self.is_approved and not self.is_expired and not self.revoked

    def to_dict(self) -> dict[str, Any]:
        """Serialize for audit trail."""
        return {
            "token_id": self.token_id,
            "requested_by": self.requested_by,
            "scope": self.scope,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "duration_minutes": self.duration_minutes,
            "required_approvals": self.required_approvals,
            "approved_by": list(self.approved_by),
            "is_approved": self.is_approved,
            "is_expired": self.is_expired,
            "is_active": self.is_active,
            "revoked": self.revoked,
            "revoked_at": self.revoked_at.isoformat() if self.revoked_at else None,
            "revoked_by": self.revoked_by,
            "reason": self.reason,
        }


# ---------------------------------------------------------------------------
# Audit entry for break-glass events
# ---------------------------------------------------------------------------


@dataclass
class BreakGlassAuditEntry:
    """Immutable audit record for break-glass events — severity=CRITICAL."""

    timestamp: datetime
    event: str
    token_id: str
    actor: str
    detail: dict[str, Any] = field(default_factory=dict)
    severity: str = "CRITICAL"
    hash: str = ""

    def compute_hash(self, prev_hash: str = "") -> None:
        """Compute SHA-256 hash chained to previous entry."""
        payload = (
            f"{self.timestamp.isoformat()}|{self.event}|{self.token_id}|"
            f"{self.actor}|{self.severity}|{prev_hash}"
        )
        self.hash = hashlib.sha256(payload.encode()).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "event": self.event,
            "token_id": self.token_id,
            "actor": self.actor,
            "detail": self.detail,
            "severity": self.severity,
            "hash": self.hash,
        }


# ---------------------------------------------------------------------------
# Break-Glass Protocol
# ---------------------------------------------------------------------------


class BreakGlassError(Exception):
    """Base exception for break-glass protocol errors."""


class BreakGlassProtocol:
    """Multi-party approval emergency override protocol.

    REQ-GOV-04:
    - Multi-party approval (configurable, default 2/3 system_admins)
    - Time-limited token (max 1h, configurable)
    - Auto-revocation on expiry
    - Immutable audit trail with severity=CRITICAL
    """

    MAX_DURATION_MINUTES: int = 60  # 1 hour hard cap

    def __init__(
        self,
        *,
        required_approvals: int = 2,
        max_duration_minutes: int = 60,
        authorized_approvers: list[str] | None = None,
    ) -> None:
        if required_approvals < 1:
            raise ValueError("required_approvals must be >= 1")
        if max_duration_minutes < 1 or max_duration_minutes > self.MAX_DURATION_MINUTES:
            raise ValueError(
                f"max_duration_minutes must be 1-{self.MAX_DURATION_MINUTES}"
            )

        self._required_approvals = required_approvals
        self._max_duration = max_duration_minutes
        self._authorized_approvers: set[str] = (
            set(authorized_approvers) if authorized_approvers else set()
        )
        self._tokens: dict[str, BreakGlassToken] = {}
        self._audit_chain: list[BreakGlassAuditEntry] = []

    @property
    def required_approvals(self) -> int:
        return self._required_approvals

    @property
    def max_duration_minutes(self) -> int:
        return self._max_duration

    def request(
        self,
        requester: str,
        *,
        scope: str,
        reason: str = "",
        duration_minutes: int = 30,
    ) -> BreakGlassToken:
        """Create a new break-glass request.

        The token is NOT active until enough approvers have approved it.
        Duration is capped at max_duration_minutes.
        """
        if not requester:
            raise BreakGlassError("Requester must be specified")
        if not scope:
            raise BreakGlassError("Scope must be specified")

        duration = min(duration_minutes, self._max_duration)
        now = datetime.now(timezone.utc)
        from datetime import timedelta

        token = BreakGlassToken(
            token_id=secrets.token_hex(16),
            requested_by=requester,
            scope=scope,
            reason=reason,
            created_at=now,
            expires_at=now + timedelta(minutes=duration),
            duration_minutes=duration,
            required_approvals=self._required_approvals,
        )
        self._tokens[token.token_id] = token
        self._append_audit("request", token.token_id, requester, {
            "scope": scope,
            "reason": reason,
            "duration_minutes": duration,
            "required_approvals": self._required_approvals,
        })
        return token

    def approve(self, token_id: str, approver: str) -> bool:
        """Approve a break-glass request.

        Returns True if this approval activates the token.
        Raises BreakGlassError if token not found, approver not authorized,
        requester tries to self-approve, or token already revoked/expired.
        """
        token = self._tokens.get(token_id)
        if token is None:
            raise BreakGlassError(f"Token not found: {token_id}")

        if token.revoked:
            raise BreakGlassError(f"Token already revoked: {token_id}")

        if token.is_expired:
            raise BreakGlassError(f"Token already expired: {token_id}")

        if approver == token.requested_by:
            raise BreakGlassError("Requester cannot self-approve")

        if self._authorized_approvers and approver not in self._authorized_approvers:
            raise BreakGlassError(
                f"Approver '{approver}' is not in the authorized approvers list"
            )

        if approver in token.approved_by:
            raise BreakGlassError(
                f"Approver '{approver}' has already approved this token"
            )

        token.approved_by.append(approver)
        self._append_audit("approve", token_id, approver, {
            "approvals": len(token.approved_by),
            "required": token.required_approvals,
            "activated": token.is_approved,
        })

        if token.is_approved:
            self._append_audit("activate", token_id, "system", {
                "scope": token.scope,
                "expires_at": token.expires_at.isoformat(),
            })

        return token.is_approved

    def revoke(self, token_id: str, revoked_by: str) -> None:
        """Revoke a break-glass token immediately."""
        token = self._tokens.get(token_id)
        if token is None:
            raise BreakGlassError(f"Token not found: {token_id}")

        if token.revoked:
            return  # Idempotent

        token.revoked = True
        token.revoked_at = datetime.now(timezone.utc)
        token.revoked_by = revoked_by
        self._append_audit("revoke", token_id, revoked_by, {
            "scope": token.scope,
            "was_active": token.is_approved and not token.is_expired,
        })

    def is_active(self, token_id: str) -> bool:
        """Check if a break-glass token is currently active."""
        token = self._tokens.get(token_id)
        if token is None:
            return False
        return token.is_active

    def check(self, token_id: str) -> BreakGlassToken | None:
        """Retrieve a token by ID. Returns None if not found."""
        return self._tokens.get(token_id)

    def check_scope(self, token_id: str, required_scope: str) -> bool:
        """Check if an active token covers the required scope."""
        token = self._tokens.get(token_id)
        if token is None or not token.is_active:
            return False
        return token.scope == required_scope or token.scope == "*"

    def cleanup_expired(self) -> int:
        """Auto-revoke all expired tokens. Returns count of newly revoked."""
        count = 0
        for token in self._tokens.values():
            if token.is_expired and not token.revoked:
                token.revoked = True
                token.revoked_at = datetime.now(timezone.utc)
                token.revoked_by = "system:auto_revoke"
                self._append_audit("auto_revoke", token.token_id, "system", {
                    "scope": token.scope,
                    "expired_at": token.expires_at.isoformat(),
                })
                count += 1
        return count

    @property
    def active_tokens(self) -> list[BreakGlassToken]:
        """Return all currently active tokens."""
        return [t for t in self._tokens.values() if t.is_active]

    @property
    def pending_tokens(self) -> list[BreakGlassToken]:
        """Return tokens awaiting approval."""
        return [
            t for t in self._tokens.values()
            if not t.is_approved and not t.revoked and not t.is_expired
        ]

    @property
    def audit_trail(self) -> list[BreakGlassAuditEntry]:
        """Return the immutable audit trail."""
        return list(self._audit_chain)

    def verify_audit_chain(self) -> bool:
        """Verify integrity of the audit hash chain."""
        if not self._audit_chain:
            return True
        prev = ""
        for entry in self._audit_chain:
            expected = BreakGlassAuditEntry(
                timestamp=entry.timestamp,
                event=entry.event,
                token_id=entry.token_id,
                actor=entry.actor,
                detail=entry.detail,
                severity=entry.severity,
            )
            expected.compute_hash(prev)
            if expected.hash != entry.hash:
                return False
            prev = entry.hash
        return True

    def _append_audit(
        self,
        event: str,
        token_id: str,
        actor: str,
        detail: dict[str, Any],
    ) -> BreakGlassAuditEntry:
        """Append an audit entry to the immutable chain."""
        prev_hash = self._audit_chain[-1].hash if self._audit_chain else ""
        entry = BreakGlassAuditEntry(
            timestamp=datetime.now(timezone.utc),
            event=event,
            token_id=token_id,
            actor=actor,
            detail=detail,
        )
        entry.compute_hash(prev_hash)
        self._audit_chain.append(entry)
        return entry
