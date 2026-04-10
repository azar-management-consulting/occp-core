"""Tests for Break-Glass Protocol — REQ-GOV-04.

Covers:
- Token lifecycle: request → approve → activate → revoke
- Multi-party approval enforcement
- Self-approve prevention
- Duplicate approval prevention
- Authorized approvers list
- Time-limited tokens and expiry
- Auto-revocation (cleanup_expired)
- Scope checking
- Immutable audit trail with hash chain
- Duration cap enforcement
- Error handling
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from security.break_glass import (
    BreakGlassAuditEntry,
    BreakGlassError,
    BreakGlassProtocol,
    BreakGlassToken,
)


# ---------------------------------------------------------------------------
# BreakGlassToken
# ---------------------------------------------------------------------------


class TestBreakGlassToken:
    def _make_token(self, **kw) -> BreakGlassToken:
        now = datetime.now(timezone.utc)
        defaults = dict(
            token_id="tok-001",
            requested_by="admin-1",
            scope="deploy-override",
            created_at=now,
            expires_at=now + timedelta(minutes=30),
            duration_minutes=30,
            required_approvals=2,
        )
        defaults.update(kw)
        return BreakGlassToken(**defaults)

    def test_not_approved_initially(self) -> None:
        t = self._make_token()
        assert t.is_approved is False
        assert t.is_active is False

    def test_approved_after_enough_approvals(self) -> None:
        t = self._make_token(required_approvals=2)
        t.approved_by = ["admin-2", "admin-3"]
        assert t.is_approved is True

    def test_not_expired(self) -> None:
        t = self._make_token(expires_at=datetime.now(timezone.utc) + timedelta(hours=1))
        assert t.is_expired is False

    def test_expired(self) -> None:
        t = self._make_token(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
        assert t.is_expired is True

    def test_active_requires_all_conditions(self) -> None:
        t = self._make_token(required_approvals=1)
        t.approved_by = ["admin-2"]
        assert t.is_active is True
        # Revoke → no longer active
        t.revoked = True
        assert t.is_active is False

    def test_to_dict(self) -> None:
        t = self._make_token()
        d = t.to_dict()
        assert d["token_id"] == "tok-001"
        assert d["requested_by"] == "admin-1"
        assert d["scope"] == "deploy-override"
        assert d["is_approved"] is False
        assert d["revoked"] is False
        assert d["revoked_at"] is None


# ---------------------------------------------------------------------------
# BreakGlassAuditEntry
# ---------------------------------------------------------------------------


class TestBreakGlassAuditEntry:
    def test_hash_chain(self) -> None:
        e1 = BreakGlassAuditEntry(
            timestamp=datetime.now(timezone.utc),
            event="request",
            token_id="tok-1",
            actor="admin-1",
        )
        e1.compute_hash("")
        assert len(e1.hash) == 64  # SHA-256 hex

        e2 = BreakGlassAuditEntry(
            timestamp=datetime.now(timezone.utc),
            event="approve",
            token_id="tok-1",
            actor="admin-2",
        )
        e2.compute_hash(e1.hash)
        assert e2.hash != e1.hash

    def test_to_dict(self) -> None:
        e = BreakGlassAuditEntry(
            timestamp=datetime.now(timezone.utc),
            event="request",
            token_id="tok-1",
            actor="admin-1",
            severity="CRITICAL",
        )
        e.compute_hash("")
        d = e.to_dict()
        assert d["event"] == "request"
        assert d["severity"] == "CRITICAL"
        assert len(d["hash"]) == 64


# ---------------------------------------------------------------------------
# BreakGlassProtocol — lifecycle
# ---------------------------------------------------------------------------


class TestBreakGlassProtocol:
    def test_request_creates_token(self) -> None:
        proto = BreakGlassProtocol(required_approvals=2)
        token = proto.request("admin-1", scope="deploy-override")
        assert token.requested_by == "admin-1"
        assert token.scope == "deploy-override"
        assert token.is_approved is False
        assert token.is_active is False

    def test_approve_activates_token(self) -> None:
        proto = BreakGlassProtocol(required_approvals=2)
        token = proto.request("admin-1", scope="deploy-override")
        proto.approve(token.token_id, "admin-2")
        activated = proto.approve(token.token_id, "admin-3")
        assert activated is True
        assert proto.is_active(token.token_id) is True

    def test_single_approval_not_enough(self) -> None:
        proto = BreakGlassProtocol(required_approvals=2)
        token = proto.request("admin-1", scope="deploy-override")
        activated = proto.approve(token.token_id, "admin-2")
        assert activated is False
        assert proto.is_active(token.token_id) is False

    def test_revoke(self) -> None:
        proto = BreakGlassProtocol(required_approvals=1)
        token = proto.request("admin-1", scope="deploy-override")
        proto.approve(token.token_id, "admin-2")
        assert proto.is_active(token.token_id) is True
        proto.revoke(token.token_id, "admin-1")
        assert proto.is_active(token.token_id) is False

    def test_revoke_idempotent(self) -> None:
        proto = BreakGlassProtocol(required_approvals=1)
        token = proto.request("admin-1", scope="deploy-override")
        proto.revoke(token.token_id, "admin-1")
        proto.revoke(token.token_id, "admin-1")  # No error

    def test_check_returns_token(self) -> None:
        proto = BreakGlassProtocol()
        token = proto.request("admin-1", scope="test")
        found = proto.check(token.token_id)
        assert found is not None
        assert found.token_id == token.token_id

    def test_check_returns_none_for_unknown(self) -> None:
        proto = BreakGlassProtocol()
        assert proto.check("nonexistent") is None

    def test_is_active_false_for_unknown(self) -> None:
        proto = BreakGlassProtocol()
        assert proto.is_active("nonexistent") is False


# ---------------------------------------------------------------------------
# Validation rules
# ---------------------------------------------------------------------------


class TestBreakGlassValidation:
    def test_self_approve_denied(self) -> None:
        proto = BreakGlassProtocol(required_approvals=1)
        token = proto.request("admin-1", scope="deploy")
        with pytest.raises(BreakGlassError, match="self-approve"):
            proto.approve(token.token_id, "admin-1")

    def test_duplicate_approve_denied(self) -> None:
        proto = BreakGlassProtocol(required_approvals=2)
        token = proto.request("admin-1", scope="deploy")
        proto.approve(token.token_id, "admin-2")
        with pytest.raises(BreakGlassError, match="already approved"):
            proto.approve(token.token_id, "admin-2")

    def test_approve_revoked_token_denied(self) -> None:
        proto = BreakGlassProtocol(required_approvals=1)
        token = proto.request("admin-1", scope="deploy")
        proto.revoke(token.token_id, "admin-1")
        with pytest.raises(BreakGlassError, match="revoked"):
            proto.approve(token.token_id, "admin-2")

    def test_approve_expired_token_denied(self) -> None:
        proto = BreakGlassProtocol(required_approvals=1)
        token = proto.request("admin-1", scope="deploy", duration_minutes=1)
        # Force expiry by manipulating expires_at
        token.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        with pytest.raises(BreakGlassError, match="expired"):
            proto.approve(token.token_id, "admin-2")

    def test_approve_unknown_token_denied(self) -> None:
        proto = BreakGlassProtocol()
        with pytest.raises(BreakGlassError, match="not found"):
            proto.approve("fake-token", "admin-2")

    def test_revoke_unknown_token_denied(self) -> None:
        proto = BreakGlassProtocol()
        with pytest.raises(BreakGlassError, match="not found"):
            proto.revoke("fake-token", "admin-1")

    def test_authorized_approvers_enforced(self) -> None:
        proto = BreakGlassProtocol(
            required_approvals=1,
            authorized_approvers=["admin-2", "admin-3"],
        )
        token = proto.request("admin-1", scope="deploy")
        with pytest.raises(BreakGlassError, match="not in the authorized"):
            proto.approve(token.token_id, "hacker-1")

    def test_authorized_approver_succeeds(self) -> None:
        proto = BreakGlassProtocol(
            required_approvals=1,
            authorized_approvers=["admin-2", "admin-3"],
        )
        token = proto.request("admin-1", scope="deploy")
        activated = proto.approve(token.token_id, "admin-2")
        assert activated is True

    def test_empty_requester_denied(self) -> None:
        proto = BreakGlassProtocol()
        with pytest.raises(BreakGlassError, match="Requester"):
            proto.request("", scope="deploy")

    def test_empty_scope_denied(self) -> None:
        proto = BreakGlassProtocol()
        with pytest.raises(BreakGlassError, match="Scope"):
            proto.request("admin-1", scope="")


# ---------------------------------------------------------------------------
# Duration and expiry
# ---------------------------------------------------------------------------


class TestBreakGlassDuration:
    def test_duration_capped(self) -> None:
        proto = BreakGlassProtocol(max_duration_minutes=30)
        token = proto.request("admin-1", scope="deploy", duration_minutes=60)
        assert token.duration_minutes == 30

    def test_max_duration_hard_cap(self) -> None:
        with pytest.raises(ValueError, match="max_duration_minutes"):
            BreakGlassProtocol(max_duration_minutes=120)

    def test_min_approvals_validation(self) -> None:
        with pytest.raises(ValueError, match="required_approvals"):
            BreakGlassProtocol(required_approvals=0)

    def test_cleanup_expired(self) -> None:
        proto = BreakGlassProtocol(required_approvals=1)
        token = proto.request("admin-1", scope="deploy", duration_minutes=1)
        # Force expiry
        token.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        count = proto.cleanup_expired()
        assert count == 1
        assert token.revoked is True
        assert token.revoked_by == "system:auto_revoke"

    def test_cleanup_only_expired(self) -> None:
        proto = BreakGlassProtocol(required_approvals=1)
        t1 = proto.request("admin-1", scope="deploy", duration_minutes=30)
        t2 = proto.request("admin-1", scope="other", duration_minutes=1)
        t2.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        count = proto.cleanup_expired()
        assert count == 1
        assert t1.revoked is False
        assert t2.revoked is True


# ---------------------------------------------------------------------------
# Scope checking
# ---------------------------------------------------------------------------


class TestBreakGlassScope:
    def test_check_scope_matching(self) -> None:
        proto = BreakGlassProtocol(required_approvals=1)
        token = proto.request("admin-1", scope="deploy-override")
        proto.approve(token.token_id, "admin-2")
        assert proto.check_scope(token.token_id, "deploy-override") is True

    def test_check_scope_wildcard(self) -> None:
        proto = BreakGlassProtocol(required_approvals=1)
        token = proto.request("admin-1", scope="*")
        proto.approve(token.token_id, "admin-2")
        assert proto.check_scope(token.token_id, "anything") is True

    def test_check_scope_mismatch(self) -> None:
        proto = BreakGlassProtocol(required_approvals=1)
        token = proto.request("admin-1", scope="deploy-override")
        proto.approve(token.token_id, "admin-2")
        assert proto.check_scope(token.token_id, "delete-data") is False

    def test_check_scope_inactive_token(self) -> None:
        proto = BreakGlassProtocol(required_approvals=2)
        token = proto.request("admin-1", scope="deploy-override")
        # Only 1 approval — not active
        proto.approve(token.token_id, "admin-2")
        assert proto.check_scope(token.token_id, "deploy-override") is False

    def test_check_scope_unknown_token(self) -> None:
        proto = BreakGlassProtocol()
        assert proto.check_scope("nonexistent", "deploy") is False


# ---------------------------------------------------------------------------
# Token listing
# ---------------------------------------------------------------------------


class TestBreakGlassListing:
    def test_active_tokens(self) -> None:
        proto = BreakGlassProtocol(required_approvals=1)
        t1 = proto.request("admin-1", scope="s1")
        t2 = proto.request("admin-1", scope="s2")
        proto.approve(t1.token_id, "admin-2")
        assert len(proto.active_tokens) == 1
        assert proto.active_tokens[0].token_id == t1.token_id

    def test_pending_tokens(self) -> None:
        proto = BreakGlassProtocol(required_approvals=2)
        t1 = proto.request("admin-1", scope="s1")
        t2 = proto.request("admin-1", scope="s2")
        proto.approve(t1.token_id, "admin-2")
        # t1 has 1/2 approvals, t2 has 0/2 — both pending
        assert len(proto.pending_tokens) == 2

    def test_pending_excludes_revoked(self) -> None:
        proto = BreakGlassProtocol(required_approvals=2)
        t1 = proto.request("admin-1", scope="s1")
        proto.revoke(t1.token_id, "admin-1")
        assert len(proto.pending_tokens) == 0


# ---------------------------------------------------------------------------
# Audit trail — hash chain integrity
# ---------------------------------------------------------------------------


class TestBreakGlassAudit:
    def test_audit_trail_records_events(self) -> None:
        proto = BreakGlassProtocol(required_approvals=1)
        token = proto.request("admin-1", scope="deploy")
        proto.approve(token.token_id, "admin-2")
        trail = proto.audit_trail
        events = [e.event for e in trail]
        assert "request" in events
        assert "approve" in events
        assert "activate" in events

    def test_audit_all_critical_severity(self) -> None:
        proto = BreakGlassProtocol(required_approvals=1)
        token = proto.request("admin-1", scope="deploy")
        proto.approve(token.token_id, "admin-2")
        for entry in proto.audit_trail:
            assert entry.severity == "CRITICAL"

    def test_audit_chain_integrity(self) -> None:
        proto = BreakGlassProtocol(required_approvals=2)
        token = proto.request("admin-1", scope="deploy")
        proto.approve(token.token_id, "admin-2")
        proto.approve(token.token_id, "admin-3")
        proto.revoke(token.token_id, "admin-1")
        assert proto.verify_audit_chain() is True

    def test_audit_chain_tamper_detected(self) -> None:
        proto = BreakGlassProtocol(required_approvals=1)
        token = proto.request("admin-1", scope="deploy")
        proto.approve(token.token_id, "admin-2")
        # Tamper with audit trail
        proto._audit_chain[0].hash = "tampered"
        assert proto.verify_audit_chain() is False

    def test_empty_audit_chain_valid(self) -> None:
        proto = BreakGlassProtocol()
        assert proto.verify_audit_chain() is True

    def test_revoke_audit_entry(self) -> None:
        proto = BreakGlassProtocol(required_approvals=1)
        token = proto.request("admin-1", scope="deploy")
        proto.approve(token.token_id, "admin-2")
        proto.revoke(token.token_id, "admin-1")
        revoke_entries = [e for e in proto.audit_trail if e.event == "revoke"]
        assert len(revoke_entries) == 1
        assert revoke_entries[0].actor == "admin-1"

    def test_auto_revoke_audit_entry(self) -> None:
        proto = BreakGlassProtocol(required_approvals=1)
        token = proto.request("admin-1", scope="deploy", duration_minutes=1)
        token.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        proto.cleanup_expired()
        auto_entries = [e for e in proto.audit_trail if e.event == "auto_revoke"]
        assert len(auto_entries) == 1
        assert auto_entries[0].actor == "system"
