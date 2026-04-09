"""Tests for autodev.approval_queue."""

from __future__ import annotations

import pytest

from autodev.approval_queue import (
    ApprovalQueue,
    ApprovalState,
    RiskLevel,
    get_approval_queue,
)


@pytest.fixture
def queue():
    return ApprovalQueue()


def _submit(queue, *, risk_level="medium", request_id="req-001"):
    return queue.submit(
        request_id=request_id,
        run_id="run-001",
        risk_level=risk_level,
        title="Test proposal",
        summary="Test summary",
        affected_paths=["evaluation/feature_flags.py"],
        diff_preview="--- diff ---",
        residual_risk_score=3.5,
    )


class TestSubmit:

    def test_submit_medium_is_pending(self, queue):
        req = _submit(queue, risk_level="medium")
        assert req.state == ApprovalState.PENDING

    def test_submit_low_is_auto_approved(self, queue):
        req = _submit(queue, risk_level="low")
        assert req.state == ApprovalState.AUTO_APPROVED
        assert req.resolved_by == "system"

    def test_submit_duplicate_raises(self, queue):
        _submit(queue, request_id="dup")
        with pytest.raises(ValueError):
            _submit(queue, request_id="dup")

    def test_submit_all_risk_levels(self, queue):
        for i, level in enumerate(["low", "medium", "high", "critical"]):
            req = _submit(queue, risk_level=level, request_id=f"r-{i}")
            assert req.risk_level == RiskLevel(level)


class TestApprovalResolution:

    def test_approve(self, queue):
        _submit(queue, risk_level="high", request_id="a1")
        req = queue.approve("a1", actor="henry", reason="LGTM")
        assert req.state == ApprovalState.APPROVED
        assert req.resolved_by == "henry"

    def test_reject(self, queue):
        _submit(queue, risk_level="high", request_id="r1")
        req = queue.reject("r1", actor="henry", reason="too risky")
        assert req.state == ApprovalState.REJECTED

    def test_cannot_resolve_terminal(self, queue):
        _submit(queue, risk_level="high", request_id="t1")
        queue.approve("t1", "henry")
        with pytest.raises(ValueError):
            queue.approve("t1", "henry")

    def test_unknown_request_raises(self, queue):
        with pytest.raises(KeyError):
            queue.approve("nonexistent", "henry")


class TestExpiry:

    def test_expiry_detection(self, queue):
        req = queue.submit(
            request_id="exp1",
            run_id="r",
            risk_level="medium",
            title="t",
            summary="s",
            affected_paths=[],
            diff_preview="",
            residual_risk_score=1.0,
            ttl_hours=0,  # expires immediately
        )
        import time
        time.sleep(0.01)
        assert req.is_expired()

    def test_cleanup_expired(self, queue):
        queue.submit(
            request_id="exp2",
            run_id="r",
            risk_level="medium",
            title="t",
            summary="s",
            affected_paths=[],
            diff_preview="",
            residual_risk_score=1.0,
            ttl_hours=0,
        )
        import time
        time.sleep(0.01)
        changed = queue.cleanup_expired()
        assert changed == 1
        req = queue.get("exp2")
        assert req.state == ApprovalState.TIMEOUT


class TestQueries:

    def test_list_pending(self, queue):
        _submit(queue, risk_level="medium", request_id="p1")
        _submit(queue, risk_level="low", request_id="p2")
        _submit(queue, risk_level="high", request_id="p3")
        pending = queue.list_pending()
        assert len(pending) == 2  # medium + high (low is auto-approved)

    def test_stats(self, queue):
        _submit(queue, risk_level="low", request_id="s1")
        _submit(queue, risk_level="medium", request_id="s2")
        queue.approve("s2", "henry")
        stats = queue.stats
        assert stats["total"] == 2
        assert stats["by_state"].get("auto_approved") == 1
        assert stats["by_state"].get("approved") == 1


class TestRiskLevelHelper:

    def test_low_does_not_require_approval(self):
        assert RiskLevel.LOW.requires_approval() is False

    def test_medium_plus_require_approval(self):
        for level in [RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]:
            assert level.requires_approval() is True


class TestSingleton:

    def test_singleton(self):
        q1 = get_approval_queue()
        q2 = get_approval_queue()
        assert q1 is q2
