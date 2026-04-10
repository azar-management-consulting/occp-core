"""Trust Level enforcement — REQ-GOV-06.

Defines L0–L5 trust hierarchy and enforces constraints at the VAP Gate stage.
Child agents inherit parent trust level minus 1.

Usage::

    enforcer = TrustEnforcer()
    result = enforcer.check_action("agent-001", TrustLevel.L2_SUPERVISED, "shell.exec")
    if not result.allowed:
        raise PermissionError(result.reason)
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Trust Level Enum
# ---------------------------------------------------------------------------


class TrustLevel(enum.IntEnum):
    """Hierarchical trust levels for agents.

    Higher levels grant more autonomy.  Each level subsumes the
    capabilities of all lower levels.
    """

    L0_DETERMINISTIC = 0
    """Pure deterministic execution — no LLM, no external calls."""

    L1_CONSTRAINED = 1
    """LLM with strict output constraints (e.g., template-only)."""

    L2_SUPERVISED = 2
    """LLM with mandatory human oversight on every action."""

    L3_AUTONOMOUS = 3
    """LLM with policy-gated autonomy — human review only on flagged actions."""

    L4_DELEGATING = 4
    """Can spawn child agents (child inherits parent level - 1)."""

    L5_ORCHESTRATOR = 5
    """Multi-agent orchestrator — full delegation chain."""


# ---------------------------------------------------------------------------
# Trust Constraints per Level
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TrustConstraint:
    """Defines what a trust level is allowed to do."""

    level: TrustLevel
    can_use_llm: bool = False
    can_execute_tools: bool = False
    can_access_network: bool = False
    can_spawn_children: bool = False
    requires_human_approval: bool = True
    max_tool_categories: frozenset[str] = field(default_factory=frozenset)
    max_output_tokens: int = 0
    max_child_depth: int = 0


# Default constraint table
TRUST_CONSTRAINTS: dict[TrustLevel, TrustConstraint] = {
    TrustLevel.L0_DETERMINISTIC: TrustConstraint(
        level=TrustLevel.L0_DETERMINISTIC,
        can_use_llm=False,
        can_execute_tools=True,
        can_access_network=False,
        can_spawn_children=False,
        requires_human_approval=False,
        max_tool_categories=frozenset({"read", "compute"}),
        max_output_tokens=0,
        max_child_depth=0,
    ),
    TrustLevel.L1_CONSTRAINED: TrustConstraint(
        level=TrustLevel.L1_CONSTRAINED,
        can_use_llm=True,
        can_execute_tools=True,
        can_access_network=False,
        can_spawn_children=False,
        requires_human_approval=True,
        max_tool_categories=frozenset({"read", "compute", "generate"}),
        max_output_tokens=4096,
        max_child_depth=0,
    ),
    TrustLevel.L2_SUPERVISED: TrustConstraint(
        level=TrustLevel.L2_SUPERVISED,
        can_use_llm=True,
        can_execute_tools=True,
        can_access_network=True,
        can_spawn_children=False,
        requires_human_approval=True,
        max_tool_categories=frozenset({"read", "compute", "generate", "write", "network"}),
        max_output_tokens=16384,
        max_child_depth=0,
    ),
    TrustLevel.L3_AUTONOMOUS: TrustConstraint(
        level=TrustLevel.L3_AUTONOMOUS,
        can_use_llm=True,
        can_execute_tools=True,
        can_access_network=True,
        can_spawn_children=False,
        requires_human_approval=False,
        max_tool_categories=frozenset({"read", "compute", "generate", "write", "network", "execute"}),
        max_output_tokens=65536,
        max_child_depth=0,
    ),
    TrustLevel.L4_DELEGATING: TrustConstraint(
        level=TrustLevel.L4_DELEGATING,
        can_use_llm=True,
        can_execute_tools=True,
        can_access_network=True,
        can_spawn_children=True,
        requires_human_approval=False,
        max_tool_categories=frozenset({"read", "compute", "generate", "write", "network", "execute", "admin"}),
        max_output_tokens=131072,
        max_child_depth=2,
    ),
    TrustLevel.L5_ORCHESTRATOR: TrustConstraint(
        level=TrustLevel.L5_ORCHESTRATOR,
        can_use_llm=True,
        can_execute_tools=True,
        can_access_network=True,
        can_spawn_children=True,
        requires_human_approval=False,
        max_tool_categories=frozenset({"read", "compute", "generate", "write", "network", "execute", "admin", "orchestrate"}),
        max_output_tokens=262144,
        max_child_depth=5,
    ),
}


# ---------------------------------------------------------------------------
# Check Results
# ---------------------------------------------------------------------------


@dataclass
class TrustCheckResult:
    """Outcome of a trust level enforcement check."""

    allowed: bool
    agent_id: str = ""
    trust_level: TrustLevel = TrustLevel.L0_DETERMINISTIC
    reason: str = ""
    constraint_violated: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize for audit trail."""
        return {
            "allowed": self.allowed,
            "agent_id": self.agent_id,
            "trust_level": self.trust_level.name,
            "trust_level_value": int(self.trust_level),
            "reason": self.reason,
            "constraint_violated": self.constraint_violated,
        }


# ---------------------------------------------------------------------------
# Trust Enforcer
# ---------------------------------------------------------------------------


class TrustEnforcer:
    """Enforces trust level constraints at the VAP Gate stage.

    REQ-GOV-06: Each agent has a trust level. Actions are only
    permitted if the agent's trust level grants the required capability.
    Child agents inherit parent trust level minus 1.
    """

    def __init__(
        self,
        constraints: dict[TrustLevel, TrustConstraint] | None = None,
    ) -> None:
        self._constraints = constraints or TRUST_CONSTRAINTS
        self._agent_levels: dict[str, TrustLevel] = {}

    def register_agent(self, agent_id: str, level: TrustLevel) -> None:
        """Register or update an agent's trust level."""
        if not isinstance(level, TrustLevel):
            raise ValueError(f"Invalid trust level: {level}")
        self._agent_levels[agent_id] = level

    def get_level(self, agent_id: str) -> TrustLevel | None:
        """Get an agent's registered trust level, or None if unregistered."""
        return self._agent_levels.get(agent_id)

    def check_action(
        self,
        agent_id: str,
        trust_level: TrustLevel,
        action: str,
        *,
        tool_category: str = "",
        requires_llm: bool = False,
        requires_network: bool = False,
        requires_spawn: bool = False,
    ) -> TrustCheckResult:
        """Check if an agent at the given trust level can perform an action.

        Returns a :class:`TrustCheckResult` indicating whether the action
        is allowed and, if not, which constraint was violated.
        """
        constraint = self._constraints.get(trust_level)
        if constraint is None:
            return TrustCheckResult(
                allowed=False,
                agent_id=agent_id,
                trust_level=trust_level,
                reason=f"Unknown trust level: {trust_level}",
                constraint_violated="unknown_level",
            )

        # LLM access check
        if requires_llm and not constraint.can_use_llm:
            return TrustCheckResult(
                allowed=False,
                agent_id=agent_id,
                trust_level=trust_level,
                reason=f"Trust level {trust_level.name} does not permit LLM access",
                constraint_violated="can_use_llm",
            )

        # Network access check
        if requires_network and not constraint.can_access_network:
            return TrustCheckResult(
                allowed=False,
                agent_id=agent_id,
                trust_level=trust_level,
                reason=f"Trust level {trust_level.name} does not permit network access",
                constraint_violated="can_access_network",
            )

        # Spawn check
        if requires_spawn and not constraint.can_spawn_children:
            return TrustCheckResult(
                allowed=False,
                agent_id=agent_id,
                trust_level=trust_level,
                reason=f"Trust level {trust_level.name} does not permit spawning children",
                constraint_violated="can_spawn_children",
            )

        # Tool category check
        if tool_category and tool_category not in constraint.max_tool_categories:
            return TrustCheckResult(
                allowed=False,
                agent_id=agent_id,
                trust_level=trust_level,
                reason=(
                    f"Trust level {trust_level.name} does not permit "
                    f"tool category '{tool_category}'"
                ),
                constraint_violated="tool_category",
            )

        return TrustCheckResult(
            allowed=True,
            agent_id=agent_id,
            trust_level=trust_level,
        )

    @staticmethod
    def inherit_level(parent_level: TrustLevel) -> TrustLevel:
        """Compute child trust level: parent level minus 1.

        REQ-GOV-06: Child agents inherit parent trust level minus 1.
        L0 parents cannot spawn children (returns L0).
        """
        child_value = max(0, int(parent_level) - 1)
        return TrustLevel(child_value)

    def validate_spawn(
        self,
        parent_id: str,
        parent_level: TrustLevel,
        child_level: TrustLevel,
        *,
        current_depth: int = 0,
    ) -> TrustCheckResult:
        """Validate that a parent agent can spawn a child at the requested level.

        Rules:
        1. Parent must have can_spawn_children capability
        2. Child level must be <= parent level - 1
        3. Current spawn depth must be within max_child_depth
        """
        constraint = self._constraints.get(parent_level)
        if constraint is None:
            return TrustCheckResult(
                allowed=False,
                agent_id=parent_id,
                trust_level=parent_level,
                reason=f"Unknown parent trust level: {parent_level}",
                constraint_violated="unknown_level",
            )

        if not constraint.can_spawn_children:
            return TrustCheckResult(
                allowed=False,
                agent_id=parent_id,
                trust_level=parent_level,
                reason=f"Trust level {parent_level.name} cannot spawn children",
                constraint_violated="can_spawn_children",
            )

        max_child = self.inherit_level(parent_level)
        if child_level > max_child:
            return TrustCheckResult(
                allowed=False,
                agent_id=parent_id,
                trust_level=parent_level,
                reason=(
                    f"Child level {child_level.name} exceeds maximum "
                    f"{max_child.name} (parent {parent_level.name} - 1)"
                ),
                constraint_violated="child_level_exceeded",
            )

        if current_depth >= constraint.max_child_depth:
            return TrustCheckResult(
                allowed=False,
                agent_id=parent_id,
                trust_level=parent_level,
                reason=(
                    f"Spawn depth {current_depth} exceeds maximum "
                    f"{constraint.max_child_depth} for {parent_level.name}"
                ),
                constraint_violated="max_child_depth",
            )

        return TrustCheckResult(
            allowed=True,
            agent_id=parent_id,
            trust_level=parent_level,
        )

    def get_constraint(self, level: TrustLevel) -> TrustConstraint | None:
        """Return the constraint definition for a trust level."""
        return self._constraints.get(level)

    @property
    def registered_agents(self) -> dict[str, TrustLevel]:
        """Return a copy of all registered agent trust levels."""
        return dict(self._agent_levels)
