"""Tests for security.scan_pipeline — Automated Scan Pipeline (REQ-TSF-05).

Covers:
- ScanFinding: creation, to_dict/from_dict
- GateResult: creation, add_finding, status tracking, serialization
- ScanReport: creation, all_passed, failed_gates, total_findings
- ScanPipeline: run (all pass, some fail, fail_fast), validate_coverage
- Finding builders: make_secret_finding, make_vuln_finding, make_static_finding
- Acceptance: hardcoded API key rejected, vulnerable dep rejected
- Serialization: to_json/from_json round-trip
"""

from __future__ import annotations

import json
import pytest

from security.scan_pipeline import (
    GateResult,
    ScanFinding,
    ScanGate,
    ScanGateFailedError,
    ScanPipeline,
    ScanPipelineError,
    ScanReport,
    ScanSeverity,
    ScanStatus,
    make_secret_finding,
    make_static_finding,
    make_vuln_finding,
)


# ---------------------------------------------------------------------------
# ScanFinding
# ---------------------------------------------------------------------------

class TestScanFinding:
    def test_create(self) -> None:
        f = ScanFinding(
            gate="secret-scan", rule_id="api-key",
            severity="critical", message="API key found",
        )
        assert f.gate == "secret-scan"
        assert f.rule_id == "api-key"

    def test_to_dict_minimal(self) -> None:
        f = ScanFinding(
            gate="g", rule_id="r", severity="low", message="msg",
        )
        d = f.to_dict()
        assert d["gate"] == "g"
        assert "filePath" not in d
        assert "line" not in d

    def test_to_dict_full(self) -> None:
        f = ScanFinding(
            gate="g", rule_id="r", severity="high", message="msg",
            file_path="src/app.py", line=42, metadata={"cve": "CVE-2024-001"},
        )
        d = f.to_dict()
        assert d["filePath"] == "src/app.py"
        assert d["line"] == 42
        assert d["metadata"]["cve"] == "CVE-2024-001"

    def test_from_dict_roundtrip(self) -> None:
        f = ScanFinding(
            gate="g", rule_id="r", severity="medium", message="m",
            file_path="x.py", line=10,
        )
        restored = ScanFinding.from_dict(f.to_dict())
        assert restored.gate == "g"
        assert restored.file_path == "x.py"
        assert restored.line == 10


# ---------------------------------------------------------------------------
# GateResult
# ---------------------------------------------------------------------------

class TestGateResult:
    def test_create_default_passed(self) -> None:
        g = GateResult(gate="static-analysis")
        assert g.passed is True
        assert g.finding_count == 0

    def test_add_finding_changes_status(self) -> None:
        g = GateResult(gate="g")
        assert g.passed is True
        g.add_finding(ScanFinding(gate="g", rule_id="r", severity="high", message="m"))
        assert g.passed is False
        assert g.finding_count == 1

    def test_explicit_status(self) -> None:
        g = GateResult(gate="g", status=ScanStatus.SKIPPED.value)
        assert g.passed is False

    def test_to_dict_roundtrip(self) -> None:
        g = GateResult(gate="g", duration_ms=123.4, metadata={"tool": "semgrep"})
        g.add_finding(ScanFinding(gate="g", rule_id="r", severity="low", message="m"))
        d = g.to_dict()
        assert d["findingCount"] == 1
        restored = GateResult.from_dict(d)
        assert restored.gate == "g"
        assert restored.finding_count == 1
        assert restored.duration_ms == 123.4


# ---------------------------------------------------------------------------
# ScanReport
# ---------------------------------------------------------------------------

class TestScanReport:
    def _make_passed_gate(self, gate: str) -> GateResult:
        return GateResult(gate=gate)

    def _make_failed_gate(self, gate: str) -> GateResult:
        g = GateResult(gate=gate)
        g.add_finding(ScanFinding(gate=gate, rule_id="r", severity="high", message="m"))
        return g

    def test_create(self) -> None:
        r = ScanReport(skill_id="s1", skill_version="1.0.0")
        assert r.skill_id == "s1"
        assert r.started_at > 0

    def test_all_passed(self) -> None:
        r = ScanReport(skill_id="s", skill_version="1.0")
        for gate in ScanPipeline.REQUIRED_GATES:
            r.add_gate_result(self._make_passed_gate(gate))
        assert r.all_passed is True
        assert r.failed_gates == []
        assert r.total_findings == 0

    def test_some_failed(self) -> None:
        r = ScanReport(skill_id="s", skill_version="1.0")
        r.add_gate_result(self._make_passed_gate("static-analysis"))
        r.add_gate_result(self._make_failed_gate("secret-scan"))
        assert r.all_passed is False
        assert "secret-scan" in r.failed_gates
        assert r.total_findings == 1

    def test_gate_count(self) -> None:
        r = ScanReport(skill_id="s", skill_version="1.0")
        r.add_gate_result(GateResult(gate="a"))
        r.add_gate_result(GateResult(gate="b"))
        assert r.gate_count == 2

    def test_complete(self) -> None:
        r = ScanReport(skill_id="s", skill_version="1.0")
        assert r.completed_at == 0.0
        r.complete()
        assert r.completed_at > 0

    def test_to_dict(self) -> None:
        r = ScanReport(skill_id="s", skill_version="1.0")
        r.add_gate_result(self._make_passed_gate("g1"))
        d = r.to_dict()
        assert d["skillId"] == "s"
        assert d["allPassed"] is True
        assert len(d["gates"]) == 1

    def test_to_json_roundtrip(self) -> None:
        r = ScanReport(skill_id="s", skill_version="1.0", started_at=1000.0)
        r.add_gate_result(self._make_passed_gate("g1"))
        r.add_gate_result(self._make_failed_gate("g2"))
        r.complete()
        j = r.to_json()
        restored = ScanReport.from_json(j)
        assert restored.skill_id == "s"
        assert restored.gate_count == 2
        assert restored.all_passed is False


# ---------------------------------------------------------------------------
# ScanPipeline
# ---------------------------------------------------------------------------

class TestScanPipeline:
    def test_run_all_pass(self) -> None:
        pipeline = ScanPipeline()
        gates = [GateResult(gate=g) for g in ScanPipeline.REQUIRED_GATES]
        report = pipeline.run("s1", "1.0.0", gate_results=gates)
        assert report.all_passed is True
        assert report.completed_at > 0

    def test_run_some_fail(self) -> None:
        pipeline = ScanPipeline()
        gates = [GateResult(gate=ScanGate.STATIC_ANALYSIS.value)]
        failed = GateResult(gate=ScanGate.SECRET_SCAN.value)
        failed.add_finding(make_secret_finding("api-key", "Hardcoded API key"))
        gates.append(failed)
        report = pipeline.run("s1", "1.0.0", gate_results=gates)
        assert report.all_passed is False
        assert ScanGate.SECRET_SCAN.value in report.failed_gates

    def test_run_fail_fast(self) -> None:
        pipeline = ScanPipeline(fail_fast=True)
        failed = GateResult(gate=ScanGate.SECRET_SCAN.value)
        failed.add_finding(make_secret_finding("key", "leak"))
        with pytest.raises(ScanGateFailedError) as exc_info:
            pipeline.run("s1", "1.0.0", gate_results=[failed])
        assert ScanGate.SECRET_SCAN.value in exc_info.value.failed_gates

    def test_run_empty_gates(self) -> None:
        pipeline = ScanPipeline()
        report = pipeline.run("s1", "1.0.0", gate_results=[])
        assert report.all_passed is True
        assert report.gate_count == 0

    def test_validate_coverage_all_present(self) -> None:
        pipeline = ScanPipeline()
        report = ScanReport(skill_id="s", skill_version="1.0")
        for gate in ScanPipeline.REQUIRED_GATES:
            report.add_gate_result(GateResult(gate=gate))
        missing = pipeline.validate_coverage(report)
        assert missing == []

    def test_validate_coverage_missing(self) -> None:
        pipeline = ScanPipeline()
        report = ScanReport(skill_id="s", skill_version="1.0")
        report.add_gate_result(GateResult(gate=ScanGate.STATIC_ANALYSIS.value))
        missing = pipeline.validate_coverage(report)
        assert len(missing) == 3
        assert ScanGate.DEPENDENCY_AUDIT.value in missing
        assert ScanGate.SECRET_SCAN.value in missing
        assert ScanGate.CAPABILITY_VALIDATION.value in missing


# ---------------------------------------------------------------------------
# Acceptance tests (REQ-TSF-05)
# ---------------------------------------------------------------------------

class TestAcceptanceTests:
    def test_hardcoded_api_key_rejected(self) -> None:
        """AT-1: Skill with hardcoded API key is rejected."""
        pipeline = ScanPipeline()

        secret_gate = GateResult(gate=ScanGate.SECRET_SCAN.value)
        secret_gate.add_finding(make_secret_finding(
            rule_id="generic-api-key",
            message="Hardcoded API key: sk-abc123...",
            file_path="skill/config.py",
            line=15,
        ))

        gates = [
            GateResult(gate=ScanGate.STATIC_ANALYSIS.value),
            GateResult(gate=ScanGate.DEPENDENCY_AUDIT.value),
            secret_gate,
            GateResult(gate=ScanGate.CAPABILITY_VALIDATION.value),
        ]

        report = pipeline.run("insecure-skill", "1.0.0", gate_results=gates)
        assert report.all_passed is False
        assert report.total_findings == 1
        assert report.gates[2].findings[0].rule_id == "generic-api-key"

    def test_vulnerable_dependency_rejected(self) -> None:
        """AT-2: Skill with known-vulnerable dependency is rejected."""
        pipeline = ScanPipeline()

        dep_gate = GateResult(gate=ScanGate.DEPENDENCY_AUDIT.value)
        dep_gate.add_finding(make_vuln_finding(
            rule_id="SNYK-PYTHON-REQUESTS-1234",
            message="requests@2.25.0 has known vulnerability",
            severity=ScanSeverity.HIGH.value,
            metadata={"cve": "CVE-2024-12345"},
        ))

        gates = [
            GateResult(gate=ScanGate.STATIC_ANALYSIS.value),
            dep_gate,
            GateResult(gate=ScanGate.SECRET_SCAN.value),
            GateResult(gate=ScanGate.CAPABILITY_VALIDATION.value),
        ]

        report = pipeline.run("vuln-skill", "1.0.0", gate_results=gates)
        assert report.all_passed is False
        assert ScanGate.DEPENDENCY_AUDIT.value in report.failed_gates

    def test_scan_results_in_metadata(self) -> None:
        """AT-3: Scan results attached to skill metadata."""
        pipeline = ScanPipeline()
        gates = [GateResult(gate=g) for g in ScanPipeline.REQUIRED_GATES]
        report = pipeline.run("clean-skill", "1.0.0", gate_results=gates)

        metadata = report.to_dict()
        assert "gates" in metadata
        assert metadata["allPassed"] is True
        assert metadata["totalFindings"] == 0


# ---------------------------------------------------------------------------
# Finding builders
# ---------------------------------------------------------------------------

class TestFindingBuilders:
    def test_make_secret_finding(self) -> None:
        f = make_secret_finding("api-key", "Key found", "app.py", 10)
        assert f.gate == ScanGate.SECRET_SCAN.value
        assert f.severity == ScanSeverity.CRITICAL.value

    def test_make_vuln_finding(self) -> None:
        f = make_vuln_finding("SNYK-001", "Vuln found", metadata={"cve": "CVE-1"})
        assert f.gate == ScanGate.DEPENDENCY_AUDIT.value
        assert f.severity == ScanSeverity.HIGH.value
        assert f.metadata["cve"] == "CVE-1"

    def test_make_static_finding(self) -> None:
        f = make_static_finding("sql-inject", "SQL injection", "db.py", 50)
        assert f.gate == ScanGate.STATIC_ANALYSIS.value
        assert f.severity == ScanSeverity.MEDIUM.value


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class TestEnums:
    def test_scan_gate_values(self) -> None:
        assert ScanGate.STATIC_ANALYSIS.value == "static-analysis"
        assert ScanGate.DEPENDENCY_AUDIT.value == "dependency-audit"
        assert ScanGate.SECRET_SCAN.value == "secret-scan"
        assert ScanGate.CAPABILITY_VALIDATION.value == "capability-validation"

    def test_scan_status_values(self) -> None:
        assert ScanStatus.PASSED.value == "passed"
        assert ScanStatus.FAILED.value == "failed"
        assert ScanStatus.SKIPPED.value == "skipped"
        assert ScanStatus.ERROR.value == "error"

    def test_scan_severity_values(self) -> None:
        assert ScanSeverity.CRITICAL.value == "critical"
        assert ScanSeverity.HIGH.value == "high"
        assert ScanSeverity.MEDIUM.value == "medium"
        assert ScanSeverity.LOW.value == "low"
        assert ScanSeverity.INFO.value == "info"
