"""Tests for security.siem_export — SIEM Export (Phase E).

Covers:
- SIEMFormat: enum values
- SIEMSeverity: enum values, ordering
- SIEMEvent: creation, auto fields, frozen, to_dict, defaults
- SIEMExporter: emit, flush, buffer, batch, format_event for each format
- TestCEFFormat: CEF structure, severity mapping, special char escaping
- TestLEEFFormat: LEEF structure, fields
- TestSyslogFormat: syslog structure, priority
- TestJSONFormat: valid JSON, all fields
- TestCreateFromAudit: factory method, mapping
- TestSIEMStats: initial, after emit, after flush
- Acceptance: ACC-SIEM-01..05
"""

from __future__ import annotations

import json
import time
import pytest

from security.siem_export import (
    SIEMEvent,
    SIEMExporter,
    SIEMFormat,
    SIEMSeverity,
    _CEF_SEVERITY_MAP,
    _SYSLOG_FACILITY,
    _SYSLOG_SEVERITY_MAP,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def event() -> SIEMEvent:
    return SIEMEvent(
        event_type="policy.gate.denied",
        severity=SIEMSeverity.HIGH,
        description="Action denied by policy gate",
        actor="agent-001",
        target="shell.exec",
        outcome="failure",
        metadata={"action": "shell.exec", "rule": "no-shell"},
    )


@pytest.fixture
def json_exporter() -> SIEMExporter:
    return SIEMExporter(format=SIEMFormat.JSON)


@pytest.fixture
def cef_exporter() -> SIEMExporter:
    return SIEMExporter(format=SIEMFormat.CEF)


@pytest.fixture
def leef_exporter() -> SIEMExporter:
    return SIEMExporter(format=SIEMFormat.LEEF)


@pytest.fixture
def syslog_exporter() -> SIEMExporter:
    return SIEMExporter(format=SIEMFormat.SYSLOG)


# ---------------------------------------------------------------------------
# TestSIEMFormat
# ---------------------------------------------------------------------------


class TestSIEMFormat:
    def test_all_formats_exist(self) -> None:
        assert SIEMFormat.CEF
        assert SIEMFormat.LEEF
        assert SIEMFormat.JSON
        assert SIEMFormat.SYSLOG

    def test_string_values(self) -> None:
        assert SIEMFormat.CEF.value == "cef"
        assert SIEMFormat.LEEF.value == "leef"
        assert SIEMFormat.JSON.value == "json"
        assert SIEMFormat.SYSLOG.value == "syslog"

    def test_is_str_enum(self) -> None:
        assert SIEMFormat.JSON == "json"


# ---------------------------------------------------------------------------
# TestSIEMSeverity
# ---------------------------------------------------------------------------


class TestSIEMSeverity:
    def test_all_severities_exist(self) -> None:
        assert SIEMSeverity.INFORMATIONAL
        assert SIEMSeverity.LOW
        assert SIEMSeverity.MEDIUM
        assert SIEMSeverity.HIGH
        assert SIEMSeverity.CRITICAL

    def test_string_values(self) -> None:
        assert SIEMSeverity.INFORMATIONAL.value == "informational"
        assert SIEMSeverity.LOW.value == "low"
        assert SIEMSeverity.MEDIUM.value == "medium"
        assert SIEMSeverity.HIGH.value == "high"
        assert SIEMSeverity.CRITICAL.value == "critical"

    def test_cef_severity_ordering(self) -> None:
        """CEF severity map: INFORMATIONAL < LOW < MEDIUM < HIGH < CRITICAL."""
        assert _CEF_SEVERITY_MAP["informational"] < _CEF_SEVERITY_MAP["low"]
        assert _CEF_SEVERITY_MAP["low"] < _CEF_SEVERITY_MAP["medium"]
        assert _CEF_SEVERITY_MAP["medium"] < _CEF_SEVERITY_MAP["high"]
        assert _CEF_SEVERITY_MAP["high"] < _CEF_SEVERITY_MAP["critical"]

    def test_cef_critical_max(self) -> None:
        assert _CEF_SEVERITY_MAP["critical"] == 10

    def test_syslog_severity_ordering(self) -> None:
        """Syslog: CRITICAL < HIGH < MEDIUM < LOW < INFORMATIONAL (lower = more severe)."""
        assert _SYSLOG_SEVERITY_MAP["critical"] < _SYSLOG_SEVERITY_MAP["high"]
        assert _SYSLOG_SEVERITY_MAP["high"] < _SYSLOG_SEVERITY_MAP["medium"]
        assert _SYSLOG_SEVERITY_MAP["medium"] < _SYSLOG_SEVERITY_MAP["low"]


# ---------------------------------------------------------------------------
# TestSIEMEvent
# ---------------------------------------------------------------------------


class TestSIEMEvent:
    def test_create_minimal(self) -> None:
        e = SIEMEvent(event_type="test.event")
        assert e.event_type == "test.event"
        assert e.source == "occp"
        assert e.outcome == "success"

    def test_auto_event_id(self) -> None:
        e1 = SIEMEvent(event_type="x")
        e2 = SIEMEvent(event_type="x")
        assert e1.event_id != e2.event_id
        assert len(e1.event_id) == 16

    def test_auto_timestamp(self) -> None:
        before = time.time()
        e = SIEMEvent(event_type="x")
        after = time.time()
        assert before <= e.timestamp <= after

    def test_frozen_immutable(self) -> None:
        e = SIEMEvent(event_type="x")
        with pytest.raises((AttributeError, TypeError)):
            e.outcome = "changed"  # type: ignore[misc]

    def test_defaults(self) -> None:
        e = SIEMEvent(event_type="x")
        assert e.severity == SIEMSeverity.INFORMATIONAL
        assert e.actor == ""
        assert e.target == ""
        assert e.description == ""
        assert e.metadata == {}

    def test_to_dict(self, event: SIEMEvent) -> None:
        d = event.to_dict()
        assert d["eventType"] == "policy.gate.denied"
        assert d["severity"] == "high"
        assert d["actor"] == "agent-001"
        assert d["target"] == "shell.exec"
        assert d["outcome"] == "failure"
        assert "eventId" in d
        assert "timestamp" in d

    def test_to_dict_metadata(self) -> None:
        e = SIEMEvent(event_type="x", metadata={"k": "v"})
        d = e.to_dict()
        assert d["metadata"] == {"k": "v"}


# ---------------------------------------------------------------------------
# TestSIEMExporter
# ---------------------------------------------------------------------------


class TestSIEMExporter:
    def test_emit_adds_to_buffer(self, json_exporter: SIEMExporter, event: SIEMEvent) -> None:
        json_exporter.emit(event)
        stats = json_exporter.get_stats()
        assert stats["buffer_size"] == 1

    def test_flush_clears_buffer(self, json_exporter: SIEMExporter, event: SIEMEvent) -> None:
        json_exporter.emit(event)
        result = json_exporter.flush()
        assert len(result) == 1
        assert json_exporter.get_stats()["buffer_size"] == 0

    def test_flush_empty_buffer_returns_empty(self, json_exporter: SIEMExporter) -> None:
        assert json_exporter.flush() == []

    def test_emit_multiple(self, json_exporter: SIEMExporter) -> None:
        for i in range(5):
            json_exporter.emit(SIEMEvent(event_type=f"event.{i}"))
        stats = json_exporter.get_stats()
        assert stats["buffer_size"] == 5
        assert stats["events_emitted"] == 5

    def test_flush_returns_list_of_strings(self, json_exporter: SIEMExporter, event: SIEMEvent) -> None:
        json_exporter.emit(event)
        result = json_exporter.flush()
        assert isinstance(result, list)
        assert all(isinstance(s, str) for s in result)

    def test_batch_multiple_events(self, cef_exporter: SIEMExporter) -> None:
        for i in range(3):
            cef_exporter.emit(SIEMEvent(event_type=f"evt.{i}"))
        formatted = cef_exporter.flush()
        assert len(formatted) == 3
        assert all(s.startswith("CEF:") for s in formatted)

    def test_format_event_json(self, json_exporter: SIEMExporter, event: SIEMEvent) -> None:
        result = json_exporter.format_event(event)
        data = json.loads(result)
        assert data["eventType"] == "policy.gate.denied"

    def test_format_event_cef(self, cef_exporter: SIEMExporter, event: SIEMEvent) -> None:
        result = cef_exporter.format_event(event)
        assert result.startswith("CEF:0")

    def test_format_event_leef(self, leef_exporter: SIEMExporter, event: SIEMEvent) -> None:
        result = leef_exporter.format_event(event)
        assert result.startswith("LEEF:2.0")

    def test_format_event_syslog(self, syslog_exporter: SIEMExporter, event: SIEMEvent) -> None:
        result = syslog_exporter.format_event(event)
        assert result.startswith("<")


# ---------------------------------------------------------------------------
# TestCEFFormat
# ---------------------------------------------------------------------------


class TestCEFFormat:
    def test_cef_header_structure(self, cef_exporter: SIEMExporter) -> None:
        e = SIEMEvent(event_type="skill.executed", description="Skill ran")
        result = cef_exporter.format_event(e)
        # CEF:Version|Vendor|Product|DevVersion|EventClassID|Name|Severity|Extension
        parts = result.split("|")
        assert parts[0] == "CEF:0"
        assert parts[1] == "OCCP"
        assert parts[2] == "AgentControlPlane"
        assert parts[3] == "1.0"

    def test_cef_severity_high_maps_to_7(self, cef_exporter: SIEMExporter) -> None:
        e = SIEMEvent(event_type="x", severity=SIEMSeverity.HIGH)
        result = cef_exporter.format_event(e)
        # 7th pipe-delimited field (index 6) is severity
        parts = result.split("|")
        assert parts[6] == "7"

    def test_cef_severity_critical_maps_to_10(self, cef_exporter: SIEMExporter) -> None:
        e = SIEMEvent(event_type="x", severity=SIEMSeverity.CRITICAL)
        result = cef_exporter.format_event(e)
        parts = result.split("|")
        assert parts[6] == "10"

    def test_cef_pipe_in_event_type_escaped(self, cef_exporter: SIEMExporter) -> None:
        e = SIEMEvent(event_type="bad|event")
        result = cef_exporter.format_event(e)
        # The pipe in event_type should be escaped as \|
        # Verify raw unescaped pipe count matches expected
        assert "bad\\|event" in result

    def test_cef_extension_contains_actor_target(self, cef_exporter: SIEMExporter) -> None:
        e = SIEMEvent(event_type="x", actor="agent-1", target="db.write")
        result = cef_exporter.format_event(e)
        assert "suser=agent-1" in result
        assert "target=db.write" in result

    def test_cef_extension_contains_outcome(self, cef_exporter: SIEMExporter) -> None:
        e = SIEMEvent(event_type="x", outcome="failure")
        result = cef_exporter.format_event(e)
        assert "outcome=failure" in result


# ---------------------------------------------------------------------------
# TestLEEFFormat
# ---------------------------------------------------------------------------


class TestLEEFFormat:
    def test_leef_header_structure(self, leef_exporter: SIEMExporter) -> None:
        e = SIEMEvent(event_type="skill.executed")
        result = leef_exporter.format_event(e)
        assert result.startswith("LEEF:2.0|OCCP|AgentControlPlane|1.0|skill.executed|")

    def test_leef_contains_severity(self, leef_exporter: SIEMExporter) -> None:
        e = SIEMEvent(event_type="x", severity=SIEMSeverity.MEDIUM)
        result = leef_exporter.format_event(e)
        assert "sev=medium" in result

    def test_leef_contains_actor(self, leef_exporter: SIEMExporter) -> None:
        e = SIEMEvent(event_type="x", actor="agent-42")
        result = leef_exporter.format_event(e)
        assert "usrName=agent-42" in result

    def test_leef_attributes_tab_separated(self, leef_exporter: SIEMExporter) -> None:
        e = SIEMEvent(event_type="x", actor="a", target="t")
        result = leef_exporter.format_event(e)
        # After the 5th pipe (event ID), attributes are tab-separated
        after_id = result.split("|", 5)[5]
        pairs = after_id.split("\t")
        assert all("=" in p for p in pairs)


# ---------------------------------------------------------------------------
# TestSyslogFormat
# ---------------------------------------------------------------------------


class TestSyslogFormat:
    def test_syslog_starts_with_priority(self, syslog_exporter: SIEMExporter) -> None:
        e = SIEMEvent(event_type="x")
        result = syslog_exporter.format_event(e)
        assert result.startswith("<")
        assert result[1:result.index(">")] .isdigit()

    def test_syslog_priority_informational(self, syslog_exporter: SIEMExporter) -> None:
        e = SIEMEvent(event_type="x", severity=SIEMSeverity.INFORMATIONAL)
        result = syslog_exporter.format_event(e)
        sev = _SYSLOG_SEVERITY_MAP["informational"]
        expected_pri = _SYSLOG_FACILITY * 8 + sev
        assert result.startswith(f"<{expected_pri}>")

    def test_syslog_priority_critical(self, syslog_exporter: SIEMExporter) -> None:
        e = SIEMEvent(event_type="x", severity=SIEMSeverity.CRITICAL)
        result = syslog_exporter.format_event(e)
        sev = _SYSLOG_SEVERITY_MAP["critical"]
        expected_pri = _SYSLOG_FACILITY * 8 + sev
        assert result.startswith(f"<{expected_pri}>")

    def test_syslog_contains_event_type_as_msgid(self, syslog_exporter: SIEMExporter) -> None:
        e = SIEMEvent(event_type="policy.denied")
        result = syslog_exporter.format_event(e)
        assert "policy.denied" in result

    def test_syslog_contains_description(self, syslog_exporter: SIEMExporter) -> None:
        e = SIEMEvent(event_type="x", description="Gate blocked action")
        result = syslog_exporter.format_event(e)
        assert "Gate blocked action" in result


# ---------------------------------------------------------------------------
# TestJSONFormat
# ---------------------------------------------------------------------------


class TestJSONFormat:
    def test_valid_json(self, json_exporter: SIEMExporter, event: SIEMEvent) -> None:
        result = json_exporter.format_event(event)
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    def test_all_fields_present(self, json_exporter: SIEMExporter, event: SIEMEvent) -> None:
        result = json_exporter.format_event(event)
        parsed = json.loads(result)
        required_keys = {
            "eventId", "timestamp", "source", "eventType",
            "severity", "description", "actor", "target", "outcome", "metadata",
        }
        assert required_keys.issubset(set(parsed.keys()))

    def test_metadata_in_json(self, json_exporter: SIEMExporter) -> None:
        e = SIEMEvent(event_type="x", metadata={"policy": "no-shell", "count": 3})
        result = json_exporter.format_event(e)
        parsed = json.loads(result)
        assert parsed["metadata"]["policy"] == "no-shell"
        assert parsed["metadata"]["count"] == 3


# ---------------------------------------------------------------------------
# TestCreateFromAudit
# ---------------------------------------------------------------------------


class TestCreateFromAudit:
    def test_basic_mapping(self, json_exporter: SIEMExporter) -> None:
        audit = {
            "event_type": "skill.executed",
            "timestamp": 1700000000.0,
            "actor": "agent-5",
            "target": "weather-skill",
            "outcome": "success",
            "severity": "low",
            "description": "Skill completed",
        }
        e = json_exporter.create_from_audit(audit)
        assert e.event_type == "skill.executed"
        assert e.actor == "agent-5"
        assert e.target == "weather-skill"
        assert e.outcome == "success"
        assert e.severity == SIEMSeverity.LOW
        assert e.description == "Skill completed"

    def test_agent_id_alias(self, json_exporter: SIEMExporter) -> None:
        audit = {
            "type": "policy.evaluated",
            "agent_id": "agt-99",
            "result": "failure",
        }
        e = json_exporter.create_from_audit(audit)
        assert e.event_type == "policy.evaluated"
        assert e.actor == "agt-99"
        assert e.outcome == "failure"

    def test_extra_fields_become_metadata(self, json_exporter: SIEMExporter) -> None:
        audit = {
            "event_type": "x",
            "custom_field": "value123",
            "rule_id": "RULE-42",
        }
        e = json_exporter.create_from_audit(audit)
        assert e.metadata.get("custom_field") == "value123"
        assert e.metadata.get("rule_id") == "RULE-42"

    def test_severity_mapping_critical(self, json_exporter: SIEMExporter) -> None:
        audit = {"event_type": "x", "severity": "critical"}
        e = json_exporter.create_from_audit(audit)
        assert e.severity == SIEMSeverity.CRITICAL

    def test_severity_mapping_warning_to_medium(self, json_exporter: SIEMExporter) -> None:
        audit = {"event_type": "x", "severity": "warning"}
        e = json_exporter.create_from_audit(audit)
        assert e.severity == SIEMSeverity.MEDIUM

    def test_missing_event_type_defaults(self, json_exporter: SIEMExporter) -> None:
        audit = {"timestamp": time.time()}
        e = json_exporter.create_from_audit(audit)
        assert e.event_type == "audit.unknown"


# ---------------------------------------------------------------------------
# TestSIEMStats
# ---------------------------------------------------------------------------


class TestSIEMStats:
    def test_initial_stats_zero(self, json_exporter: SIEMExporter) -> None:
        stats = json_exporter.get_stats()
        assert stats["events_emitted"] == 0
        assert stats["events_flushed"] == 0
        assert stats["buffer_size"] == 0

    def test_stats_after_emit(self, json_exporter: SIEMExporter) -> None:
        json_exporter.emit(SIEMEvent(event_type="x"))
        json_exporter.emit(SIEMEvent(event_type="y"))
        stats = json_exporter.get_stats()
        assert stats["events_emitted"] == 2
        assert stats["buffer_size"] == 2
        assert stats["events_flushed"] == 0

    def test_stats_after_flush(self, json_exporter: SIEMExporter) -> None:
        json_exporter.emit(SIEMEvent(event_type="x"))
        json_exporter.emit(SIEMEvent(event_type="y"))
        json_exporter.flush()
        stats = json_exporter.get_stats()
        assert stats["events_emitted"] == 2
        assert stats["events_flushed"] == 2
        assert stats["buffer_size"] == 0

    def test_stats_cumulative_across_multiple_flushes(self, json_exporter: SIEMExporter) -> None:
        json_exporter.emit(SIEMEvent(event_type="a"))
        json_exporter.flush()
        json_exporter.emit(SIEMEvent(event_type="b"))
        json_exporter.emit(SIEMEvent(event_type="c"))
        json_exporter.flush()
        stats = json_exporter.get_stats()
        assert stats["events_emitted"] == 3
        assert stats["events_flushed"] == 3


# ---------------------------------------------------------------------------
# Acceptance Tests
# ---------------------------------------------------------------------------


class TestAcceptanceSIEM:
    def test_acc_siem_01_cef_format_valid(self) -> None:
        """ACC-SIEM-01: Event emitted in CEF format is valid CEF."""
        exporter = SIEMExporter(format=SIEMFormat.CEF)
        exporter.emit(SIEMEvent(
            event_type="agent.spawned",
            severity=SIEMSeverity.MEDIUM,
            actor="orchestrator",
            target="skill-runner",
            outcome="success",
        ))
        formatted = exporter.flush()
        assert len(formatted) == 1
        line = formatted[0]
        # CEF must start with CEF:0
        assert line.startswith("CEF:0|")
        # Must have at least 8 pipe-delimited fields (7 pipes)
        assert line.count("|") >= 7
        parts = line.split("|")
        assert parts[1] == "OCCP"
        assert parts[2] == "AgentControlPlane"

    def test_acc_siem_02_json_format_valid(self) -> None:
        """ACC-SIEM-02: Event emitted in JSON format is valid JSON."""
        exporter = SIEMExporter(format=SIEMFormat.JSON)
        exporter.emit(SIEMEvent(
            event_type="policy.gate.allowed",
            severity=SIEMSeverity.INFORMATIONAL,
            actor="agent-3",
            outcome="success",
        ))
        formatted = exporter.flush()
        assert len(formatted) == 1
        parsed = json.loads(formatted[0])
        assert parsed["eventType"] == "policy.gate.allowed"
        assert parsed["actor"] == "agent-3"
        assert parsed["severity"] == "informational"

    def test_acc_siem_03_batch_flush_correct_count(self) -> None:
        """ACC-SIEM-03: Batch flush returns correct count of formatted events."""
        exporter = SIEMExporter(format=SIEMFormat.LEEF, batch_size=50)
        for i in range(25):
            exporter.emit(SIEMEvent(event_type=f"event.{i}", severity=SIEMSeverity.LOW))
        formatted = exporter.flush()
        assert len(formatted) == 25
        assert all(f.startswith("LEEF:2.0") for f in formatted)
        # Buffer is now empty
        assert exporter.get_stats()["buffer_size"] == 0

    def test_acc_siem_04_create_from_audit_correct(self) -> None:
        """ACC-SIEM-04: Create from internal audit format produces correct SIEM event."""
        exporter = SIEMExporter(format=SIEMFormat.JSON)
        audit_event = {
            "type": "merkle.root.published",
            "timestamp": 1700000000.0,
            "agent_id": "audit-service",
            "resource": "audit-chain",
            "result": "success",
            "severity": "informational",
            "message": "Merkle root published at threshold",
            "root_hash": "abc123",
            "entry_count": 1000,
        }
        e = exporter.create_from_audit(audit_event)
        assert e.event_type == "merkle.root.published"
        assert e.actor == "audit-service"
        assert e.target == "audit-chain"
        assert e.outcome == "success"
        assert e.severity == SIEMSeverity.INFORMATIONAL
        assert e.metadata.get("root_hash") == "abc123"
        assert e.metadata.get("entry_count") == 1000

    def test_acc_siem_05_stats_track_lifecycle(self) -> None:
        """ACC-SIEM-05: Stats accurately track emit/flush lifecycle."""
        exporter = SIEMExporter(format=SIEMFormat.JSON)

        # Phase 1: emit 10
        for i in range(10):
            exporter.emit(SIEMEvent(event_type=f"evt.{i}"))

        stats = exporter.get_stats()
        assert stats["events_emitted"] == 10
        assert stats["buffer_size"] == 10
        assert stats["events_flushed"] == 0

        # Phase 2: flush
        exporter.flush()
        stats = exporter.get_stats()
        assert stats["events_emitted"] == 10
        assert stats["buffer_size"] == 0
        assert stats["events_flushed"] == 10

        # Phase 3: emit 5 more
        for i in range(5):
            exporter.emit(SIEMEvent(event_type=f"more.{i}"))

        stats = exporter.get_stats()
        assert stats["events_emitted"] == 15
        assert stats["buffer_size"] == 5
        assert stats["events_flushed"] == 10

        # Phase 4: flush remainder
        exporter.flush()
        stats = exporter.get_stats()
        assert stats["events_emitted"] == 15
        assert stats["events_flushed"] == 15
        assert stats["buffer_size"] == 0
