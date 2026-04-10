"""OCCP auto-dev pipeline (v0.10.0 — safe self-improvement subsystem).

Components:
- sandbox_worktree: ephemeral git-worktree sandbox lifecycle
- verification_gate: lint + targeted test + regression runner
- approval_queue: HITL approval queue with TTL
- rate_budget_tracker: per-day resource caps
- residual_risk: deterministic risk scoring
- orchestrator: end-to-end state machine (propose → build → verify → approve → merge)

Safety contract (non-negotiable):
- Every change happens inside a disposable git worktree.
- Live repo branches are never modified directly.
- Every state transition is audited in the hash chain.
- Kill switch aborts any in-flight run.
- LOW risk auto-approves after verification.
- MEDIUM+ risk requires HITL approval via Telegram.
- Hard failure at any stage → automatic rollback (worktree cleanup).
"""

from autodev.approval_queue import (
    ApprovalQueue,
    ApprovalRequest,
    ApprovalState,
    RiskLevel,
    get_approval_queue,
)
from autodev.orchestrator import (
    AutoDevOrchestrator,
    AutoDevRun,
    RunState,
    get_orchestrator,
)
from autodev.rate_budget_tracker import (
    BudgetExhausted,
    BudgetLimits,
    DailyUsage,
    RateBudgetTracker,
    get_rate_budget_tracker,
)
from autodev.residual_risk import (
    ResidualRiskCalculator,
    RiskAssessment,
    RiskFactor,
    get_residual_risk_calculator,
)
from autodev.sandbox_worktree import (
    SandboxError,
    SandboxWorktree,
    WorktreeHandle,
    get_sandbox_worktree,
)
from autodev.verification_gate import (
    StageResult,
    VerificationGate,
    VerificationReport,
    get_verification_gate,
)

__all__ = [
    # Sandbox
    "SandboxWorktree",
    "WorktreeHandle",
    "SandboxError",
    "get_sandbox_worktree",
    # Verification
    "VerificationGate",
    "VerificationReport",
    "StageResult",
    "get_verification_gate",
    # Approval
    "ApprovalQueue",
    "ApprovalRequest",
    "ApprovalState",
    "RiskLevel",
    "get_approval_queue",
    # Budget
    "RateBudgetTracker",
    "BudgetLimits",
    "DailyUsage",
    "BudgetExhausted",
    "get_rate_budget_tracker",
    # Risk
    "ResidualRiskCalculator",
    "RiskAssessment",
    "RiskFactor",
    "get_residual_risk_calculator",
    # Orchestrator
    "AutoDevOrchestrator",
    "AutoDevRun",
    "RunState",
    "get_orchestrator",
]
