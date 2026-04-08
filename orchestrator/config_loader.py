"""Config-First Agent Definition — REQ-CORE-03: YAML Agent Definitions.

Loads agent definitions from YAML files, validates them against trust level
constraints, and produces AgentConfig objects ready for the Scheduler.

Directory structure::

    agents/
      coding-agent.yaml
      review-agent.yaml
      deploy-agent.yaml

Example YAML::

    name: coding-agent
    display_name: "Coding Assistant"
    trust_level: L3_AUTONOMOUS
    capabilities:
      - code_generation
      - test_writing
    tools:
      - shell.exec
      - file.write
      - git.commit
    model: claude-sonnet-4-6
    policy_profile: default
    max_concurrent: 2
    timeout_seconds: 600
    metadata:
      team: engineering
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from orchestrator.models import AgentConfig
from policy_engine.trust_levels import TRUST_CONSTRAINTS, TrustLevel

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Agent definition model
# ---------------------------------------------------------------------------


@dataclass
class AgentDefinition:
    """Parsed and validated agent definition from YAML."""

    name: str
    display_name: str
    trust_level: TrustLevel
    capabilities: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    model: str = ""
    policy_profile: str = "default"
    max_concurrent: int = 1
    timeout_seconds: int = 300
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_agent_config(self) -> AgentConfig:
        """Convert to orchestrator AgentConfig."""
        return AgentConfig(
            agent_type=self.name,
            display_name=self.display_name,
            capabilities=self.capabilities,
            max_concurrent=self.max_concurrent,
            timeout_seconds=self.timeout_seconds,
            metadata={
                "trust_level": self.trust_level.name,
                "tools": self.tools,
                "model": self.model,
                "policy_profile": self.policy_profile,
                **self.metadata,
            },
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "trust_level": self.trust_level.name,
            "capabilities": self.capabilities,
            "tools": self.tools,
            "model": self.model,
            "policy_profile": self.policy_profile,
            "max_concurrent": self.max_concurrent,
            "timeout_seconds": self.timeout_seconds,
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ConfigLoaderError(Exception):
    """Configuration loading error."""


class AgentDefinitionError(ConfigLoaderError):
    """Invalid agent definition."""

    def __init__(self, name: str, reason: str) -> None:
        self.name = name
        self.reason = reason
        super().__init__(f"Invalid agent definition '{name}': {reason}")


class TrustViolationError(ConfigLoaderError):
    """Agent tools violate trust level constraints."""

    def __init__(self, name: str, violations: list[str]) -> None:
        self.name = name
        self.violations = violations
        super().__init__(
            f"Agent '{name}' trust violations: {'; '.join(violations)}"
        )


# ---------------------------------------------------------------------------
# Config Loader
# ---------------------------------------------------------------------------


class ConfigLoader:
    """Loads and validates YAML agent definitions — REQ-CORE-03.

    Features:
    - YAML agent definition files in ``agents/`` directory
    - Trust level constraint validation
    - Tool category extraction and checking
    - Produces AgentConfig objects for the Scheduler
    """

    # Tool → category mapping for trust validation
    TOOL_CATEGORIES: dict[str, str] = {
        "shell.exec": "execute",
        "shell.read": "read",
        "file.read": "read",
        "file.write": "write",
        "file.delete": "write",
        "git.commit": "write",
        "git.push": "network",
        "git.pull": "network",
        "http.request": "network",
        "http.fetch": "network",
        "browser.navigate": "network",
        "browser.click": "execute",
        "llm.generate": "generate",
        "llm.embed": "compute",
        "agent.spawn": "orchestrate",
        "agent.delegate": "orchestrate",
        "db.query": "read",
        "db.mutate": "write",
        "deploy.staging": "execute",
        "deploy.production": "admin",
    }

    def __init__(self, *, validate_trust: bool = True) -> None:
        self._validate_trust = validate_trust
        self._definitions: dict[str, AgentDefinition] = {}

    @property
    def definitions(self) -> dict[str, AgentDefinition]:
        """All loaded definitions by agent name."""
        return dict(self._definitions)

    def load_yaml(self, data: dict[str, Any]) -> AgentDefinition:
        """Parse and validate a single YAML agent definition dict.

        Raises AgentDefinitionError for missing/invalid fields.
        Raises TrustViolationError if tools violate trust constraints.
        """
        # Required fields
        name = data.get("name", "").strip()
        if not name:
            raise AgentDefinitionError("<unknown>", "Missing required field: name")

        display_name = data.get("display_name", name)
        if not display_name:
            raise AgentDefinitionError(name, "display_name must not be empty")

        # Trust level parsing
        trust_str = data.get("trust_level", "")
        if not trust_str:
            raise AgentDefinitionError(name, "Missing required field: trust_level")

        try:
            trust_level = TrustLevel[trust_str]
        except KeyError:
            valid = [t.name for t in TrustLevel]
            raise AgentDefinitionError(
                name,
                f"Invalid trust_level '{trust_str}'. Valid: {valid}",
            )

        # Optional fields with defaults
        capabilities = data.get("capabilities", [])
        if not isinstance(capabilities, list):
            raise AgentDefinitionError(name, "capabilities must be a list")

        tools = data.get("tools", [])
        if not isinstance(tools, list):
            raise AgentDefinitionError(name, "tools must be a list")

        model = data.get("model", "")
        policy_profile = data.get("policy_profile", "default")

        max_concurrent = data.get("max_concurrent", 1)
        if not isinstance(max_concurrent, int) or max_concurrent < 1:
            raise AgentDefinitionError(
                name, "max_concurrent must be a positive integer"
            )

        timeout_seconds = data.get("timeout_seconds", 300)
        if not isinstance(timeout_seconds, int) or timeout_seconds < 1:
            raise AgentDefinitionError(
                name, "timeout_seconds must be a positive integer"
            )

        metadata = data.get("metadata", {})
        if not isinstance(metadata, dict):
            raise AgentDefinitionError(name, "metadata must be a dict")

        defn = AgentDefinition(
            name=name,
            display_name=display_name,
            trust_level=trust_level,
            capabilities=capabilities,
            tools=tools,
            model=model,
            policy_profile=policy_profile,
            max_concurrent=max_concurrent,
            timeout_seconds=timeout_seconds,
            metadata=metadata,
        )

        # Trust validation
        if self._validate_trust:
            self._check_trust_constraints(defn)

        self._definitions[name] = defn
        logger.info(
            "Loaded agent definition: name=%s trust=%s tools=%d",
            name,
            trust_level.name,
            len(tools),
        )
        return defn

    def load_directory(self, directory: str | Path) -> list[AgentDefinition]:
        """Load all YAML agent definitions from a directory.

        Returns list of successfully loaded definitions.
        Raises ConfigLoaderError if directory doesn't exist.
        """
        try:
            import yaml
        except ImportError:
            raise ConfigLoaderError(
                "pyyaml package is required for YAML config loading. "
                "Install with: pip install pyyaml"
            )

        path = Path(directory)
        if not path.is_dir():
            raise ConfigLoaderError(f"Agent directory not found: {path}")

        loaded: list[AgentDefinition] = []
        for yaml_file in sorted(path.glob("*.yaml")):
            try:
                with open(yaml_file) as f:
                    data = yaml.safe_load(f)
                if not isinstance(data, dict):
                    logger.warning("Skipping %s: not a valid YAML dict", yaml_file)
                    continue
                defn = self.load_yaml(data)
                loaded.append(defn)
            except (AgentDefinitionError, TrustViolationError) as exc:
                logger.error("Failed to load %s: %s", yaml_file, exc)
                raise

        logger.info(
            "Loaded %d agent definitions from %s", len(loaded), directory,
        )
        return loaded

    def _check_trust_constraints(self, defn: AgentDefinition) -> None:
        """Validate that agent's tools are allowed by its trust level."""
        constraint = TRUST_CONSTRAINTS[defn.trust_level]
        violations: list[str] = []

        for tool in defn.tools:
            category = self.TOOL_CATEGORIES.get(tool, "")
            if category and category not in constraint.max_tool_categories:
                violations.append(
                    f"Tool '{tool}' (category: {category}) not allowed "
                    f"at trust level {defn.trust_level.name} "
                    f"(allowed: {list(constraint.max_tool_categories)})"
                )

        # Check LLM usage
        has_llm_tool = any(
            t.startswith("llm.") for t in defn.tools
        )
        if has_llm_tool and not constraint.can_use_llm:
            violations.append(
                f"LLM tools not allowed at trust level {defn.trust_level.name}"
            )

        # Check network usage
        has_network_tool = any(
            self.TOOL_CATEGORIES.get(t, "") == "network" for t in defn.tools
        )
        if has_network_tool and not constraint.can_access_network:
            violations.append(
                f"Network tools not allowed at trust level {defn.trust_level.name}"
            )

        # Check spawn/orchestration
        has_spawn_tool = any(
            t.startswith("agent.") for t in defn.tools
        )
        if has_spawn_tool and not constraint.can_spawn_children:
            violations.append(
                f"Agent spawn tools not allowed at trust level {defn.trust_level.name}"
            )

        if violations:
            raise TrustViolationError(defn.name, violations)

    def get_agent_configs(self) -> list[AgentConfig]:
        """Convert all loaded definitions to AgentConfig objects."""
        return [d.to_agent_config() for d in self._definitions.values()]

    def get_definition(self, name: str) -> AgentDefinition | None:
        """Get a specific agent definition by name."""
        return self._definitions.get(name)

    def clear(self) -> None:
        """Clear all loaded definitions."""
        self._definitions.clear()
