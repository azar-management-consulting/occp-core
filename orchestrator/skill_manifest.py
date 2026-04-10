"""Capability Declaration Schema — REQ-TSF-02.

Every skill declares capabilities via structured manifest:
- Network scope (domains)
- File scope (paths)
- System command scope (commands)
- Data domain scope (PII, financial, medical)

Policy gate uses declared capabilities to enforce boundaries.

Acceptance Tests:
  (1) Skill without manifest rejected.
  (2) Skill declaring ``network: [api.example.com]`` blocked from other domains.
  (3) Skill declaring ``data: [pii]`` triggers enhanced audit logging.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class DataDomain(str, Enum):
    """Sensitive data domains that trigger enhanced controls."""
    PII = "pii"
    FINANCIAL = "financial"
    MEDICAL = "medical"
    CREDENTIALS = "credentials"
    INTERNAL = "internal"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class ManifestError(Exception):
    """Base error for manifest operations."""


class ManifestValidationError(ManifestError):
    """Manifest fails validation."""


class ManifestRequiredError(ManifestError):
    """Skill has no manifest — rejected by policy."""


# ---------------------------------------------------------------------------
# Capability scopes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class NetworkScope:
    """Allowed network destinations for a skill."""
    allowed_domains: list[str] = field(default_factory=list)
    allow_all: bool = False

    def is_domain_allowed(self, domain: str) -> bool:
        """Check if a domain is within the declared scope."""
        if self.allow_all:
            return True
        domain_lower = domain.lower()
        for pattern in self.allowed_domains:
            pat = pattern.lower()
            if pat == domain_lower:
                return True
            # Wildcard: *.example.com matches sub.example.com
            if pat.startswith("*.") and domain_lower.endswith(pat[1:]):
                return True
        return False

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"allowedDomains": self.allowed_domains}
        if self.allow_all:
            d["allowAll"] = True
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NetworkScope:
        return cls(
            allowed_domains=data.get("allowedDomains", []),
            allow_all=data.get("allowAll", False),
        )


@dataclass(frozen=True)
class FileScope:
    """Allowed filesystem paths for a skill."""
    allowed_paths: list[str] = field(default_factory=list)
    read_only: bool = True

    def is_path_allowed(self, path: str) -> bool:
        """Check if a path is within the declared scope."""
        for allowed in self.allowed_paths:
            if path.startswith(allowed):
                return True
        return len(self.allowed_paths) == 0 and self.read_only

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowedPaths": self.allowed_paths,
            "readOnly": self.read_only,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FileScope:
        return cls(
            allowed_paths=data.get("allowedPaths", []),
            read_only=data.get("readOnly", True),
        )


@dataclass(frozen=True)
class CommandScope:
    """Allowed system commands for a skill."""
    allowed_commands: list[str] = field(default_factory=list)

    def is_command_allowed(self, command: str) -> bool:
        """Check if a command is within the declared scope."""
        cmd_base = command.split()[0] if command else ""
        return cmd_base in self.allowed_commands

    def to_dict(self) -> dict[str, Any]:
        return {"allowedCommands": self.allowed_commands}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CommandScope:
        return cls(allowed_commands=data.get("allowedCommands", []))


@dataclass(frozen=True)
class DataScope:
    """Declared data domains the skill accesses."""
    domains: list[str] = field(default_factory=list)

    @property
    def has_pii(self) -> bool:
        return DataDomain.PII.value in self.domains

    @property
    def has_financial(self) -> bool:
        return DataDomain.FINANCIAL.value in self.domains

    @property
    def has_medical(self) -> bool:
        return DataDomain.MEDICAL.value in self.domains

    @property
    def requires_enhanced_audit(self) -> bool:
        """True if any sensitive domain declared."""
        sensitive = {DataDomain.PII.value, DataDomain.FINANCIAL.value,
                     DataDomain.MEDICAL.value, DataDomain.CREDENTIALS.value}
        return bool(set(self.domains) & sensitive)

    def to_dict(self) -> dict[str, Any]:
        return {"domains": self.domains}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DataScope:
        return cls(domains=data.get("domains", []))


# ---------------------------------------------------------------------------
# SkillManifest
# ---------------------------------------------------------------------------

@dataclass
class SkillManifest:
    """Complete capability declaration for a skill."""

    skill_id: str
    name: str
    version: str
    description: str = ""
    author: str = ""
    network: NetworkScope = field(default_factory=NetworkScope)
    filesystem: FileScope = field(default_factory=FileScope)
    commands: CommandScope = field(default_factory=CommandScope)
    data: DataScope = field(default_factory=DataScope)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "skillId": self.skill_id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "capabilities": {
                "network": self.network.to_dict(),
                "filesystem": self.filesystem.to_dict(),
                "commands": self.commands.to_dict(),
                "data": self.data.to_dict(),
            },
            "metadata": self.metadata,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SkillManifest:
        caps = data.get("capabilities", {})
        return cls(
            skill_id=data["skillId"],
            name=data["name"],
            version=data["version"],
            description=data.get("description", ""),
            author=data.get("author", ""),
            network=NetworkScope.from_dict(caps.get("network", {})),
            filesystem=FileScope.from_dict(caps.get("filesystem", {})),
            commands=CommandScope.from_dict(caps.get("commands", {})),
            data=DataScope.from_dict(caps.get("data", {})),
            metadata=data.get("metadata", {}),
        )

    @classmethod
    def from_json(cls, raw: str) -> SkillManifest:
        return cls.from_dict(json.loads(raw))


# ---------------------------------------------------------------------------
# ManifestValidator
# ---------------------------------------------------------------------------

class ManifestValidator:
    """Validates skill manifests against policy requirements.

    Fail-closed: skills without manifests are rejected.
    """

    def __init__(
        self,
        *,
        require_manifest: bool = True,
        max_network_domains: int = 50,
        max_file_paths: int = 20,
        max_commands: int = 10,
        blocked_domains: list[str] | None = None,
        blocked_commands: list[str] | None = None,
    ) -> None:
        self._require_manifest = require_manifest
        self._max_network = max_network_domains
        self._max_paths = max_file_paths
        self._max_commands = max_commands
        self._blocked_domains = [d.lower() for d in (blocked_domains or [])]
        self._blocked_commands = blocked_commands or []

    def validate(self, manifest: SkillManifest | None) -> list[str]:
        """Validate a manifest. Returns list of violations (empty = valid).

        Raises:
            ManifestRequiredError: If no manifest provided and required.
        """
        if manifest is None:
            if self._require_manifest:
                raise ManifestRequiredError(
                    "Skill manifest is required. Skills without manifests are rejected."
                )
            return []

        violations: list[str] = []

        # Required fields
        if not manifest.skill_id:
            violations.append("Missing skill_id")
        if not manifest.name:
            violations.append("Missing name")
        if not manifest.version:
            violations.append("Missing version")

        # Network scope limits
        if len(manifest.network.allowed_domains) > self._max_network:
            violations.append(
                f"Too many network domains: {len(manifest.network.allowed_domains)} > {self._max_network}"
            )

        # Blocked domains
        for domain in manifest.network.allowed_domains:
            if domain.lower() in self._blocked_domains:
                violations.append(f"Blocked domain in network scope: {domain}")

        # File scope limits
        if len(manifest.filesystem.allowed_paths) > self._max_paths:
            violations.append(
                f"Too many file paths: {len(manifest.filesystem.allowed_paths)} > {self._max_paths}"
            )

        # Path traversal check
        for path in manifest.filesystem.allowed_paths:
            if ".." in path:
                violations.append(f"Path traversal detected: {path}")

        # Command scope limits
        if len(manifest.commands.allowed_commands) > self._max_commands:
            violations.append(
                f"Too many commands: {len(manifest.commands.allowed_commands)} > {self._max_commands}"
            )

        # Blocked commands
        for cmd in manifest.commands.allowed_commands:
            if cmd in self._blocked_commands:
                violations.append(f"Blocked command in manifest: {cmd}")

        # Data domain validation
        valid_domains = {d.value for d in DataDomain}
        for d in manifest.data.domains:
            if d not in valid_domains:
                violations.append(f"Unknown data domain: {d}")

        return violations

    def check_network_access(
        self,
        manifest: SkillManifest,
        target_domain: str,
    ) -> bool:
        """Check if a skill is allowed to access a given domain.

        Returns True if allowed, False if blocked.
        """
        return manifest.network.is_domain_allowed(target_domain)

    def check_file_access(
        self,
        manifest: SkillManifest,
        target_path: str,
    ) -> bool:
        """Check if a skill is allowed to access a given path."""
        return manifest.filesystem.is_path_allowed(target_path)

    def check_command_access(
        self,
        manifest: SkillManifest,
        command: str,
    ) -> bool:
        """Check if a skill is allowed to execute a given command."""
        return manifest.commands.is_command_allowed(command)
