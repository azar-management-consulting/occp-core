"""Automated Scan Pipeline — REQ-TSF-05.

Pre-publish pipeline: (1) Static analysis (Semgrep), (2) Dependency audit
(Snyk), (3) Secret scan (GitGuardian), (4) Capability declaration validation.
All 4 gates must pass for a skill to be published.

Acceptance Tests:
  (1) Skill with hardcoded API key rejected.
  (2) Skill with known-vulnerable dependency rejected.
  (3) Scan results attached to skill metadata.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ScanGate(str, Enum):
    """Scan pipeline gates."""
    STATIC_ANALYSIS = "static-analysis"
    DEPENDENCY_AUDIT = "dependency-audit"
    SECRET_SCAN = "secret-scan"
    CAPABILITY_VALIDATION = "capability-validation"


class ScanStatus(str, Enum):
    """Gate result status."""
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


class ScanSeverity(str, Enum):
    """Finding severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class ScanPipelineError(Exception):
    """Base error for scan pipeline operations."""


class ScanGateFailedError(ScanPipelineError):
    """One or more scan gates failed."""

    def __init__(self, failed_gates: list[str]) -> None:
        self.failed_gates = failed_gates
        super().__init__(f"Scan gates failed: {', '.join(failed_gates)}")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ScanFinding:
    """A single finding from a scan gate."""

    gate: str
    rule_id: str
    severity: str
    message: str
    file_path: str = ""
    line: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "gate": self.gate,
            "ruleId": self.rule_id,
            "severity": self.severity,
            "message": self.message,
        }
        if self.file_path:
            d["filePath"] = self.file_path
        if self.line:
            d["line"] = self.line
        if self.metadata:
            d["metadata"] = self.metadata
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ScanFinding:
        return cls(
            gate=data["gate"],
            rule_id=data["ruleId"],
            severity=data["severity"],
            message=data["message"],
            file_path=data.get("filePath", ""),
            line=data.get("line", 0),
            metadata=data.get("metadata", {}),
        )


@dataclass
class GateResult:
    """Result from a single scan gate."""

    gate: str
    status: str = ScanStatus.PASSED.value
    findings: list[ScanFinding] = field(default_factory=list)
    duration_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.status == ScanStatus.PASSED.value

    @property
    def finding_count(self) -> int:
        return len(self.findings)

    def add_finding(self, finding: ScanFinding) -> None:
        self.findings.append(finding)
        if self.status == ScanStatus.PASSED.value:
            self.status = ScanStatus.FAILED.value

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate": self.gate,
            "status": self.status,
            "findingCount": self.finding_count,
            "findings": [f.to_dict() for f in self.findings],
            "durationMs": self.duration_ms,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GateResult:
        result = cls(
            gate=data["gate"],
            status=data.get("status", ScanStatus.PASSED.value),
            duration_ms=data.get("durationMs", 0.0),
            metadata=data.get("metadata", {}),
        )
        for fd in data.get("findings", []):
            result.findings.append(ScanFinding.from_dict(fd))
        return result


# ---------------------------------------------------------------------------
# ScanReport
# ---------------------------------------------------------------------------

@dataclass
class ScanReport:
    """Complete scan pipeline report."""

    skill_id: str
    skill_version: str
    gates: list[GateResult] = field(default_factory=list)
    started_at: float = 0.0
    completed_at: float = 0.0

    def __post_init__(self) -> None:
        if not self.started_at:
            self.started_at = time.time()

    @property
    def all_passed(self) -> bool:
        return all(g.passed for g in self.gates)

    @property
    def failed_gates(self) -> list[str]:
        return [g.gate for g in self.gates if not g.passed]

    @property
    def total_findings(self) -> int:
        return sum(g.finding_count for g in self.gates)

    @property
    def gate_count(self) -> int:
        return len(self.gates)

    def add_gate_result(self, result: GateResult) -> None:
        self.gates.append(result)

    def complete(self) -> None:
        self.completed_at = time.time()

    def to_dict(self) -> dict[str, Any]:
        return {
            "skillId": self.skill_id,
            "skillVersion": self.skill_version,
            "allPassed": self.all_passed,
            "totalFindings": self.total_findings,
            "startedAt": self.started_at,
            "completedAt": self.completed_at,
            "gates": [g.to_dict() for g in self.gates],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, indent=2)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ScanReport:
        report = cls(
            skill_id=data["skillId"],
            skill_version=data["skillVersion"],
            started_at=data.get("startedAt", 0.0),
            completed_at=data.get("completedAt", 0.0),
        )
        for gd in data.get("gates", []):
            report.gates.append(GateResult.from_dict(gd))
        return report

    @classmethod
    def from_json(cls, raw: str) -> ScanReport:
        return cls.from_dict(json.loads(raw))


# ---------------------------------------------------------------------------
# ScanPipeline — orchestrator
# ---------------------------------------------------------------------------

class ScanPipeline:
    """Orchestrates the 4-gate scan pipeline.

    Each gate is a callable that receives scan context and returns GateResult.
    All 4 gates must pass for the pipeline to succeed.
    """

    REQUIRED_GATES = [
        ScanGate.STATIC_ANALYSIS.value,
        ScanGate.DEPENDENCY_AUDIT.value,
        ScanGate.SECRET_SCAN.value,
        ScanGate.CAPABILITY_VALIDATION.value,
    ]

    def __init__(self, *, fail_fast: bool = False) -> None:
        self._fail_fast = fail_fast

    def run(
        self,
        skill_id: str,
        skill_version: str,
        gate_results: list[GateResult] | None = None,
    ) -> ScanReport:
        """Run the scan pipeline with provided gate results.

        In production, gate results come from actual scanners.
        For testing, gate results can be injected.

        Args:
            skill_id: Skill identifier.
            skill_version: Version being scanned.
            gate_results: Pre-computed gate results (for testing/integration).

        Returns:
            ScanReport with all gate results.

        Raises:
            ScanGateFailedError: If any gate failed and fail_fast is True.
        """
        report = ScanReport(skill_id=skill_id, skill_version=skill_version)

        for result in (gate_results or []):
            report.add_gate_result(result)

            if self._fail_fast and not result.passed:
                report.complete()
                raise ScanGateFailedError(report.failed_gates)

        report.complete()

        if not report.all_passed:
            logger.warning(
                "Scan pipeline FAILED for %s@%s: gates=%s findings=%d",
                skill_id, skill_version,
                report.failed_gates, report.total_findings,
            )
        else:
            logger.info(
                "Scan pipeline PASSED for %s@%s: %d gates, 0 findings",
                skill_id, skill_version, report.gate_count,
            )

        return report

    def validate_coverage(self, report: ScanReport) -> list[str]:
        """Check that all required gates were executed.

        Returns list of missing gates.
        """
        executed = {g.gate for g in report.gates}
        missing = [g for g in self.REQUIRED_GATES if g not in executed]
        return missing


# ---------------------------------------------------------------------------
# Utility: finding builders
# ---------------------------------------------------------------------------

def make_secret_finding(
    rule_id: str,
    message: str,
    file_path: str = "",
    line: int = 0,
    severity: str = ScanSeverity.CRITICAL.value,
) -> ScanFinding:
    """Create a secret scan finding."""
    return ScanFinding(
        gate=ScanGate.SECRET_SCAN.value,
        rule_id=rule_id,
        severity=severity,
        message=message,
        file_path=file_path,
        line=line,
    )


def make_vuln_finding(
    rule_id: str,
    message: str,
    severity: str = ScanSeverity.HIGH.value,
    metadata: dict[str, Any] | None = None,
) -> ScanFinding:
    """Create a dependency vulnerability finding."""
    return ScanFinding(
        gate=ScanGate.DEPENDENCY_AUDIT.value,
        rule_id=rule_id,
        severity=severity,
        message=message,
        metadata=metadata or {},
    )


def make_static_finding(
    rule_id: str,
    message: str,
    file_path: str = "",
    line: int = 0,
    severity: str = ScanSeverity.MEDIUM.value,
) -> ScanFinding:
    """Create a static analysis finding."""
    return ScanFinding(
        gate=ScanGate.STATIC_ANALYSIS.value,
        rule_id=rule_id,
        severity=severity,
        message=message,
        file_path=file_path,
        line=line,
    )
