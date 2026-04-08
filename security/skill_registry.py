"""Private-First Skill Registry — REQ-TSF-01.

Default skill registry is private (org-scoped). Public OCCPHub is opt-in.
Private registries support self-hosted deployment without external network.

Acceptance Tests:
  (1) Fresh install has empty skill registry.
  (2) OCCPHub connection requires explicit ``hub_enable()``.
  (3) Private registry serves skills without external network.
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


# ---------------------------------------------------------------------------
# Enums & constants
# ---------------------------------------------------------------------------

class RegistryScope(str, Enum):
    """Registry visibility scope."""
    PRIVATE = "private"    # org-scoped, default
    PUBLIC = "public"      # OCCPHub (opt-in)


class SkillStatus(str, Enum):
    """Lifecycle status of an installed skill."""
    INSTALLED = "installed"
    ENABLED = "enabled"
    DISABLED = "disabled"
    REVOKED = "revoked"


DEFAULT_REGISTRY_URL = "https://hub.occp.ai/v1"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class RegistryError(Exception):
    """Base error for registry operations."""


class SkillNotFoundError(RegistryError):
    """Skill not found in registry."""


class HubNotEnabledError(RegistryError):
    """OCCPHub operations require explicit hub enable."""


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SkillRecord:
    """Metadata about an installed skill in the registry."""

    skill_id: str
    name: str
    version: str
    description: str = ""
    author: str = ""
    scope: str = "private"          # "private" or "public"
    source: str = "local"           # "local", "hub", or custom registry URL
    installed_at: float = 0.0
    hash_sha256: str = ""
    capabilities: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "skillId": self.skill_id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "scope": self.scope,
            "source": self.source,
            "installedAt": self.installed_at,
            "hashSha256": self.hash_sha256,
            "capabilities": self.capabilities,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SkillRecord:
        return cls(
            skill_id=data["skillId"],
            name=data["name"],
            version=data["version"],
            description=data.get("description", ""),
            author=data.get("author", ""),
            scope=data.get("scope", "private"),
            source=data.get("source", "local"),
            installed_at=data.get("installedAt", 0.0),
            hash_sha256=data.get("hashSha256", ""),
            capabilities=data.get("capabilities", {}),
            metadata=data.get("metadata", {}),
        )


@dataclass
class HubConfig:
    """Configuration for OCCPHub connection (opt-in)."""

    enabled: bool = False
    url: str = DEFAULT_REGISTRY_URL
    api_key: str = ""
    enabled_at: float = 0.0
    enabled_by: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "url": self.url,
            "enabledAt": self.enabled_at,
            "enabledBy": self.enabled_by,
            # api_key intentionally excluded from serialization
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HubConfig:
        return cls(
            enabled=data.get("enabled", False),
            url=data.get("url", DEFAULT_REGISTRY_URL),
            enabled_at=data.get("enabledAt", 0.0),
            enabled_by=data.get("enabledBy", ""),
        )


# ---------------------------------------------------------------------------
# SkillRegistry — private-first
# ---------------------------------------------------------------------------

class SkillRegistry:
    """Private-first skill registry.

    - Fresh install → empty registry (no pre-installed skills)
    - All skills are org-scoped (private) by default
    - OCCPHub connection is opt-in (requires explicit ``hub_enable()``)
    - Supports self-hosted deployment (no external network needed)
    """

    def __init__(self, org_id: str = "default") -> None:
        self._org_id = org_id
        self._skills: dict[str, SkillRecord] = {}   # skill_id → SkillRecord
        self._hub = HubConfig()

    # -- Properties ----------------------------------------------------------

    @property
    def org_id(self) -> str:
        return self._org_id

    @property
    def hub_enabled(self) -> bool:
        return self._hub.enabled

    @property
    def hub_config(self) -> HubConfig:
        return self._hub

    @property
    def skill_count(self) -> int:
        return len(self._skills)

    @property
    def installed_skills(self) -> list[str]:
        """Return list of installed skill IDs."""
        return list(self._skills.keys())

    # -- Hub management (opt-in) ---------------------------------------------

    def hub_enable(
        self,
        *,
        url: str = DEFAULT_REGISTRY_URL,
        api_key: str = "",
        enabled_by: str = "",
    ) -> None:
        """Explicitly enable OCCPHub connection. Required for public skill access."""
        self._hub = HubConfig(
            enabled=True,
            url=url,
            api_key=api_key,
            enabled_at=time.time(),
            enabled_by=enabled_by,
        )
        logger.info("OCCPHub enabled: url=%s by=%s", url, enabled_by)

    def hub_disable(self) -> None:
        """Disable OCCPHub connection."""
        self._hub = HubConfig(enabled=False)
        logger.info("OCCPHub disabled")

    # -- Skill operations ----------------------------------------------------

    def install(
        self,
        skill_id: str,
        name: str,
        version: str,
        content_hash: str = "",
        *,
        description: str = "",
        author: str = "",
        source: str = "local",
        capabilities: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SkillRecord:
        """Install a skill into the private registry.

        Args:
            skill_id: Unique skill identifier.
            name: Human-readable name.
            version: Semantic version string.
            content_hash: SHA-256 hash of skill content.
            source: Origin — "local" (default) or "hub".

        Raises:
            HubNotEnabledError: If source is "hub" but hub is not enabled.
            RegistryError: If skill_id already installed (use upgrade instead).
        """
        if source == "hub" and not self._hub.enabled:
            raise HubNotEnabledError(
                f"Cannot install '{skill_id}' from OCCPHub — hub not enabled. "
                "Call hub_enable() first."
            )

        if skill_id in self._skills:
            raise RegistryError(
                f"Skill '{skill_id}' already installed at version "
                f"{self._skills[skill_id].version}. Use upgrade() instead."
            )

        record = SkillRecord(
            skill_id=skill_id,
            name=name,
            version=version,
            description=description,
            author=author,
            scope="private",
            source=source,
            installed_at=time.time(),
            hash_sha256=content_hash,
            capabilities=capabilities or {},
            metadata=metadata or {},
        )
        self._skills[skill_id] = record
        logger.info(
            "Skill installed: id=%s version=%s source=%s",
            skill_id, version, source,
        )
        return record

    def uninstall(self, skill_id: str) -> bool:
        """Remove a skill from the registry. Returns True if it existed."""
        if skill_id not in self._skills:
            return False
        del self._skills[skill_id]
        logger.info("Skill uninstalled: id=%s", skill_id)
        return True

    def upgrade(
        self,
        skill_id: str,
        new_version: str,
        content_hash: str = "",
        **kwargs: Any,
    ) -> SkillRecord:
        """Upgrade an installed skill to a new version.

        Raises:
            SkillNotFoundError: If skill_id is not installed.
        """
        old = self._skills.get(skill_id)
        if old is None:
            raise SkillNotFoundError(f"Cannot upgrade: '{skill_id}' not installed")

        new_record = SkillRecord(
            skill_id=skill_id,
            name=kwargs.get("name", old.name),
            version=new_version,
            description=kwargs.get("description", old.description),
            author=kwargs.get("author", old.author),
            scope=old.scope,
            source=old.source,
            installed_at=time.time(),
            hash_sha256=content_hash or old.hash_sha256,
            capabilities=kwargs.get("capabilities", old.capabilities),
            metadata=kwargs.get("metadata", old.metadata),
        )
        self._skills[skill_id] = new_record
        logger.info("Skill upgraded: id=%s %s → %s", skill_id, old.version, new_version)
        return new_record

    def get(self, skill_id: str) -> SkillRecord | None:
        """Get a skill record by ID. Returns None if not found."""
        return self._skills.get(skill_id)

    def list_skills(self, *, source: str = "") -> list[SkillRecord]:
        """List all installed skills, optionally filtered by source."""
        if source:
            return [s for s in self._skills.values() if s.source == source]
        return list(self._skills.values())

    def is_installed(self, skill_id: str) -> bool:
        return skill_id in self._skills

    # -- Search hub (requires hub enabled) -----------------------------------

    def search_hub(self, query: str) -> list[dict[str, Any]]:
        """Search OCCPHub for skills. Requires hub to be enabled.

        In production, this would make an HTTP call to the hub API.
        This implementation provides the interface contract.

        Raises:
            HubNotEnabledError: If hub is not enabled.
        """
        if not self._hub.enabled:
            raise HubNotEnabledError(
                "Cannot search OCCPHub — hub not enabled. Call hub_enable() first."
            )
        # Stub — real implementation would call self._hub.url
        return []

    # -- Serialization -------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "orgId": self._org_id,
            "hub": self._hub.to_dict(),
            "skills": {sid: rec.to_dict() for sid, rec in self._skills.items()},
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SkillRegistry:
        reg = cls(org_id=data.get("orgId", "default"))
        reg._hub = HubConfig.from_dict(data.get("hub", {}))
        for sid, sdata in data.get("skills", {}).items():
            reg._skills[sid] = SkillRecord.from_dict(sdata)
        return reg

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_json(cls, raw: str) -> SkillRegistry:
        return cls.from_dict(json.loads(raw))
