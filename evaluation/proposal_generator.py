"""Proposal generator — produces ranked RFC candidates from:
- architectural issue registry (`architecture/issue_registry.yaml`)
- anomaly detector output (runtime metrics interpretation)
- governance validation (self_modifier)

This is the smallest professional working redesign engine that fits
current OCCP. It does NOT auto-apply proposals — it ranks them and
produces RFC markdown scaffolds for human review.

Design choices:
- Read-only input (no DB writes)
- Deterministic ranking (testable)
- Governance-aware (skips proposals that touch immutable paths)
- Plain text output (markdown) stored under `.planning/rfc/`
"""

from __future__ import annotations

import logging
import pathlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import yaml

from evaluation.self_modifier import SelfModifier, get_self_modifier
from observability.anomaly_detector import (
    Anomaly,
    AnomalyDetector,
    get_anomaly_detector,
)

logger = logging.getLogger(__name__)


# ── Data models ───────────────────────────────────────────────

@dataclass
class ProposalCandidate:
    """A ranked redesign candidate."""

    proposal_id: str
    title: str
    source_type: str  # "issue_registry" | "anomaly" | "critique"
    source_ref: str
    category: str
    severity: str
    affected_paths: list[str]
    evidence: str
    suggested_fix: str
    risk_of_fix: str
    score: float
    governance_verdict: str  # "allowed" | "human_review" | "immutable" | "unknown"
    governance_blockers: list[str] = field(default_factory=list)
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "title": self.title,
            "source_type": self.source_type,
            "source_ref": self.source_ref,
            "category": self.category,
            "severity": self.severity,
            "affected_paths": self.affected_paths,
            "evidence": self.evidence,
            "suggested_fix": self.suggested_fix,
            "risk_of_fix": self.risk_of_fix,
            "score": self.score,
            "governance_verdict": self.governance_verdict,
            "governance_blockers": self.governance_blockers,
            "generated_at": self.generated_at.isoformat(),
        }


# ── Generator ─────────────────────────────────────────────────

class ProposalGenerator:
    """Reads sources and produces ranked proposals.

    Sources:
    - issue_registry: architectural debt / known issues
    - anomalies: runtime-detected problems (optional)

    Ranking formula:
        score = severity_weight + category_boost + risk_penalty
    (lower-risk fixes score higher; critical security issues score highest)
    """

    DEFAULT_REGISTRY = (
        pathlib.Path(__file__).parent.parent / "architecture" / "issue_registry.yaml"
    )

    def __init__(
        self,
        registry_path: pathlib.Path | None = None,
        detector: AnomalyDetector | None = None,
        modifier: SelfModifier | None = None,
    ) -> None:
        self._registry_path = registry_path or self.DEFAULT_REGISTRY
        self._detector = detector
        self._modifier = modifier
        self._registry: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        if not self._registry_path.exists():
            logger.warning(
                "proposal_generator: registry missing at %s", self._registry_path
            )
            self._registry = {"issues": [], "ranking": {}}
            return
        with self._registry_path.open() as f:
            self._registry = yaml.safe_load(f) or {"issues": [], "ranking": {}}

    def reload(self) -> None:
        self._load()

    def _get_detector(self) -> AnomalyDetector:
        return self._detector or get_anomaly_detector()

    def _get_modifier(self) -> SelfModifier:
        return self._modifier or get_self_modifier()

    # ── Core ──────────────────────────────────────────────────

    def generate(
        self,
        include_anomalies: bool = True,
        include_resolved: bool = False,
    ) -> list[ProposalCandidate]:
        """Return a ranked list of proposal candidates."""
        issues = self._registry.get("issues", [])
        candidates: list[ProposalCandidate] = []

        for issue in issues:
            status = issue.get("status", "open")
            if status != "open" and not include_resolved:
                continue
            candidate = self._issue_to_candidate(issue)
            if candidate:
                candidates.append(candidate)

        if include_anomalies:
            for anomaly in self._get_detector().detect():
                candidate = self._anomaly_to_candidate(anomaly)
                if candidate:
                    candidates.append(candidate)

        # Sort by score descending
        candidates.sort(key=lambda c: c.score, reverse=True)
        logger.info("proposal_generator: generated %d candidates", len(candidates))
        return candidates

    # ── Scoring ───────────────────────────────────────────────

    def _compute_score(
        self,
        severity: str,
        category: str,
        risk_of_fix: str,
    ) -> float:
        ranking = self._registry.get("ranking", {})
        sev_w = ranking.get("severity_weight", {
            "critical": 10, "high": 5, "medium": 3, "low": 1, "info": 0
        })
        risk_p = ranking.get("risk_penalty", {
            "low": 0, "medium": -1, "high": -3
        })
        cat_b = ranking.get("category_boost", {
            "security": 2, "reliability": 2, "performance": 1,
            "maintainability": 0, "scalability": 0, "debt": 0
        })

        return float(
            sev_w.get(severity, 0)
            + cat_b.get(category, 0)
            + risk_p.get(risk_of_fix, 0)
        )

    # ── Converters ────────────────────────────────────────────

    def _issue_to_candidate(
        self, issue: dict[str, Any]
    ) -> ProposalCandidate | None:
        affected = issue.get("affected_paths", []) or []
        verdicts = self._get_modifier().check_many(affected)

        blockers = [
            v.path for v in verdicts.values()
            if v.tier == "immutable"
        ]
        # If any affected path is immutable, governance_verdict is immutable.
        # Human-review is fine — we still produce the candidate for review.
        if blockers:
            governance_verdict = "immutable"
        elif any(v.tier == "human_review_required" for v in verdicts.values()):
            governance_verdict = "human_review"
        elif all(v.tier == "autonomous_safe" for v in verdicts.values()) and verdicts:
            governance_verdict = "allowed"
        elif not verdicts:
            governance_verdict = "no_paths"
        else:
            governance_verdict = "unknown"

        return ProposalCandidate(
            proposal_id=issue.get("id", "ISS-???"),
            title=issue.get("title", "untitled"),
            source_type="issue_registry",
            source_ref=issue.get("id", "?"),
            category=issue.get("category", "debt"),
            severity=issue.get("severity", "low"),
            affected_paths=affected,
            evidence=issue.get("evidence", ""),
            suggested_fix=issue.get("suggested_fix", ""),
            risk_of_fix=issue.get("risk_of_fix", "medium"),
            score=self._compute_score(
                issue.get("severity", "low"),
                issue.get("category", "debt"),
                issue.get("risk_of_fix", "medium"),
            ),
            governance_verdict=governance_verdict,
            governance_blockers=blockers,
        )

    def _anomaly_to_candidate(
        self, anomaly: Anomaly
    ) -> ProposalCandidate:
        # Anomalies default to "reliability" category.
        return ProposalCandidate(
            proposal_id=f"ANO-{anomaly.code.replace('.', '-')}",
            title=f"anomaly: {anomaly.subject}",
            source_type="anomaly",
            source_ref=anomaly.code,
            category="reliability",
            severity=anomaly.severity if anomaly.severity != "info" else "low",
            affected_paths=[],  # anomalies do not directly map to paths
            evidence=anomaly.message,
            suggested_fix=(
                "Investigate runtime pattern, identify hot path, propose fix "
                "via follow-up RFC."
            ),
            risk_of_fix="medium",
            score=self._compute_score(
                anomaly.severity if anomaly.severity != "info" else "low",
                "reliability",
                "medium",
            ),
            governance_verdict="no_paths",
        )

    # ── RFC markdown generation ──────────────────────────────

    def to_rfc_markdown(self, candidate: ProposalCandidate) -> str:
        """Render a ProposalCandidate as an RFC markdown document."""
        md = [
            f"# RFC {candidate.proposal_id}: {candidate.title}",
            "",
            "**Status:** DRAFT (auto-generated from issue registry / anomalies)",
            f"**Type:** {candidate.category}",
            "**Author:** Claude Code (autonomous proposal generator)",
            f"**Created:** {candidate.generated_at.date().isoformat()}",
            f"**Severity:** {candidate.severity}",
            f"**Risk of fix:** {candidate.risk_of_fix}",
            f"**Score:** {candidate.score:.1f}",
            f"**Governance verdict:** {candidate.governance_verdict}",
            "",
            "---",
            "",
            "## 1. Summary",
            "",
            candidate.title,
            "",
            "## 2. Evidence",
            "",
            candidate.evidence or "(see source)",
            "",
            "## 3. Affected paths",
            "",
        ]
        if candidate.affected_paths:
            for p in candidate.affected_paths:
                md.append(f"- `{p}`")
        else:
            md.append("(no direct file paths — runtime anomaly)")

        md.extend([
            "",
            "## 4. Suggested fix",
            "",
            candidate.suggested_fix or "(needs human scoping)",
            "",
            "## 5. Governance check",
            "",
            f"- verdict: **{candidate.governance_verdict}**",
        ])
        if candidate.governance_blockers:
            md.append("- immutable blockers:")
            for b in candidate.governance_blockers:
                md.append(f"  - `{b}`")

        md.extend([
            "",
            "## 6. Next action",
            "",
            self._next_action(candidate),
            "",
            "---",
            "",
            f"**Generated at** {candidate.generated_at.isoformat()}",
            "**Source:** issue_registry.yaml + anomaly_detector",
            "",
        ])
        return "\n".join(md)

    @staticmethod
    def _next_action(candidate: ProposalCandidate) -> str:
        if candidate.governance_verdict == "immutable":
            return (
                "**BLOCKED** — proposal affects immutable paths. "
                "Escalate to Henry with full change plan + 2FA."
            )
        if candidate.governance_verdict == "human_review":
            return (
                "Draft PR with full implementation. Requires human review "
                "per `architecture/boundaries.yaml`."
            )
        if candidate.governance_verdict == "allowed":
            return (
                "Claude Code may autonomously implement this change in a "
                "feature branch. Run tests before merging."
            )
        return "Human triage required to classify this proposal."

    def write_rfc_to_disk(
        self,
        candidate: ProposalCandidate,
        output_dir: pathlib.Path | None = None,
    ) -> pathlib.Path:
        """Persist a candidate as `<output_dir>/NNNN-<slug>.md`.

        Returns the written path.
        """
        target_dir = output_dir or (
            pathlib.Path(__file__).parent.parent / ".planning" / "rfc"
        )
        target_dir.mkdir(parents=True, exist_ok=True)
        slug = re.sub(r"[^a-z0-9]+", "-", candidate.title.lower()).strip("-")[:60]
        # Use proposal_id in filename for stability
        filename = f"{candidate.proposal_id.lower()}-{slug}.md"
        path = target_dir / filename
        path.write_text(self.to_rfc_markdown(candidate))
        logger.info("proposal_generator: wrote RFC to %s", path)
        return path


# ── Singleton accessor ────────────────────────────────────────
_global_generator: ProposalGenerator | None = None


def get_proposal_generator() -> ProposalGenerator:
    """Return the process-global proposal generator singleton."""
    global _global_generator
    if _global_generator is None:
        _global_generator = ProposalGenerator()
    return _global_generator
