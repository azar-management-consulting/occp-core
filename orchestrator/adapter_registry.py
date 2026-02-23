"""Adapter Registry — routes pipeline stages to per-agent-type adapters.

Each agent_type can register its own Planner, Executor, Validator, and Shipper.
The Pipeline uses this registry to select adapters dynamically based on task.agent_type.
Unregistered types fall back to default adapters.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Protocols (re-exported for convenience)
# ---------------------------------------------------------------------------

class Planner(Protocol):
    async def create_plan(self, task: Any) -> dict[str, Any]: ...

class Executor(Protocol):
    async def execute(self, task: Any) -> dict[str, Any]: ...

class Validator(Protocol):
    async def validate(self, task: Any) -> list[str]: ...

class Shipper(Protocol):
    async def ship(self, task: Any) -> dict[str, Any]: ...


@dataclass
class AdapterSet:
    """A bundle of adapters for one agent type."""
    planner: Planner | None = None
    executor: Executor | None = None
    validator: Validator | None = None
    shipper: Shipper | None = None


class AdapterRegistry:
    """Maps agent_type → AdapterSet with fallback to defaults.

    Usage::

        registry = AdapterRegistry(
            default_planner=echo_planner,
            default_executor=mock_executor,
            default_validator=basic_validator,
            default_shipper=log_shipper,
        )
        registry.register("code-reviewer", planner=claude_planner)

        # Later, in Pipeline:
        planner = registry.get_planner("code-reviewer")  # → claude_planner
        planner = registry.get_planner("unknown-type")    # → echo_planner (default)
    """

    def __init__(
        self,
        *,
        default_planner: Planner,
        default_executor: Executor,
        default_validator: Validator,
        default_shipper: Shipper,
    ) -> None:
        self._defaults = AdapterSet(
            planner=default_planner,
            executor=default_executor,
            validator=default_validator,
            shipper=default_shipper,
        )
        self._overrides: dict[str, AdapterSet] = {}

    def register(
        self,
        agent_type: str,
        *,
        planner: Planner | None = None,
        executor: Executor | None = None,
        validator: Validator | None = None,
        shipper: Shipper | None = None,
    ) -> None:
        """Register adapter overrides for a specific agent type."""
        self._overrides[agent_type] = AdapterSet(
            planner=planner,
            executor=executor,
            validator=validator,
            shipper=shipper,
        )
        logger.info("Adapter overrides registered for agent_type=%s", agent_type)

    def unregister(self, agent_type: str) -> None:
        """Remove adapter overrides for an agent type."""
        self._overrides.pop(agent_type, None)

    def get_planner(self, agent_type: str) -> Planner:
        """Get planner for agent_type, falling back to default."""
        override = self._overrides.get(agent_type)
        if override and override.planner:
            return override.planner
        return self._defaults.planner  # type: ignore[return-value]

    def get_executor(self, agent_type: str) -> Executor:
        """Get executor for agent_type, falling back to default."""
        override = self._overrides.get(agent_type)
        if override and override.executor:
            return override.executor
        return self._defaults.executor  # type: ignore[return-value]

    def get_validator(self, agent_type: str) -> Validator:
        """Get validator for agent_type, falling back to default."""
        override = self._overrides.get(agent_type)
        if override and override.validator:
            return override.validator
        return self._defaults.validator  # type: ignore[return-value]

    def get_shipper(self, agent_type: str) -> Shipper:
        """Get shipper for agent_type, falling back to default."""
        override = self._overrides.get(agent_type)
        if override and override.shipper:
            return override.shipper
        return self._defaults.shipper  # type: ignore[return-value]

    @property
    def registered_types(self) -> list[str]:
        """List all agent types with custom adapter overrides."""
        return list(self._overrides.keys())

    def get_routing_info(self, agent_type: str) -> dict[str, str]:
        """Return which adapter source (default/override) is used per stage."""
        override = self._overrides.get(agent_type)
        return {
            "planner": "override" if (override and override.planner) else "default",
            "executor": "override" if (override and override.executor) else "default",
            "validator": "override" if (override and override.validator) else "default",
            "shipper": "override" if (override and override.shipper) else "default",
        }
