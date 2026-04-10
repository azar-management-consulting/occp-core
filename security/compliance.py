"""Compliance Framework — Phase E: Compliance + Audit Hardening.

Modular compliance tracking for regulatory frameworks: EU AI Act, SOC2,
ISO 27001, GDPR, HIPAA, and custom frameworks.

Usage::

    engine = ComplianceEngine()
    control = ComplianceControl(
        control_id="EU-AI-01",
        framework=ComplianceFramework.EU_AI_ACT,
        title="Risk Classification",
        description="AI systems must be classified by risk level.",
    )
    engine.register_control(control)
    updated = engine.update_control(
        "EU-AI-01",
        ComplianceStatus.COMPLIANT,
        evidence=["docs/risk-classification.md"],
        assessed_by="security-team",
    )
    report = engine.generate_report(ComplianceFramework.EU_AI_ACT, "audit-bot")
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ComplianceFramework(str, Enum):
    """Supported regulatory compliance frameworks."""

    EU_AI_ACT = "eu_ai_act"
    SOC2 = "soc2"
    ISO27001 = "iso27001"
    GDPR = "gdpr"
    HIPAA = "hipaa"
    CUSTOM = "custom"


class ComplianceStatus(str, Enum):
    """Compliance assessment status for a control."""

    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    PARTIAL = "partial"
    NOT_ASSESSED = "not_assessed"
    EXEMPT = "exempt"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ComplianceError(Exception):
    """Base error for compliance operations."""


class ControlNotFoundError(ComplianceError):
    """Requested control ID does not exist."""

    def __init__(self, control_id: str) -> None:
        self.control_id = control_id
        super().__init__(f"Control not found: {control_id!r}")


class DuplicateControlError(ComplianceError):
    """Control with this ID already registered."""

    def __init__(self, control_id: str) -> None:
        self.control_id = control_id
        super().__init__(f"Control already registered: {control_id!r}")


# ---------------------------------------------------------------------------
# ComplianceControl
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ComplianceControl:
    """A single compliance control within a framework.

    Immutable — use ComplianceEngine.update_control() to produce updated copies.
    """

    control_id: str
    framework: ComplianceFramework
    title: str
    description: str = ""
    status: ComplianceStatus = ComplianceStatus.NOT_ASSESSED
    evidence: tuple[str, ...] = field(default_factory=tuple)
    assessed_at: float = 0.0
    assessed_by: str = ""
    notes: str = ""

    def __post_init__(self) -> None:
        # Normalise evidence: accept list input, store as tuple for hashability
        if isinstance(self.evidence, list):
            object.__setattr__(self, "evidence", tuple(self.evidence))

    def to_dict(self) -> dict[str, Any]:
        return {
            "controlId": self.control_id,
            "framework": self.framework.value,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "evidence": list(self.evidence),
            "assessedAt": self.assessed_at,
            "assessedBy": self.assessed_by,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ComplianceControl:
        return cls(
            control_id=data["controlId"],
            framework=ComplianceFramework(data["framework"]),
            title=data["title"],
            description=data.get("description", ""),
            status=ComplianceStatus(data.get("status", ComplianceStatus.NOT_ASSESSED.value)),
            evidence=tuple(data.get("evidence", [])),
            assessed_at=data.get("assessedAt", 0.0),
            assessed_by=data.get("assessedBy", ""),
            notes=data.get("notes", ""),
        )


# ---------------------------------------------------------------------------
# ComplianceReport
# ---------------------------------------------------------------------------


@dataclass
class ComplianceReport:
    """Compliance assessment report for a single framework.

    overall_status and score are computed automatically from controls.
    """

    framework: ComplianceFramework
    controls: list[ComplianceControl]
    generated_by: str
    report_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    generated_at: float = field(default_factory=time.time)
    overall_status: ComplianceStatus = field(init=False)
    score: float = field(init=False)

    def __post_init__(self) -> None:
        self.overall_status, self.score = self._compute_status_and_score()

    def _compute_status_and_score(self) -> tuple[ComplianceStatus, float]:
        if not self.controls:
            return ComplianceStatus.NOT_ASSESSED, 0.0

        # Exclude exempt controls from scoring
        scoreable = [c for c in self.controls if c.status != ComplianceStatus.EXEMPT]
        if not scoreable:
            return ComplianceStatus.EXEMPT, 100.0

        compliant_count = sum(1 for c in scoreable if c.status == ComplianceStatus.COMPLIANT)
        score = (compliant_count / len(scoreable)) * 100.0

        non_compliant = any(c.status == ComplianceStatus.NON_COMPLIANT for c in scoreable)
        not_assessed = any(c.status == ComplianceStatus.NOT_ASSESSED for c in scoreable)
        partial = any(c.status == ComplianceStatus.PARTIAL for c in scoreable)

        if score == 100.0:
            overall = ComplianceStatus.COMPLIANT
        elif non_compliant:
            overall = ComplianceStatus.NON_COMPLIANT
        elif not_assessed:
            overall = ComplianceStatus.NOT_ASSESSED
        elif partial:
            overall = ComplianceStatus.PARTIAL
        else:
            overall = ComplianceStatus.COMPLIANT

        return overall, score

    def to_dict(self) -> dict[str, Any]:
        return {
            "reportId": self.report_id,
            "framework": self.framework.value,
            "generatedAt": self.generated_at,
            "generatedBy": self.generated_by,
            "overallStatus": self.overall_status.value,
            "score": self.score,
            "controlCount": len(self.controls),
            "controls": [c.to_dict() for c in self.controls],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ComplianceReport:
        controls = [ComplianceControl.from_dict(c) for c in data.get("controls", [])]
        report = cls(
            framework=ComplianceFramework(data["framework"]),
            controls=controls,
            generated_by=data.get("generatedBy", ""),
        )
        # Override auto-generated fields if present in data
        if "reportId" in data:
            report.report_id = data["reportId"]
        if "generatedAt" in data:
            report.generated_at = data["generatedAt"]
        return report


# ---------------------------------------------------------------------------
# ComplianceEngine
# ---------------------------------------------------------------------------


class ComplianceEngine:
    """Manages compliance controls across multiple frameworks.

    Args:
        audit_callback: Optional callable(event_type: str, data: dict) invoked
            on register and update operations for audit trail integration.
    """

    def __init__(self, audit_callback: Callable[[str, dict[str, Any]], None] | None = None) -> None:
        self._controls: dict[str, ComplianceControl] = {}
        self._audit_callback = audit_callback

    # -- Registration --------------------------------------------------------

    def register_control(self, control: ComplianceControl) -> None:
        """Register a compliance control.

        Raises:
            DuplicateControlError: If control_id already registered.
        """
        if control.control_id in self._controls:
            raise DuplicateControlError(control.control_id)

        self._controls[control.control_id] = control
        logger.debug("Registered control: %s [%s]", control.control_id, control.framework.value)

        if self._audit_callback:
            self._audit_callback("compliance.control.registered", {
                "control_id": control.control_id,
                "framework": control.framework.value,
                "title": control.title,
                "status": control.status.value,
            })

    def update_control(
        self,
        control_id: str,
        status: ComplianceStatus,
        evidence: list[str] | None = None,
        assessed_by: str = "",
        notes: str = "",
    ) -> ComplianceControl:
        """Update a control's compliance status.

        Returns updated (new) ComplianceControl instance.

        Raises:
            ControlNotFoundError: If control_id not registered.
        """
        existing = self._controls.get(control_id)
        if existing is None:
            raise ControlNotFoundError(control_id)

        new_evidence = tuple(evidence) if evidence is not None else existing.evidence

        updated = ComplianceControl(
            control_id=existing.control_id,
            framework=existing.framework,
            title=existing.title,
            description=existing.description,
            status=status,
            evidence=new_evidence,
            assessed_at=time.time(),
            assessed_by=assessed_by or existing.assessed_by,
            notes=notes or existing.notes,
        )

        self._controls[control_id] = updated
        logger.debug(
            "Updated control: %s status=%s assessed_by=%s",
            control_id, status.value, assessed_by,
        )

        if self._audit_callback:
            self._audit_callback("compliance.control.updated", {
                "control_id": control_id,
                "framework": existing.framework.value,
                "old_status": existing.status.value,
                "new_status": status.value,
                "assessed_by": assessed_by,
                "evidence_count": len(new_evidence),
            })

        return updated

    # -- Queries -------------------------------------------------------------

    def get_control(self, control_id: str) -> ComplianceControl | None:
        """Return control by ID, or None if not found."""
        return self._controls.get(control_id)

    def list_controls(
        self,
        framework: ComplianceFramework | None = None,
    ) -> list[ComplianceControl]:
        """List all controls, optionally filtered by framework."""
        controls = list(self._controls.values())
        if framework is not None:
            controls = [c for c in controls if c.framework == framework]
        return controls

    # -- Reporting -----------------------------------------------------------

    def generate_report(
        self,
        framework: ComplianceFramework,
        generated_by: str,
    ) -> ComplianceReport:
        """Generate a compliance report for a framework.

        Calculates overall_status and score from current control states.
        """
        controls = self.list_controls(framework)
        report = ComplianceReport(
            framework=framework,
            controls=controls,
            generated_by=generated_by,
        )
        logger.info(
            "Generated compliance report: framework=%s score=%.1f%% status=%s controls=%d",
            framework.value, report.score, report.overall_status.value, len(controls),
        )
        return report

    def get_gaps(self, framework: ComplianceFramework) -> list[ComplianceControl]:
        """Return controls that are NON_COMPLIANT or NOT_ASSESSED for a framework."""
        return [
            c for c in self.list_controls(framework)
            if c.status in (ComplianceStatus.NON_COMPLIANT, ComplianceStatus.NOT_ASSESSED)
        ]

    def get_stats(self) -> dict[str, Any]:
        """Return statistics across all controls."""
        controls = list(self._controls.values())

        by_framework: dict[str, int] = {}
        by_status: dict[str, int] = {}

        for c in controls:
            fw = c.framework.value
            by_framework[fw] = by_framework.get(fw, 0) + 1
            st = c.status.value
            by_status[st] = by_status.get(st, 0) + 1

        return {
            "total_controls": len(controls),
            "by_framework": by_framework,
            "by_status": by_status,
        }
