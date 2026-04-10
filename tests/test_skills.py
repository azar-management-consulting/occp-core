"""Tests for cli.skills — Version Pinning in Production (REQ-TSF-04).

Covers:
- is_exact_version: exact semver, floating, ranges, empty
- is_production_mode: env detection
- parse_skill_spec: skill@version parsing
- validate_install_version: production vs non-production
- PinnedSkill: creation, frozen, to_dict/from_dict
- SkillsLockfile: pin, unpin, get, list, content_hash, integrity
- File I/O: save, load, load_or_create, integrity check
- Error cases: floating pin, lockfile integrity
"""

from __future__ import annotations

import json
import os
import pytest
from pathlib import Path

from cli.skills import (
    FloatingVersionError,
    LockfileIntegrityError,
    PinnedSkill,
    SkillsLockfile,
    VersionPinningError,
    is_exact_version,
    is_production_mode,
    parse_skill_spec,
    validate_install_version,
    LOCKFILE_VERSION,
)


# ---------------------------------------------------------------------------
# is_exact_version
# ---------------------------------------------------------------------------

class TestIsExactVersion:
    def test_exact_semver(self) -> None:
        assert is_exact_version("1.2.3") is True
        assert is_exact_version("0.0.1") is True
        assert is_exact_version("10.20.30") is True

    def test_exact_with_prerelease(self) -> None:
        assert is_exact_version("1.2.3-beta") is True
        assert is_exact_version("1.2.3-rc.1") is True
        assert is_exact_version("1.2.3+build123") is True

    def test_floating_keywords(self) -> None:
        assert is_exact_version("latest") is False
        assert is_exact_version("stable") is False
        assert is_exact_version("next") is False
        assert is_exact_version("canary") is False
        assert is_exact_version("*") is False

    def test_floating_case_insensitive(self) -> None:
        assert is_exact_version("LATEST") is False
        assert is_exact_version("Latest") is False

    def test_range_prefixes(self) -> None:
        assert is_exact_version("^1.2.3") is False
        assert is_exact_version("~1.2.3") is False
        assert is_exact_version(">=1.2.3") is False

    def test_empty(self) -> None:
        assert is_exact_version("") is False

    def test_partial_version(self) -> None:
        assert is_exact_version("1.2") is False
        assert is_exact_version("1") is False


# ---------------------------------------------------------------------------
# is_production_mode
# ---------------------------------------------------------------------------

class TestIsProductionMode:
    def test_production(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OCCP_ENV", "production")
        assert is_production_mode() is True

    def test_production_case_insensitive(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OCCP_ENV", "Production")
        assert is_production_mode() is True

    def test_development(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OCCP_ENV", "development")
        assert is_production_mode() is False

    def test_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OCCP_ENV", raising=False)
        assert is_production_mode() is False


# ---------------------------------------------------------------------------
# parse_skill_spec
# ---------------------------------------------------------------------------

class TestParseSkillSpec:
    def test_with_version(self) -> None:
        assert parse_skill_spec("web-search@1.2.3") == ("web-search", "1.2.3")

    def test_with_latest(self) -> None:
        assert parse_skill_spec("web-search@latest") == ("web-search", "latest")

    def test_no_version(self) -> None:
        assert parse_skill_spec("web-search") == ("web-search", "")

    def test_multiple_at_signs(self) -> None:
        skill_id, version = parse_skill_spec("@scope/pkg@2.0.0")
        assert skill_id == "@scope/pkg"
        assert version == "2.0.0"


# ---------------------------------------------------------------------------
# validate_install_version
# ---------------------------------------------------------------------------

class TestValidateInstallVersion:
    def test_exact_in_production(self) -> None:
        violations = validate_install_version("s1", "1.2.3", production=True)
        assert violations == []

    def test_floating_in_production(self) -> None:
        violations = validate_install_version("s1", "latest", production=True)
        assert len(violations) == 1
        assert "floating" in violations[0].lower() or "Floating" in violations[0]

    def test_range_in_production(self) -> None:
        violations = validate_install_version("s1", "^1.0.0", production=True)
        assert len(violations) == 1

    def test_no_version_in_production(self) -> None:
        violations = validate_install_version("s1", "", production=True)
        assert len(violations) == 1
        assert "no version" in violations[0].lower() or "No version" in violations[0]

    def test_floating_in_development(self) -> None:
        violations = validate_install_version("s1", "latest", production=False)
        assert violations == []

    def test_no_version_in_development(self) -> None:
        violations = validate_install_version("s1", "", production=False)
        assert violations == []

    def test_exact_in_development(self) -> None:
        violations = validate_install_version("s1", "1.0.0", production=False)
        assert violations == []


# ---------------------------------------------------------------------------
# PinnedSkill
# ---------------------------------------------------------------------------

class TestPinnedSkill:
    def test_create(self) -> None:
        p = PinnedSkill(skill_id="s1", version="1.0.0")
        assert p.skill_id == "s1"
        assert p.version == "1.0.0"
        assert p.source == "local"

    def test_frozen(self) -> None:
        p = PinnedSkill(skill_id="s1", version="1.0.0")
        with pytest.raises(AttributeError):
            p.skill_id = "s2"  # type: ignore[misc]

    def test_to_dict_roundtrip(self) -> None:
        p = PinnedSkill(
            skill_id="s1", version="2.0.0",
            hash_sha256="abc123", source="hub",
            pinned_at=1000.0, pinned_by="admin",
        )
        d = p.to_dict()
        restored = PinnedSkill.from_dict(d)
        assert restored.skill_id == "s1"
        assert restored.version == "2.0.0"
        assert restored.hash_sha256 == "abc123"
        assert restored.source == "hub"
        assert restored.pinned_at == 1000.0
        assert restored.pinned_by == "admin"

    def test_defaults(self) -> None:
        p = PinnedSkill(skill_id="x", version="1.0.0")
        assert p.hash_sha256 == ""
        assert p.source == "local"
        assert p.pinned_at == 0.0
        assert p.pinned_by == ""


# ---------------------------------------------------------------------------
# SkillsLockfile — basic operations
# ---------------------------------------------------------------------------

class TestSkillsLockfile:
    def test_empty(self) -> None:
        lf = SkillsLockfile()
        assert lf.skill_count == 0
        assert lf.pinned_skills == []

    def test_pin(self) -> None:
        lf = SkillsLockfile()
        entry = lf.pin("s1", "1.0.0", hash_sha256="h1")
        assert entry.skill_id == "s1"
        assert entry.version == "1.0.0"
        assert lf.skill_count == 1
        assert lf.is_pinned("s1") is True

    def test_pin_floating_raises(self) -> None:
        lf = SkillsLockfile()
        with pytest.raises(FloatingVersionError):
            lf.pin("s1", "latest")

    def test_pin_range_raises(self) -> None:
        lf = SkillsLockfile()
        with pytest.raises(FloatingVersionError):
            lf.pin("s1", "^1.0.0")

    def test_unpin(self) -> None:
        lf = SkillsLockfile()
        lf.pin("s1", "1.0.0")
        assert lf.unpin("s1") is True
        assert lf.is_pinned("s1") is False

    def test_unpin_nonexistent(self) -> None:
        lf = SkillsLockfile()
        assert lf.unpin("nope") is False

    def test_get(self) -> None:
        lf = SkillsLockfile()
        lf.pin("s1", "1.0.0")
        assert lf.get("s1") is not None
        assert lf.get("s1").version == "1.0.0"
        assert lf.get("nope") is None

    def test_check_version_match(self) -> None:
        lf = SkillsLockfile()
        lf.pin("s1", "1.0.0")
        assert lf.check_version_match("s1", "1.0.0") is True
        assert lf.check_version_match("s1", "2.0.0") is False

    def test_check_version_match_not_pinned(self) -> None:
        lf = SkillsLockfile()
        assert lf.check_version_match("s1", "any") is True

    def test_list_pins(self) -> None:
        lf = SkillsLockfile()
        lf.pin("a", "1.0.0")
        lf.pin("b", "2.0.0")
        pins = lf.list_pins()
        assert len(pins) == 2
        names = {p.skill_id for p in pins}
        assert names == {"a", "b"}

    def test_pin_overwrites(self) -> None:
        lf = SkillsLockfile()
        lf.pin("s1", "1.0.0")
        lf.pin("s1", "2.0.0")
        assert lf.get("s1").version == "2.0.0"
        assert lf.skill_count == 1


# ---------------------------------------------------------------------------
# Content hash & integrity
# ---------------------------------------------------------------------------

class TestLockfileIntegrity:
    def test_content_hash_deterministic(self) -> None:
        lf = SkillsLockfile()
        lf.pin("s1", "1.0.0")
        h1 = lf.content_hash()
        h2 = lf.content_hash()
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex

    def test_content_hash_changes(self) -> None:
        lf1 = SkillsLockfile()
        lf1.pin("s1", "1.0.0")
        lf2 = SkillsLockfile()
        lf2.pin("s1", "2.0.0")
        assert lf1.content_hash() != lf2.content_hash()

    def test_verify_integrity_valid(self) -> None:
        lf = SkillsLockfile()
        lf.pin("s1", "1.0.0")
        h = lf.content_hash()
        assert lf.verify_integrity(h) is True

    def test_verify_integrity_invalid(self) -> None:
        lf = SkillsLockfile()
        lf.pin("s1", "1.0.0")
        assert lf.verify_integrity("bad_hash") is False

    def test_verify_integrity_none(self) -> None:
        lf = SkillsLockfile()
        assert lf.verify_integrity(None) is True


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

class TestLockfileSerialization:
    def test_to_dict_roundtrip(self) -> None:
        lf = SkillsLockfile()
        lf.pin("s1", "1.0.0", hash_sha256="h1")
        lf.pin("s2", "2.0.0", source="hub")
        d = lf.to_dict()
        assert d["lockfileVersion"] == LOCKFILE_VERSION
        assert "contentHash" in d
        assert len(d["skills"]) == 2

        lf2 = SkillsLockfile.from_dict(d)
        assert lf2.skill_count == 2
        assert lf2.is_pinned("s1")
        assert lf2.get("s2").source == "hub"

    def test_to_json_roundtrip(self) -> None:
        lf = SkillsLockfile()
        lf.pin("x", "1.0.0")
        j = lf.to_json()
        parsed = json.loads(j)
        assert parsed["lockfileVersion"] == LOCKFILE_VERSION
        lf2 = SkillsLockfile.from_json(j)
        assert lf2.is_pinned("x")

    def test_empty_serialization(self) -> None:
        lf = SkillsLockfile()
        d = lf.to_dict()
        lf2 = SkillsLockfile.from_dict(d)
        assert lf2.skill_count == 0


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------

class TestLockfileIO:
    def test_save_and_load(self, tmp_path: Path) -> None:
        lf = SkillsLockfile()
        lf.pin("s1", "1.0.0", hash_sha256="abc")
        lf.pin("s2", "2.0.0")

        filepath = tmp_path / "skills.lock"
        lf.save(filepath)

        loaded = SkillsLockfile.load(filepath)
        assert loaded.skill_count == 2
        assert loaded.get("s1").hash_sha256 == "abc"

    def test_load_nonexistent_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            SkillsLockfile.load(tmp_path / "nope.lock")

    def test_load_tampered_raises(self, tmp_path: Path) -> None:
        lf = SkillsLockfile()
        lf.pin("s1", "1.0.0")
        filepath = tmp_path / "skills.lock"
        lf.save(filepath)

        # Tamper: modify version in file
        data = json.loads(filepath.read_text())
        data["skills"]["s1"]["version"] = "9.9.9"
        filepath.write_text(json.dumps(data))

        with pytest.raises(LockfileIntegrityError):
            SkillsLockfile.load(filepath)

    def test_load_or_create_existing(self, tmp_path: Path) -> None:
        lf = SkillsLockfile()
        lf.pin("s1", "1.0.0")
        filepath = tmp_path / "skills.lock"
        lf.save(filepath)

        loaded = SkillsLockfile.load_or_create(filepath)
        assert loaded.skill_count == 1

    def test_load_or_create_new(self, tmp_path: Path) -> None:
        filepath = tmp_path / "skills.lock"
        loaded = SkillsLockfile.load_or_create(filepath)
        assert loaded.skill_count == 0
