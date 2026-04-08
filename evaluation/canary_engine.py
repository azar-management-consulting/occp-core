"""Canary engine — deterministic metric comparison for staged rollouts.

Given a baseline metric snapshot and a candidate metric snapshot, produce
a verdict about whether the candidate is safe to promote.

This is NOT a traffic splitter — that requires reverse-proxy integration
and will land in v0.11.0. This is the *comparison* layer: the part that
decides "baseline vs candidate — promote, hold, or rollback".

Criteria (configurable):
- Success rate must not drop by more than delta_success
- Denial rate must not increase by more than delta_denial
- p99 stage duration must not increase by more than factor_latency
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CanaryCriteria:
    """Tunable canary thresholds."""

    min_candidate_samples: int = 5

    # Max allowed drop in success rate (e.g. 0.05 = 5 percentage points)
    max_success_rate_drop: float = 0.05

    # Max allowed increase in denial rate
    max_denial_rate_increase: float = 0.05

    # Max allowed latency growth factor (e.g. 1.5 = 50% slower allowed)
    max_latency_growth_factor: float = 1.5


@dataclass
class CanaryVerdict:
    """The outcome of a canary comparison."""

    decision: str  # "promote" | "hold" | "rollback"
    reason: str
    baseline_success_rate: float
    candidate_success_rate: float
    baseline_denial_rate: float
    candidate_denial_rate: float
    baseline_avg_ms: float
    candidate_avg_ms: float
    regressions: list[str] = field(default_factory=list)
    improvements: list[str] = field(default_factory=list)
    decided_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "reason": self.reason,
            "baseline_success_rate": self.baseline_success_rate,
            "candidate_success_rate": self.candidate_success_rate,
            "baseline_denial_rate": self.baseline_denial_rate,
            "candidate_denial_rate": self.candidate_denial_rate,
            "baseline_avg_ms": self.baseline_avg_ms,
            "candidate_avg_ms": self.candidate_avg_ms,
            "regressions": self.regressions,
            "improvements": self.improvements,
            "decided_at": self.decided_at.isoformat(),
        }


class CanaryEngine:
    """Compare two metric snapshots and produce a rollout decision."""

    def __init__(self, criteria: CanaryCriteria | None = None) -> None:
        self._criteria = criteria or CanaryCriteria()

    @staticmethod
    def _extract_success_rate(snap: dict[str, Any]) -> tuple[float, int]:
        """Return (success_rate, total_samples)."""
        tasks = snap.get("counters", {}).get("occp.pipeline.tasks")
        if not tasks:
            return 0.0, 0
        total = 0.0
        success = 0.0
        for series in tasks["values"]:
            val = float(series["value"])
            total += val
            if series["labels"].get("outcome") == "success":
                success += val
        return (success / total if total else 0.0), int(total)

    @staticmethod
    def _extract_denial_rate(snap: dict[str, Any]) -> float:
        tasks = snap.get("counters", {}).get("occp.pipeline.tasks")
        if not tasks:
            return 0.0
        total = 0.0
        denied = 0.0
        for series in tasks["values"]:
            val = float(series["value"])
            total += val
            if series["labels"].get("outcome") in ("gate_rejected", "human_rejected"):
                denied += val
        return denied / total if total else 0.0

    @staticmethod
    def _extract_avg_latency(snap: dict[str, Any]) -> float:
        """Weighted average of all stage histograms."""
        hist = snap.get("histograms", {}).get("occp.pipeline.stage_duration_ms")
        if not hist:
            return 0.0
        total_sum = 0.0
        total_count = 0
        for series in hist["series"]:
            total_sum += float(series["sum"])
            total_count += int(series["count"])
        return total_sum / total_count if total_count else 0.0

    def compare(
        self,
        baseline_snapshot: dict[str, Any],
        candidate_snapshot: dict[str, Any],
    ) -> CanaryVerdict:
        """Compare baseline to candidate and produce a verdict."""
        b_success_rate, _ = self._extract_success_rate(baseline_snapshot)
        c_success_rate, c_samples = self._extract_success_rate(candidate_snapshot)
        b_denial_rate = self._extract_denial_rate(baseline_snapshot)
        c_denial_rate = self._extract_denial_rate(candidate_snapshot)
        b_avg_ms = self._extract_avg_latency(baseline_snapshot)
        c_avg_ms = self._extract_avg_latency(candidate_snapshot)

        regressions: list[str] = []
        improvements: list[str] = []

        # Minimum samples gate
        if c_samples < self._criteria.min_candidate_samples:
            return CanaryVerdict(
                decision="hold",
                reason=(
                    f"candidate has {c_samples} samples, "
                    f"need >= {self._criteria.min_candidate_samples}"
                ),
                baseline_success_rate=b_success_rate,
                candidate_success_rate=c_success_rate,
                baseline_denial_rate=b_denial_rate,
                candidate_denial_rate=c_denial_rate,
                baseline_avg_ms=b_avg_ms,
                candidate_avg_ms=c_avg_ms,
            )

        # Success rate regression check
        success_drop = b_success_rate - c_success_rate
        if success_drop > self._criteria.max_success_rate_drop:
            regressions.append(
                f"success rate dropped by {success_drop:.3f} "
                f"(allowed {self._criteria.max_success_rate_drop})"
            )
        elif c_success_rate > b_success_rate:
            improvements.append(
                f"success rate improved by {c_success_rate - b_success_rate:.3f}"
            )

        # Denial rate regression check
        denial_increase = c_denial_rate - b_denial_rate
        if denial_increase > self._criteria.max_denial_rate_increase:
            regressions.append(
                f"denial rate increased by {denial_increase:.3f} "
                f"(allowed {self._criteria.max_denial_rate_increase})"
            )

        # Latency regression check
        if b_avg_ms > 0:
            growth = c_avg_ms / b_avg_ms
            if growth > self._criteria.max_latency_growth_factor:
                regressions.append(
                    f"latency grew to {growth:.2f}x baseline "
                    f"(allowed {self._criteria.max_latency_growth_factor}x)"
                )
            elif c_avg_ms < b_avg_ms * 0.9:
                improvements.append(
                    f"latency reduced to {growth:.2f}x baseline"
                )

        # Decision
        if regressions:
            # Hard regressions → rollback. Soft → hold.
            severe = any(
                "success rate dropped" in r or "latency grew" in r
                for r in regressions
            )
            decision = "rollback" if severe else "hold"
            reason = "; ".join(regressions)
        else:
            decision = "promote"
            reason = "all criteria passed"

        verdict = CanaryVerdict(
            decision=decision,
            reason=reason,
            baseline_success_rate=b_success_rate,
            candidate_success_rate=c_success_rate,
            baseline_denial_rate=b_denial_rate,
            candidate_denial_rate=c_denial_rate,
            baseline_avg_ms=b_avg_ms,
            candidate_avg_ms=c_avg_ms,
            regressions=regressions,
            improvements=improvements,
        )
        logger.info(
            "canary: decision=%s success_rate=%.3f→%.3f denial=%.3f→%.3f latency=%.1f→%.1fms",
            decision,
            b_success_rate,
            c_success_rate,
            b_denial_rate,
            c_denial_rate,
            b_avg_ms,
            c_avg_ms,
        )
        return verdict


# ── Singleton accessor ────────────────────────────────────────
_global_canary: CanaryEngine | None = None


def get_canary_engine() -> CanaryEngine:
    """Return the process-global canary engine singleton."""
    global _global_canary
    if _global_canary is None:
        _global_canary = CanaryEngine()
    return _global_canary
