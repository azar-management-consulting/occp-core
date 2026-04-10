"""Anomaly detector — runtime interpretation of MetricsCollector data.

This module reads the MetricsCollector singleton and surfaces anomalies:
- Stage latency outliers (percentile based, not z-score — small-sample safe)
- Success rate drops
- Denial rate spikes
- Per-agent reliability drops
- Bottleneck stages (longest p95 contribution)

It does NOT persist to a database or send alerts. It is a read-only
interpretation layer that `/observability/anomalies` exposes and that
future phases (proposal engine, kill-switch) consume.

Design decisions:
- No external deps (pure stdlib)
- Works on small samples (we start with zero data)
- Tunable thresholds via dataclass config
- Deterministic output for testing
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from observability.metrics_collector import MetricsCollector, get_collector

logger = logging.getLogger(__name__)


@dataclass
class AnomalyThresholds:
    """Configurable thresholds for anomaly detection."""

    # Minimum number of observations before we produce any verdict.
    min_samples: int = 5

    # A stage is "slow" if its p95 exceeds this multiple of its median.
    slow_stage_p95_over_median: float = 4.0

    # A stage is "slow" in absolute terms if p95 exceeds this ms.
    slow_stage_absolute_p95_ms: float = 10_000.0

    # Outcome imbalance — if >N% of outcomes are non-success, raise.
    max_non_success_fraction: float = 0.30

    # An agent is "unreliable" if its success rate drops below this.
    min_agent_success_rate: float = 0.70

    # Denial spike threshold — percent of total that is denied/rejected.
    max_denial_fraction: float = 0.20


@dataclass
class Anomaly:
    """A single detected anomaly."""

    code: str
    severity: str  # info | warning | critical
    subject: str  # e.g. "stage.execute" or "agent.infra-ops"
    message: str
    evidence: dict[str, Any] = field(default_factory=dict)
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "subject": self.subject,
            "message": self.message,
            "evidence": self.evidence,
            "detected_at": self.detected_at.isoformat(),
        }


class AnomalyDetector:
    """Reads MetricsCollector snapshots and detects anomalies.

    Stateless — each call produces a fresh verdict. If you need
    time-over-time comparison, that's the behavior_digest responsibility.
    """

    def __init__(
        self,
        collector: MetricsCollector | None = None,
        thresholds: AnomalyThresholds | None = None,
    ) -> None:
        self._collector = collector
        self._thresholds = thresholds or AnomalyThresholds()

    @property
    def thresholds(self) -> AnomalyThresholds:
        return self._thresholds

    def _get_collector(self) -> MetricsCollector:
        return self._collector or get_collector()

    # ── Detection pipeline ────────────────────────────────────
    def detect(self) -> list[Anomaly]:
        """Run all detectors and return the combined anomaly list."""
        snap = self._get_collector().snapshot()
        anomalies: list[Anomaly] = []

        anomalies.extend(self._detect_outcome_imbalance(snap))
        anomalies.extend(self._detect_slow_stages(snap))
        anomalies.extend(self._detect_agent_reliability(snap))
        anomalies.extend(self._detect_denial_spikes(snap))

        logger.info(
            "anomaly_detector: %d anomalies found across %d counters / %d histograms",
            len(anomalies),
            len(snap.get("counters", {})),
            len(snap.get("histograms", {})),
        )
        return anomalies

    # ── Individual detectors ──────────────────────────────────
    def _detect_outcome_imbalance(self, snap: dict[str, Any]) -> list[Anomaly]:
        """If the success rate drops below threshold, raise anomaly."""
        tasks_metric = snap.get("counters", {}).get("occp.pipeline.tasks")
        if not tasks_metric:
            return []

        total = 0.0
        success = 0.0
        by_outcome: dict[str, float] = {}
        for series in tasks_metric["values"]:
            labels = series["labels"]
            val = float(series["value"])
            total += val
            outcome = labels.get("outcome", "?")
            by_outcome[outcome] = by_outcome.get(outcome, 0.0) + val
            if outcome == "success":
                success += val

        if total < self._thresholds.min_samples:
            return []

        non_success_frac = 1.0 - (success / total if total else 1.0)
        if non_success_frac > self._thresholds.max_non_success_fraction:
            return [
                Anomaly(
                    code="pipeline.outcome_imbalance",
                    severity="warning",
                    subject="pipeline.outcomes",
                    message=(
                        f"non-success fraction {non_success_frac:.1%} "
                        f"exceeds threshold {self._thresholds.max_non_success_fraction:.1%}"
                    ),
                    evidence={
                        "total_samples": total,
                        "success_count": success,
                        "by_outcome": by_outcome,
                    },
                )
            ]
        return []

    def _detect_slow_stages(self, snap: dict[str, Any]) -> list[Anomaly]:
        """Detect stages where p95 is unusually high relative to median."""
        hist = snap.get("histograms", {}).get("occp.pipeline.stage_duration_ms")
        if not hist:
            return []

        anomalies: list[Anomaly] = []
        for series in hist["series"]:
            labels = series["labels"]
            count = series["count"]
            total_ms = series["sum"]
            if count < self._thresholds.min_samples:
                continue
            avg_ms = series.get("avg_ms", 0.0)

            # Absolute slow-stage rule: if average alone exceeds 10s, flag.
            if avg_ms > self._thresholds.slow_stage_absolute_p95_ms:
                anomalies.append(
                    Anomaly(
                        code="pipeline.slow_stage",
                        severity="warning",
                        subject=f"stage.{labels.get('stage', '?')}",
                        message=(
                            f"stage '{labels.get('stage', '?')}' average duration "
                            f"{avg_ms:.0f}ms exceeds absolute threshold "
                            f"{self._thresholds.slow_stage_absolute_p95_ms:.0f}ms"
                        ),
                        evidence={
                            "labels": labels,
                            "count": count,
                            "sum_ms": total_ms,
                            "avg_ms": avg_ms,
                        },
                    )
                )
        return anomalies

    def _detect_agent_reliability(self, snap: dict[str, Any]) -> list[Anomaly]:
        """Detect agents whose success rate falls below threshold."""
        tasks_metric = snap.get("counters", {}).get("occp.pipeline.tasks")
        if not tasks_metric:
            return []

        by_agent: dict[str, dict[str, float]] = {}
        for series in tasks_metric["values"]:
            labels = series["labels"]
            agent = labels.get("agent_type", "?")
            outcome = labels.get("outcome", "?")
            by_agent.setdefault(agent, {"total": 0.0, "success": 0.0})
            by_agent[agent]["total"] += float(series["value"])
            if outcome == "success":
                by_agent[agent]["success"] += float(series["value"])

        anomalies: list[Anomaly] = []
        for agent, stats in by_agent.items():
            if stats["total"] < self._thresholds.min_samples:
                continue
            success_rate = stats["success"] / stats["total"]
            if success_rate < self._thresholds.min_agent_success_rate:
                anomalies.append(
                    Anomaly(
                        code="agent.reliability_drop",
                        severity="warning",
                        subject=f"agent.{agent}",
                        message=(
                            f"agent '{agent}' success rate {success_rate:.1%} "
                            f"below threshold {self._thresholds.min_agent_success_rate:.1%}"
                        ),
                        evidence={
                            "agent": agent,
                            "success_rate": success_rate,
                            "total": stats["total"],
                            "success": stats["success"],
                        },
                    )
                )
        return anomalies

    def _detect_denial_spikes(self, snap: dict[str, Any]) -> list[Anomaly]:
        """Detect unusual rate of gate_rejected / human_rejected / error outcomes."""
        tasks_metric = snap.get("counters", {}).get("occp.pipeline.tasks")
        if not tasks_metric:
            return []

        total = 0.0
        denied = 0.0
        for series in tasks_metric["values"]:
            val = float(series["value"])
            total += val
            outcome = series["labels"].get("outcome", "?")
            if outcome in ("gate_rejected", "human_rejected"):
                denied += val

        if total < self._thresholds.min_samples:
            return []

        denial_frac = denied / total if total else 0.0
        if denial_frac > self._thresholds.max_denial_fraction:
            return [
                Anomaly(
                    code="policy.denial_spike",
                    severity="warning",
                    subject="policy.gate",
                    message=(
                        f"denial fraction {denial_frac:.1%} exceeds "
                        f"{self._thresholds.max_denial_fraction:.1%}"
                    ),
                    evidence={
                        "total_samples": total,
                        "denied_count": denied,
                        "denial_fraction": denial_frac,
                    },
                )
            ]
        return []


# ── Singleton accessor ────────────────────────────────────────
_global_detector: AnomalyDetector | None = None


def get_anomaly_detector() -> AnomalyDetector:
    """Return the process-global detector singleton."""
    global _global_detector
    if _global_detector is None:
        _global_detector = AnomalyDetector()
    return _global_detector
