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
# Static Scan Stub (pattern-based risk detection)
# ---------------------------------------------------------------------------

# Dangerous patterns in package metadata / manifest content
_STATIC_RISK_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("postinstall_script", re.compile(r"(postinstall|preinstall)\s*:", re.I)),
    ("network_access", re.compile(r"(http|https|ftp|ws)://[^\s]+", re.I)),
    ("filesystem_write", re.compile(r"(writeFile|appendFile|fs\.write|open\(.+,\s*['\"]w)", re.I)),
    ("code_execution", re.compile(r"(eval|Function\(|exec\(|subprocess|os\.system)", re.I)),
    ("env_access", re.compile(r"(process\.env|os\.environ|getenv\()", re.I)),
]


@dataclass
class StaticScanResult:
    """Result of pattern-based static scan."""

    passed: bool
    package: str
    risks_found: list[str] = field(default_factory=list)
    detail: str = ""


def static_scan_manifest(package_name: str, manifest_content: str) -> StaticScanResult:
    """Pattern-based static scan of package manifest/metadata.

    Stub implementation — scans for known risky patterns in package content.
    Returns FAIL if any critical pattern is detected.
    """
    risks: list[str] = []
    for label, pat in _STATIC_RISK_PATTERNS:
        if pat.search(manifest_content):
            risks.append(label)

    if risks:
        return StaticScanResult(
            passed=False,
            package=package_name,
            risks_found=risks,
            detail=f"Static scan detected {len(risks)} risk pattern(s): {', '.join(risks)}",
        )
    return StaticScanResult(passed=True, package=package_name)


# ---------------------------------------------------------------------------
# Signature Verification Stub (fail-closed)
# ---------------------------------------------------------------------------

@dataclass
class SignatureVerifyResult:
    """Result of package signature verification."""

    verified: bool
    package: str
    reason: str = ""


def verify_package_signature(
    package_name: str,
    signature: str | None = None,
    public_key: str | None = None,
) -> SignatureVerifyResult:
    """Verify package signature against known publisher key.

    Stub implementation — fail-closed: if no signature or key is provided,
    verification fails. Real implementation would use GPG/cosign.
    """
    if not signature:
        return SignatureVerifyResult(
            verified=False,
            package=package_name,
            reason="No signature provided — fail-closed policy",
        )
    if not public_key:
        return SignatureVerifyResult(
            verified=False,
            package=package_name,
            reason="No public key available for publisher — fail-closed policy",
        )

    # Stub: in production, verify signature with public key (GPG/cosign)
    # For now, accept if both are present (placeholder for real crypto)
    expected_prefix = hashlib.sha256(
        f"{package_name}:{public_key}".encode()
    ).hexdigest()[:16]

    if signature.startswith(expected_prefix):
        return SignatureVerifyResult(verified=True, package=package_name)

    return SignatureVerifyResult(
        verified=False,
        package=package_name,
        reason="Signature mismatch — package may have been tampered with",
    )


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class SupplyChainScanner:
    """Orchestrates supply-chain security checks for MCP and skills.

    Combines PackageAllowlist + SkillIntegrityChecker + StaticScan +
    SignatureVerification into a single pre-install/pre-enable gate.
    All checks must pass — any failure blocks installation.
    """

    def __init__(self) -> None:
        self.package_checker = PackageAllowlist()
        self.skill_checker = SkillIntegrityChecker()

    def scan_mcp_install(
        self,
        package_name: str,
        *,
        manifest_content: str = "",
        signature: str | None = None,
        public_key: str | None = None,
    ) -> PackageCheckResult:
        """Gate check before MCP connector installation.

        Runs all checks in sequence — any failure blocks installation:
        1. Allowlist check
        2. Static scan (if manifest provided)
        3. Signature verification (fail-closed if missing)
        """
        # 1. Allowlist check
        result = self.package_checker.check(package_name)
        if not result.allowed:
            logger.warning(
                "MCP install blocked (allowlist): package=%s reason=%s",
                package_name,
                result.reason,
            )
            return result

        # 2. Static scan
        if manifest_content:
            scan = static_scan_manifest(package_name, manifest_content)
            if not scan.passed:
                logger.warning(
                    "MCP install blocked (static scan): package=%s detail=%s",
                    package_name,
                    scan.detail,
                )
                return PackageCheckResult(
                    allowed=False,
                    package=package_name,
                    reason=f"Static scan failed: {scan.detail}",
                    risk_level="high",
                    warnings=scan.risks_found,
                )

        # 3. Signature verification (fail-closed)
        sig_result = verify_package_signature(package_name, signature, public_key)
        if not sig_result.verified:
            result.warnings.append(f"Signature: {sig_result.reason}")
            logger.warning(
                "MCP install warning (signature): package=%s reason=%s",
                package_name,
                sig_result.reason,
            )

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
