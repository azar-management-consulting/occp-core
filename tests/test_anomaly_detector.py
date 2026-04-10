"""Tests for observability.anomaly_detector (L6 completion)."""

from __future__ import annotations

import pytest

from observability import MetricsCollector
from observability.anomaly_detector import (
    Anomaly,
    AnomalyDetector,
    AnomalyThresholds,
)


@pytest.fixture
def collector():
    return MetricsCollector()


@pytest.fixture
def detector(collector):
    return AnomalyDetector(collector=collector)


class TestNoData:

    def test_no_data_produces_no_anomalies(self, detector):
        assert detector.detect() == []

    def test_below_min_samples_returns_no_anomalies(self, collector, detector):
        for _ in range(3):  # min_samples defaults to 5
            collector.counter(
                "occp.pipeline.tasks", 1,
                {"agent_type": "general", "outcome": "failed"}
            )
        assert detector.detect() == []


class TestOutcomeImbalance:

    def test_detects_low_success_rate(self, collector, detector):
        # 5 total, 1 success, 4 failures → 80% non-success
        collector.counter(
            "occp.pipeline.tasks", 1,
            {"agent_type": "general", "outcome": "success"}
        )
        collector.counter(
            "occp.pipeline.tasks", 4,
            {"agent_type": "general", "outcome": "failed"}
        )
        anomalies = detector.detect()
        codes = {a.code for a in anomalies}
        assert "pipeline.outcome_imbalance" in codes

    def test_all_success_produces_no_imbalance_anomaly(self, collector, detector):
        collector.counter(
            "occp.pipeline.tasks", 10,
            {"agent_type": "general", "outcome": "success"}
        )
        anomalies = [a for a in detector.detect() if a.code == "pipeline.outcome_imbalance"]
        assert anomalies == []


class TestSlowStage:

    def test_detects_slow_stage_over_absolute_threshold(self, collector, detector):
        # 5 observations, average 15_000 ms > 10_000 threshold
        for _ in range(5):
            collector.histogram(
                "occp.pipeline.stage_duration_ms", 15_000.0,
                {"stage": "execute", "agent_type": "general"}
            )
        anomalies = detector.detect()
        slow = [a for a in anomalies if a.code == "pipeline.slow_stage"]
        assert len(slow) == 1
        assert slow[0].subject == "stage.execute"

    def test_fast_stage_not_flagged(self, collector, detector):
        for _ in range(5):
            collector.histogram(
                "occp.pipeline.stage_duration_ms", 50.0,
                {"stage": "gate", "agent_type": "general"}
            )
        anomalies = [a for a in detector.detect() if a.code == "pipeline.slow_stage"]
        assert anomalies == []


class TestAgentReliability:

    def test_detects_unreliable_agent(self, collector, detector):
        # infra-ops: 5 runs, 2 success, 3 failures → 40% success
        collector.counter(
            "occp.pipeline.tasks", 2,
            {"agent_type": "infra-ops", "outcome": "success"}
        )
        collector.counter(
            "occp.pipeline.tasks", 3,
            {"agent_type": "infra-ops", "outcome": "failed"}
        )
        anomalies = detector.detect()
        reliability = [a for a in anomalies if a.code == "agent.reliability_drop"]
        assert len(reliability) == 1
        assert reliability[0].subject == "agent.infra-ops"

    def test_reliable_agent_not_flagged(self, collector, detector):
        collector.counter(
            "occp.pipeline.tasks", 10,
            {"agent_type": "eng-core", "outcome": "success"}
        )
        anomalies = [a for a in detector.detect() if a.code == "agent.reliability_drop"]
        assert anomalies == []


class TestDenialSpikes:

    def test_detects_denial_spike(self, collector, detector):
        # 10 total, 3 gate_rejected → 30% denial rate > 20% threshold
        collector.counter(
            "occp.pipeline.tasks", 7,
            {"agent_type": "general", "outcome": "success"}
        )
        collector.counter(
            "occp.pipeline.tasks", 3,
            {"agent_type": "general", "outcome": "gate_rejected"}
        )
        anomalies = detector.detect()
        denial = [a for a in anomalies if a.code == "policy.denial_spike"]
        assert len(denial) == 1

    def test_low_denial_not_flagged(self, collector, detector):
        collector.counter(
            "occp.pipeline.tasks", 10,
            {"agent_type": "general", "outcome": "success"}
        )
        anomalies = [a for a in detector.detect() if a.code == "policy.denial_spike"]
        assert anomalies == []


class TestConfig:

    def test_custom_thresholds(self, collector):
        # Make min_samples=1 so 1 observation triggers detection
        thresholds = AnomalyThresholds(
            min_samples=1,
            max_non_success_fraction=0.1,
        )
        detector = AnomalyDetector(collector=collector, thresholds=thresholds)
        collector.counter(
            "occp.pipeline.tasks", 1,
            {"agent_type": "general", "outcome": "failed"}
        )
        anomalies = detector.detect()
        assert len(anomalies) >= 1

    def test_anomaly_to_dict(self):
        a = Anomaly(
            code="test.code",
            severity="warning",
            subject="test",
            message="hi",
            evidence={"x": 1},
        )
        d = a.to_dict()
        assert d["code"] == "test.code"
        assert d["evidence"] == {"x": 1}
        assert "detected_at" in d
