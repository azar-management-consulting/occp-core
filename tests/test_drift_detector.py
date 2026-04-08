"""Tests for evaluation.drift_detector (L6 maximum state)."""

from __future__ import annotations

import pathlib

import pytest
import yaml

from evaluation.drift_detector import (
    DriftDetector,
    DriftEntry,
    DriftReport,
    get_drift_detector,
)


@pytest.fixture
def detector():
    """Use real repo architecture memory."""
    return DriftDetector()


class TestRealRepoDriftDetection:
    """These tests run against the actual repo to catch real drift."""

    def test_no_agent_drift_in_real_repo(self, detector):
        """agents.yaml must match security/agent_allowlist.py."""
        entries = detector.check_agent_drift()
        assert entries == [], f"agent drift found: {[e.to_dict() for e in entries]}"

    def test_no_host_orphans_in_real_repo(self, detector):
        entries = detector.check_service_hosts()
        assert entries == [], f"host orphans: {[e.to_dict() for e in entries]}"

    def test_full_detect_produces_report(self, detector):
        report = detector.detect()
        assert isinstance(report, DriftReport)
        assert len(report.checks_performed) >= 3

    def test_report_to_dict(self, detector):
        report = detector.detect()
        d = report.to_dict()
        assert "generated_at" in d
        assert "has_drift" in d
        assert "entries" in d
        assert "by_kind" in d


class TestSyntheticDrift:
    """Use tmp paths to simulate drift scenarios."""

    @pytest.fixture
    def tmp_arch(self, tmp_path):
        arch = tmp_path / "architecture"
        arch.mkdir()
        return arch

    def test_agent_drift_detected(self, tmp_arch, tmp_path):
        # agents.yaml declares an agent that doesn't exist in code
        (tmp_arch / "agents.yaml").write_text(yaml.safe_dump({
            "version": 1,
            "schema": "occp.architecture.agents.v1",
            "specialists": [
                {"id": "ghost-agent-not-in-code"},
            ],
            "orchestrators": [],
            "seeded_pipeline_agents": [],
        }))
        (tmp_arch / "services.yaml").write_text(yaml.safe_dump({
            "version": 1, "schema": "x", "services": [], "hosts": []
        }))
        (tmp_arch / "tools.yaml").write_text(yaml.safe_dump({
            "version": 1, "schema": "x", "tools": []
        }))
        (tmp_arch / "issue_registry.yaml").write_text(yaml.safe_dump({
            "version": 1, "schema": "x", "issues": []
        }))

        detector = DriftDetector(arch_dir=tmp_arch, repo_root=tmp_path)
        entries = detector.check_agent_drift()
        kinds = {e.kind for e in entries}
        assert "agent_missing_in_code" in kinds

    def test_host_orphan_detected(self, tmp_arch, tmp_path):
        (tmp_arch / "services.yaml").write_text(yaml.safe_dump({
            "version": 1, "schema": "x",
            "services": [
                {"id": "svc-a", "host": "nonexistent-host"},
            ],
            "hosts": [
                {"id": "real-host"},
            ],
        }))
        detector = DriftDetector(arch_dir=tmp_arch, repo_root=tmp_path)
        entries = detector.check_service_hosts()
        assert len(entries) == 1
        assert entries[0].kind == "host_orphan"
        assert entries[0].subject == "svc-a"

    def test_issue_path_missing_detected(self, tmp_arch, tmp_path):
        (tmp_arch / "issue_registry.yaml").write_text(yaml.safe_dump({
            "version": 1, "schema": "x",
            "issues": [
                {
                    "id": "TEST-001",
                    "title": "ghost",
                    "affected_paths": ["nonexistent/ghost_file.py"],
                }
            ],
        }))
        detector = DriftDetector(arch_dir=tmp_arch, repo_root=tmp_path)
        entries = detector.check_issue_paths()
        assert len(entries) == 1
        assert entries[0].kind == "issue_path_missing"


class TestSingleton:

    def test_singleton(self):
        d1 = get_drift_detector()
        d2 = get_drift_detector()
        assert d1 is d2
