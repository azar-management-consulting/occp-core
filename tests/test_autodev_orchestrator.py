"""Tests for autodev.orchestrator state machine.

These tests use mocked sandbox + verification to test the state machine
without running real git or pytest subprocesses.
"""

from __future__ import annotations

import pathlib
from unittest.mock import MagicMock, patch

import pytest

from autodev.approval_queue import ApprovalState
from autodev.orchestrator import (
    AutoDevOrchestrator,
    AutoDevRun,
    RunState,
    get_orchestrator,
)
from autodev.rate_budget_tracker import BudgetExhausted, BudgetLimits, RateBudgetTracker
from autodev.residual_risk import RiskAssessment, RiskFactor
from autodev.verification_gate import StageResult, VerificationReport
from autodev.sandbox_worktree import WorktreeHandle


def _mock_sandbox(run_id: str, files_modified: list[str] | None = None):
    sandbox = MagicMock()
    handle = WorktreeHandle(
        run_id=run_id,
        worktree_path=pathlib.Path(f"/tmp/{run_id}"),
        branch_name=f"autodev/{run_id}",
        base_branch="HEAD",
    )
    handle.files_modified = files_modified or ["architecture/services.yaml"]
    sandbox.create.return_value = handle
    sandbox.capture_diff.return_value = "--- a\n+++ b"
    sandbox.cleanup = MagicMock()
    return sandbox, handle


def _mock_verification_pass():
    gate = MagicMock()
    gate.verify.return_value = VerificationReport(
        run_id="r",
        worktree_path=pathlib.Path("/tmp/r"),
        stages=[
            StageResult(stage="lint", verdict="pass", duration_seconds=1.0),
            StageResult(stage="targeted_test", verdict="pass", duration_seconds=5.0),
            StageResult(stage="regression", verdict="pass", duration_seconds=10.0),
        ],
    )
    return gate


def _mock_verification_fail():
    gate = MagicMock()
    gate.verify.return_value = VerificationReport(
        run_id="r",
        worktree_path=pathlib.Path("/tmp/r"),
        stages=[
            StageResult(stage="lint", verdict="fail", duration_seconds=1.0),
        ],
    )
    return gate


def _mock_risk_low():
    calc = MagicMock()
    calc.assess.return_value = RiskAssessment(
        score=1.0,
        risk_level="low",
        recommendation="auto_merge",
        factors=[],
    )
    return calc


def _mock_risk_medium():
    calc = MagicMock()
    calc.assess.return_value = RiskAssessment(
        score=3.5,
        risk_level="medium",
        recommendation="review",
        factors=[],
    )
    return calc


def _mock_risk_critical():
    calc = MagicMock()
    calc.assess.return_value = RiskAssessment(
        score=9.0,
        risk_level="critical",
        recommendation="reject",
        factors=[RiskFactor("immutable_path", 10, "security/")],
    )
    return calc


@pytest.fixture
def fresh_orchestrator(tmp_path):
    from autodev.approval_queue import ApprovalQueue
    budget = RateBudgetTracker(
        limits=BudgetLimits(
            max_runs_per_day=10,
            max_medium_plus_proposals_per_day=10,
        )
    )
    return AutoDevOrchestrator(
        approval_queue=ApprovalQueue(),
        budget=budget,
    )


class TestPropose:

    def test_propose_creates_run(self, fresh_orchestrator):
        run = fresh_orchestrator.propose(
            title="Test",
            rationale="Test rationale that is long enough to pass validation",
            proposed_diff="--- a\n+++ b",
        )
        assert run.state == RunState.PROPOSED
        assert run.run_id is not None

    def test_propose_empty_diff_raises(self, fresh_orchestrator):
        with pytest.raises(ValueError, match="empty"):
            fresh_orchestrator.propose(
                title="Test",
                rationale="rationale",
                proposed_diff="   ",
            )

    def test_propose_budget_exhausted(self, tmp_path):
        from autodev.approval_queue import ApprovalQueue
        budget = RateBudgetTracker(limits=BudgetLimits(max_runs_per_day=1))
        orch = AutoDevOrchestrator(approval_queue=ApprovalQueue(), budget=budget)
        orch.propose(title="A", rationale="ok rationale here", proposed_diff="+a")
        with pytest.raises(BudgetExhausted):
            orch.propose(title="B", rationale="ok rationale here", proposed_diff="+b")


class TestExecute:

    def test_execute_low_risk_auto_approved(self, fresh_orchestrator):
        fresh_orchestrator._sandbox, handle = _mock_sandbox("low1")
        fresh_orchestrator._verification = _mock_verification_pass()
        fresh_orchestrator._risk_calc = _mock_risk_low()

        run = fresh_orchestrator.propose(
            title="T", rationale="ok rationale here", proposed_diff="+x"
        )
        # Rewire sandbox for that specific run_id
        fresh_orchestrator._sandbox, handle = _mock_sandbox(run.run_id)
        with patch.object(fresh_orchestrator, "_apply_diff"):
            executed = fresh_orchestrator.execute_build_and_verify(run.run_id)

        assert executed.state == RunState.APPROVED  # LOW auto-approved
        assert executed.verification_report is not None
        assert executed.risk_assessment.risk_level == "low"

    def test_execute_medium_awaits_approval(self, fresh_orchestrator):
        fresh_orchestrator._verification = _mock_verification_pass()
        fresh_orchestrator._risk_calc = _mock_risk_medium()

        run = fresh_orchestrator.propose(
            title="T", rationale="ok rationale here", proposed_diff="+x"
        )
        fresh_orchestrator._sandbox, _ = _mock_sandbox(run.run_id)
        with patch.object(fresh_orchestrator, "_apply_diff"):
            executed = fresh_orchestrator.execute_build_and_verify(run.run_id)

        assert executed.state == RunState.AWAITING_APPROVAL
        assert executed.approval_request_id is not None

    def test_execute_critical_is_rejected(self, fresh_orchestrator):
        fresh_orchestrator._verification = _mock_verification_pass()
        fresh_orchestrator._risk_calc = _mock_risk_critical()

        run = fresh_orchestrator.propose(
            title="T", rationale="ok rationale here", proposed_diff="+x"
        )
        fresh_orchestrator._sandbox, _ = _mock_sandbox(run.run_id)
        with patch.object(fresh_orchestrator, "_apply_diff"):
            executed = fresh_orchestrator.execute_build_and_verify(run.run_id)

        assert executed.state == RunState.REJECTED

    def test_verification_failure_fails_run(self, fresh_orchestrator):
        fresh_orchestrator._verification = _mock_verification_fail()
        fresh_orchestrator._risk_calc = _mock_risk_low()

        run = fresh_orchestrator.propose(
            title="T", rationale="ok rationale here", proposed_diff="+x"
        )
        fresh_orchestrator._sandbox, _ = _mock_sandbox(run.run_id)
        with patch.object(fresh_orchestrator, "_apply_diff"):
            executed = fresh_orchestrator.execute_build_and_verify(run.run_id)

        assert executed.state == RunState.FAILED


class TestApprovalFlow:

    def test_approve_medium_transitions_to_approved(self, fresh_orchestrator):
        fresh_orchestrator._verification = _mock_verification_pass()
        fresh_orchestrator._risk_calc = _mock_risk_medium()

        run = fresh_orchestrator.propose(
            title="T", rationale="ok rationale here", proposed_diff="+x"
        )
        fresh_orchestrator._sandbox, _ = _mock_sandbox(run.run_id)
        with patch.object(fresh_orchestrator, "_apply_diff"):
            fresh_orchestrator.execute_build_and_verify(run.run_id)

        resolved = fresh_orchestrator.resolve_approval(
            run.run_id, approved=True, actor="henry", reason="ok"
        )
        assert resolved.state == RunState.APPROVED

    def test_reject_medium(self, fresh_orchestrator):
        fresh_orchestrator._verification = _mock_verification_pass()
        fresh_orchestrator._risk_calc = _mock_risk_medium()

        run = fresh_orchestrator.propose(
            title="T", rationale="ok rationale here", proposed_diff="+x"
        )
        fresh_orchestrator._sandbox, _ = _mock_sandbox(run.run_id)
        with patch.object(fresh_orchestrator, "_apply_diff"):
            fresh_orchestrator.execute_build_and_verify(run.run_id)

        rejected = fresh_orchestrator.resolve_approval(
            run.run_id, approved=False, actor="henry", reason="bad"
        )
        assert rejected.state == RunState.REJECTED


class TestMerge:

    def test_merge_approved_run(self, fresh_orchestrator):
        fresh_orchestrator._verification = _mock_verification_pass()
        fresh_orchestrator._risk_calc = _mock_risk_low()

        run = fresh_orchestrator.propose(
            title="T", rationale="ok rationale here", proposed_diff="+x"
        )
        fresh_orchestrator._sandbox, _ = _mock_sandbox(run.run_id)
        with patch.object(fresh_orchestrator, "_apply_diff"):
            fresh_orchestrator.execute_build_and_verify(run.run_id)

        merged = fresh_orchestrator.finalize_merge(run.run_id)
        assert merged.state == RunState.MERGED
        assert merged.merge_branch is not None


class TestCancel:

    def test_cancel_in_flight(self, fresh_orchestrator):
        run = fresh_orchestrator.propose(
            title="T", rationale="ok rationale here", proposed_diff="+x"
        )
        cancelled = fresh_orchestrator.cancel(run.run_id, reason="test")
        assert cancelled.state == RunState.CANCELLED

    def test_cancel_terminal_is_noop(self, fresh_orchestrator):
        run = fresh_orchestrator.propose(
            title="T", rationale="ok rationale here", proposed_diff="+x"
        )
        fresh_orchestrator.cancel(run.run_id, reason="once")
        state_before = fresh_orchestrator.get(run.run_id).state
        fresh_orchestrator.cancel(run.run_id, reason="twice")
        state_after = fresh_orchestrator.get(run.run_id).state
        assert state_before == state_after


class TestKillSwitch:

    def test_propose_fails_if_kill_switch_active(self, fresh_orchestrator, monkeypatch):
        from evaluation.kill_switch import (
            KillSwitch,
            KillSwitchActive,
            KillSwitchTrigger,
        )
        ks = KillSwitch()
        ks.activate(
            trigger=KillSwitchTrigger.MANUAL,
            actor="test",
            reason="drill",
        )
        from evaluation import kill_switch as ks_mod
        monkeypatch.setattr(ks_mod, "_global_switch", ks)

        with pytest.raises(KillSwitchActive):
            fresh_orchestrator.propose(
                title="T",
                rationale="ok rationale here",
                proposed_diff="+x",
            )


class TestSingleton:

    def test_singleton(self):
        o1 = get_orchestrator()
        o2 = get_orchestrator()
        assert o1 is o2
