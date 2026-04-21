#!/usr/bin/env python3
"""Migrate legacy OCCP SKILL.md files to anthropics/skills YAML-frontmatter format.

Source: config/openclaw/skills/<slug>/SKILL.md
Target: skills_v2/<slug>.md

The target format is a single Markdown file with YAML frontmatter:

    ---
    name: <slug>
    description: <one-sentence description>
    version: 1
    ---

    <markdown body>

Legacy files may already contain YAML frontmatter (with arbitrary extra keys).
In that case we preserve `name` + `description`, set `version: 1`, drop the
OCCP-internal keys (`user-invocable`, `command-dispatch`, ...), and copy the
body unchanged. For files without frontmatter we extract `name` from the
first `# ` heading and `description` from the first `## Description` section
(if present) or the first non-header paragraph.

Idempotent. Dry-run by default. Use --write to actually write files. Use
--force to overwrite existing target files.

Exit code: 0 success, 1 if any skill failed to parse.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_GLOB = "config/openclaw/skills/*/SKILL.md"
TARGET_DIR = REPO_ROOT / "skills_v2"
MANIFEST_PATH = TARGET_DIR / "MANIFEST.json"

# Keys from the anthropics/skills spec we keep in frontmatter.
ALLOWED_FRONTMATTER_KEYS: tuple[str, ...] = ("name", "description", "version")

MAX_DESCRIPTION_LEN = 200


@dataclass
class Skill:
    """Parsed skill ready for writing in anthropics/skills format."""

    slug: str
    name: str
    description: str
    version: int
    body: str
    source_path: Path
    description_is_fallback: bool

    def render(self) -> str:
        """Render the skill as a single Markdown file with YAML frontmatter."""

        # We intentionally emit YAML by hand (no dependency on PyYAML) so this
        # script runs under a stock Python 3.13 interpreter.
        description = _yaml_escape(self.description)
        name = _yaml_escape(self.name)
        frontmatter = (
            "---\n"
            f"name: {name}\n"
            f"description: {description}\n"
            f"version: {self.version}\n"
            "---\n\n"
        )
        body = self.body.rstrip() + "\n"
        return frontmatter + body


def _yaml_escape(value: str) -> str:
    """Quote a YAML scalar if it contains characters that need escaping.

    Keeps plain scalars where safe (no colon, hash, quote, leading/trailing
    whitespace) to match the hand-written style of the anthropics/skills repo.
    """

    needs_quote = (
        not value
        or value != value.strip()
        or any(ch in value for ch in (":", "#", "'", '"', "\n", "\t"))
        or value[0] in "[]{}&*!|>%@`,"
    )
    if not needs_quote:
        return value
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def slugify(name: str) -> str:
    """Convert a human-friendly name to a kebab-case slug."""

    lowered = name.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", lowered)
    return slug.strip("-")


def _split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Split a markdown file into (frontmatter_dict, body).

    Supports only the simple `key: value` YAML used in legacy SKILL.md files.
    Returns an empty dict if no frontmatter present.
    """

    if not text.startswith("---"):
        return {}, text

    lines = text.splitlines()
    # Find closing `---`.
    end_index: int | None = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_index = i
            break
    if end_index is None:
        return {}, text

    fm: dict[str, str] = {}
    for raw in lines[1:end_index]:
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in stripped:
            continue
        key, _, value = stripped.partition(":")
        fm[key.strip()] = value.strip().strip('"').strip("'")
    body = "\n".join(lines[end_index + 1 :]).lstrip("\n")
    return fm, body


def _first_heading(body: str) -> str | None:
    """Return the text of the first level-1 heading in the body."""

    for line in body.splitlines():
        m = re.match(r"^#\s+(.+?)\s*$", line)
        if m:
            return m.group(1)
    return None


def _first_description_section(body: str) -> str | None:
    """Return the first paragraph under `## Description` if present."""

    match = re.search(
        r"^##\s+Description\s*\n+(.+?)(?:\n\n|\n##|\Z)",
        body,
        flags=re.MULTILINE | re.DOTALL,
    )
    if not match:
        return None
    return match.group(1).strip()


def _first_paragraph(body: str) -> str | None:
    """Return the first non-heading paragraph."""

    paragraphs = re.split(r"\n\s*\n", body)
    for para in paragraphs:
        stripped = para.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        # Flatten multi-line paragraph into single line.
        return re.sub(r"\s+", " ", stripped)
    return None


def _strip_leading_heading(body: str, heading_text: str) -> str:
    """Remove the first `# <heading_text>` line from the body."""

    pattern = re.compile(
        r"^#\s+" + re.escape(heading_text) + r"\s*\n+", flags=re.MULTILINE
    )
    return pattern.sub("", body, count=1).lstrip("\n")


def parse_skill(source_path: Path) -> Skill:
    """Parse a legacy SKILL.md into a Skill dataclass."""

    text = source_path.read_text(encoding="utf-8")
    legacy_fm, body = _split_frontmatter(text)

    name = legacy_fm.get("name") or _first_heading(body) or source_path.parent.name
    slug = slugify(name)

    description_is_fallback = False
    description = legacy_fm.get("description")
    if not description:
        description = _first_description_section(body)
    if not description:
        description = _first_paragraph(body)
    if not description:
        description = (
            f"Description: TODO - extracted from "
            f"{source_path.relative_to(REPO_ROOT)}"
        )
        description_is_fallback = True

    # Collapse whitespace and enforce length limit.
    description = re.sub(r"\s+", " ", description).strip()
    if len(description) > MAX_DESCRIPTION_LEN:
        description = description[: MAX_DESCRIPTION_LEN - 1].rstrip() + "…"

    # If the body still leads with `# <name>`, drop it to avoid duplicating
    # the title now that it lives in frontmatter.
    first_h1 = _first_heading(body)
    if first_h1 is not None:
        body = _strip_leading_heading(body, first_h1)

    return Skill(
        slug=slug,
        name=slug,  # anthropics/skills uses the slug as the canonical name
        description=description,
        version=1,
        body=body,
        source_path=source_path,
        description_is_fallback=description_is_fallback,
    )


def collect_sources() -> list[Path]:
    sources = sorted((REPO_ROOT).glob(SOURCE_GLOB))
    return sources


def build_manifest(skills: list[Skill]) -> dict[str, object]:
    return {
        "version": 1,
        "generated_at": date.today().isoformat(),
        "skills": [
            {
                "name": s.slug,
                "path": f"skills_v2/{s.slug}.md",
                "version": s.version,
                "description": s.description,
            }
            for s in sorted(skills, key=lambda x: x.slug)
        ],
    }


def migrate(
    *, dry_run: bool, force: bool, write_manifest: bool = True
) -> tuple[int, int, list[str]]:
    """Run the migration.

    Returns (written_count, skipped_count, errors).
    """

    sources = collect_sources()
    if not sources:
        print(f"ERROR: no source skills matched {SOURCE_GLOB}", file=sys.stderr)
        return 0, 0, ["no-sources"]

    skills: list[Skill] = []
    errors: list[str] = []
    for src in sources:
        try:
            skills.append(parse_skill(src))
        except Exception as exc:  # pragma: no cover - defensive
            errors.append(f"{src}: {exc}")

    if errors:
        for err in errors:
            print(f"PARSE-FAIL: {err}", file=sys.stderr)
        return 0, 0, errors

    written = 0
    skipped = 0
    if not dry_run:
        TARGET_DIR.mkdir(parents=True, exist_ok=True)

    for skill in skills:
        target = TARGET_DIR / f"{skill.slug}.md"
        rendered = skill.render()
        exists = target.exists()

        if exists and not force:
            existing = target.read_text(encoding="utf-8") if not dry_run else None
            if existing == rendered:
                skipped += 1
                print(f"UNCHANGED: {target.relative_to(REPO_ROOT)}")
                continue
            skipped += 1
            print(
                f"SKIP (exists, --force to overwrite): "
                f"{target.relative_to(REPO_ROOT)}"
            )
            continue

        if dry_run:
            print(f"WOULD WRITE: {target.relative_to(REPO_ROOT)} "
                  f"({len(rendered)} bytes)")
        else:
            target.write_text(rendered, encoding="utf-8")
            print(f"WROTE: {target.relative_to(REPO_ROOT)}")
        written += 1

    if write_manifest:
        manifest = build_manifest(skills)
        manifest_json = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
        if dry_run:
            print(f"WOULD WRITE: {MANIFEST_PATH.relative_to(REPO_ROOT)} "
                  f"({len(manifest_json)} bytes)")
        else:
            MANIFEST_PATH.write_text(manifest_json, encoding="utf-8")
            print(f"WROTE: {MANIFEST_PATH.relative_to(REPO_ROOT)}")

    fallback_slugs = [s.slug for s in skills if s.description_is_fallback]
    if fallback_slugs:
        print(
            "FALLBACK-DESCRIPTION: " + ", ".join(fallback_slugs), file=sys.stderr
        )

    return written, skipped, errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--write",
        action="store_true",
        help="Actually write files (default: dry-run)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Force dry-run mode (default behaviour)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing target files",
    )
    args = parser.parse_args(argv)

    dry_run = not args.write or args.dry_run
    written, skipped, errors = migrate(dry_run=dry_run, force=args.force)
    print(
        f"\nSUMMARY: written={written} skipped={skipped} "
        f"errors={len(errors)} dry_run={dry_run}"
    )
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
