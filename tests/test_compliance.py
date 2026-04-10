"""Tests for security.compliance — Compliance Framework (Phase E).

Covers:
- ComplianceFramework: enum values, string values
- ComplianceStatus: enum values, all 5 statuses
- ComplianceControl: creation, defaults, frozen, to_dict, from_dict
- ComplianceReport: creation, auto fields, score calculation, overall_status, to_dict
- ComplianceEngine: register, update, get, list, filter, generate_report, gaps, stats,
                    duplicate control error, control not found
- ComplianceAudit: callback on register, callback on update, no callback
- Acceptance: ACC-COMP-01..05
"""

from __future__ import annotations

import time
import pytest
from typing import Any

from security.compliance import (
    ComplianceControl,
    ComplianceEngine,
    ComplianceError,
    ComplianceFramework,
    ComplianceReport,
    ComplianceStatus,
    ControlNotFoundError,
    DuplicateControlError,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def engine() -> ComplianceEngine:
    return ComplianceEngine()


@pytest.fixture
def eu_control() -> ComplianceControl:
    return ComplianceControl(
        control_id="EU-AI-01",
        framework=ComplianceFramework.EU_AI_ACT,
        title="Risk Classification",
        description="AI systems must be classified by risk level.",
    )


@pytest.fixture
def soc2_control() -> ComplianceControl:
    return ComplianceControl(
        control_id="SOC2-CC-01",
        framework=ComplianceFramework.SOC2,
        title="Access Control",
        description="Logical access controls in place.",
    )


@pytest.fixture
def audit_log() -> list[dict[str, Any]]:
    return []


@pytest.fixture
def engine_with_callback(audit_log: list[dict[str, Any]]) -> ComplianceEngine:
    def cb(event_type: str, data: dict[str, Any]) -> None:
        audit_log.append({"event_type": event_type, **data})
    return ComplianceEngine(audit_callback=cb)


# ---------------------------------------------------------------------------
# TestComplianceFramework
# ---------------------------------------------------------------------------


class TestComplianceFramework:
    def test_values_exist(self) -> None:
        assert ComplianceFramework.EU_AI_ACT
        assert ComplianceFramework.SOC2
        assert ComplianceFramework.ISO27001
        assert ComplianceFramework.GDPR
        assert ComplianceFramework.HIPAA
        assert ComplianceFramework.CUSTOM

    def test_string_values(self) -> None:
        assert ComplianceFramework.EU_AI_ACT.value == "eu_ai_act"
        assert ComplianceFramework.SOC2.value == "soc2"
        assert ComplianceFramework.ISO27001.value == "iso27001"
        assert ComplianceFramework.GDPR.value == "gdpr"
        assert ComplianceFramework.HIPAA.value == "hipaa"
        assert ComplianceFramework.CUSTOM.value == "custom"

    def test_is_str_enum(self) -> None:
        # ComplianceFramework is str-Enum, usable as string directly
        assert ComplianceFramework.EU_AI_ACT == "eu_ai_act"


# ---------------------------------------------------------------------------
# TestComplianceStatus
# ---------------------------------------------------------------------------


class TestComplianceStatus:
    def test_all_five_statuses(self) -> None:
        statuses = {s.value for s in ComplianceStatus}
        assert statuses == {
            "compliant", "non_compliant", "partial", "not_assessed", "exempt"
        }

    def test_compliant_value(self) -> None:
        assert ComplianceStatus.COMPLIANT.value == "compliant"

    def test_non_compliant_value(self) -> None:
        assert ComplianceStatus.NON_COMPLIANT.value == "non_compliant"

    def test_partial_value(self) -> None:
        assert ComplianceStatus.PARTIAL.value == "partial"

    def test_not_assessed_value(self) -> None:
        assert ComplianceStatus.NOT_ASSESSED.value == "not_assessed"

    def test_exempt_value(self) -> None:
        assert ComplianceStatus.EXEMPT.value == "exempt"


# ---------------------------------------------------------------------------
# TestComplianceControl
# ---------------------------------------------------------------------------


class TestComplianceControl:
    def test_create_minimal(self) -> None:
        c = ComplianceControl(
            control_id="X-01",
            framework=ComplianceFramework.SOC2,
            title="Test",
        )
        assert c.control_id == "X-01"
        assert c.framework == ComplianceFramework.SOC2
        assert c.title == "Test"

    def test_defaults(self) -> None:
        c = ComplianceControl(
            control_id="X-01",
            framework=ComplianceFramework.GDPR,
            title="Test",
        )
        assert c.description == ""
        assert c.status == ComplianceStatus.NOT_ASSESSED
        assert c.evidence == ()
        assert c.assessed_at == 0.0
        assert c.assessed_by == ""
        assert c.notes == ""

    def test_frozen_immutable(self) -> None:
        c = ComplianceControl(
            control_id="X-01",
            framework=ComplianceFramework.SOC2,
            title="Test",
        )
        with pytest.raises((AttributeError, TypeError)):
            c.status = ComplianceStatus.COMPLIANT  # type: ignore[misc]

    def test_to_dict(self) -> None:
        c = ComplianceControl(
            control_id="EU-AI-01",
            framework=ComplianceFramework.EU_AI_ACT,
            title="Risk Class",
            description="Classify risk",
            status=ComplianceStatus.COMPLIANT,
            evidence=["docs/risk.md"],
            assessed_by="team",
        )
        d = c.to_dict()
        assert d["controlId"] == "EU-AI-01"
        assert d["framework"] == "eu_ai_act"
        assert d["status"] == "compliant"
        assert d["evidence"] == ["docs/risk.md"]
        assert d["assessedBy"] == "team"

    def test_from_dict_roundtrip(self) -> None:
        c = ComplianceControl(
            control_id="ISO-01",
            framework=ComplianceFramework.ISO27001,
            title="Asset Management",
            description="Inventory of assets",
            status=ComplianceStatus.PARTIAL,
            evidence=["policy.pdf"],
            assessed_at=1234567890.0,
            assessed_by="auditor",
            notes="partially done",
        )
        restored = ComplianceControl.from_dict(c.to_dict())
        assert restored.control_id == c.control_id
        assert restored.framework == c.framework
        assert restored.status == c.status
        assert restored.evidence == c.evidence
        assert restored.notes == c.notes

    def test_evidence_list_normalised_to_tuple(self) -> None:
        c = ComplianceControl(
            control_id="X-01",
            framework=ComplianceFramework.CUSTOM,
            title="Test",
            evidence=["a.md", "b.md"],
        )
        assert isinstance(c.evidence, tuple)
        assert c.evidence == ("a.md", "b.md")


# ---------------------------------------------------------------------------
# TestComplianceReport
# ---------------------------------------------------------------------------


class TestComplianceReport:
    def test_creation(self) -> None:
        report = ComplianceReport(
            framework=ComplianceFramework.EU_AI_ACT,
            controls=[],
            generated_by="test",
        )
        assert report.framework == ComplianceFramework.EU_AI_ACT
        assert report.generated_by == "test"

    def test_auto_report_id(self) -> None:
        r1 = ComplianceReport(framework=ComplianceFramework.SOC2, controls=[], generated_by="x")
        r2 = ComplianceReport(framework=ComplianceFramework.SOC2, controls=[], generated_by="x")
        assert r1.report_id != r2.report_id
        assert len(r1.report_id) == 16

    def test_auto_generated_at(self) -> None:
        before = time.time()
        r = ComplianceReport(framework=ComplianceFramework.GDPR, controls=[], generated_by="x")
        after = time.time()
        assert before <= r.generated_at <= after

    def test_score_calculation(self) -> None:
        controls = [
            ComplianceControl("X-01", ComplianceFramework.CUSTOM, "T", status=ComplianceStatus.COMPLIANT),
            ComplianceControl("X-02", ComplianceFramework.CUSTOM, "T", status=ComplianceStatus.COMPLIANT),
            ComplianceControl("X-03", ComplianceFramework.CUSTOM, "T", status=ComplianceStatus.NON_COMPLIANT),
            ComplianceControl("X-04", ComplianceFramework.CUSTOM, "T", status=ComplianceStatus.NON_COMPLIANT),
        ]
        r = ComplianceReport(framework=ComplianceFramework.CUSTOM, controls=controls, generated_by="x")
        assert r.score == 50.0

    def test_overall_status_compliant(self) -> None:
        controls = [
            ComplianceControl("X-01", ComplianceFramework.CUSTOM, "T", status=ComplianceStatus.COMPLIANT),
            ComplianceControl("X-02", ComplianceFramework.CUSTOM, "T", status=ComplianceStatus.COMPLIANT),
        ]
        r = ComplianceReport(framework=ComplianceFramework.CUSTOM, controls=controls, generated_by="x")
        assert r.overall_status == ComplianceStatus.COMPLIANT
        assert r.score == 100.0

    def test_overall_status_non_compliant(self) -> None:
        controls = [
            ComplianceControl("X-01", ComplianceFramework.CUSTOM, "T", status=ComplianceStatus.COMPLIANT),
            ComplianceControl("X-02", ComplianceFramework.CUSTOM, "T", status=ComplianceStatus.NON_COMPLIANT),
        ]
        r = ComplianceReport(framework=ComplianceFramework.CUSTOM, controls=controls, generated_by="x")
        assert r.overall_status == ComplianceStatus.NON_COMPLIANT

    def test_overall_status_empty_controls(self) -> None:
        r = ComplianceReport(framework=ComplianceFramework.CUSTOM, controls=[], generated_by="x")
        assert r.overall_status == ComplianceStatus.NOT_ASSESSED
        assert r.score == 0.0

    def test_to_dict(self) -> None:
        controls = [
            ComplianceControl("X-01", ComplianceFramework.CUSTOM, "T", status=ComplianceStatus.COMPLIANT),
        ]
        r = ComplianceReport(framework=ComplianceFramework.CUSTOM, controls=controls, generated_by="tester")
        d = r.to_dict()
        assert d["framework"] == "custom"
        assert d["generatedBy"] == "tester"
        assert d["score"] == 100.0
        assert d["overallStatus"] == "compliant"
        assert len(d["controls"]) == 1

    def test_exempt_controls_excluded_from_score(self) -> None:
        controls = [
            ComplianceControl("X-01", ComplianceFramework.CUSTOM, "T", status=ComplianceStatus.COMPLIANT),
            ComplianceControl("X-02", ComplianceFramework.CUSTOM, "T", status=ComplianceStatus.EXEMPT),
        ]
        r = ComplianceReport(framework=ComplianceFramework.CUSTOM, controls=controls, generated_by="x")
        # Only X-01 counts, X-02 is exempt
        assert r.score == 100.0


# ---------------------------------------------------------------------------
# TestComplianceEngine
# ---------------------------------------------------------------------------


class TestComplianceEngine:
    def test_register_control(self, engine: ComplianceEngine, eu_control: ComplianceControl) -> None:
        engine.register_control(eu_control)
        assert engine.get_control("EU-AI-01") is not None

    def test_update_control_status(self, engine: ComplianceEngine, eu_control: ComplianceControl) -> None:
        engine.register_control(eu_control)
        updated = engine.update_control(
            "EU-AI-01",
            ComplianceStatus.COMPLIANT,
            evidence=["docs/risk.md"],
            assessed_by="team",
        )
        assert updated.status == ComplianceStatus.COMPLIANT
        assert updated.evidence == ("docs/risk.md",)
        assert updated.assessed_by == "team"
        assert updated.assessed_at > 0.0

    def test_get_control_exists(self, engine: ComplianceEngine, eu_control: ComplianceControl) -> None:
        engine.register_control(eu_control)
        c = engine.get_control("EU-AI-01")
        assert c is not None
        assert c.control_id == "EU-AI-01"

    def test_get_control_not_found_returns_none(self, engine: ComplianceEngine) -> None:
        assert engine.get_control("NONEXISTENT") is None

    def test_list_controls_all(
        self, engine: ComplianceEngine,
        eu_control: ComplianceControl,
        soc2_control: ComplianceControl,
    ) -> None:
        engine.register_control(eu_control)
        engine.register_control(soc2_control)
        all_controls = engine.list_controls()
        assert len(all_controls) == 2

    def test_list_controls_filter_by_framework(
        self, engine: ComplianceEngine,
        eu_control: ComplianceControl,
        soc2_control: ComplianceControl,
    ) -> None:
        engine.register_control(eu_control)
        engine.register_control(soc2_control)
        eu_controls = engine.list_controls(ComplianceFramework.EU_AI_ACT)
        assert len(eu_controls) == 1
        assert eu_controls[0].control_id == "EU-AI-01"

    def test_generate_report(self, engine: ComplianceEngine, eu_control: ComplianceControl) -> None:
        engine.register_control(eu_control)
        engine.update_control("EU-AI-01", ComplianceStatus.COMPLIANT)
        report = engine.generate_report(ComplianceFramework.EU_AI_ACT, "audit-bot")
        assert report.framework == ComplianceFramework.EU_AI_ACT
        assert report.overall_status == ComplianceStatus.COMPLIANT
        assert report.score == 100.0

    def test_get_gaps_includes_not_assessed(self, engine: ComplianceEngine) -> None:
        c1 = ComplianceControl("X-01", ComplianceFramework.CUSTOM, "T")  # NOT_ASSESSED
        c2 = ComplianceControl("X-02", ComplianceFramework.CUSTOM, "T", status=ComplianceStatus.COMPLIANT)
        engine.register_control(c1)
        engine.register_control(c2)
        gaps = engine.get_gaps(ComplianceFramework.CUSTOM)
        assert len(gaps) == 1
        assert gaps[0].control_id == "X-01"

    def test_get_gaps_includes_non_compliant(self, engine: ComplianceEngine) -> None:
        c1 = ComplianceControl("X-01", ComplianceFramework.CUSTOM, "T", status=ComplianceStatus.NON_COMPLIANT)
        engine.register_control(c1)
        gaps = engine.get_gaps(ComplianceFramework.CUSTOM)
        assert len(gaps) == 1

    def test_get_stats(
        self, engine: ComplianceEngine,
        eu_control: ComplianceControl,
        soc2_control: ComplianceControl,
    ) -> None:
        engine.register_control(eu_control)
        engine.register_control(soc2_control)
        stats = engine.get_stats()
        assert stats["total_controls"] == 2
        assert stats["by_framework"]["eu_ai_act"] == 1
        assert stats["by_framework"]["soc2"] == 1
        assert stats["by_status"]["not_assessed"] == 2

    def test_duplicate_control_raises(self, engine: ComplianceEngine, eu_control: ComplianceControl) -> None:
        engine.register_control(eu_control)
        with pytest.raises(DuplicateControlError) as exc_info:
            engine.register_control(eu_control)
        assert "EU-AI-01" in str(exc_info.value)

    def test_update_nonexistent_control_raises(self, engine: ComplianceEngine) -> None:
        with pytest.raises(ControlNotFoundError) as exc_info:
            engine.update_control("GHOST-99", ComplianceStatus.COMPLIANT)
        assert "GHOST-99" in str(exc_info.value)

    def test_update_stores_new_control_in_registry(
        self, engine: ComplianceEngine, eu_control: ComplianceControl
    ) -> None:
        engine.register_control(eu_control)
        engine.update_control("EU-AI-01", ComplianceStatus.COMPLIANT)
        c = engine.get_control("EU-AI-01")
        assert c is not None
        assert c.status == ComplianceStatus.COMPLIANT


# ---------------------------------------------------------------------------
# TestComplianceAudit
# ---------------------------------------------------------------------------


class TestComplianceAudit:
    def test_callback_on_register(
        self, engine_with_callback: ComplianceEngine, audit_log: list[dict[str, Any]]
    ) -> None:
        c = ComplianceControl("X-01", ComplianceFramework.GDPR, "Data Minimisation")
        engine_with_callback.register_control(c)
        assert len(audit_log) == 1
        assert audit_log[0]["event_type"] == "compliance.control.registered"
        assert audit_log[0]["control_id"] == "X-01"

    def test_callback_on_update(
        self, engine_with_callback: ComplianceEngine, audit_log: list[dict[str, Any]]
    ) -> None:
        c = ComplianceControl("X-01", ComplianceFramework.GDPR, "Data Minimisation")
        engine_with_callback.register_control(c)
        engine_with_callback.update_control("X-01", ComplianceStatus.COMPLIANT)
        # register + update = 2 events
        assert len(audit_log) == 2
        update_event = audit_log[1]
        assert update_event["event_type"] == "compliance.control.updated"
        assert update_event["new_status"] == "compliant"
        assert update_event["old_status"] == "not_assessed"

    def test_no_callback_no_error(self) -> None:
        engine = ComplianceEngine()  # no callback
        c = ComplianceControl("X-01", ComplianceFramework.CUSTOM, "Test")
        engine.register_control(c)
        engine.update_control("X-01", ComplianceStatus.COMPLIANT)
        # Should not raise


# ---------------------------------------------------------------------------
# Acceptance Tests
# ---------------------------------------------------------------------------


class TestAcceptanceCompliance:
    def test_acc_comp_01_register_and_generate_eu_ai_act_report(self) -> None:
        """ACC-COMP-01: Register controls and generate EU AI Act report."""
        engine = ComplianceEngine()
        controls = [
            ComplianceControl("EU-AI-01", ComplianceFramework.EU_AI_ACT, "Risk Classification"),
            ComplianceControl("EU-AI-02", ComplianceFramework.EU_AI_ACT, "Transparency"),
            ComplianceControl("EU-AI-03", ComplianceFramework.EU_AI_ACT, "Human Oversight"),
        ]
        for c in controls:
            engine.register_control(c)

        engine.update_control("EU-AI-01", ComplianceStatus.COMPLIANT, evidence=["docs/risk.md"])
        engine.update_control("EU-AI-02", ComplianceStatus.COMPLIANT)
        engine.update_control("EU-AI-03", ComplianceStatus.PARTIAL)

        report = engine.generate_report(ComplianceFramework.EU_AI_ACT, "audit-bot")
        assert report.framework == ComplianceFramework.EU_AI_ACT
        assert len(report.controls) == 3
        assert report.generated_by == "audit-bot"
        assert report.report_id is not None

    def test_acc_comp_02_gap_analysis(self) -> None:
        """ACC-COMP-02: Gap analysis identifies non-compliant controls."""
        engine = ComplianceEngine()
        engine.register_control(
            ComplianceControl("SOC2-01", ComplianceFramework.SOC2, "Availability",
                              status=ComplianceStatus.COMPLIANT)
        )
        engine.register_control(
            ComplianceControl("SOC2-02", ComplianceFramework.SOC2, "Security")
            # NOT_ASSESSED by default
        )
        engine.register_control(
            ComplianceControl("SOC2-03", ComplianceFramework.SOC2, "Processing Integrity",
                              status=ComplianceStatus.NON_COMPLIANT)
        )

        gaps = engine.get_gaps(ComplianceFramework.SOC2)
        gap_ids = {c.control_id for c in gaps}
        assert "SOC2-02" in gap_ids  # NOT_ASSESSED
        assert "SOC2-03" in gap_ids  # NON_COMPLIANT
        assert "SOC2-01" not in gap_ids  # COMPLIANT — not a gap

    def test_acc_comp_03_score_accuracy(self) -> None:
        """ACC-COMP-03: Report score accurately reflects compliance percentage."""
        engine = ComplianceEngine()
        for i in range(1, 5):
            engine.register_control(
                ComplianceControl(f"G-{i:02d}", ComplianceFramework.GDPR, f"Control {i}")
            )

        # Mark 3/4 compliant
        engine.update_control("G-01", ComplianceStatus.COMPLIANT)
        engine.update_control("G-02", ComplianceStatus.COMPLIANT)
        engine.update_control("G-03", ComplianceStatus.COMPLIANT)
        # G-04 remains NOT_ASSESSED

        report = engine.generate_report(ComplianceFramework.GDPR, "tester")
        assert report.score == 75.0  # 3/4

    def test_acc_comp_04_multi_framework_independent(self) -> None:
        """ACC-COMP-04: Multi-framework controls tracked independently."""
        engine = ComplianceEngine()
        engine.register_control(
            ComplianceControl("EU-01", ComplianceFramework.EU_AI_ACT, "EU Control")
        )
        engine.register_control(
            ComplianceControl("SOC-01", ComplianceFramework.SOC2, "SOC Control",
                              status=ComplianceStatus.COMPLIANT)
        )

        eu_report = engine.generate_report(ComplianceFramework.EU_AI_ACT, "bot")
        soc_report = engine.generate_report(ComplianceFramework.SOC2, "bot")

        assert len(eu_report.controls) == 1
        assert len(soc_report.controls) == 1
        assert eu_report.overall_status == ComplianceStatus.NOT_ASSESSED
        assert soc_report.overall_status == ComplianceStatus.COMPLIANT

    def test_acc_comp_05_audit_trail(self) -> None:
        """ACC-COMP-05: Audit trail for all compliance changes."""
        events: list[dict] = []

        def callback(event_type: str, data: dict) -> None:
            events.append({"event_type": event_type, **data})

        engine = ComplianceEngine(audit_callback=callback)
        c = ComplianceControl("HIPAA-01", ComplianceFramework.HIPAA, "PHI Protection")
        engine.register_control(c)
        engine.update_control("HIPAA-01", ComplianceStatus.COMPLIANT, assessed_by="ciso")
        engine.update_control("HIPAA-01", ComplianceStatus.NON_COMPLIANT, notes="gap found")

        assert len(events) == 3  # 1 register + 2 updates
        types = [e["event_type"] for e in events]
        assert types[0] == "compliance.control.registered"
        assert types[1] == "compliance.control.updated"
        assert types[2] == "compliance.control.updated"
        # Verify status progression is recorded
        assert events[1]["new_status"] == "compliant"
        assert events[2]["new_status"] == "non_compliant"
