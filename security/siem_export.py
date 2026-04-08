"""SIEM Export — Phase E: Compliance + Audit Hardening.

Export audit events to SIEM systems in CEF, LEEF, JSON, and Syslog formats.
Compatible with Splunk (CEF/LEEF), Elasticsearch (JSON), rsyslog (SYSLOG).

Usage::

    exporter = SIEMExporter(format=SIEMFormat.CEF)
    event = SIEMEvent(
        event_type="policy.gate.denied",
        severity=SIEMSeverity.HIGH,
        description="Policy gate denied action shell.exec",
        actor="agent-001",
        target="shell.exec",
        outcome="failure",
    )
    exporter.emit(event)
    formatted = exporter.flush()  # Returns list[str], does NOT send
"""

from __future__ import annotations

import json
import logging
import math
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SIEMFormat(str, Enum):
    """Supported SIEM export formats."""

    CEF = "cef"
    LEEF = "leef"
    JSON = "json"
    SYSLOG = "syslog"


class SIEMSeverity(str, Enum):
    """Event severity levels for SIEM systems."""

    INFORMATIONAL = "informational"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# Severity mappings
# ---------------------------------------------------------------------------

# CEF severity: 0-10 integer
_CEF_SEVERITY_MAP: dict[str, int] = {
    SIEMSeverity.INFORMATIONAL.value: 0,
    SIEMSeverity.LOW.value: 3,
    SIEMSeverity.MEDIUM.value: 5,
    SIEMSeverity.HIGH.value: 7,
    SIEMSeverity.CRITICAL.value: 10,
}

# Syslog priority: facility=1 (user) * 8 + severity
# RFC 5424 severity: 7=debug/info, 6=info, 4=warning, 3=error, 2=critical
_SYSLOG_SEVERITY_MAP: dict[str, int] = {
    SIEMSeverity.INFORMATIONAL.value: 6,  # informational
    SIEMSeverity.LOW.value: 5,             # notice
    SIEMSeverity.MEDIUM.value: 4,          # warning
    SIEMSeverity.HIGH.value: 3,            # error
    SIEMSeverity.CRITICAL.value: 2,        # critical
}

_SYSLOG_FACILITY = 1  # user-level messages


# ---------------------------------------------------------------------------
# SIEMEvent
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SIEMEvent:
    """A single SIEM event ready for export.

    Immutable after creation — use SIEMExporter.create_from_audit() to
    construct from internal audit log format.
    """

    event_type: str
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    timestamp: float = field(default_factory=time.time)
    source: str = "occp"
    severity: SIEMSeverity = SIEMSeverity.INFORMATIONAL
    description: str = ""
    actor: str = ""
    target: str = ""
    outcome: str = "success"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Normalise metadata: ensure it's a plain dict (not a proxy)
        if not isinstance(self.metadata, dict):
            object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "eventId": self.event_id,
            "timestamp": self.timestamp,
            "source": self.source,
            "eventType": self.event_type,
            "severity": self.severity.value,
            "description": self.description,
            "actor": self.actor,
            "target": self.target,
            "outcome": self.outcome,
            "metadata": dict(self.metadata),
        }


# ---------------------------------------------------------------------------
# SIEMExporter
# ---------------------------------------------------------------------------


class SIEMExporter:
    """Formats and buffers SIEM events for export.

    Does NOT send events over the network — callers must consume the output
    of flush() and deliver it to the SIEM destination.

    Args:
        format: Output format (CEF, LEEF, JSON, SYSLOG).
        destination: Target destination string (informational, not used for I/O).
        batch_size: Maximum events per flush batch (0 = unlimited).
    """

    def __init__(
        self,
        format: SIEMFormat = SIEMFormat.JSON,
        destination: str = "",
        batch_size: int = 100,
    ) -> None:
        self._format = format
        self._destination = destination
        self._batch_size = batch_size
        self._buffer: list[SIEMEvent] = []
        self._events_emitted: int = 0
        self._events_flushed: int = 0

    @property
    def format(self) -> SIEMFormat:
        return self._format

    @property
    def destination(self) -> str:
        return self._destination

    # -- Emit / Flush --------------------------------------------------------

    def emit(self, event: SIEMEvent) -> None:
        """Buffer an event for export."""
        self._buffer.append(event)
        self._events_emitted += 1
        logger.debug(
            "SIEM event buffered: id=%s type=%s severity=%s",
            event.event_id, event.event_type, event.severity.value,
        )

    def flush(self) -> list[str]:
        """Format all buffered events and clear the buffer.

        Returns formatted event strings. Does NOT transmit.
        """
        if not self._buffer:
            return []

        batch = list(self._buffer)
        self._buffer.clear()
        self._events_flushed += len(batch)

        formatted = [self.format_event(e) for e in batch]
        logger.debug("SIEM flush: %d events formatted as %s", len(formatted), self._format.value)
        return formatted

    # -- Formatting ----------------------------------------------------------

    def format_event(self, event: SIEMEvent) -> str:
        """Format a single event according to the configured SIEM format."""
        if self._format == SIEMFormat.JSON:
            return self._format_json(event)
        elif self._format == SIEMFormat.CEF:
            return self._format_cef(event)
        elif self._format == SIEMFormat.LEEF:
            return self._format_leef(event)
        elif self._format == SIEMFormat.SYSLOG:
            return self._format_syslog(event)
        else:
            return self._format_json(event)

    def _format_json(self, event: SIEMEvent) -> str:
        """JSON format — compatible with Elasticsearch / Splunk HEC."""
        return json.dumps(event.to_dict(), separators=(",", ":"))

    def _format_cef(self, event: SIEMEvent) -> str:
        """CEF (Common Event Format) — ArcSight / Splunk compatible.

        Format: CEF:Version|Device Vendor|Device Product|Device Version|
                Device Event Class ID|Name|Severity|Extension
        """
        severity_int = _CEF_SEVERITY_MAP.get(event.severity.value, 0)
        # Escape CEF header fields: | and \ must be escaped
        event_type_escaped = _cef_escape_header(event.event_type)
        description_escaped = _cef_escape_header(event.description or event.event_type)

        # Extension key=value pairs (spaces in values handled by CEF spec)
        ext_parts = [
            f"rt={_iso_timestamp(event.timestamp)}",
            f"src={_cef_escape_ext(event.source)}",
            f"act={_cef_escape_ext(event.event_type)}",
            f"outcome={_cef_escape_ext(event.outcome)}",
        ]
        if event.actor:
            ext_parts.append(f"suser={_cef_escape_ext(event.actor)}")
        if event.target:
            ext_parts.append(f"target={_cef_escape_ext(event.target)}")
        if event.metadata:
            for k, v in event.metadata.items():
                safe_k = k.replace(" ", "_")
                ext_parts.append(f"{safe_k}={_cef_escape_ext(str(v))}")

        extension = " ".join(ext_parts)

        return (
            f"CEF:0|OCCP|AgentControlPlane|1.0"
            f"|{event_type_escaped}"
            f"|{description_escaped}"
            f"|{severity_int}"
            f"|{extension}"
        )

    def _format_leef(self, event: SIEMEvent) -> str:
        """LEEF (Log Event Extended Format) — IBM QRadar compatible.

        Format: LEEF:Version|Vendor|Product|Version|EventID|key=value\t...
        """
        # LEEF attributes are tab-separated key=value
        attrs: dict[str, str] = {
            "devTime": _iso_timestamp(event.timestamp),
            "sev": event.severity.value,
            "src": event.source,
            "outcome": event.outcome,
        }
        if event.actor:
            attrs["usrName"] = event.actor
        if event.target:
            attrs["resource"] = event.target
        if event.description:
            attrs["msg"] = event.description
        if event.metadata:
            for k, v in event.metadata.items():
                attrs[k.replace(" ", "_")] = str(v)

        attr_str = "\t".join(f"{k}={v}" for k, v in attrs.items())

        return (
            f"LEEF:2.0|OCCP|AgentControlPlane|1.0"
            f"|{event.event_type}"
            f"|{attr_str}"
        )

    def _format_syslog(self, event: SIEMEvent) -> str:
        """RFC 5424 Syslog format.

        Format: <PRI>VERSION TIMESTAMP HOSTNAME APPNAME PROCID MSGID MSG
        """
        sev = _SYSLOG_SEVERITY_MAP.get(event.severity.value, 6)
        pri = _SYSLOG_FACILITY * 8 + sev
        timestamp = _iso_timestamp(event.timestamp)
        hostname = "occp-agent"
        appname = "OCCP"
        procid = "-"
        msgid = event.event_type.replace(" ", "_")
        msg = event.description or event.event_type

        return f"<{pri}>1 {timestamp} {hostname} {appname} {procid} {msgid} {msg}"

    # -- Factory -------------------------------------------------------------

    def create_from_audit(self, audit_event: dict[str, Any]) -> SIEMEvent:
        """Create a SIEMEvent from an internal OCCP audit log event dict.

        Expected audit_event keys (all optional except 'event_type' or 'type'):
            type / event_type, timestamp, actor / agent_id, target / resource,
            outcome / result, severity, description / message, metadata
        """
        event_type = (
            audit_event.get("event_type")
            or audit_event.get("type")
            or "audit.unknown"
        )
        timestamp = audit_event.get("timestamp", time.time())
        actor = audit_event.get("actor") or audit_event.get("agent_id", "")
        target = audit_event.get("target") or audit_event.get("resource", "")
        description = audit_event.get("description") or audit_event.get("message", "")
        outcome = audit_event.get("outcome") or audit_event.get("result", "success")

        # Map internal severity strings to SIEMSeverity
        raw_sev = str(audit_event.get("severity", "informational")).lower()
        severity = _map_severity(raw_sev)

        # Collect remaining keys as metadata
        known_keys = {
            "event_type", "type", "timestamp", "actor", "agent_id",
            "target", "resource", "description", "message",
            "outcome", "result", "severity",
        }
        metadata = {k: v for k, v in audit_event.items() if k not in known_keys}

        return SIEMEvent(
            event_type=event_type,
            timestamp=timestamp,
            source=audit_event.get("source", "occp"),
            severity=severity,
            description=description,
            actor=actor,
            target=target,
            outcome=outcome,
            metadata=metadata,
        )

    # -- Stats ---------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """Return emit/flush lifecycle statistics."""
        return {
            "events_emitted": self._events_emitted,
            "events_flushed": self._events_flushed,
            "buffer_size": len(self._buffer),
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _iso_timestamp(ts: float) -> str:
    """Convert Unix timestamp to ISO 8601 UTC string."""
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _cef_escape_header(value: str) -> str:
    """Escape CEF header field: backslash and pipe."""
    return value.replace("\\", "\\\\").replace("|", "\\|")


def _cef_escape_ext(value: str) -> str:
    """Escape CEF extension value: backslash, equals, newlines."""
    return (
        value.replace("\\", "\\\\")
        .replace("=", "\\=")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
    )


def _map_severity(raw: str) -> SIEMSeverity:
    """Map arbitrary severity strings to SIEMSeverity."""
    mapping: dict[str, SIEMSeverity] = {
        "critical": SIEMSeverity.CRITICAL,
        "high": SIEMSeverity.HIGH,
        "medium": SIEMSeverity.MEDIUM,
        "low": SIEMSeverity.LOW,
        "info": SIEMSeverity.INFORMATIONAL,
        "informational": SIEMSeverity.INFORMATIONAL,
        "debug": SIEMSeverity.INFORMATIONAL,
        "warning": SIEMSeverity.MEDIUM,
        "warn": SIEMSeverity.MEDIUM,
        "error": SIEMSeverity.HIGH,
    }
    return mapping.get(raw, SIEMSeverity.INFORMATIONAL)
