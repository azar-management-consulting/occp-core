"""Tests for evaluation.canary_engine (L6 completion)."""

from __future__ import annotations

import pytest

from evaluation.canary_engine import (
    CanaryCriteria,
    CanaryEngine,
    CanaryVerdict,
    get_canary_engine,
)
from observability.metrics_collector import MetricsCollector


def _populate_metrics(
    collector: MetricsCollector,
    *,
    success: int,
    failed: int = 0,
    gate_rejected: int = 0,
    avg_latency_ms: float = 100.0,
    stage: str = "execute",
) -> None:
    if success:
        collector.counter(
            "occp.pipeline.tasks", success,
            {"agent_type": "general", "outcome": "success"}
        )
    if failed:
        collector.counter(
            "occp.pipeline.tasks", failed,
            {"agent_type": "general", "outcome": "failed"}
        )
    if gate_rejected:
        collector.counter(
            "occp.pipeline.tasks", gate_rejected,
            {"agent_type": "general", "outcome": "gate_rejected"}
        )
    for _ in range(success + failed + gate_rejected):
        collector.histogram(
            "occp.pipeline.stage_duration_ms", avg_latency_ms,
            {"stage": stage, "agent_type": "general"}
        )


@pytest.fixture
def engine():
    return CanaryEngine()


class TestHoldOnInsufficientSamples:

    def test_hold_when_candidate_too_small(self, engine):
        baseline = MetricsCollector()
        candidate = MetricsCollector()
        _populate_metrics(baseline, success=20)
        _populate_metrics(candidate, success=2)  # below min_candidate_samples=5

        verdict = engine.compare(baseline.snapshot(), candidate.snapshot())
        assert verdict.decision == "hold"
        assert "samples" in verdict.reason


class TestPromote:

    def test_promote_when_everything_stable(self, engine):
        baseline = MetricsCollector()
        candidate = MetricsCollector()
        _populate_metrics(baseline, success=20)
        _populate_metrics(candidate, success=20)

        verdict = engine.compare(baseline.snapshot(), candidate.snapshot())
        assert verdict.decision == "promote"
        assert verdict.regressions == []

    def test_promote_with_improvement(self, engine):
        baseline = MetricsCollector()
        candidate = MetricsCollector()
        _populate_metrics(baseline, success=15, failed=5, avg_latency_ms=200.0)
        _populate_metrics(candidate, success=20, avg_latency_ms=100.0)

        verdict = engine.compare(baseline.snapshot(), candidate.snapshot())
        assert verdict.decision == "promote"
        assert len(verdict.improvements) >= 1


class TestRollback:

    def test_rollback_on_success_rate_drop(self, engine):
        baseline = MetricsCollector()
        candidate = MetricsCollector()
        _populate_metrics(baseline, success=20)
        _populate_metrics(candidate, success=10, failed=10)  # 50% drop

        verdict = engine.compare(baseline.snapshot(), candidate.snapshot())
        assert verdict.decision == "rollback"
        assert any("success rate dropped" in r for r in verdict.regressions)

    def test_rollback_on_latency_growth(self, engine):
        baseline = MetricsCollector()
        candidate = MetricsCollector()
        _populate_metrics(baseline, success=20, avg_latency_ms=100.0)
        _populate_metrics(candidate, success=20, avg_latency_ms=500.0)  # 5x

        verdict = engine.compare(baseline.snapshot(), candidate.snapshot())
        assert verdict.decision == "rollback"
        assert any("latency grew" in r for r in verdict.regressions)


class TestHoldOnSoftRegression:

    def test_rollback_when_denial_and_success_both_move(self, engine):
        # Realistic case: gate_rejected also counts as non-success.
        # This drops success rate AND increases denial → severe → rollback.
        baseline = MetricsCollector()
        candidate = MetricsCollector()
        _populate_metrics(baseline, success=20, gate_rejected=0)
        _populate_metrics(candidate, success=14, gate_rejected=6)  # 30% denial

        verdict = engine.compare(baseline.snapshot(), candidate.snapshot())
        # Because success_rate drops (20/20=1.0 → 14/20=0.70, drop=0.30 > 0.05)
        # the severe classifier triggers rollback, not hold.
        assert verdict.decision == "rollback"
        assert any("success rate dropped" in r for r in verdict.regressions)


class TestCustomCriteria:

    def test_strict_criteria(self):
        criteria = CanaryCriteria(
            min_candidate_samples=1,
            max_success_rate_drop=0.01,  # extremely strict
            max_latency_growth_factor=1.1,
        )
        engine = CanaryEngine(criteria=criteria)
        baseline = MetricsCollector()
        candidate = MetricsCollector()
        _populate_metrics(baseline, success=100)
        _populate_metrics(candidate, success=99, failed=1)  # 1% drop

        verdict = engine.compare(baseline.snapshot(), candidate.snapshot())
        assert verdict.decision == "rollback"


class TestVerdictSerialization:

    def test_verdict_to_dict(self, engine):
        baseline = MetricsCollector()
        candidate = MetricsCollector()
        _populate_metrics(baseline, success=20)
        _populate_metrics(candidate, success=20)

        verdict = engine.compare(baseline.snapshot(), candidate.snapshot())
        d = verdict.to_dict()
        assert d["decision"] in {"promote", "hold", "rollback"}
        assert "decided_at" in d


class TestHistory:

    def test_verdicts_recorded(self, engine):
        baseline = MetricsCollector()
        candidate = MetricsCollector()
        _populate_metrics(baseline, success=20)
        _populate_metrics(candidate, success=20)
        engine.clear_history()
        engine.compare(baseline.snapshot(), candidate.snapshot())
        engine.compare(baseline.snapshot(), candidate.snapshot())
        recent = engine.recent_verdicts
        assert len(recent) == 2

    def test_stats_aggregate(self, engine):
        engine.clear_history()
        baseline = MetricsCollector()
        candidate_ok = MetricsCollector()
        candidate_bad = MetricsCollector()
        _populate_metrics(baseline, success=20)
        _populate_metrics(candidate_ok, success=20)
        _populate_metrics(candidate_bad, success=5, failed=15)

        engine.compare(baseline.snapshot(), candidate_ok.snapshot())
        engine.compare(baseline.snapshot(), candidate_bad.snapshot())
        stats = engine.stats
        assert stats["total_verdicts"] == 2
        assert stats["by_decision"].get("promote", 0) >= 1
        assert stats["by_decision"].get("rollback", 0) >= 1

    def test_history_ring_buffer_cap(self, engine):
        engine.clear_history()
        # Force the ring-buffer to hold max 200; we insert 210 noops
        engine._HISTORY_MAX = 5  # test override
        baseline = MetricsCollector()
        candidate = MetricsCollector()
        _populate_metrics(baseline, success=20)
        _populate_metrics(candidate, success=20)
        for _ in range(10):
            engine.compare(baseline.snapshot(), candidate.snapshot())
        assert len(engine.recent_verdicts) == 5


class TestSingleton:

    def test_singleton(self):
        e1 = get_canary_engine()
        e2 = get_canary_engine()
        assert e1 is e2
