"""Self-modifier — runtime governance enforcement for autonomous edits.

This module takes a proposed change (a file path or set of paths) and
validates it against `architecture/boundaries.yaml` and
`architecture/governance.yaml`. It produces a verdict that the RFC
proposer or an automated tool must respect before applying any edit.

Principles:
- Fail secure: unknown paths → require human review
- Never touch immutable paths regardless of risk level
- Log every verdict for audit

This is a read-only validator. It does NOT perform the modification;
it only says whether the modification is allowed.
"""

from __future__ import annotations

import fnmatch
import logging
import pathlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import yaml

logger = logging.getLogger(__name__)


def _glob_to_regex(glob: str) -> re.Pattern[str]:
    """Convert a `**` aware glob to a regex.

    Supports:
    - `**`            matches any number of path segments (including zero)
    - `*`             matches any character except `/`
    - `?`             matches a single character except `/`
    - `{a,b,c}`       brace expansion — matches any of the alternatives
    """
    parts: list[str] = []
    i = 0
    n = len(glob)
    while i < n:
        ch = glob[i]
        if glob[i : i + 2] == "**":
            parts.append(".*")
            i += 2
            if i < n and glob[i] == "/":
                i += 1  # consume following slash — **/x means "any depth x"
        elif ch == "*":
            parts.append("[^/]*")
            i += 1
        elif ch == "?":
            parts.append("[^/]")
            i += 1
        elif ch == "{":
            # Find matching }
            close = glob.find("}", i)
            if close == -1:
                parts.append("\\{")
                i += 1
                continue
            alternatives = glob[i + 1 : close].split(",")
            escaped = [re.escape(a) for a in alternatives]
            parts.append("(?:" + "|".join(escaped) + ")")
            i = close + 1
        elif ch in ".+^$()|":
            parts.append("\\" + ch)
            i += 1
        else:
            parts.append(ch)
            i += 1
    pattern = "".join(parts)
    return re.compile(f"^{pattern}$")


def _glob_has_meta(glob: str) -> bool:
    """Return True iff glob needs regex conversion (vs fnmatch)."""
    return "**" in glob or "{" in glob


def _glob_match(path: str, glob: str) -> bool:
    """Match a path against a `**` and `{a,b}` aware glob."""
    if not _glob_has_meta(glob):
        return fnmatch.fnmatch(path, glob)
    return _glob_to_regex(glob).match(path) is not None


@dataclass
class ModificationVerdict:
    """Result of a self-modifier check."""

    allowed: bool
    tier: str  # "autonomous_safe" | "human_review_required" | "immutable" | "unknown"
    reason: str
    path: str
    matched_rule: str | None = None
    required_reviewers: int = 0
    escalation: str | None = None
    decided_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "tier": self.tier,
            "reason": self.reason,
            "path": self.path,
            "matched_rule": self.matched_rule,
            "required_reviewers": self.required_reviewers,
            "escalation": self.escalation,
            "decided_at": self.decided_at.isoformat(),
        }


class SelfModifier:
    """Runtime enforcement of governance boundaries.

    Loads `architecture/boundaries.yaml` once and uses fnmatch glob
    matching to decide the tier for any given file path.
    """

    DEFAULT_BOUNDARIES_PATH = pathlib.Path(__file__).parent.parent / "architecture" / "boundaries.yaml"

    def __init__(
        self,
        boundaries_path: pathlib.Path | None = None,
    ) -> None:
        self._boundaries_path = boundaries_path or self.DEFAULT_BOUNDARIES_PATH
        self._data: dict[str, Any] = {}
        self._verdicts_history: list[ModificationVerdict] = []
        self._load()

    def _load(self) -> None:
        if not self._boundaries_path.exists():
            logger.error(
                "self_modifier: boundaries.yaml missing at %s", self._boundaries_path
            )
            self._data = {}
            return
        with self._boundaries_path.open() as f:
            self._data = yaml.safe_load(f) or {}

    def reload(self) -> None:
        """Re-read boundaries.yaml (useful when it's updated in-memory tests)."""
        self._load()

    # ── Path validation ──────────────────────────────────────

    def _match_rule(
        self, path: str, bucket: list[dict[str, Any]] | None
    ) -> dict[str, Any] | None:
        """Return the first matching rule dict in the bucket, or None.

        Uses `**` aware glob matching (via _glob_match).
        """
        if not bucket:
            return None
        for rule in bucket:
            glob = rule.get("path_glob", "")
            if not glob:
                continue
            if _glob_match(path, glob):
                # Check exclusion list
                exclude = rule.get("exclude") or []
                if isinstance(exclude, list):
                    excluded = any(_glob_match(path, ex) for ex in exclude)
                    if excluded:
                        continue
                return rule
        return None

    def check(self, path: str) -> ModificationVerdict:
        """Return a verdict for modifying *path*.

        Fail-secure ordering:
        1. Immutable paths → always denied
        2. Human-review paths → allowed only through RFC flow
        3. Autonomous-safe paths → allowed
        4. Anything else → unknown (treated as human-review)
        """
        # 1. Immutable — absolute denial
        imm = self._match_rule(path, self._data.get("immutable"))
        if imm:
            verdict = ModificationVerdict(
                allowed=False,
                tier="immutable",
                reason=imm.get("reason", "path is immutable"),
                path=path,
                matched_rule=imm.get("path_glob"),
                escalation=imm.get("escalation"),
            )
            self._record(verdict)
            logger.warning(
                "self_modifier: DENIED path=%s (immutable: %s)",
                path,
                verdict.reason,
            )
            return verdict

        # 2. Human review required — NOT autonomously allowed
        hr = self._match_rule(path, self._data.get("human_review_required"))
        if hr:
            verdict = ModificationVerdict(
                allowed=False,
                tier="human_review_required",
                reason=hr.get("reason", "path requires human review"),
                path=path,
                matched_rule=hr.get("path_glob"),
                required_reviewers=int(hr.get("required_reviewers", 1)),
            )
            self._record(verdict)
            logger.info(
                "self_modifier: review-required path=%s (%s)",
                path,
                verdict.reason,
            )
            return verdict

        # 3. Autonomous safe — allowed
        auto = self._match_rule(path, self._data.get("autonomous_safe"))
        if auto:
            verdict = ModificationVerdict(
                allowed=True,
                tier="autonomous_safe",
                reason=auto.get("reason", "autonomous-safe zone"),
                path=path,
                matched_rule=auto.get("path_glob"),
            )
            self._record(verdict)
            return verdict

        # 4. Unknown → fail secure (treat as human-review)
        verdict = ModificationVerdict(
            allowed=False,
            tier="unknown",
            reason=(
                "path not listed in any boundaries tier — fail-secure default "
                "requires explicit declaration in architecture/boundaries.yaml"
            ),
            path=path,
            required_reviewers=1,
        )
        self._record(verdict)
        logger.warning("self_modifier: unknown-path fail-secure path=%s", path)
        return verdict

    def check_many(self, paths: list[str]) -> dict[str, ModificationVerdict]:
        """Check multiple paths and return a dict keyed by path."""
        return {p: self.check(p) for p in paths}

    def validate_proposal(self, proposal_paths: list[str]) -> bool:
        """Quick-pass validator: True iff every path is allowed.

        Use when evaluating a proposal that touches multiple files.
        """
        return all(self.check(p).allowed for p in proposal_paths)

    # ── Introspection ─────────────────────────────────────────

    def _record(self, verdict: ModificationVerdict) -> None:
        self._verdicts_history.append(verdict)
        # Cap in-memory history to 1000 entries
        if len(self._verdicts_history) > 1000:
            self._verdicts_history = self._verdicts_history[-1000:]

    @property
    def recent_verdicts(self) -> list[ModificationVerdict]:
        return list(self._verdicts_history[-50:])

    @property
    def stats(self) -> dict[str, Any]:
        total = len(self._verdicts_history)
        denied = sum(1 for v in self._verdicts_history if not v.allowed)
        by_tier: dict[str, int] = {}
        for v in self._verdicts_history:
            by_tier[v.tier] = by_tier.get(v.tier, 0) + 1
        return {
            "total_checks": total,
            "total_denied": denied,
            "deny_rate": denied / total if total else 0.0,
            "by_tier": by_tier,
        }

    # ── Governance-rule introspection ─────────────────────────
    def list_immutable_globs(self) -> list[str]:
        return [r.get("path_glob", "") for r in self._data.get("immutable", [])]

    def list_human_review_globs(self) -> list[str]:
        return [
            r.get("path_glob", "") for r in self._data.get("human_review_required", [])
        ]

    def list_autonomous_safe_globs(self) -> list[str]:
        return [r.get("path_glob", "") for r in self._data.get("autonomous_safe", [])]


# ── Singleton accessor ────────────────────────────────────────
_global_modifier: SelfModifier | None = None


def get_self_modifier() -> SelfModifier:
    """Return the process-global self-modifier singleton."""
    global _global_modifier
    if _global_modifier is None:
        _global_modifier = SelfModifier()
    return _global_modifier
