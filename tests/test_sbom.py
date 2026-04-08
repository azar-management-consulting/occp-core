"""Tests for security.sbom — SBOM per Version (REQ-TSF-03).

Covers:
- SBOMComponent: creation, auto license_risk, to_dict/from_dict
- SBOM: creation, add_component, to_cyclonedx, from_cyclonedx, content_hash
- SBOMGenerator: generate with dependencies
- LicensePolicyChecker: default policy, custom policy, allowlist override
- License classification: classify_license for all risk levels
- Serialization: to_json/from_json round-trip
"""

from __future__ import annotations

import json
import time
import pytest

from security.sbom import (
    CYCLONEDX_BOM_FORMAT,
    CYCLONEDX_SPEC_VERSION,
    LicensePolicyChecker,
    LicensePolicyViolation,
    LicenseRisk,
    SBOM,
    SBOMComponent,
    SBOMGenerator,
    classify_license,
)


# ---------------------------------------------------------------------------
# classify_license
# ---------------------------------------------------------------------------

class TestClassifyLicense:
    def test_permissive(self) -> None:
        assert classify_license("MIT") == LicenseRisk.PERMISSIVE
        assert classify_license("Apache-2.0") == LicenseRisk.PERMISSIVE
        assert classify_license("BSD-3-Clause") == LicenseRisk.PERMISSIVE
        assert classify_license("ISC") == LicenseRisk.PERMISSIVE

    def test_weak_copyleft(self) -> None:
        assert classify_license("LGPL-3.0-only") == LicenseRisk.WEAK_COPYLEFT
        assert classify_license("MPL-2.0") == LicenseRisk.WEAK_COPYLEFT

    def test_strong_copyleft(self) -> None:
        assert classify_license("GPL-3.0-only") == LicenseRisk.STRONG_COPYLEFT
        assert classify_license("AGPL-3.0-only") == LicenseRisk.STRONG_COPYLEFT

    def test_proprietary(self) -> None:
        assert classify_license("proprietary") == LicenseRisk.PROPRIETARY
        assert classify_license("commercial") == LicenseRisk.PROPRIETARY

    def test_unknown(self) -> None:
        assert classify_license("SomeWeirdLicense") == LicenseRisk.UNKNOWN
        assert classify_license("") == LicenseRisk.UNKNOWN


# ---------------------------------------------------------------------------
# SBOMComponent
# ---------------------------------------------------------------------------

class TestSBOMComponent:
    def test_create(self) -> None:
        c = SBOMComponent(name="requests", version="2.31.0")
        assert c.name == "requests"
        assert c.version == "2.31.0"

    def test_auto_license_risk(self) -> None:
        c = SBOMComponent(name="x", version="1.0", license_id="MIT")
        assert c.license_risk == "permissive"

    def test_auto_license_risk_copyleft(self) -> None:
        c = SBOMComponent(name="x", version="1.0", license_id="GPL-3.0-only")
        assert c.license_risk == "strong-copyleft"

    def test_no_auto_risk_without_license(self) -> None:
        c = SBOMComponent(name="x", version="1.0")
        assert c.license_risk == ""

    def test_explicit_risk_not_overridden(self) -> None:
        c = SBOMComponent(name="x", version="1.0", license_id="MIT", license_risk="custom")
        assert c.license_risk == "custom"

    def test_to_dict_minimal(self) -> None:
        c = SBOMComponent(name="pkg", version="1.0")
        d = c.to_dict()
        assert d["name"] == "pkg"
        assert d["version"] == "1.0"
        assert d["type"] == "library"
        assert "purl" not in d
        assert "licenses" not in d

    def test_to_dict_full(self) -> None:
        c = SBOMComponent(
            name="pkg", version="1.0",
            purl="pkg:pypi/pkg@1.0",
            license_id="MIT",
            hash_sha256="abc123",
            author="Author",
            description="Desc",
        )
        d = c.to_dict()
        assert d["purl"] == "pkg:pypi/pkg@1.0"
        assert d["licenses"][0]["license"]["id"] == "MIT"
        assert d["hashes"][0]["content"] == "abc123"
        assert d["author"] == "Author"

    def test_from_dict_roundtrip(self) -> None:
        c = SBOMComponent(
            name="pkg", version="2.0",
            purl="pkg:pypi/pkg@2.0",
            license_id="Apache-2.0",
            hash_sha256="def456",
        )
        d = c.to_dict()
        restored = SBOMComponent.from_dict(d)
        assert restored.name == "pkg"
        assert restored.version == "2.0"
        assert restored.purl == "pkg:pypi/pkg@2.0"
        assert restored.license_id == "Apache-2.0"
        assert restored.hash_sha256 == "def456"

    def test_from_dict_minimal(self) -> None:
        d = {"name": "x", "version": "1.0", "type": "library"}
        c = SBOMComponent.from_dict(d)
        assert c.name == "x"
        assert c.license_id == ""
        assert c.hash_sha256 == ""


# ---------------------------------------------------------------------------
# SBOM
# ---------------------------------------------------------------------------

class TestSBOM:
    def test_create(self) -> None:
        sbom = SBOM(skill_id="my-skill", skill_version="1.0.0")
        assert sbom.skill_id == "my-skill"
        assert sbom.component_count == 0
        assert sbom.generated_at > 0
        assert sbom.serial_number.startswith("urn:uuid:")

    def test_add_component(self) -> None:
        sbom = SBOM(skill_id="s", skill_version="1.0")
        sbom.add_component(SBOMComponent(name="a", version="1.0"))
        sbom.add_component(SBOMComponent(name="b", version="2.0"))
        assert sbom.component_count == 2

    def test_to_cyclonedx(self) -> None:
        sbom = SBOM(skill_id="s", skill_version="1.0")
        sbom.add_component(SBOMComponent(name="pkg", version="1.0", license_id="MIT"))
        cdx = sbom.to_cyclonedx()
        assert cdx["bomFormat"] == CYCLONEDX_BOM_FORMAT
        assert cdx["specVersion"] == CYCLONEDX_SPEC_VERSION
        assert cdx["metadata"]["component"]["name"] == "s"
        assert len(cdx["components"]) == 1
        assert cdx["components"][0]["name"] == "pkg"

    def test_from_cyclonedx_roundtrip(self) -> None:
        sbom = SBOM(skill_id="s", skill_version="2.0")
        sbom.add_component(SBOMComponent(name="a", version="1.0", license_id="MIT"))
        sbom.add_component(SBOMComponent(name="b", version="2.0", purl="pkg:pypi/b@2.0"))
        cdx = sbom.to_cyclonedx()
        restored = SBOM.from_cyclonedx(cdx)
        assert restored.skill_id == "s"
        assert restored.skill_version == "2.0"
        assert restored.component_count == 2

    def test_to_json_from_json(self) -> None:
        sbom = SBOM(skill_id="s", skill_version="1.0")
        sbom.add_component(SBOMComponent(name="x", version="1.0"))
        j = sbom.to_json()
        parsed = json.loads(j)
        assert parsed["bomFormat"] == CYCLONEDX_BOM_FORMAT
        restored = SBOM.from_json(j)
        assert restored.component_count == 1

    def test_content_hash_deterministic(self) -> None:
        sbom = SBOM(
            skill_id="s", skill_version="1.0",
            generated_at=1000.0, serial_number="urn:uuid:test",
        )
        sbom.add_component(SBOMComponent(name="a", version="1.0"))
        h1 = sbom.content_hash()
        h2 = sbom.content_hash()
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex

    def test_content_hash_changes_with_content(self) -> None:
        sbom1 = SBOM(
            skill_id="s", skill_version="1.0",
            generated_at=1000.0, serial_number="urn:uuid:test",
        )
        sbom1.add_component(SBOMComponent(name="a", version="1.0"))

        sbom2 = SBOM(
            skill_id="s", skill_version="1.0",
            generated_at=1000.0, serial_number="urn:uuid:test",
        )
        sbom2.add_component(SBOMComponent(name="a", version="2.0"))

        assert sbom1.content_hash() != sbom2.content_hash()

    def test_metadata_tools(self) -> None:
        sbom = SBOM(skill_id="s", skill_version="1.0", tool_name="custom", tool_version="2.0")
        cdx = sbom.to_cyclonedx()
        assert cdx["metadata"]["tools"][0]["name"] == "custom"
        assert cdx["metadata"]["tools"][0]["version"] == "2.0"


# ---------------------------------------------------------------------------
# SBOMGenerator
# ---------------------------------------------------------------------------

class TestSBOMGenerator:
    def test_generate_empty(self) -> None:
        gen = SBOMGenerator()
        sbom = gen.generate("skill-1", "1.0.0")
        assert sbom.skill_id == "skill-1"
        assert sbom.component_count == 0

    def test_generate_with_dependencies(self) -> None:
        gen = SBOMGenerator()
        deps = [
            {"name": "requests", "version": "2.31.0", "license": "Apache-2.0",
             "purl": "pkg:pypi/requests@2.31.0"},
            {"name": "click", "version": "8.1.7", "license": "BSD-3-Clause"},
        ]
        sbom = gen.generate("skill-1", "1.0.0", dependencies=deps)
        assert sbom.component_count == 2
        names = {c.name for c in sbom.components}
        assert names == {"requests", "click"}

    def test_generate_preserves_license(self) -> None:
        gen = SBOMGenerator()
        deps = [{"name": "pkg", "version": "1.0", "license": "MIT"}]
        sbom = gen.generate("s", "1.0", dependencies=deps)
        assert sbom.components[0].license_id == "MIT"
        assert sbom.components[0].license_risk == "permissive"

    def test_generate_with_hash(self) -> None:
        gen = SBOMGenerator()
        deps = [{"name": "pkg", "version": "1.0", "hash_sha256": "deadbeef"}]
        sbom = gen.generate("s", "1.0", dependencies=deps)
        assert sbom.components[0].hash_sha256 == "deadbeef"


# ---------------------------------------------------------------------------
# LicensePolicyChecker
# ---------------------------------------------------------------------------

class TestLicensePolicyChecker:
    def test_default_blocks_strong_copyleft(self) -> None:
        checker = LicensePolicyChecker()
        sbom = SBOM(skill_id="s", skill_version="1.0")
        sbom.add_component(SBOMComponent(name="gpl-pkg", version="1.0", license_id="GPL-3.0-only"))
        violations = checker.check(sbom)
        assert len(violations) == 1
        assert "strong-copyleft" in violations[0]

    def test_default_blocks_unknown(self) -> None:
        checker = LicensePolicyChecker()
        sbom = SBOM(skill_id="s", skill_version="1.0")
        sbom.add_component(SBOMComponent(name="weird", version="1.0", license_id="WeirdLicense"))
        violations = checker.check(sbom)
        assert len(violations) == 1
        assert "unknown" in violations[0]

    def test_permissive_passes(self) -> None:
        checker = LicensePolicyChecker()
        sbom = SBOM(skill_id="s", skill_version="1.0")
        sbom.add_component(SBOMComponent(name="ok", version="1.0", license_id="MIT"))
        sbom.add_component(SBOMComponent(name="ok2", version="1.0", license_id="Apache-2.0"))
        violations = checker.check(sbom)
        assert violations == []

    def test_no_license_is_violation(self) -> None:
        checker = LicensePolicyChecker()
        sbom = SBOM(skill_id="s", skill_version="1.0")
        sbom.add_component(SBOMComponent(name="nolic", version="1.0"))
        violations = checker.check(sbom)
        assert len(violations) == 1
        assert "no license" in violations[0].lower()

    def test_custom_blocked_risks(self) -> None:
        checker = LicensePolicyChecker(blocked_risks=["weak-copyleft"])
        sbom = SBOM(skill_id="s", skill_version="1.0")
        sbom.add_component(SBOMComponent(name="lgpl", version="1.0", license_id="LGPL-3.0-only"))
        violations = checker.check(sbom)
        assert len(violations) == 1
        assert "weak-copyleft" in violations[0]

    def test_allowlist_override(self) -> None:
        """Explicit allowlist overrides risk classification."""
        checker = LicensePolicyChecker(allowed_licenses={"GPL-3.0-only"})
        sbom = SBOM(skill_id="s", skill_version="1.0")
        sbom.add_component(SBOMComponent(name="gpl", version="1.0", license_id="GPL-3.0-only"))
        violations = checker.check(sbom)
        assert violations == []

    def test_multiple_violations(self) -> None:
        checker = LicensePolicyChecker()
        sbom = SBOM(skill_id="s", skill_version="1.0")
        sbom.add_component(SBOMComponent(name="a", version="1.0", license_id="GPL-3.0-only"))
        sbom.add_component(SBOMComponent(name="b", version="1.0"))  # no license
        sbom.add_component(SBOMComponent(name="c", version="1.0", license_id="MIT"))  # ok
        violations = checker.check(sbom)
        assert len(violations) == 2

    def test_empty_sbom_no_violations(self) -> None:
        checker = LicensePolicyChecker()
        sbom = SBOM(skill_id="s", skill_version="1.0")
        violations = checker.check(sbom)
        assert violations == []


# ---------------------------------------------------------------------------
# LicenseRisk enum
# ---------------------------------------------------------------------------

class TestLicenseRiskEnum:
    def test_values(self) -> None:
        assert LicenseRisk.PERMISSIVE.value == "permissive"
        assert LicenseRisk.WEAK_COPYLEFT.value == "weak-copyleft"
        assert LicenseRisk.STRONG_COPYLEFT.value == "strong-copyleft"
        assert LicenseRisk.PROPRIETARY.value == "proprietary"
        assert LicenseRisk.UNKNOWN.value == "unknown"
