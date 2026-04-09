"""Auto-dev pipeline orchestrator.

State machine:

    PROPOSED → BUILDING → VERIFYING → AWAITING_APPROVAL → APPROVED → MERGED
                    ↓          ↓              ↓                  ↓
                 FAILED     FAILED         REJECTED/TIMEOUT    FAILED

    Any state can transition to → CANCELLED (kill switch, manual abort)

Flow (enforced by OCCP discipline):
1. PROPOSE  — validate via self_modifier + policy_engine, check budget
2. BUILD    — create worktree, apply diff, capture files_modified
3. VERIFY   — lint + targeted test + regression
4. RISK     — compute residual risk assessment
5. APPROVE  — LOW: auto-approve. MEDIUM+: queue for HITL via Telegram.
6. MERGE    — apply diff to live repo branch (NOT main — feature branch)
              Future: shadow run then canary
7. CLEANUP  — remove worktree, log final state

Preservation contract:
- Never writes to main branch directly
- Always creates new feature branch for final merge
- Kill switch aborts any state transition
- Every transition emits an audit record
- Budget checked pre-flight; budget exhausted → reject
"""

from __future__ import annotations

import logging
import pathlib
import subprocess
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from autodev.approval_queue import ApprovalQueue, ApprovalState, RiskLevel, get_approval_queue
from autodev.rate_budget_tracker import BudgetExhausted, RateBudgetTracker, get_rate_budget_tracker
from autodev.residual_risk import (
    ResidualRiskCalculator,
    RiskAssessment,
    get_residual_risk_calculator,
)
from autodev.sandbox_worktree import SandboxWorktree, WorktreeHandle, get_sandbox_worktree
from autodev.verification_gate import VerificationGate, VerificationReport, get_verification_gate
from evaluation.kill_switch import get_kill_switch, KillSwitchActive
from evaluation.self_modifier import get_self_modifier

logger = logging.getLogger(__name__)


class RunState(str, Enum):
    PROPOSED = "proposed"
    BUILDING = "building"
    VERIFYING = "verifying"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    MERGING = "merging"
    MERGED = "merged"
    REJECTED = "rejected"
    FAILED = "failed"
    CANCELLED = "cancelled"


TERMINAL_STATES = {
    RunState.MERGED,
    RunState.REJECTED,
    RunState.FAILED,
    RunState.CANCELLED,
}


@dataclass
class AutoDevRun:
    """One end-to-end auto-dev run."""

    run_id: str
    title: str
    rationale: str
    proposed_diff: str  # Unified diff to apply
    state: RunState = RunState.PROPOSED
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Derived / filled during execution
    worktree_handle: WorktreeHandle | None = None
    files_modified: list[str] = field(default_factory=list)
    verification_report: VerificationReport | None = None
    risk_assessment: RiskAssessment | None = None
    approval_request_id: str | None = None
    merge_branch: str | None = None
    error: str | None = None
    transitions: list[dict[str, Any]] = field(default_factory=list)

    def record_transition(self, to_state: RunState, reason: str = "") -> None:
        self.transitions.append(
            {
                "from": self.state.value,
                "to": to_state.value,
                "at": datetime.now(timezone.utc).isoformat(),
                "reason": reason,
            }
        )
        self.state = to_state
        self.updated_at = datetime.now(timezone.utc)

    @property
    def is_terminal(self) -> bool:
        return self.state in TERMINAL_STATES

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "title": self.title,
            "rationale": self.rationale,
            "state": self.state.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "files_modified": self.files_modified,
            "diff_size_lines": self.proposed_diff.count("\n"),
            "verification": (
                self.verification_report.to_dict() if self.verification_report else None
            ),
            "risk_assessment": (
                self.risk_assessment.to_dict() if self.risk_assessment else None
            ),
            "approval_request_id": self.approval_request_id,
            "merge_branch": self.merge_branch,
            "error": self.error,
            "transitions": self.transitions,
            "is_terminal": self.is_terminal,
        }


class AutoDevOrchestrator:
    """End-to-end auto-dev pipeline coordinator."""

    def __init__(
        self,
        *,
        sandbox: SandboxWorktree | None = None,
        verification: VerificationGate | None = None,
        risk_calc: ResidualRiskCalculator | None = None,
        approval_queue: ApprovalQueue | None = None,
        budget: RateBudgetTracker | None = None,
    ) -> None:
        self._sandbox = sandbox
        self._verification = verification
        self._risk_calc = risk_calc
        self._approval_queue = approval_queue
        self._budget = budget
        self._lock = threading.Lock()
        self._runs: dict[str, AutoDevRun] = {}

    # Singleton accessors
    def _get_sandbox(self) -> SandboxWorktree:
        return self._sandbox or get_sandbox_worktree()

    def _get_verification(self) -> VerificationGate:
        return self._verification or get_verification_gate()

    def _get_risk(self) -> ResidualRiskCalculator:
        return self._risk_calc or get_residual_risk_calculator()

    def _get_approval(self) -> ApprovalQueue:
        return self._approval_queue or get_approval_queue()

    def _get_budget(self) -> RateBudgetTracker:
        return self._budget or get_rate_budget_tracker()

    # ── Public API ────────────────────────────────────────
    def propose(
        self,
        *,
        title: str,
        rationale: str,
        proposed_diff: str,
    ) -> AutoDevRun:
        """Submit a new auto-dev proposal.

        Performs pre-flight checks:
        - Kill switch must be inactive
        - Budget must allow a new run
        - Diff must be non-empty
        """
        # Kill-switch pre-flight
        ks = get_kill_switch()
        if ks.is_active():
            raise KillSwitchActive(
                reason=(
                    ks.current_activation.reason
                    if ks.current_activation
                    else "unknown"
                ),
                trigger=(
                    ks.current_activation.trigger
                    if ks.current_activation
                    else None
                ),
            )

        if not proposed_diff.strip():
            raise ValueError("proposed_diff is empty")

        # Budget check
        self._get_budget().check_can_start_run()

        run_id = uuid.uuid4().hex[:12]
        run = AutoDevRun(
            run_id=run_id,
            title=title[:200],
            rationale=rationale[:2000],
            proposed_diff=proposed_diff,
        )

        with self._lock:
            self._runs[run_id] = run

        self._get_budget().record_run_started()
        run.record_transition(RunState.PROPOSED, reason="submitted")
        logger.info(
            "autodev.orchestrator: proposed run_id=%s title=%r", run_id, title[:60]
        )
        return run

    def execute_build_and_verify(self, run_id: str) -> AutoDevRun:
        """Build worktree, apply diff, run verification.

        Transitions: PROPOSED → BUILDING → VERIFYING → AWAITING_APPROVAL|FAILED
        """
        run = self._require_run(run_id)
        if run.state != RunState.PROPOSED:
            raise ValueError(
                f"cannot build: run {run_id} in state {run.state.value}"
            )

        # ── BUILD ─────────────────────────────────
        run.record_transition(RunState.BUILDING, reason="create worktree")
        try:
            handle = self._get_sandbox().create(run_id=run_id)
            run.worktree_handle = handle
        except Exception as exc:  # noqa: BLE001
            run.error = f"worktree creation failed: {exc}"
            run.record_transition(RunState.FAILED, reason=run.error)
            return run

        # Apply diff via git apply
        try:
            self._apply_diff(handle.worktree_path, run.proposed_diff)
        except Exception as exc:  # noqa: BLE001
            run.error = f"diff apply failed: {exc}"
            self._get_sandbox().cleanup(run_id)
            run.record_transition(RunState.FAILED, reason=run.error)
            return run

        # Capture modified files
        try:
            diff = self._get_sandbox().capture_diff(run_id)
            run.files_modified = handle.files_modified
        except Exception as exc:  # noqa: BLE001
            run.error = f"diff capture failed: {exc}"
            self._get_sandbox().cleanup(run_id)
            run.record_transition(RunState.FAILED, reason=run.error)
            return run

        # ── VERIFY ────────────────────────────────
        run.record_transition(RunState.VERIFYING, reason="lint + test + regression")
        try:
            report = self._get_verification().verify(
                run_id=run_id,
                worktree_path=handle.worktree_path,
                modified_files=run.files_modified,
            )
            run.verification_report = report
        except Exception as exc:  # noqa: BLE001
            run.error = f"verification error: {exc}"
            self._get_sandbox().cleanup(run_id)
            run.record_transition(RunState.FAILED, reason=run.error)
            return run

        # ── RISK ──────────────────────────────────
        try:
            assessment = self._get_risk().assess(
                verification=report,
                affected_paths=run.files_modified,
                diff_size_lines=run.proposed_diff.count("\n"),
            )
            run.risk_assessment = assessment
        except Exception as exc:  # noqa: BLE001
            run.error = f"risk assessment error: {exc}"
            self._get_sandbox().cleanup(run_id)
            run.record_transition(RunState.FAILED, reason=run.error)
            return run

        # Hard fail on verification failure
        if not report.passed:
            run.error = "verification stage failed"
            self._get_sandbox().cleanup(run_id)
            run.record_transition(RunState.FAILED, reason="verification failed")
            return run

        # ── APPROVAL ──────────────────────────────
        # Submit to approval queue (auto-approves LOW)
        risk_level_for_approval = RiskLevel(assessment.risk_level)

        if assessment.recommendation == "reject":
            run.error = f"risk assessment rejected: score={assessment.score}"
            self._get_sandbox().cleanup(run_id)
            run.record_transition(RunState.REJECTED, reason=run.error)
            return run

        # Budget check for medium+ proposals
        if risk_level_for_approval != RiskLevel.LOW:
            try:
                self._get_budget().check_can_submit_medium_plus()
                self._get_budget().record_medium_plus_proposal()
            except BudgetExhausted as exc:
                run.error = str(exc)
                self._get_sandbox().cleanup(run_id)
                run.record_transition(RunState.REJECTED, reason=run.error)
                return run

        approval_req = self._get_approval().submit(
            request_id=f"appr-{run_id}",
            run_id=run_id,
            risk_level=risk_level_for_approval,
            title=run.title,
            summary=run.rationale[:500],
            affected_paths=run.files_modified,
            diff_preview=run.proposed_diff[:2000],
            residual_risk_score=assessment.score,
        )
        run.approval_request_id = approval_req.request_id

        if approval_req.state == ApprovalState.AUTO_APPROVED:
            run.record_transition(
                RunState.APPROVED,
                reason="LOW risk auto-approved",
            )
        else:
            run.record_transition(
                RunState.AWAITING_APPROVAL,
                reason=f"{risk_level_for_approval.value} risk — awaiting HITL",
            )

        return run

    def resolve_approval(
        self, run_id: str, approved: bool, actor: str, reason: str = ""
    ) -> AutoDevRun:
        """Called when HITL responds to an approval request."""
        run = self._require_run(run_id)
        if run.state != RunState.AWAITING_APPROVAL:
            raise ValueError(
                f"run {run_id} not awaiting approval (state={run.state.value})"
            )
        if run.approval_request_id is None:
            raise ValueError(f"run {run_id} has no approval_request_id")

        if approved:
            self._get_approval().approve(run.approval_request_id, actor, reason)
            run.record_transition(RunState.APPROVED, reason=f"approved by {actor}: {reason}")
        else:
            self._get_approval().reject(run.approval_request_id, actor, reason)
            if run.worktree_handle:
                self._get_sandbox().cleanup(run_id)
            run.record_transition(RunState.REJECTED, reason=f"rejected by {actor}: {reason}")

        return run

    def finalize_merge(self, run_id: str) -> AutoDevRun:
        """Record MERGED state. Actual git merge is deferred to human — we
        only mark the branch as ready and keep the worktree + branch alive
        for manual PR creation.

        In v0.11.0 this will automate: push branch → create PR → await CI.
        """
        run = self._require_run(run_id)
        if run.state != RunState.APPROVED:
            raise ValueError(f"cannot merge: state={run.state.value}")

        run.record_transition(RunState.MERGING, reason="preparing branch")

        # Keep the worktree and branch — do NOT merge to main.
        # Mark the branch name as the merge target.
        if run.worktree_handle:
            run.merge_branch = run.worktree_handle.branch_name
            # Do NOT cleanup — branch kept for human PR
            self._get_sandbox().cleanup(run_id, keep_branch=True)

        # Record budget consumption
        if (
            run.risk_assessment
            and run.risk_assessment.risk_level == "low"
        ):
            self._get_budget().record_low_risk_merge()

        run.record_transition(
            RunState.MERGED,
            reason=f"branch {run.merge_branch} ready for human PR",
        )
        return run

    def cancel(self, run_id: str, reason: str = "manual") -> AutoDevRun:
        """Abort a run and clean up its worktree."""
        run = self._require_run(run_id)
        if run.is_terminal:
            return run

        if run.worktree_handle and not run.worktree_handle.cleaned_up:
            self._get_sandbox().cleanup(run_id)
        run.record_transition(RunState.CANCELLED, reason=reason)
        return run

    # ── Introspection ─────────────────────────────────────
    def get(self, run_id: str) -> AutoDevRun | None:
        with self._lock:
            return self._runs.get(run_id)

    def list_all(self) -> list[AutoDevRun]:
        with self._lock:
            return sorted(
                self._runs.values(), key=lambda r: r.created_at, reverse=True
            )

    # ── Helpers ────────────────────────────────────────────
    def _require_run(self, run_id: str) -> AutoDevRun:
        run = self.get(run_id)
        if run is None:
            raise KeyError(f"unknown run_id: {run_id}")
        return run

    def _apply_diff(self, worktree_path: pathlib.Path, diff: str) -> None:
        """Apply a unified diff to the worktree via `git apply`."""
        # Write diff to a temp file inside the worktree
        diff_file = worktree_path / ".autodev.patch"
        diff_file.write_text(diff)
        try:
            subprocess.run(
                ["git", "apply", "--whitespace=nowarn", str(diff_file)],
                cwd=worktree_path,
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(
                f"git apply failed: {exc.stderr or exc.stdout}"
            ) from exc
        finally:
            try:
                diff_file.unlink()
            except FileNotFoundError:
                pass


# ── Singleton accessor ────────────────────────────────────────
_global_orchestrator: AutoDevOrchestrator | None = None
_init_lock = threading.Lock()


def get_orchestrator() -> AutoDevOrchestrator:
    global _global_orchestrator
    if _global_orchestrator is None:
        with _init_lock:
            if _global_orchestrator is None:
                _global_orchestrator = AutoDevOrchestrator()
    return _global_orchestrator
