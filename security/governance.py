"""Continuous Governance Loop — post-execution scanning and compliance checks.

Provides:
- GovernanceLoop: orchestrates post-execution output sanitization
- SessionGovernor: per-session policy enforcement (tool governance)

Integrates with PolicyEngine for audit trail and OutputSanitizationGuard
for post-execution PII/secret leakage detection.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from policy_engine.guards import GuardResult, HumanOversightGuard, OutputSanitizationGuard

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Agent Boundary Enforcement (Gap H)
# ---------------------------------------------------------------------------

# Capabilities that require system_admin role to register
ADMIN_ONLY_CAPABILITIES: frozenset[str] = frozenset({
    "policy-override",
    "governance-override",
    "agent-admin",
    "token-rotate",
    "system-config",
    "rbac-manage",
    "audit-delete",
    "user-impersonate",
})

# Maximum capabilities per agent (prevents unbounded scope)
MAX_CAPABILITIES_PER_AGENT: int = 20


@dataclass
class BoundaryCheckResult:
    """Result of agent boundary / capability scope validation."""

    allowed: bool
    agent_type: str
    reason: str = ""
    violations: list[str] = field(default_factory=list)


class AgentBoundaryGuard:
    """Enforces capability scope boundaries for agents.

    Validates that:
    1. Tasks only request capabilities within the agent's registered set
    2. Agent registrations do not include admin-level capabilities
       unless the caller has system_admin role
    3. No agent can exceed MAX_CAPABILITIES_PER_AGENT

    Usage::

        guard = AgentBoundaryGuard()
        result = guard.validate_task_scope(task_metadata, agent_config)
        if not result.allowed:
            # reject task — out of scope
    """

    def validate_task_scope(
        self,
        task_capabilities: list[str],
        agent_capabilities: list[str],
        agent_type: str = "",
    ) -> BoundaryCheckResult:
        """Check that requested task capabilities are within the agent's scope."""
        if not task_capabilities:
            return BoundaryCheckResult(allowed=True, agent_type=agent_type)

        agent_set = set(agent_capabilities)
        requested_set = set(task_capabilities)
        out_of_scope = requested_set - agent_set

        if out_of_scope:
            return BoundaryCheckResult(
                allowed=False,
                agent_type=agent_type,
                reason=f"Task requests capabilities outside agent scope: {', '.join(sorted(out_of_scope))}",
                violations=sorted(out_of_scope),
            )
        return BoundaryCheckResult(allowed=True, agent_type=agent_type)

    def validate_registration(
        self,
        capabilities: list[str],
        agent_type: str = "",
        *,
        caller_is_admin: bool = False,
    ) -> BoundaryCheckResult:
        """Validate agent registration capabilities for privilege escalation.

        Non-admin callers cannot register agents with admin-level capabilities.
        """
        violations: list[str] = []

        # Check capability count
        if len(capabilities) > MAX_CAPABILITIES_PER_AGENT:
            return BoundaryCheckResult(
                allowed=False,
                agent_type=agent_type,
                reason=f"Too many capabilities ({len(capabilities)} > {MAX_CAPABILITIES_PER_AGENT})",
            )

        # Check admin-only capabilities
        if not caller_is_admin:
            for cap in capabilities:
                if cap in ADMIN_ONLY_CAPABILITIES:
                    violations.append(cap)

        if violations:
            return BoundaryCheckResult(
                allowed=False,
                agent_type=agent_type,
                reason=f"Admin-only capabilities require system_admin role: {', '.join(sorted(violations))}",
                violations=sorted(violations),
            )
        return BoundaryCheckResult(allowed=True, agent_type=agent_type)


@dataclass
class GovernanceScanResult:
    """Result of a governance scan cycle."""

    passed: bool
    checks_run: int = 0
    checks_passed: int = 0
    issues: list[str] = field(default_factory=list)
    guard_results: list[GuardResult] = field(default_factory=list)


class GovernanceLoop:
    """Post-execution governance scanner.

    Runs after task execution to detect:
    - PII leakage in outputs (OutputSanitizationGuard)
    - API key / JWT exposure in results
    - Anomalous output patterns

    Usage::

        loop = GovernanceLoop()
        result = loop.scan_output({"result": "some output text"})
        if not result.passed:
            # quarantine or redact output
    """

    def __init__(self) -> None:
        self._output_guard = OutputSanitizationGuard()
        self._scan_count = 0
        self._violation_count = 0

    def scan_output(self, output: dict[str, Any]) -> GovernanceScanResult:
        """Scan execution output for policy violations."""
        self._scan_count += 1
        guard_results: list[GuardResult] = []
        issues: list[str] = []

        # Run output sanitization guard
        gr = self._output_guard.check(output)
        guard_results.append(gr)
        if not gr.passed:
            issues.append(f"Output sanitization: {gr.detail}")
            self._violation_count += 1

        checks_run = len(guard_results)
        checks_passed = sum(1 for g in guard_results if g.passed)

        return GovernanceScanResult(
            passed=len(issues) == 0,
            checks_run=checks_run,
            checks_passed=checks_passed,
            issues=issues,
            guard_results=guard_results,
        )

    @property
    def stats(self) -> dict[str, int]:
        """Return governance loop statistics."""
        return {
            "total_scans": self._scan_count,
            "total_violations": self._violation_count,
        }


@dataclass
class ToolPermission:
    """Per-tool permission entry for session governance."""

    tool_name: str
    allowed: bool = True
    requires_approval: bool = False
    max_calls_per_session: int = 0  # 0 = unlimited
    calls_made: int = 0


class SessionGovernor:
    """Per-session tool governance — enforces which tools an agent may call.

    Configured during onboarding step 7 (policy_config).
    Integrates with PolicyEngine for enforcement.

    Usage::

        gov = SessionGovernor(session_id="abc-123")
        gov.configure_tool("file_write", allowed=True, requires_approval=True)
        check = gov.check_tool_access("file_write")
        if not check.allowed:
            # block tool call
    """

    def __init__(self, session_id: str = "", *, human_oversight: bool = True) -> None:
        self.session_id = session_id
        self._tool_permissions: dict[str, ToolPermission] = {}
        self._default_allow = True  # open by default, restrict explicitly
        self.oversight = HumanOversightGuard(enabled=human_oversight)

    def configure_tool(
        self,
        tool_name: str,
        *,
        allowed: bool = True,
        requires_approval: bool = False,
        max_calls: int = 0,
    ) -> None:
        """Configure governance policy for a specific tool."""
        self._tool_permissions[tool_name] = ToolPermission(
            tool_name=tool_name,
            allowed=allowed,
            requires_approval=requires_approval,
            max_calls_per_session=max_calls,
        )

    def check_tool_access(self, tool_name: str) -> ToolPermission:
        """Check if a tool call is permitted under current session policy."""
        perm = self._tool_permissions.get(tool_name)
        if perm is None:
            # Default policy
            return ToolPermission(
                tool_name=tool_name,
                allowed=self._default_allow,
            )

        # Rate limit check
        if perm.max_calls_per_session > 0 and perm.calls_made >= perm.max_calls_per_session:
            return ToolPermission(
                tool_name=tool_name,
                allowed=False,
                requires_approval=False,
            )

        return perm

    def record_tool_call(self, tool_name: str) -> None:
        """Record that a tool was called (for rate limiting)."""
        perm = self._tool_permissions.get(tool_name)
        if perm:
            perm.calls_made += 1

    def set_default_policy(self, *, allow: bool) -> None:
        """Set the default policy for unconfigured tools."""
        self._default_allow = allow

    @property
    def configured_tools(self) -> list[str]:
        """Return list of tools with explicit governance configuration."""
        return list(self._tool_permissions.keys())

    def check_oversight(self, action: str) -> bool:
        """Check if an action requires human oversight approval.

        Returns True if approval is needed (i.e., action is blocked until approved).
        """
        return self.oversight.requires_approval(action)

    def approve_action(self, action: str) -> None:
        """Record human approval for a sensitive action."""
        self.oversight.approve(action)

    def to_dict(self) -> dict[str, Any]:
        """Serialize session governance state for audit/persistence."""
        return {
            "session_id": self.session_id,
            "default_allow": self._default_allow,
            "human_oversight": self.oversight.to_dict(),
            "tools": {
                name: {
                    "allowed": p.allowed,
                    "requires_approval": p.requires_approval,
                    "max_calls": p.max_calls_per_session,
                    "calls_made": p.calls_made,
                }
                for name, p in self._tool_permissions.items()
            },
        }
