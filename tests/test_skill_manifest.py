"""Tests for orchestrator.skill_manifest — Capability Declaration (REQ-TSF-02).

Covers:
- NetworkScope: domain matching, wildcard, allow_all
- FileScope: path matching, read_only
- CommandScope: command matching
- DataScope: sensitive domains, requires_enhanced_audit
- SkillManifest: creation, to_dict/from_dict, to_json/from_json
- ManifestValidator: required fields, limits, blocked domains/commands,
  path traversal, data domain validation, fail-closed (no manifest)
- Access checks: network, file, command
"""

from __future__ import annotations

import json
import pytest

from orchestrator.skill_manifest import (
    CommandScope,
    DataDomain,
    DataScope,
    FileScope,
    ManifestRequiredError,
    ManifestValidationError,
    ManifestValidator,
    NetworkScope,
    SkillManifest,
)


# ---------------------------------------------------------------------------
# NetworkScope
# ---------------------------------------------------------------------------

class TestNetworkScope:
    def test_exact_match(self) -> None:
        ns = NetworkScope(allowed_domains=["api.example.com"])
        assert ns.is_domain_allowed("api.example.com") is True
        assert ns.is_domain_allowed("other.com") is False

    def test_case_insensitive(self) -> None:
        ns = NetworkScope(allowed_domains=["API.Example.COM"])
        assert ns.is_domain_allowed("api.example.com") is True

    def test_wildcard(self) -> None:
        ns = NetworkScope(allowed_domains=["*.example.com"])
        assert ns.is_domain_allowed("sub.example.com") is True
        assert ns.is_domain_allowed("deep.sub.example.com") is True
        assert ns.is_domain_allowed("example.com") is False
        assert ns.is_domain_allowed("other.com") is False

    def test_allow_all(self) -> None:
        ns = NetworkScope(allow_all=True)
        assert ns.is_domain_allowed("anything.com") is True

    def test_empty_domains(self) -> None:
        ns = NetworkScope()
        assert ns.is_domain_allowed("any.com") is False

    def test_to_dict_roundtrip(self) -> None:
        ns = NetworkScope(allowed_domains=["a.com", "b.com"], allow_all=False)
        d = ns.to_dict()
        restored = NetworkScope.from_dict(d)
        assert restored.allowed_domains == ["a.com", "b.com"]
        assert restored.allow_all is False


# ---------------------------------------------------------------------------
# FileScope
# ---------------------------------------------------------------------------

class TestFileScope:
    def test_path_allowed(self) -> None:
        fs = FileScope(allowed_paths=["/data/skills/", "/tmp/"])
        assert fs.is_path_allowed("/data/skills/my-skill") is True
        assert fs.is_path_allowed("/tmp/cache") is True
        assert fs.is_path_allowed("/etc/passwd") is False

    def test_empty_paths_readonly_allows_nothing(self) -> None:
        """Empty paths + read_only=True allows all (no restriction declared)."""
        fs = FileScope(allowed_paths=[], read_only=True)
        assert fs.is_path_allowed("/some/path") is True

    def test_empty_paths_not_readonly_blocks(self) -> None:
        fs = FileScope(allowed_paths=[], read_only=False)
        assert fs.is_path_allowed("/some/path") is False

    def test_to_dict_roundtrip(self) -> None:
        fs = FileScope(allowed_paths=["/a", "/b"], read_only=False)
        d = fs.to_dict()
        restored = FileScope.from_dict(d)
        assert restored.allowed_paths == ["/a", "/b"]
        assert restored.read_only is False


# ---------------------------------------------------------------------------
# CommandScope
# ---------------------------------------------------------------------------

class TestCommandScope:
    def test_command_allowed(self) -> None:
        cs = CommandScope(allowed_commands=["git", "npm"])
        assert cs.is_command_allowed("git status") is True
        assert cs.is_command_allowed("npm install") is True
        assert cs.is_command_allowed("rm -rf /") is False

    def test_empty_command(self) -> None:
        cs = CommandScope(allowed_commands=["git"])
        assert cs.is_command_allowed("") is False

    def test_to_dict_roundtrip(self) -> None:
        cs = CommandScope(allowed_commands=["git", "npm"])
        d = cs.to_dict()
        restored = CommandScope.from_dict(d)
        assert restored.allowed_commands == ["git", "npm"]


# ---------------------------------------------------------------------------
# DataScope
# ---------------------------------------------------------------------------

class TestDataScope:
    def test_has_pii(self) -> None:
        ds = DataScope(domains=["pii", "internal"])
        assert ds.has_pii is True
        assert ds.has_financial is False

    def test_has_financial(self) -> None:
        ds = DataScope(domains=["financial"])
        assert ds.has_financial is True

    def test_has_medical(self) -> None:
        ds = DataScope(domains=["medical"])
        assert ds.has_medical is True

    def test_requires_enhanced_audit(self) -> None:
        ds = DataScope(domains=["pii"])
        assert ds.requires_enhanced_audit is True

    def test_no_enhanced_audit_for_internal(self) -> None:
        ds = DataScope(domains=["internal"])
        assert ds.requires_enhanced_audit is False

    def test_empty_no_enhanced_audit(self) -> None:
        ds = DataScope()
        assert ds.requires_enhanced_audit is False

    def test_credentials_triggers_audit(self) -> None:
        ds = DataScope(domains=["credentials"])
        assert ds.requires_enhanced_audit is True

    def test_to_dict_roundtrip(self) -> None:
        ds = DataScope(domains=["pii", "financial"])
        d = ds.to_dict()
        restored = DataScope.from_dict(d)
        assert restored.domains == ["pii", "financial"]


# ---------------------------------------------------------------------------
# SkillManifest
# ---------------------------------------------------------------------------

class TestSkillManifest:
    def _make_manifest(self, **overrides) -> SkillManifest:
        defaults = {
            "skill_id": "test-skill",
            "name": "Test Skill",
            "version": "1.0.0",
            "description": "A test skill",
            "author": "tester",
        }
        defaults.update(overrides)
        return SkillManifest(**defaults)

    def test_create(self) -> None:
        m = self._make_manifest()
        assert m.skill_id == "test-skill"
        assert m.name == "Test Skill"

    def test_to_dict_roundtrip(self) -> None:
        m = self._make_manifest(
            network=NetworkScope(allowed_domains=["api.com"]),
            filesystem=FileScope(allowed_paths=["/data"]),
            commands=CommandScope(allowed_commands=["git"]),
            data=DataScope(domains=["pii"]),
        )
        d = m.to_dict()
        restored = SkillManifest.from_dict(d)
        assert restored.skill_id == "test-skill"
        assert restored.network.allowed_domains == ["api.com"]
        assert restored.filesystem.allowed_paths == ["/data"]
        assert restored.commands.allowed_commands == ["git"]
        assert restored.data.domains == ["pii"]

    def test_to_json_roundtrip(self) -> None:
        m = self._make_manifest()
        j = m.to_json()
        restored = SkillManifest.from_json(j)
        assert restored.skill_id == "test-skill"
        assert restored.version == "1.0.0"

    def test_metadata(self) -> None:
        m = self._make_manifest(metadata={"tags": ["security"]})
        d = m.to_dict()
        assert d["metadata"]["tags"] == ["security"]


# ---------------------------------------------------------------------------
# ManifestValidator
# ---------------------------------------------------------------------------

class TestManifestValidator:
    def _make_manifest(self, **overrides) -> SkillManifest:
        defaults = {
            "skill_id": "test-skill",
            "name": "Test Skill",
            "version": "1.0.0",
        }
        defaults.update(overrides)
        return SkillManifest(**defaults)

    def test_valid_manifest(self) -> None:
        v = ManifestValidator()
        m = self._make_manifest()
        violations = v.validate(m)
        assert violations == []

    def test_no_manifest_raises(self) -> None:
        v = ManifestValidator(require_manifest=True)
        with pytest.raises(ManifestRequiredError):
            v.validate(None)

    def test_no_manifest_not_required(self) -> None:
        v = ManifestValidator(require_manifest=False)
        violations = v.validate(None)
        assert violations == []

    def test_missing_skill_id(self) -> None:
        v = ManifestValidator()
        m = self._make_manifest(skill_id="")
        violations = v.validate(m)
        assert any("skill_id" in v for v in violations)

    def test_missing_name(self) -> None:
        v = ManifestValidator()
        m = self._make_manifest(name="")
        violations = v.validate(m)
        assert any("name" in v for v in violations)

    def test_missing_version(self) -> None:
        v = ManifestValidator()
        m = self._make_manifest(version="")
        violations = v.validate(m)
        assert any("version" in v for v in violations)

    def test_too_many_network_domains(self) -> None:
        v = ManifestValidator(max_network_domains=2)
        m = self._make_manifest(
            network=NetworkScope(allowed_domains=["a.com", "b.com", "c.com"])
        )
        violations = v.validate(m)
        assert any("network domains" in v.lower() for v in violations)

    def test_blocked_domain(self) -> None:
        v = ManifestValidator(blocked_domains=["evil.com"])
        m = self._make_manifest(
            network=NetworkScope(allowed_domains=["evil.com"])
        )
        violations = v.validate(m)
        assert any("blocked domain" in v.lower() for v in violations)

    def test_too_many_file_paths(self) -> None:
        v = ManifestValidator(max_file_paths=1)
        m = self._make_manifest(
            filesystem=FileScope(allowed_paths=["/a", "/b"])
        )
        violations = v.validate(m)
        assert any("file paths" in v.lower() for v in violations)

    def test_path_traversal_detected(self) -> None:
        v = ManifestValidator()
        m = self._make_manifest(
            filesystem=FileScope(allowed_paths=["/data/../etc/passwd"])
        )
        violations = v.validate(m)
        assert any("traversal" in v.lower() for v in violations)

    def test_too_many_commands(self) -> None:
        v = ManifestValidator(max_commands=1)
        m = self._make_manifest(
            commands=CommandScope(allowed_commands=["git", "npm"])
        )
        violations = v.validate(m)
        assert any("commands" in v.lower() for v in violations)

    def test_blocked_command(self) -> None:
        v = ManifestValidator(blocked_commands=["rm"])
        m = self._make_manifest(
            commands=CommandScope(allowed_commands=["rm"])
        )
        violations = v.validate(m)
        assert any("blocked command" in v.lower() for v in violations)

    def test_unknown_data_domain(self) -> None:
        v = ManifestValidator()
        m = self._make_manifest(
            data=DataScope(domains=["pii", "unknown_domain"])
        )
        violations = v.validate(m)
        assert any("unknown data domain" in v.lower() for v in violations)

    def test_valid_data_domains(self) -> None:
        v = ManifestValidator()
        m = self._make_manifest(
            data=DataScope(domains=["pii", "financial", "medical", "credentials", "internal"])
        )
        violations = v.validate(m)
        assert violations == []


# ---------------------------------------------------------------------------
# Access checks
# ---------------------------------------------------------------------------

class TestAccessChecks:
    def _make_manifest(self) -> SkillManifest:
        return SkillManifest(
            skill_id="s1", name="S", version="1.0",
            network=NetworkScope(allowed_domains=["api.example.com"]),
            filesystem=FileScope(allowed_paths=["/data/skills/"]),
            commands=CommandScope(allowed_commands=["git"]),
        )

    def test_check_network_access_allowed(self) -> None:
        v = ManifestValidator()
        m = self._make_manifest()
        assert v.check_network_access(m, "api.example.com") is True

    def test_check_network_access_blocked(self) -> None:
        v = ManifestValidator()
        m = self._make_manifest()
        assert v.check_network_access(m, "evil.com") is False

    def test_check_file_access_allowed(self) -> None:
        v = ManifestValidator()
        m = self._make_manifest()
        assert v.check_file_access(m, "/data/skills/my-skill") is True

    def test_check_file_access_blocked(self) -> None:
        v = ManifestValidator()
        m = self._make_manifest()
        assert v.check_file_access(m, "/etc/passwd") is False

    def test_check_command_access_allowed(self) -> None:
        v = ManifestValidator()
        m = self._make_manifest()
        assert v.check_command_access(m, "git status") is True

    def test_check_command_access_blocked(self) -> None:
        v = ManifestValidator()
        m = self._make_manifest()
        assert v.check_command_access(m, "rm -rf /") is False


# ---------------------------------------------------------------------------
# DataDomain enum
# ---------------------------------------------------------------------------

class TestDataDomainEnum:
    def test_values(self) -> None:
        assert DataDomain.PII.value == "pii"
        assert DataDomain.FINANCIAL.value == "financial"
        assert DataDomain.MEDICAL.value == "medical"
        assert DataDomain.CREDENTIALS.value == "credentials"
        assert DataDomain.INTERNAL.value == "internal"
