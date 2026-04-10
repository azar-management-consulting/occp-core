"""Tests for evaluation.proposal_generator (L6 completion)."""

from __future__ import annotations

import pathlib

import pytest
import yaml

from evaluation.proposal_generator import (
    ProposalCandidate,
    ProposalGenerator,
    get_proposal_generator,
)
from evaluation.self_modifier import SelfModifier
from observability.anomaly_detector import AnomalyDetector
from observability.metrics_collector import MetricsCollector


@pytest.fixture
def tmp_registry(tmp_path):
    registry = tmp_path / "issue_registry.yaml"
    registry.write_text(yaml.safe_dump({
        "version": 1,
        "schema": "occp.architecture.issue_registry.v1",
        "issues": [
            {
                "id": "TEST-001",
                "title": "Test critical security issue",
                "category": "security",
                "severity": "critical",
                "status": "open",
                "affected_paths": ["observability/metrics_collector.py"],
                "evidence": "test evidence",
                "suggested_fix": "test fix",
                "risk_of_fix": "low",
            },
            {
                "id": "TEST-002",
                "title": "Low severity debt",
                "category": "debt",
                "severity": "low",
                "status": "open",
                "affected_paths": ["evaluation/feature_flags.py"],
                "evidence": "evidence",
                "suggested_fix": "fix",
                "risk_of_fix": "low",
            },
            {
                "id": "TEST-003",
                "title": "Resolved issue",
                "category": "debt",
                "severity": "medium",
                "status": "resolved",
                "affected_paths": ["observability/metrics_collector.py"],
                "evidence": "e",
                "suggested_fix": "f",
                "risk_of_fix": "low",
            },
            {
                "id": "TEST-004",
                "title": "Issue touching immutable path",
                "category": "reliability",
                "severity": "high",
                "status": "open",
                "affected_paths": ["security/agent_allowlist.py"],
                "evidence": "e",
                "suggested_fix": "f",
                "risk_of_fix": "medium",
            },
        ],
        "ranking": {
            "severity_weight": {
                "critical": 10, "high": 5, "medium": 3, "low": 1, "info": 0
            },
            "risk_penalty": {"low": 0, "medium": -1, "high": -3},
            "category_boost": {
                "security": 2, "reliability": 2, "performance": 1,
                "maintainability": 0, "scalability": 0, "debt": 0,
            },
        },
    }))
    return registry


@pytest.fixture
def generator(tmp_registry):
    collector = MetricsCollector()
    detector = AnomalyDetector(collector=collector)
    modifier = SelfModifier()  # uses real boundaries.yaml
    return ProposalGenerator(
        registry_path=tmp_registry,
        detector=detector,
        modifier=modifier,
    )


class TestGeneration:

    def test_generate_skips_resolved_by_default(self, generator):
        candidates = generator.generate(include_anomalies=False)
        ids = {c.proposal_id for c in candidates}
        assert "TEST-003" not in ids  # resolved

    def test_generate_includes_resolved_when_requested(self, generator):
        candidates = generator.generate(
            include_anomalies=False, include_resolved=True
        )
        ids = {c.proposal_id for c in candidates}
        assert "TEST-003" in ids

    def test_candidates_are_sorted_by_score(self, generator):
        candidates = generator.generate(include_anomalies=False)
        scores = [c.score for c in candidates]
        assert scores == sorted(scores, reverse=True)

    def test_critical_security_ranks_highest(self, generator):
        candidates = generator.generate(include_anomalies=False)
        assert candidates[0].proposal_id == "TEST-001"
        # Expected score: sev(critical)=10 + cat(security)=2 + risk(low)=0 = 12
        assert candidates[0].score == 12.0

    def test_low_debt_ranks_lowest(self, generator):
        candidates = generator.generate(include_anomalies=False)
        # TEST-002: sev(low)=1 + cat(debt)=0 + risk(low)=0 = 1
        low_cand = next(c for c in candidates if c.proposal_id == "TEST-002")
        assert low_cand.score == 1.0


class TestGovernanceVerdict:

    def test_safe_path_allowed(self, generator):
        candidates = generator.generate(include_anomalies=False)
        cand = next(c for c in candidates if c.proposal_id == "TEST-001")
        # observability/metrics_collector.py is autonomous_safe
        assert cand.governance_verdict == "allowed"

    def test_immutable_path_blocked(self, generator):
        candidates = generator.generate(include_anomalies=False)
        cand = next(c for c in candidates if c.proposal_id == "TEST-004")
        assert cand.governance_verdict == "immutable"
        assert "security/agent_allowlist.py" in cand.governance_blockers


class TestAnomaliesAsProposals:

    def test_anomalies_become_candidates(self, generator):
        collector = generator._get_detector()._get_collector()  # type: ignore[attr-defined]
        collector.counter(
            "occp.pipeline.tasks", 5,
            {"agent_type": "general", "outcome": "gate_rejected"}
        )
        candidates = generator.generate(include_anomalies=True)
        anomaly_cands = [c for c in candidates if c.source_type == "anomaly"]
        assert len(anomaly_cands) >= 1


class TestRFCRendering:

    def test_render_rfc_markdown(self, generator):
        candidates = generator.generate(include_anomalies=False)
        c = candidates[0]
        md = generator.to_rfc_markdown(c)
        assert f"# RFC {c.proposal_id}" in md
        assert c.title in md
        assert "## 1. Summary" in md
        assert "## 6. Next action" in md

    def test_write_rfc_to_disk(self, generator, tmp_path):
        candidates = generator.generate(include_anomalies=False)
        c = candidates[0]
        path = generator.write_rfc_to_disk(c, output_dir=tmp_path)
        assert path.exists()
        content = path.read_text()
        assert c.title in content

    def test_immutable_next_action(self, generator):
        candidates = generator.generate(include_anomalies=False)
        c = next(x for x in candidates if x.governance_verdict == "immutable")
        next_action = generator._next_action(c)
        assert "BLOCKED" in next_action


class TestSingleton:

    def test_singleton(self):
        g1 = get_proposal_generator()
        g2 = get_proposal_generator()
        assert g1 is g2
