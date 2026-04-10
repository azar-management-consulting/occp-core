"""Mandatory SBOM per Version — REQ-TSF-03.

Every skill version includes CycloneDX SBOM listing all dependencies
with license information. EU Cyber Resilience Act compliance.

Acceptance Tests:
  (1) ``occp skill info my-skill --sbom`` displays dependency tree.
  (2) SBOM generated automatically during ``occp skill publish``.
  (3) License policy violations flagged at install.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

# CycloneDX spec version
CYCLONEDX_SPEC_VERSION = "1.5"
CYCLONEDX_BOM_FORMAT = "CycloneDX"


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class LicenseRisk(str, Enum):
    """License risk classification."""
    PERMISSIVE = "permissive"       # MIT, Apache-2.0, BSD
    WEAK_COPYLEFT = "weak-copyleft" # LGPL, MPL
    STRONG_COPYLEFT = "strong-copyleft"  # GPL, AGPL
    PROPRIETARY = "proprietary"
    UNKNOWN = "unknown"


class ComponentType(str, Enum):
    """CycloneDX component type."""
    LIBRARY = "library"
    FRAMEWORK = "framework"
    APPLICATION = "application"
    DEVICE = "device"
    FILE = "file"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class SBOMError(Exception):
    """Base error for SBOM operations."""


class LicensePolicyViolation(SBOMError):
    """License policy violation detected in SBOM."""


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

# Known permissive licenses
_PERMISSIVE_LICENSES = {
    "MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC",
    "Unlicense", "CC0-1.0", "0BSD", "BlueOak-1.0.0",
}

_WEAK_COPYLEFT_LICENSES = {
    "LGPL-2.1-only", "LGPL-3.0-only", "MPL-2.0", "LGPL-2.1-or-later",
    "LGPL-3.0-or-later", "EPL-2.0",
}

_STRONG_COPYLEFT_LICENSES = {
    "GPL-2.0-only", "GPL-3.0-only", "AGPL-3.0-only",
    "GPL-2.0-or-later", "GPL-3.0-or-later", "AGPL-3.0-or-later",
}


def classify_license(spdx_id: str) -> LicenseRisk:
    """Classify a SPDX license identifier by risk level."""
    if spdx_id in _PERMISSIVE_LICENSES:
        return LicenseRisk.PERMISSIVE
    if spdx_id in _WEAK_COPYLEFT_LICENSES:
        return LicenseRisk.WEAK_COPYLEFT
    if spdx_id in _STRONG_COPYLEFT_LICENSES:
        return LicenseRisk.STRONG_COPYLEFT
    if spdx_id.lower() in ("proprietary", "commercial"):
        return LicenseRisk.PROPRIETARY
    return LicenseRisk.UNKNOWN


@dataclass
class SBOMComponent:
    """A single dependency component in the SBOM."""

    name: str
    version: str
    purl: str = ""                     # Package URL (pkg:pypi/requests@2.31.0)
    component_type: str = "library"
    license_id: str = ""               # SPDX identifier
    license_risk: str = ""
    hash_sha256: str = ""
    author: str = ""
    description: str = ""

    def __post_init__(self) -> None:
        if not self.license_risk and self.license_id:
            self.license_risk = classify_license(self.license_id).value

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "type": self.component_type,
            "name": self.name,
            "version": self.version,
        }
        if self.purl:
            d["purl"] = self.purl
        if self.license_id:
            d["licenses"] = [{"license": {"id": self.license_id}}]
        if self.hash_sha256:
            d["hashes"] = [{"alg": "SHA-256", "content": self.hash_sha256}]
        if self.author:
            d["author"] = self.author
        if self.description:
            d["description"] = self.description
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SBOMComponent:
        license_id = ""
        licenses = data.get("licenses", [])
        if licenses and isinstance(licenses[0], dict):
            lic = licenses[0].get("license", {})
            license_id = lic.get("id", "")

        hash_sha256 = ""
        hashes = data.get("hashes", [])
        for h in hashes:
            if h.get("alg") == "SHA-256":
                hash_sha256 = h.get("content", "")
                break

        return cls(
            name=data["name"],
            version=data["version"],
            purl=data.get("purl", ""),
            component_type=data.get("type", "library"),
            license_id=license_id,
            hash_sha256=hash_sha256,
            author=data.get("author", ""),
            description=data.get("description", ""),
        )


@dataclass
class SBOM:
    """CycloneDX-compatible Software Bill of Materials."""

    skill_id: str
    skill_version: str
    components: list[SBOMComponent] = field(default_factory=list)
    serial_number: str = ""
    generated_at: float = 0.0
    tool_name: str = "occp-sbom"
    tool_version: str = "1.0.0"

    def __post_init__(self) -> None:
        if not self.generated_at:
            self.generated_at = time.time()
        if not self.serial_number:
            content = f"{self.skill_id}:{self.skill_version}:{self.generated_at}"
            self.serial_number = "urn:uuid:" + hashlib.sha256(
                content.encode()
            ).hexdigest()[:32]

    @property
    def component_count(self) -> int:
        return len(self.components)

    def add_component(self, component: SBOMComponent) -> None:
        self.components.append(component)

    def to_cyclonedx(self) -> dict[str, Any]:
        """Export as CycloneDX JSON format."""
        return {
            "bomFormat": CYCLONEDX_BOM_FORMAT,
            "specVersion": CYCLONEDX_SPEC_VERSION,
            "serialNumber": self.serial_number,
            "version": 1,
            "metadata": {
                "timestamp": time.strftime(
                    "%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.generated_at)
                ),
                "tools": [{"name": self.tool_name, "version": self.tool_version}],
                "component": {
                    "type": "application",
                    "name": self.skill_id,
                    "version": self.skill_version,
                },
            },
            "components": [c.to_dict() for c in self.components],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_cyclonedx(), sort_keys=True, indent=2)

    @classmethod
    def from_cyclonedx(cls, data: dict[str, Any]) -> SBOM:
        meta = data.get("metadata", {})
        comp_meta = meta.get("component", {})
        tools = meta.get("tools", [{}])
        tool = tools[0] if tools else {}

        sbom = cls(
            skill_id=comp_meta.get("name", ""),
            skill_version=comp_meta.get("version", ""),
            serial_number=data.get("serialNumber", ""),
            tool_name=tool.get("name", "occp-sbom"),
            tool_version=tool.get("version", "1.0.0"),
        )
        for c_data in data.get("components", []):
            sbom.components.append(SBOMComponent.from_dict(c_data))
        return sbom

    @classmethod
    def from_json(cls, raw: str) -> SBOM:
        return cls.from_cyclonedx(json.loads(raw))

    def content_hash(self) -> str:
        """Deterministic hash of SBOM content for integrity verification."""
        canonical = json.dumps(self.to_cyclonedx(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()


# ---------------------------------------------------------------------------
# SBOMGenerator
# ---------------------------------------------------------------------------

class SBOMGenerator:
    """Generates CycloneDX SBOMs for skill versions."""

    def generate(
        self,
        skill_id: str,
        skill_version: str,
        dependencies: list[dict[str, Any]] | None = None,
    ) -> SBOM:
        """Generate an SBOM for a skill version.

        Args:
            skill_id: Skill identifier.
            skill_version: Version string.
            dependencies: List of dependency dicts with at least ``name`` and ``version``.

        Returns:
            SBOM with all components populated.
        """
        sbom = SBOM(skill_id=skill_id, skill_version=skill_version)

        for dep in (dependencies or []):
            comp = SBOMComponent(
                name=dep["name"],
                version=dep["version"],
                purl=dep.get("purl", ""),
                license_id=dep.get("license", ""),
                hash_sha256=dep.get("hash_sha256", ""),
                author=dep.get("author", ""),
                description=dep.get("description", ""),
            )
            sbom.add_component(comp)

        logger.info(
            "SBOM generated: skill=%s version=%s components=%d",
            skill_id, skill_version, sbom.component_count,
        )
        return sbom


# ---------------------------------------------------------------------------
# License policy checker
# ---------------------------------------------------------------------------

class LicensePolicyChecker:
    """Checks SBOM dependencies against license policy.

    Default policy: block strong-copyleft and unknown licenses.
    """

    def __init__(
        self,
        *,
        blocked_risks: list[str] | None = None,
        allowed_licenses: set[str] | None = None,
    ) -> None:
        self._blocked_risks = set(
            blocked_risks or [LicenseRisk.STRONG_COPYLEFT.value, LicenseRisk.UNKNOWN.value]
        )
        self._allowed_licenses = allowed_licenses  # override: explicit allowlist

    def check(self, sbom: SBOM) -> list[str]:
        """Check SBOM against license policy. Returns list of violations."""
        violations: list[str] = []

        for comp in sbom.components:
            if not comp.license_id:
                violations.append(
                    f"Component '{comp.name}@{comp.version}' has no license declared"
                )
                continue

            # Explicit allowlist overrides risk classification
            if self._allowed_licenses and comp.license_id in self._allowed_licenses:
                continue

            risk = classify_license(comp.license_id)
            if risk.value in self._blocked_risks:
                violations.append(
                    f"Component '{comp.name}@{comp.version}' has {risk.value} "
                    f"license ({comp.license_id})"
                )

        return violations
