"""Behavior digest — produces narrative operational summaries.

Reads the MetricsCollector snapshot and the AnomalyDetector verdict and
produces a human-readable multi-section digest suitable for display on
the dashboard, Telegram status messages, or embedded in handover docs.

Not a database. Not a cron. Pure read-side interpretation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from observability.anomaly_detector import (
    Anomaly,
    AnomalyDetector,
    get_anomaly_detector,
)
from observability.metrics_collector import MetricsCollector, get_collector

logger = logging.getLogger(__name__)


@dataclass
class BehaviorDigest:
    """Structured digest result."""

    generated_at: datetime
    uptime_seconds: float
    tasks_total: float
    tasks_by_outcome: dict[str, float]
    tasks_by_agent: dict[str, int]
    slowest_stages: list[dict[str, Any]]
    anomalies: list[Anomaly]
    narrative: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "uptime_seconds": self.uptime_seconds,
            "tasks_total": self.tasks_total,
            "tasks_by_outcome": self.tasks_by_outcome,
            "tasks_by_agent": self.tasks_by_agent,
            "slowest_stages": self.slowest_stages,
            "anomalies": [a.to_dict() for a in self.anomalies],
            "narrative": self.narrative,
        }


class BehaviorDigestGenerator:
    """Produces a BehaviorDigest from live metrics + anomalies."""

    def __init__(
        self,
        collector: MetricsCollector | None = None,
        detector: AnomalyDetector | None = None,
    ) -> None:
        self._collector = collector
        self._detector = detector

    def _get_collector(self) -> MetricsCollector:
        return self._collector or get_collector()

    def _get_detector(self) -> AnomalyDetector:
        return self._detector or get_anomaly_detector()

    def generate(self) -> BehaviorDigest:
        """Produce the digest now."""
        snap = self._get_collector().snapshot()
        anomalies = self._get_detector().detect()

        tasks_metric = snap.get("counters", {}).get("occp.pipeline.tasks")
        tasks_total = 0.0
        tasks_by_outcome: dict[str, float] = {}
        tasks_by_agent: dict[str, int] = {}
        if tasks_metric:
            for series in tasks_metric["values"]:
                val = float(series["value"])
                tasks_total += val
                out = series["labels"].get("outcome", "?")
                ag = series["labels"].get("agent_type", "?")
                tasks_by_outcome[out] = tasks_by_outcome.get(out, 0.0) + val
                tasks_by_agent[ag] = int(tasks_by_agent.get(ag, 0) + val)

        hist = snap.get("histograms", {}).get("occp.pipeline.stage_duration_ms")
        slowest: list[dict[str, Any]] = []
        if hist:
            enriched = []
            for series in hist["series"]:
                labels = series["labels"]
                enriched.append(
                    {
                        "stage": labels.get("stage", "?"),
                        "agent_type": labels.get("agent_type", "?"),
                        "count": series["count"],
                        "sum_ms": series["sum"],
                        "avg_ms": series.get("avg_ms", 0.0),
                    }
                )
            slowest = sorted(
                enriched, key=lambda s: s["avg_ms"], reverse=True
            )[:5]

        narrative = self._build_narrative(
            uptime=snap["uptime_seconds"],
            tasks_total=tasks_total,
            tasks_by_outcome=tasks_by_outcome,
            tasks_by_agent=tasks_by_agent,
            slowest=slowest,
            anomalies=anomalies,
        )

        return BehaviorDigest(
            generated_at=datetime.now(timezone.utc),
            uptime_seconds=snap["uptime_seconds"],
            tasks_total=tasks_total,
            tasks_by_outcome=tasks_by_outcome,
            tasks_by_agent=tasks_by_agent,
            slowest_stages=slowest,
            anomalies=anomalies,
            narrative=narrative,
        )

    def _build_narrative(
        self,
        *,
        uptime: float,
        tasks_total: float,
        tasks_by_outcome: dict[str, float],
        tasks_by_agent: dict[str, int],
        slowest: list[dict[str, Any]],
        anomalies: list[Anomaly],
    ) -> str:
        lines: list[str] = []
        hours = uptime / 3600.0
        lines.append(
            f"OCCP observed for {hours:.2f}h — {int(tasks_total)} pipeline tasks processed."
        )

        if tasks_total == 0:
            lines.append("No pipeline activity yet in this metrics window.")
        else:
            success = tasks_by_outcome.get("success", 0.0)
            success_rate = success / tasks_total if tasks_total else 0.0
            lines.append(
                f"Success rate: {success_rate:.1%} ({int(success)}/{int(tasks_total)})."
            )

            if tasks_by_outcome:
                breakdown = ", ".join(
                    f"{k}: {int(v)}"
                    for k, v in sorted(
                        tasks_by_outcome.items(),
                        key=lambda kv: kv[1],
                        reverse=True,
                    )
                )
                lines.append(f"Outcome breakdown — {breakdown}.")

            if tasks_by_agent:
                top_agent = max(tasks_by_agent.items(), key=lambda kv: kv[1])
                lines.append(
                    f"Busiest agent: {top_agent[0]} ({top_agent[1]} tasks)."
                )

        if slowest:
            top = slowest[0]
            lines.append(
                f"Slowest stage: {top['stage']} "
                f"avg {top['avg_ms']:.0f}ms over {top['count']} samples."
            )

        if anomalies:
            critical = sum(1 for a in anomalies if a.severity == "critical")
            warning = sum(1 for a in anomalies if a.severity == "warning")
            lines.append(
                f"Anomalies detected: {len(anomalies)} "
                f"({critical} critical, {warning} warning)."
            )
            for a in anomalies[:3]:
                lines.append(f"  - [{a.severity}] {a.subject}: {a.message}")
        else:
            lines.append("No anomalies detected.")

        return " ".join(lines)


# ── Singleton accessor ────────────────────────────────────────
_global_generator: BehaviorDigestGenerator | None = None


def get_digest_generator() -> BehaviorDigestGenerator:
    """Return the process-global digest generator singleton."""
    global _global_generator
    if _global_generator is None:
        _global_generator = BehaviorDigestGenerator()
    return _global_generator
