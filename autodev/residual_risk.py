"""Residual risk calculator for auto-dev proposals.

Computes a risk score [0.0, 10.0] for a proposal AFTER verification.
Low scores = safer; high scores = needs human scrutiny.

Inputs:
- Verification report (lint/test/regression results)
- Diff size (lines changed)
- File count affected
- Severity of files (security/policy_engine are forbidden; orchestrator is high)
- Governance verdict from SelfModifier

Output: residual_risk_score + human-readable risk factors + recommendation.

This is deterministic and testable — no LLM involved.
"""

from __future__ import annotations

import logging
import pathlib
from dataclasses import dataclass, field
from typing import Any

from autodev.verification_gate import VerificationReport
from evaluation.self_modifier import SelfModifier, get_self_modifier

logger = logging.getLogger(__name__)


@dataclass
class RiskFactor:
    """A single contributing factor to the residual risk score."""

    name: str
    weight: float
    reason: str


@dataclass
class RiskAssessment:
    """Result of residual risk calculation."""

    score: float  # 0.0..10.0
    risk_level: str  # "low" | "medium" | "high" | "critical"
    recommendation: str  # "auto_merge" | "review" | "reject"
    factors: list[RiskFactor] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": round(self.score, 2),
            "risk_level": self.risk_level,
            "recommendation": self.recommendation,
            "factors": [
                {"name": f.name, "weight": f.weight, "reason": f.reason}
                for f in self.factors
            ],
        }


class ResidualRiskCalculator:
    """Deterministic residual risk scoring."""

    # Per-category base weights (out of 10)
    VERIFICATION_FAIL_WEIGHT = 10.0  # auto-reject on any stage failure
    LARGE_DIFF_WEIGHT = 2.0
    MULTI_FILE_WEIGHT = 1.5
    SENSITIVE_MODULE_WEIGHT = 3.0
    GOVERNANCE_REVIEW_WEIGHT = 2.0
    GOVERNANCE_IMMUTABLE_WEIGHT = 10.0  # auto-reject if any immutable path

    # Thresholds
    LARGE_DIFF_THRESHOLD_LINES = 200
    MULTI_FILE_THRESHOLD = 5

    # Sensitive path substrings (lower = more sensitive)
    SENSITIVE_PATH_SUBSTRINGS = (
        "orchestrator/",
        "adapters/claude_planner",
        "adapters/multi_llm_planner",
        "adapters/openclaw_executor",
        "store/",
    )

    def __init__(self, modifier: SelfModifier | None = None) -> None:
        self._modifier = modifier

    def _get_modifier(self) -> SelfModifier:
        return self._modifier or get_self_modifier()

    def assess(
        self,
        *,
        verification: VerificationReport | None,
        affected_paths: list[str],
        diff_size_lines: int,
    ) -> RiskAssessment:
        """Compute the residual risk score."""
        factors: list[RiskFactor] = []
        score = 0.0

        # 1. Verification outcome — hard fail
        if verification is not None and not verification.passed:
            failed_stages = [
                s.stage for s in verification.stages if s.verdict == "fail"
            ]
            factors.append(
                RiskFactor(
                    name="verification_failed",
                    weight=self.VERIFICATION_FAIL_WEIGHT,
                    reason=f"stages failed: {failed_stages}",
                )
            )
            score += self.VERIFICATION_FAIL_WEIGHT

        # 2. Governance check on affected paths
        modifier = self._get_modifier()
        verdicts = modifier.check_many(affected_paths) if affected_paths else {}

        has_immutable = any(v.tier == "immutable" for v in verdicts.values())
        review_count = sum(
            1 for v in verdicts.values() if v.tier == "human_review_required"
        )
        unknown_count = sum(1 for v in verdicts.values() if v.tier == "unknown")

        if has_immutable:
            immutable_paths = [
                p for p, v in verdicts.items() if v.tier == "immutable"
            ]
            factors.append(
                RiskFactor(
                    name="immutable_path",
                    weight=self.GOVERNANCE_IMMUTABLE_WEIGHT,
                    reason=f"touches immutable: {immutable_paths}",
                )
            )
            score += self.GOVERNANCE_IMMUTABLE_WEIGHT

        if review_count > 0:
            factors.append(
                RiskFactor(
                    name="human_review_paths",
                    weight=self.GOVERNANCE_REVIEW_WEIGHT,
                    reason=f"{review_count} path(s) require human review",
                )
            )
            score += self.GOVERNANCE_REVIEW_WEIGHT

        if unknown_count > 0:
            factors.append(
                RiskFactor(
                    name="unknown_paths",
                    weight=1.0 * unknown_count,
                    reason=f"{unknown_count} path(s) not in any boundary tier",
                )
            )
            score += 1.0 * unknown_count

        # 3. Diff size
        if diff_size_lines > self.LARGE_DIFF_THRESHOLD_LINES:
            factors.append(
                RiskFactor(
                    name="large_diff",
                    weight=self.LARGE_DIFF_WEIGHT,
                    reason=f"{diff_size_lines} lines (> {self.LARGE_DIFF_THRESHOLD_LINES})",
                )
            )
            score += self.LARGE_DIFF_WEIGHT

        # 4. File count
        if len(affected_paths) > self.MULTI_FILE_THRESHOLD:
            factors.append(
                RiskFactor(
                    name="multi_file",
                    weight=self.MULTI_FILE_WEIGHT,
                    reason=f"{len(affected_paths)} files modified (> {self.MULTI_FILE_THRESHOLD})",
                )
            )
            score += self.MULTI_FILE_WEIGHT

        # 5. Sensitive modules
        sensitive_hits: list[str] = []
        for path in affected_paths:
            for sub in self.SENSITIVE_PATH_SUBSTRINGS:
                if sub in path:
                    sensitive_hits.append(path)
                    break
        if sensitive_hits:
            factors.append(
                RiskFactor(
                    name="sensitive_module",
                    weight=self.SENSITIVE_MODULE_WEIGHT,
                    reason=f"touches: {sensitive_hits[:3]}",
                )
            )
            score += self.SENSITIVE_MODULE_WEIGHT

        # Clamp to [0, 10]
        score = max(0.0, min(10.0, score))

        # Risk level
        if score >= 8.0:
            risk_level = "critical"
            recommendation = "reject"
        elif score >= 5.0:
            risk_level = "high"
            recommendation = "review"
        elif score >= 2.0:
            risk_level = "medium"
            recommendation = "review"
        else:
            risk_level = "low"
            recommendation = "auto_merge"

        return RiskAssessment(
            score=score,
            risk_level=risk_level,
            recommendation=recommendation,
            factors=factors,
        )


# ── Singleton accessor ────────────────────────────────────────
_global_calc: ResidualRiskCalculator | None = None


def get_residual_risk_calculator() -> ResidualRiskCalculator:
    global _global_calc
    if _global_calc is None:
        _global_calc = ResidualRiskCalculator()
    return _global_calc
