"""Snapshot test for the OpenClaw prompt bundle.

Hashes every file under ``config/openclaw/prompts/`` and compares the aggregate
SHA-256 to a stored snapshot.  Drift in any prompt / schema / allow-list
triggers a failure with a per-file diff.

FELT: the spec said ``*.yaml`` but the repo currently ships ``.md`` + ``.json``
prompt artefacts — we therefore hash every regular file under the directory
(excluding ``.DS_Store`` etc.) so the test is useful today and will
automatically cover future ``.yaml`` files.

Regenerate:
    pytest tests/eval/test_prompt_snapshot.py --update-snapshot
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PROMPT_DIR = REPO_ROOT / "config" / "openclaw" / "prompts"
SNAPSHOT_PATH = Path(__file__).parent / "snapshots" / "prompts.sha256"

_EXCLUDED_NAMES = {".DS_Store", "Thumbs.db"}
_EXCLUDED_SUFFIXES = {".pyc", ".pyo"}


def _iter_prompt_files() -> list[Path]:
    if not PROMPT_DIR.exists():
        return []
    out: list[Path] = []
    for p in sorted(PROMPT_DIR.rglob("*")):
        if not p.is_file():
            continue
        if p.name in _EXCLUDED_NAMES:
            continue
        if p.suffix in _EXCLUDED_SUFFIXES:
            continue
        out.append(p)
    return out


def _hash_file(p: Path) -> str:
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


def _build_current_manifest() -> dict[str, str]:
    """Returns {relative_path: sha256} for every prompt file."""
    manifest: dict[str, str] = {}
    for p in _iter_prompt_files():
        rel = p.relative_to(PROMPT_DIR).as_posix()
        manifest[rel] = _hash_file(p)
    return manifest


def _load_snapshot() -> dict[str, str]:
    if not SNAPSHOT_PATH.exists():
        return {}
    out: dict[str, str] = {}
    for line in SNAPSHOT_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # format: "<sha256>  <relative/path>"
        parts = line.split(maxsplit=1)
        if len(parts) != 2:
            continue
        sha, rel = parts
        out[rel] = sha
    return out


def _write_snapshot(manifest: dict[str, str]) -> None:
    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Auto-generated; regenerate with `pytest --update-snapshot`"]
    for rel in sorted(manifest):
        lines.append(f"{manifest[rel]}  {rel}")
    SNAPSHOT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_prompt_bundle_snapshot(request: pytest.FixtureRequest) -> None:
    if not PROMPT_DIR.exists():
        pytest.skip(f"prompt dir not found: {PROMPT_DIR}")

    current = _build_current_manifest()
    if not current:
        pytest.skip(f"no prompt files under {PROMPT_DIR}")

    update = bool(
        request.config.getoption("update_snapshot", default=False)
        or request.config.getoption("--update-snapshot", default=False)
    )
    if update:
        _write_snapshot(current)
        return  # treat as pass after write

    stored = _load_snapshot()
    if not stored:
        # First run — seed the snapshot so the test is self-bootstrapping.
        _write_snapshot(current)
        return

    missing = sorted(set(stored) - set(current))
    added = sorted(set(current) - set(stored))
    changed = sorted(
        rel for rel in set(stored) & set(current) if stored[rel] != current[rel]
    )

    if missing or added or changed:
        diff_lines = []
        for rel in added:
            diff_lines.append(f"+ {rel}  {current[rel]}")
        for rel in missing:
            diff_lines.append(f"- {rel}  {stored[rel]}")
        for rel in changed:
            diff_lines.append(
                f"~ {rel}  {stored[rel][:12]}…  ->  {current[rel][:12]}…"
            )
        pytest.fail(
            "Prompt snapshot drift detected.  Regenerate with "
            "`pytest tests/eval/test_prompt_snapshot.py --update-snapshot`\n"
            + "\n".join(diff_lines)
        )
