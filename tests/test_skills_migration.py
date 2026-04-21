"""Tests for the skills_v2 migration output.

These tests assert that every file in `skills_v2/*.md` conforms to the
anthropics/skills YAML-frontmatter format and that `MANIFEST.json` is in
sync with the directory listing. The migration script
(`scripts/migrate_skills.py`) is responsible for producing these files;
this test is the contract it must uphold.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "skills_v2"
MANIFEST_PATH = SKILLS_DIR / "MANIFEST.json"

MAX_DESCRIPTION_LEN = 200
SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _skill_files() -> list[Path]:
    """Return every `.md` file in skills_v2 except README.md."""

    return sorted(
        p for p in SKILLS_DIR.glob("*.md") if p.name.lower() != "readme.md"
    )


def _split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Extract a simple `key: value` YAML frontmatter block and the body."""

    assert text.startswith("---\n"), "file must start with YAML frontmatter"
    lines = text.splitlines()
    end_index: int | None = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_index = i
            break
    assert end_index is not None, "frontmatter is not closed with `---`"

    fm: dict[str, str] = {}
    for raw in lines[1:end_index]:
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        assert ":" in stripped, f"malformed frontmatter line: {raw!r}"
        key, _, value = stripped.partition(":")
        fm[key.strip()] = value.strip().strip('"').strip("'")

    body = "\n".join(lines[end_index + 1 :]).lstrip("\n")
    return fm, body


SKILL_FILES = _skill_files()


def test_skills_v2_dir_exists() -> None:
    assert SKILLS_DIR.is_dir(), f"missing directory: {SKILLS_DIR}"


def test_has_skill_files() -> None:
    assert SKILL_FILES, "skills_v2/ contains no skill files"


@pytest.mark.parametrize(
    "skill_path",
    SKILL_FILES,
    ids=[p.stem for p in SKILL_FILES],
)
def test_skill_file_conforms_to_format(skill_path: Path) -> None:
    """Every skill file must have valid frontmatter, slug, description, body."""

    text = skill_path.read_text(encoding="utf-8")
    fm, body = _split_frontmatter(text)

    # Required frontmatter keys.
    for required_key in ("name", "description", "version"):
        assert required_key in fm, (
            f"{skill_path.name}: missing frontmatter key {required_key!r}"
        )

    # name matches filename slug.
    slug = skill_path.stem
    assert SLUG_PATTERN.match(slug), (
        f"{skill_path.name}: filename is not a valid kebab-case slug"
    )
    assert fm["name"] == slug, (
        f"{skill_path.name}: frontmatter name {fm['name']!r} "
        f"does not match filename slug {slug!r}"
    )

    # description checks.
    description = fm["description"]
    assert description, f"{skill_path.name}: description is empty"
    assert len(description) <= MAX_DESCRIPTION_LEN, (
        f"{skill_path.name}: description > {MAX_DESCRIPTION_LEN} chars"
    )
    assert not description.lower().startswith("description: todo"), (
        f"{skill_path.name}: description is a TODO fallback — fix it"
    )

    # version is a positive integer.
    version_str = fm["version"]
    assert version_str.isdigit() and int(version_str) >= 1, (
        f"{skill_path.name}: version must be a positive integer, got "
        f"{version_str!r}"
    )

    # body is non-empty.
    assert body.strip(), f"{skill_path.name}: body is empty"


def test_manifest_exists_and_is_valid_json() -> None:
    assert MANIFEST_PATH.is_file(), f"missing manifest: {MANIFEST_PATH}"
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    assert data.get("version") == 1
    assert "generated_at" in data
    assert isinstance(data.get("skills"), list)


def test_manifest_in_sync_with_directory() -> None:
    """One manifest entry per skill file, slugs match exactly."""

    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    manifest_slugs = sorted(entry["name"] for entry in data["skills"])
    file_slugs = sorted(p.stem for p in SKILL_FILES)

    assert manifest_slugs == file_slugs, (
        "MANIFEST.json is out of sync with skills_v2/. "
        f"manifest={manifest_slugs} files={file_slugs}"
    )

    # Every manifest entry has the required keys and sane values.
    for entry in data["skills"]:
        assert set(entry.keys()) >= {"name", "path", "version", "description"}
        assert entry["path"] == f"skills_v2/{entry['name']}.md"
        assert entry["version"] >= 1
        assert 0 < len(entry["description"]) <= MAX_DESCRIPTION_LEN


def test_manifest_description_matches_file_frontmatter() -> None:
    """Prevent drift between manifest description and file frontmatter."""

    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    for entry in data["skills"]:
        path = SKILLS_DIR / f"{entry['name']}.md"
        fm, _ = _split_frontmatter(path.read_text(encoding="utf-8"))
        assert fm["description"] == entry["description"], (
            f"{path.name}: manifest description drifted from frontmatter"
        )
