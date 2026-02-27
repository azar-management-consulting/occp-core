"""Supply-chain security for MCP connectors and skills.

Provides:
- PackageAllowlist: validates MCP packages against curated registry
- SkillIntegrityChecker: verifies skill hashes/signatures
- SupplyChainScanner: orchestrates pre-install security checks

All installs are gated: unlisted packages are blocked by default.
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# MCP Package Allowlist
# ---------------------------------------------------------------------------

# Curated registry of known-safe MCP packages.
# Format: package_name → {min_version, publisher, integrity_notes}
_MCP_ALLOWLIST: dict[str, dict[str, Any]] = {
    "@anthropic/mcp-filesystem": {
        "publisher": "anthropic",
        "category": "core",
        "risk": "low",
    },
    "@anthropic/mcp-github": {
        "publisher": "anthropic",
        "category": "integration",
        "risk": "low",
    },
    "@anthropic/mcp-postgres": {
        "publisher": "anthropic",
        "category": "database",
        "risk": "medium",
    },
    "@anthropic/mcp-sqlite": {
        "publisher": "anthropic",
        "category": "database",
        "risk": "low",
    },
    "@anthropic/mcp-memory": {
        "publisher": "anthropic",
        "category": "core",
        "risk": "low",
    },
}

# Suspicious patterns in package names (typosquatting, homoglyph attacks)
_SUSPICIOUS_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"anthroplc|anthr0pic|anthropik", re.I),  # typosquatting
    re.compile(r"\.\.\/|\.\.\\", re.I),  # path traversal
    re.compile(r"[^\x00-\x7F]"),  # non-ASCII (homoglyph)
    re.compile(r"(eval|exec|spawn|child_process|require\()", re.I),  # code injection
    re.compile(r"(rm\s+-rf|del\s+/|format\s+c:)", re.I),  # destructive cmds
]


@dataclass
class PackageCheckResult:
    """Result of MCP package supply-chain check."""

    allowed: bool
    package: str
    reason: str = ""
    risk_level: str = "unknown"
    publisher: str = ""
    warnings: list[str] = field(default_factory=list)


class PackageAllowlist:
    """Validates MCP packages against the curated allowlist."""

    def __init__(self, extra_allowed: dict[str, dict[str, Any]] | None = None) -> None:
        self._allowlist = dict(_MCP_ALLOWLIST)
        if extra_allowed:
            self._allowlist.update(extra_allowed)

    def check(self, package_name: str) -> PackageCheckResult:
        """Check if a package is in the allowlist and free of suspicious patterns."""
        warnings: list[str] = []

        # Suspicious pattern scan
        for pat in _SUSPICIOUS_PATTERNS:
            if pat.search(package_name):
                return PackageCheckResult(
                    allowed=False,
                    package=package_name,
                    reason=f"Suspicious pattern detected: {pat.pattern}",
                    risk_level="critical",
                    warnings=["Package name matches known attack pattern"],
                )

        # Allowlist lookup
        entry = self._allowlist.get(package_name)
        if entry is None:
            return PackageCheckResult(
                allowed=False,
                package=package_name,
                reason=f"Package '{package_name}' not in curated allowlist",
                risk_level="high",
                warnings=["Unlisted packages require manual security review"],
            )

        # Package is allowed
        risk = entry.get("risk", "unknown")
        if risk == "medium":
            warnings.append("Medium-risk package — monitor for data access patterns")

        return PackageCheckResult(
            allowed=True,
            package=package_name,
            risk_level=risk,
            publisher=entry.get("publisher", ""),
            warnings=warnings,
        )

    @property
    def allowed_packages(self) -> list[str]:
        """Return list of all allowed package names."""
        return list(self._allowlist.keys())


# ---------------------------------------------------------------------------
# Skill Integrity Checker
# ---------------------------------------------------------------------------

@dataclass
class SkillCheckResult:
    """Result of skill integrity check."""

    valid: bool
    skill_id: str
    reason: str = ""
    hash_sha256: str = ""
    warnings: list[str] = field(default_factory=list)


class SkillIntegrityChecker:
    """Verifies skill definitions against known-good hashes.

    In Phase 1, all baseline skills are in-memory and trusted.
    This checker validates that skill metadata hasn't been tampered with.
    """

    def __init__(self) -> None:
        self._known_hashes: dict[str, str] = {}

    def register_hash(self, skill_id: str, content: str) -> str:
        """Register the SHA-256 hash of a skill's definition."""
        h = hashlib.sha256(content.encode("utf-8")).hexdigest()
        self._known_hashes[skill_id] = h
        return h

    def verify(self, skill_id: str, content: str) -> SkillCheckResult:
        """Verify a skill's content against its registered hash."""
        current_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

        known = self._known_hashes.get(skill_id)
        if known is None:
            # First-time registration (bootstrap)
            self._known_hashes[skill_id] = current_hash
            return SkillCheckResult(
                valid=True,
                skill_id=skill_id,
                hash_sha256=current_hash,
                warnings=["First registration — hash stored for future verification"],
            )

        if current_hash != known:
            return SkillCheckResult(
                valid=False,
                skill_id=skill_id,
                reason="Hash mismatch — skill definition may have been tampered with",
                hash_sha256=current_hash,
                warnings=[f"Expected: {known[:16]}... Got: {current_hash[:16]}..."],
            )

        return SkillCheckResult(
            valid=True,
            skill_id=skill_id,
            hash_sha256=current_hash,
        )

    def check_trusted(self, skill: dict[str, Any]) -> SkillCheckResult:
        """Check if a skill dict has the trusted flag and valid content."""
        skill_id = skill.get("id", "unknown")
        if not skill.get("trusted", False):
            return SkillCheckResult(
                valid=False,
                skill_id=skill_id,
                reason="Skill is not in trusted allowlist",
            )
        # Hash the canonical representation
        content = f"{skill.get('id', '')}/{skill.get('name', '')}/{skill.get('description', '')}"
        return self.verify(skill_id, content)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class SupplyChainScanner:
    """Orchestrates supply-chain security checks for MCP and skills.

    Combines PackageAllowlist + SkillIntegrityChecker into a single
    pre-install/pre-enable gate.
    """

    def __init__(self) -> None:
        self.package_checker = PackageAllowlist()
        self.skill_checker = SkillIntegrityChecker()

    def scan_mcp_install(self, package_name: str) -> PackageCheckResult:
        """Gate check before MCP connector installation."""
        result = self.package_checker.check(package_name)
        if not result.allowed:
            logger.warning(
                "MCP install blocked: package=%s reason=%s",
                package_name,
                result.reason,
            )
        else:
            logger.info(
                "MCP install approved: package=%s risk=%s",
                package_name,
                result.risk_level,
            )
        return result

    def scan_skill_enable(self, skill: dict[str, Any]) -> SkillCheckResult:
        """Gate check before skill enable."""
        result = self.skill_checker.check_trusted(skill)
        if not result.valid:
            logger.warning(
                "Skill enable blocked: skill=%s reason=%s",
                skill.get("id", "?"),
                result.reason,
            )
        else:
            logger.info(
                "Skill enable approved: skill=%s hash=%s",
                skill.get("id", "?"),
                result.hash_sha256[:16],
            )
        return result
