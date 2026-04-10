"""Drift detector — compare architecture memory YAML to live code.

The L6 discipline requires that `architecture/*.yaml` reflect reality.
This module produces a drift report by cross-checking YAML declarations
against the running code.

Detected drift classes:
- Agents declared in YAML but missing from `security/agent_allowlist.py`
  (or vice-versa).
- Services declared in YAML but their `host` is not in the hosts list.
- Tools declared in `tools.yaml` but not registered in the default
  MCP bridge build.
- Issue paths in `issue_registry.yaml` that do not exist in the repo.

Every drift check is read-only. No automatic repair — the proposal
generator picks up drift as regular proposals for human review.
"""

from __future__ import annotations

import logging
import pathlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import yaml

logger = logging.getLogger(__name__)


@dataclass
class DriftEntry:
    """A single drift record."""

    kind: str  # "agent_missing_in_code" | "host_orphan" | "tool_not_registered" | "path_missing"
    subject: str
    expected_in: str
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "subject": self.subject,
            "expected_in": self.expected_in,
            "evidence": self.evidence,
        }


@dataclass
class DriftReport:
    """Aggregate drift report."""

    generated_at: datetime
    entries: list[DriftEntry]
    checks_performed: list[str]

    @property
    def has_drift(self) -> bool:
        return len(self.entries) > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "has_drift": self.has_drift,
            "total_entries": len(self.entries),
            "checks_performed": self.checks_performed,
            "by_kind": self._by_kind(),
            "entries": [e.to_dict() for e in self.entries],
        }

    def _by_kind(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for e in self.entries:
            counts[e.kind] = counts.get(e.kind, 0) + 1
        return counts


class DriftDetector:
    """Cross-reference architecture memory against runtime code."""

    DEFAULT_ARCH_DIR = pathlib.Path(__file__).parent.parent / "architecture"
    DEFAULT_REPO_ROOT = pathlib.Path(__file__).parent.parent

    def __init__(
        self,
        arch_dir: pathlib.Path | None = None,
        repo_root: pathlib.Path | None = None,
    ) -> None:
        self._arch_dir = arch_dir or self.DEFAULT_ARCH_DIR
        self._repo_root = repo_root or self.DEFAULT_REPO_ROOT

    # ── Individual checks ────────────────────────────────

    def check_agent_drift(self) -> list[DriftEntry]:
        """Compare agents.yaml to security/agent_allowlist.py."""
        entries: list[DriftEntry] = []
        try:
            with (self._arch_dir / "agents.yaml").open() as f:
                agents_doc = yaml.safe_load(f) or {}
            from security.agent_allowlist import AGENT_TOOL_ALLOWLISTS
        except Exception as exc:  # noqa: BLE001
            logger.warning("drift_detector: agent check skipped: %s", exc)
            return entries

        yaml_ids = (
            {a["id"] for a in agents_doc.get("specialists", [])}
            | {o["id"] for o in agents_doc.get("orchestrators", [])}
            | {a["id"] for a in agents_doc.get("seeded_pipeline_agents", [])}
        )
        code_ids = set(AGENT_TOOL_ALLOWLISTS.keys())

        for missing in yaml_ids - code_ids:
            entries.append(
                DriftEntry(
                    kind="agent_missing_in_code",
                    subject=missing,
                    expected_in="security/agent_allowlist.py::AGENT_TOOL_ALLOWLISTS",
                    evidence={"declared_in": "architecture/agents.yaml"},
                )
            )
        for extra in code_ids - yaml_ids:
            entries.append(
                DriftEntry(
                    kind="agent_missing_in_yaml",
                    subject=extra,
                    expected_in="architecture/agents.yaml",
                    evidence={"declared_in": "security/agent_allowlist.py"},
                )
            )
        return entries

    def check_service_hosts(self) -> list[DriftEntry]:
        """Ensure every service.host references a defined host."""
        entries: list[DriftEntry] = []
        try:
            with (self._arch_dir / "services.yaml").open() as f:
                doc = yaml.safe_load(f) or {}
        except Exception as exc:  # noqa: BLE001
            logger.warning("drift_detector: services check skipped: %s", exc)
            return entries

        hosts_defined = {h["id"] for h in doc.get("hosts", [])}
        for svc in doc.get("services", []):
            host = svc.get("host")
            if host and host not in hosts_defined:
                entries.append(
                    DriftEntry(
                        kind="host_orphan",
                        subject=svc["id"],
                        expected_in="services.yaml::hosts",
                        evidence={"referenced_host": host},
                    )
                )
        return entries

    def check_tool_registration(self) -> list[DriftEntry]:
        """Ensure every tool in tools.yaml is registered in the default bridge.

        This is a best-effort check — it imports build_default_bridge and
        compares registered tool names.
        """
        entries: list[DriftEntry] = []
        try:
            with (self._arch_dir / "tools.yaml").open() as f:
                doc = yaml.safe_load(f) or {}
            from adapters.mcp_bridge import build_default_bridge

            bridge = build_default_bridge()
            registered = set(bridge.list_tools())
        except Exception as exc:  # noqa: BLE001
            logger.warning("drift_detector: tool check skipped: %s", exc)
            return entries

        declared = {t["id"] for t in doc.get("tools", [])}
        for missing in declared - registered:
            entries.append(
                DriftEntry(
                    kind="tool_not_registered",
                    subject=missing,
                    expected_in="adapters.mcp_bridge.build_default_bridge",
                    evidence={"declared_in": "architecture/tools.yaml"},
                )
            )
        return entries

    def check_issue_paths(self) -> list[DriftEntry]:
        """Ensure affected_paths in issue_registry.yaml exist in the repo.

        Skips:
        - directory-only references (path ends with '/')
        - glob patterns (contain '*')
        - paths known to be deployment-stripped (`.planning/`, `docs/`, `tests/`)
          since they may not be shipped into the container.
        """
        entries: list[DriftEntry] = []
        try:
            with (self._arch_dir / "issue_registry.yaml").open() as f:
                doc = yaml.safe_load(f) or {}
        except Exception as exc:  # noqa: BLE001
            logger.warning("drift_detector: issue check skipped: %s", exc)
            return entries

        deployment_stripped_prefixes = (
            ".planning/",
            "docs/",
            "tests/",
            ".github/",
            "migrations/",
        )

        for issue in doc.get("issues", []):
            for affected in issue.get("affected_paths", []) or []:
                if not affected:
                    continue
                if affected.endswith("/"):
                    continue  # directory reference, skip
                if "*" in affected:
                    continue  # glob, skip
                if any(affected.startswith(p) for p in deployment_stripped_prefixes):
                    continue  # not in container, expected
                target = self._repo_root / affected
                if not target.exists():
                    entries.append(
                        DriftEntry(
                            kind="issue_path_missing",
                            subject=affected,
                            expected_in=f"issue {issue.get('id', '?')}",
                            evidence={"issue_id": issue.get("id")},
                        )
                    )
        return entries

    # ── Aggregate ────────────────────────────────────────
    def detect(self) -> DriftReport:
        """Run all checks and produce a report."""
        all_entries: list[DriftEntry] = []
        checks_run = []

        for name, fn in [
            ("agent_drift", self.check_agent_drift),
            ("service_hosts", self.check_service_hosts),
            ("tool_registration", self.check_tool_registration),
            ("issue_paths", self.check_issue_paths),
        ]:
            checks_run.append(name)
            try:
                all_entries.extend(fn())
            except Exception as exc:  # noqa: BLE001
                logger.warning("drift check %s raised: %s", name, exc)

        return DriftReport(
            generated_at=datetime.now(timezone.utc),
            entries=all_entries,
            checks_performed=checks_run,
        )


# ── Singleton accessor ────────────────────────────────────────
_global_detector: DriftDetector | None = None


def get_drift_detector() -> DriftDetector:
    """Return the process-global drift detector singleton."""
    global _global_detector
    if _global_detector is None:
        _global_detector = DriftDetector()
    return _global_detector
