"""Version Pinning in Production — REQ-TSF-04.

No floating version installs in production mode (OCCP_ENV=production).
All skills pinned to exact version in ``skills.lock``.

Acceptance Tests:
  (1) ``occp skill install web-search@latest`` in production → error.
  (2) ``occp skill install web-search@1.2.3`` succeeds.
  (3) ``skills.lock`` tracks exact versions.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LOCKFILE_NAME = "skills.lock"
LOCKFILE_VERSION = "1"

# Version patterns
_EXACT_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+].+)?$")  # 1.2.3, 1.2.3-beta
_FLOATING_PATTERNS = {"latest", "stable", "next", "canary", "*"}


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class VersionPinningError(Exception):
    """Base error for version pinning operations."""


class FloatingVersionError(VersionPinningError):
    """Attempted floating version install in production."""


class LockfileIntegrityError(VersionPinningError):
    """Lockfile hash mismatch or corruption detected."""


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PinnedSkill:
    """A version-pinned skill entry in skills.lock."""

    skill_id: str
    version: str
    hash_sha256: str = ""
    source: str = "local"
    pinned_at: float = 0.0
    pinned_by: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "skillId": self.skill_id,
            "version": self.version,
            "hashSha256": self.hash_sha256,
            "source": self.source,
            "pinnedAt": self.pinned_at,
            "pinnedBy": self.pinned_by,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PinnedSkill:
        return cls(
            skill_id=data["skillId"],
            version=data["version"],
            hash_sha256=data.get("hashSha256", ""),
            source=data.get("source", "local"),
            pinned_at=data.get("pinnedAt", 0.0),
            pinned_by=data.get("pinnedBy", ""),
        )


# ---------------------------------------------------------------------------
# Version validation
# ---------------------------------------------------------------------------

def is_exact_version(version: str) -> bool:
    """Check if a version string is exact (not floating)."""
    if not version:
        return False
    if version.lower() in _FLOATING_PATTERNS:
        return False
    if version.startswith("^") or version.startswith("~") or version.startswith(">="):
        return False
    return bool(_EXACT_VERSION_RE.match(version))


def is_production_mode() -> bool:
    """Check if running in production mode (OCCP_ENV=production)."""
    return os.environ.get("OCCP_ENV", "").lower() == "production"


def parse_skill_spec(spec: str) -> tuple[str, str]:
    """Parse 'skill-id@version' into (skill_id, version).

    Examples:
        'web-search@1.2.3' → ('web-search', '1.2.3')
        'web-search@latest' → ('web-search', 'latest')
        'web-search' → ('web-search', '')
    """
    if "@" in spec:
        skill_id, version = spec.rsplit("@", 1)
        return skill_id, version
    return spec, ""


def validate_install_version(
    skill_id: str,
    version: str,
    *,
    production: bool | None = None,
) -> list[str]:
    """Validate a version for installation. Returns list of violations.

    In production mode:
      - Floating versions (latest, stable, ^, ~) are blocked.
      - Only exact semver versions allowed.

    Args:
        skill_id: Skill identifier.
        version: Version string to validate.
        production: Override production detection (for testing).
    """
    is_prod = production if production is not None else is_production_mode()
    violations: list[str] = []

    if not version:
        if is_prod:
            violations.append(
                f"No version specified for '{skill_id}' in production mode. "
                "Exact version required (e.g., web-search@1.2.3)."
            )
        return violations

    if is_prod and not is_exact_version(version):
        violations.append(
            f"Floating version '{version}' not allowed for '{skill_id}' in "
            "production mode. Pin to exact version (e.g., 1.2.3)."
        )

    return violations


# ---------------------------------------------------------------------------
# SkillsLockfile
# ---------------------------------------------------------------------------

class SkillsLockfile:
    """Manages skills.lock — version pinning for reproducible deployments.

    Format:
        {
            "lockfileVersion": "1",
            "generatedAt": <timestamp>,
            "contentHash": "<sha256>",
            "skills": { "<skill_id>": { ... PinnedSkill ... } }
        }
    """

    def __init__(self) -> None:
        self._skills: dict[str, PinnedSkill] = {}
        self._generated_at: float = 0.0

    # -- Properties ----------------------------------------------------------

    @property
    def skill_count(self) -> int:
        return len(self._skills)

    @property
    def pinned_skills(self) -> list[str]:
        return list(self._skills.keys())

    @property
    def generated_at(self) -> float:
        return self._generated_at

    # -- Operations ----------------------------------------------------------

    def pin(
        self,
        skill_id: str,
        version: str,
        hash_sha256: str = "",
        source: str = "local",
        pinned_by: str = "",
    ) -> PinnedSkill:
        """Pin a skill to an exact version.

        Raises:
            FloatingVersionError: If version is not exact.
        """
        if not is_exact_version(version):
            raise FloatingVersionError(
                f"Cannot pin '{skill_id}' to floating version '{version}'. "
                "Use exact version (e.g., 1.2.3)."
            )

        entry = PinnedSkill(
            skill_id=skill_id,
            version=version,
            hash_sha256=hash_sha256,
            source=source,
            pinned_at=time.time(),
            pinned_by=pinned_by,
        )
        self._skills[skill_id] = entry
        self._generated_at = time.time()
        logger.info("Skill pinned: %s@%s", skill_id, version)
        return entry

    def unpin(self, skill_id: str) -> bool:
        """Remove a skill from the lockfile. Returns True if it existed."""
        if skill_id not in self._skills:
            return False
        del self._skills[skill_id]
        self._generated_at = time.time()
        logger.info("Skill unpinned: %s", skill_id)
        return True

    def get(self, skill_id: str) -> PinnedSkill | None:
        """Get a pinned skill entry. Returns None if not pinned."""
        return self._skills.get(skill_id)

    def is_pinned(self, skill_id: str) -> bool:
        return skill_id in self._skills

    def check_version_match(self, skill_id: str, version: str) -> bool:
        """Check if the installed version matches the pinned version."""
        entry = self._skills.get(skill_id)
        if entry is None:
            return True  # not pinned, no constraint
        return entry.version == version

    def list_pins(self) -> list[PinnedSkill]:
        """Return all pinned skills."""
        return list(self._skills.values())

    # -- Content hash --------------------------------------------------------

    def content_hash(self) -> str:
        """Deterministic hash of lockfile content for integrity verification."""
        skills_data = {
            sid: entry.to_dict() for sid, entry in sorted(self._skills.items())
        }
        canonical = json.dumps(skills_data, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()

    # -- Serialization -------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "lockfileVersion": LOCKFILE_VERSION,
            "generatedAt": self._generated_at,
            "contentHash": self.content_hash(),
            "skills": {sid: e.to_dict() for sid, e in self._skills.items()},
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SkillsLockfile:
        lockfile = cls()
        lockfile._generated_at = data.get("generatedAt", 0.0)
        for sid, sdata in data.get("skills", {}).items():
            lockfile._skills[sid] = PinnedSkill.from_dict(sdata)
        return lockfile

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, indent=2)

    @classmethod
    def from_json(cls, raw: str) -> SkillsLockfile:
        return cls.from_dict(json.loads(raw))

    def verify_integrity(self, stored_hash: str | None = None) -> bool:
        """Verify lockfile content integrity.

        Args:
            stored_hash: Hash from the lockfile header. If None, recompute.
        """
        if stored_hash is None:
            return True  # no hash to check
        return self.content_hash() == stored_hash

    # -- File I/O ------------------------------------------------------------

    def save(self, path: Path | str) -> None:
        """Write lockfile to disk."""
        path = Path(path)
        path.write_text(self.to_json(), encoding="utf-8")
        logger.info("Lockfile saved: %s (%d skills)", path, self.skill_count)

    @classmethod
    def load(cls, path: Path | str) -> SkillsLockfile:
        """Load lockfile from disk.

        Raises:
            LockfileIntegrityError: If content hash doesn't match.
            FileNotFoundError: If lockfile doesn't exist.
        """
        path = Path(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        lockfile = cls.from_dict(data)

        stored_hash = data.get("contentHash", "")
        if stored_hash and not lockfile.verify_integrity(stored_hash):
            raise LockfileIntegrityError(
                f"Lockfile integrity check failed: {path}. "
                "Content may have been tampered with."
            )

        return lockfile

    @classmethod
    def load_or_create(cls, path: Path | str) -> SkillsLockfile:
        """Load existing lockfile or create empty one."""
        path = Path(path)
        if path.exists():
            return cls.load(path)
        return cls()
