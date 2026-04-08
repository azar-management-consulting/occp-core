"""Tests for observability.behavior_digest (L6 completion)."""

from __future__ import annotations

import pytest

from observability import MetricsCollector
from observability.anomaly_detector import AnomalyDetector, AnomalyThresholds
from observability.behavior_digest import (
    BehaviorDigest,
    BehaviorDigestGenerator,
)


@pytest.fixture
def collector():
    return MetricsCollector()


@pytest.fixture
def detector(collector):
    return AnomalyDetector(collector=collector)


@pytest.fixture
def generator(collector, detector):
    return BehaviorDigestGenerator(collector=collector, detector=detector)


class TestEmptyDigest:

    def test_empty_digest_produces_narrative(self, generator):
        digest = generator.generate()
        assert isinstance(digest, BehaviorDigest)
        assert digest.tasks_total == 0
        assert "No pipeline activity" in digest.narrative
        assert digest.anomalies == []


class TestPopulatedDigest:

    def test_successful_runs_narrative(self, collector, generator):
        collector.counter(
            "occp.pipeline.tasks", 8,
            {"agent_type": "eng-core", "outcome": "success"}
        )
        collector.counter(
            "occp.pipeline.tasks", 2,
            {"agent_type": "eng-core", "outcome": "failed"}
        )
        for _ in range(10):
            collector.histogram(
                "occp.pipeline.stage_duration_ms", 250.0,
                {"stage": "plan", "agent_type": "eng-core"}
            )

        digest = generator.generate()
        assert digest.tasks_total == 10
        assert digest.tasks_by_outcome["success"] == 8
        assert digest.tasks_by_outcome["failed"] == 2
        assert digest.tasks_by_agent["eng-core"] == 10
        assert "80.0%" in digest.narrative  # success rate
        assert "Busiest agent" in digest.narrative

    def test_slowest_stages_sorted(self, collector, generator):
        for _ in range(5):
            collector.histogram(
                "occp.pipeline.stage_duration_ms", 100.0,
                {"stage": "gate", "agent_type": "a"}
            )
        for _ in range(5):
            collector.histogram(
                "occp.pipeline.stage_duration_ms", 5000.0,
                {"stage": "execute", "agent_type": "a"}
            )
        digest = generator.generate()
        assert digest.slowest_stages[0]["stage"] == "execute"
        assert digest.slowest_stages[0]["avg_ms"] >= digest.slowest_stages[1]["avg_ms"]

    def test_digest_mentions_anomalies(self, collector, generator):
        # Force a denial spike anomaly
        collector.counter(
            "occp.pipeline.tasks", 5,
            {"agent_type": "general", "outcome": "success"}
        )
        collector.counter(
            "occp.pipeline.tasks", 5,
            {"agent_type": "general", "outcome": "gate_rejected"}
        )
        digest = generator.generate()
        assert any(a.code == "policy.denial_spike" for a in digest.anomalies)
        assert "Anomalies detected" in digest.narrative

    def test_to_dict_structure(self, collector, generator):
        collector.counter(
            "occp.pipeline.tasks", 3,
            {"agent_type": "brain", "outcome": "success"}
        )
        digest = generator.generate()
        d = digest.to_dict()
        assert "narrative" in d
        assert "tasks_total" in d
        assert "tasks_by_outcome" in d
        assert "slowest_stages" in d
        assert "anomalies" in d
        assert "generated_at" in d
