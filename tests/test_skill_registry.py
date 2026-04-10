"""Tests for security.skill_registry — Private-First Skill Registry (REQ-TSF-01).

Covers:
- SkillRegistry: fresh install empty, install, uninstall, upgrade, list
- Hub management: hub_enable, hub_disable, search_hub requires enable
- SkillRecord: frozen, to_dict/from_dict
- HubConfig: api_key excluded from serialization
- Serialization: to_dict/from_dict, to_json/from_json round-trip
- Error cases: duplicate install, upgrade nonexistent, hub not enabled
"""

from __future__ import annotations

import json
import time
import pytest

from security.skill_registry import (
    HubConfig,
    HubNotEnabledError,
    RegistryError,
    RegistryScope,
    SkillNotFoundError,
    SkillRecord,
    SkillRegistry,
    SkillStatus,
    DEFAULT_REGISTRY_URL,
)


# ---------------------------------------------------------------------------
# SkillRecord
# ---------------------------------------------------------------------------

class TestSkillRecord:
    def test_create(self) -> None:
        r = SkillRecord(
            skill_id="s1", name="Skill One", version="1.0.0",
            description="desc", author="auth", scope="private",
        )
        assert r.skill_id == "s1"
        assert r.scope == "private"

    def test_frozen(self) -> None:
        r = SkillRecord(skill_id="s1", name="n", version="1.0")
        with pytest.raises(AttributeError):
            r.skill_id = "s2"  # type: ignore[misc]

    def test_to_dict_roundtrip(self) -> None:
        r = SkillRecord(
            skill_id="s1", name="Skill", version="2.0.0",
            description="d", author="a", scope="private",
            source="local", installed_at=1000.0,
            hash_sha256="abc123",
            capabilities={"network": {"allowAll": False}},
            metadata={"tags": ["test"]},
        )
        d = r.to_dict()
        restored = SkillRecord.from_dict(d)
        assert restored.skill_id == "s1"
        assert restored.version == "2.0.0"
        assert restored.hash_sha256 == "abc123"
        assert restored.capabilities == {"network": {"allowAll": False}}

    def test_defaults(self) -> None:
        r = SkillRecord(skill_id="x", name="n", version="1.0")
        assert r.scope == "private"
        assert r.source == "local"
        assert r.installed_at == 0.0


# ---------------------------------------------------------------------------
# HubConfig
# ---------------------------------------------------------------------------

class TestHubConfig:
    def test_default_disabled(self) -> None:
        h = HubConfig()
        assert h.enabled is False
        assert h.url == DEFAULT_REGISTRY_URL

    def test_api_key_excluded_from_serialization(self) -> None:
        h = HubConfig(enabled=True, api_key="secret-key-123")
        d = h.to_dict()
        assert "api_key" not in d
        assert "apiKey" not in d
        assert d["enabled"] is True

    def test_from_dict(self) -> None:
        d = {"enabled": True, "url": "https://custom.hub", "enabledBy": "admin"}
        h = HubConfig.from_dict(d)
        assert h.enabled is True
        assert h.url == "https://custom.hub"
        assert h.enabled_by == "admin"


# ---------------------------------------------------------------------------
# SkillRegistry — fresh install
# ---------------------------------------------------------------------------

class TestSkillRegistryFreshInstall:
    def test_empty_on_init(self) -> None:
        reg = SkillRegistry()
        assert reg.skill_count == 0
        assert reg.installed_skills == []

    def test_hub_disabled_by_default(self) -> None:
        reg = SkillRegistry()
        assert reg.hub_enabled is False

    def test_default_org_id(self) -> None:
        reg = SkillRegistry()
        assert reg.org_id == "default"

    def test_custom_org_id(self) -> None:
        reg = SkillRegistry(org_id="my-org")
        assert reg.org_id == "my-org"


# ---------------------------------------------------------------------------
# Skill operations
# ---------------------------------------------------------------------------

class TestSkillOperations:
    def test_install_and_get(self) -> None:
        reg = SkillRegistry()
        record = reg.install("s1", "Skill One", "1.0.0", description="test")
        assert record.skill_id == "s1"
        assert reg.is_installed("s1") is True
        assert reg.get("s1") is not None
        assert reg.get("s1").version == "1.0.0"

    def test_install_duplicate_raises(self) -> None:
        reg = SkillRegistry()
        reg.install("s1", "Skill", "1.0")
        with pytest.raises(RegistryError, match="already installed"):
            reg.install("s1", "Skill", "2.0")

    def test_install_from_hub_requires_enable(self) -> None:
        reg = SkillRegistry()
        with pytest.raises(HubNotEnabledError):
            reg.install("s1", "Skill", "1.0", source="hub")

    def test_install_from_hub_after_enable(self) -> None:
        reg = SkillRegistry()
        reg.hub_enable(api_key="key")
        record = reg.install("s1", "Skill", "1.0", source="hub")
        assert record.source == "hub"
        assert record.scope == "private"  # still private by default

    def test_uninstall(self) -> None:
        reg = SkillRegistry()
        reg.install("s1", "Skill", "1.0")
        assert reg.uninstall("s1") is True
        assert reg.is_installed("s1") is False

    def test_uninstall_nonexistent(self) -> None:
        reg = SkillRegistry()
        assert reg.uninstall("nope") is False

    def test_upgrade(self) -> None:
        reg = SkillRegistry()
        reg.install("s1", "Skill", "1.0.0")
        upgraded = reg.upgrade("s1", "2.0.0")
        assert upgraded.version == "2.0.0"
        assert reg.get("s1").version == "2.0.0"

    def test_upgrade_nonexistent_raises(self) -> None:
        reg = SkillRegistry()
        with pytest.raises(SkillNotFoundError):
            reg.upgrade("nope", "2.0")

    def test_upgrade_preserves_fields(self) -> None:
        reg = SkillRegistry()
        reg.install("s1", "Skill", "1.0", description="orig", author="auth")
        upgraded = reg.upgrade("s1", "2.0")
        assert upgraded.name == "Skill"
        assert upgraded.description == "orig"
        assert upgraded.author == "auth"

    def test_list_skills(self) -> None:
        reg = SkillRegistry()
        reg.install("a", "A", "1.0")
        reg.install("b", "B", "1.0")
        skills = reg.list_skills()
        assert len(skills) == 2

    def test_list_skills_by_source(self) -> None:
        reg = SkillRegistry()
        reg.hub_enable()
        reg.install("a", "A", "1.0", source="local")
        reg.install("b", "B", "1.0", source="hub")
        assert len(reg.list_skills(source="local")) == 1
        assert len(reg.list_skills(source="hub")) == 1

    def test_get_nonexistent(self) -> None:
        reg = SkillRegistry()
        assert reg.get("nope") is None

    def test_install_with_hash_and_capabilities(self) -> None:
        reg = SkillRegistry()
        record = reg.install(
            "s1", "Skill", "1.0",
            content_hash="deadbeef",
            capabilities={"network": {"allowAll": False}},
            metadata={"custom": True},
        )
        assert record.hash_sha256 == "deadbeef"
        assert record.capabilities["network"]["allowAll"] is False
        assert record.metadata["custom"] is True


# ---------------------------------------------------------------------------
# Hub management
# ---------------------------------------------------------------------------

class TestHubManagement:
    def test_hub_enable(self) -> None:
        reg = SkillRegistry()
        reg.hub_enable(url="https://custom.hub", api_key="key", enabled_by="admin")
        assert reg.hub_enabled is True
        assert reg.hub_config.url == "https://custom.hub"
        assert reg.hub_config.enabled_by == "admin"
        assert reg.hub_config.enabled_at > 0

    def test_hub_disable(self) -> None:
        reg = SkillRegistry()
        reg.hub_enable()
        reg.hub_disable()
        assert reg.hub_enabled is False

    def test_search_hub_requires_enable(self) -> None:
        reg = SkillRegistry()
        with pytest.raises(HubNotEnabledError):
            reg.search_hub("test")

    def test_search_hub_after_enable(self) -> None:
        reg = SkillRegistry()
        reg.hub_enable()
        results = reg.search_hub("test")
        assert isinstance(results, list)


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

class TestRegistrySerialization:
    def test_to_dict_roundtrip(self) -> None:
        reg = SkillRegistry(org_id="org-1")
        reg.install("s1", "Skill", "1.0", content_hash="h1")
        reg.install("s2", "Skill2", "2.0", description="d")
        reg.hub_enable(url="https://hub.test", enabled_by="admin")

        d = reg.to_dict()
        reg2 = SkillRegistry.from_dict(d)
        assert reg2.org_id == "org-1"
        assert reg2.skill_count == 2
        assert reg2.is_installed("s1")
        assert reg2.is_installed("s2")
        assert reg2.hub_enabled is True

    def test_to_json_roundtrip(self) -> None:
        reg = SkillRegistry()
        reg.install("x", "X", "1.0")
        j = reg.to_json()
        reg2 = SkillRegistry.from_json(j)
        assert reg2.is_installed("x")

    def test_empty_registry_serialization(self) -> None:
        reg = SkillRegistry()
        d = reg.to_dict()
        reg2 = SkillRegistry.from_dict(d)
        assert reg2.skill_count == 0
        assert reg2.hub_enabled is False


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class TestEnums:
    def test_registry_scope_values(self) -> None:
        assert RegistryScope.PRIVATE.value == "private"
        assert RegistryScope.PUBLIC.value == "public"

    def test_skill_status_values(self) -> None:
        assert SkillStatus.INSTALLED.value == "installed"
        assert SkillStatus.REVOKED.value == "revoked"
