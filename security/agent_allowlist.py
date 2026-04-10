"""Per-agent tool allowlist enforcement.

Each of the 8 specialist agents has a defined set of allowed tools.
Any tool call outside the allowlist is DENIED and logged.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ToolAccessResult:
    allowed: bool
    agent_id: str
    tool_name: str
    reason: str = ""


# Default tool allowlists per agent
AGENT_TOOL_ALLOWLISTS: dict[str, set[str]] = {
    "eng-core": {"bash", "read", "write", "edit", "grep", "glob", "browser", "exec", "test_runner"},
    "wp-web": {"bash", "read", "write", "edit", "grep", "glob", "browser", "wp_cli", "ftp"},
    "infra-ops": {"bash", "read", "exec", "ssh", "docker", "dns", "ssl", "grep", "glob"},
    "design-lab": {"read", "write", "browser", "screenshot"},  # NO bash, NO exec
    "content-forge": {"read", "write", "browser", "translate"},
    "social-growth": {"read", "write", "browser", "api_call"},
    "intel-research": {"read", "browser", "web_search", "web_fetch", "grep", "glob"},  # read-only workspace
    "biz-strategy": {"read", "write", "browser", "calculator", "web_search"},
    # Brain orchestrator — MCP bridge tools (server-side dispatch surface)
    "brain": {
        "brain.status", "brain.health",
        "filesystem.read", "filesystem.write", "filesystem.list",
        "http.get", "http.post",
        "wordpress.get_posts", "wordpress.get_pages",
        "wordpress.get_site_info", "wordpress.update_post",
        "node.list", "node.status", "node.exec",
        "read", "write", "grep", "glob",
    },
    # Default seeded agents (api/app.py _DEFAULT_AGENTS) — pipeline execute path
    "general": {"read", "write", "execute", "browser", "web_search"},
    "demo": {"execute", "read"},
    "code-reviewer": {"read", "grep", "glob", "execute"},
    "onboarding-wizard": {"read", "write", "execute"},
    "mcp-installer": {"read", "write", "execute", "browser"},
    "llm-setup": {"read", "write", "execute"},
    "skills-manager": {"read", "write", "execute"},
    "session-policy": {"read", "execute"},
    "ux-copy": {"read", "write", "translate"},
    "openclaw": {"read", "write", "execute", "browser", "api_call"},
    "remote-agent": {"read", "write", "execute", "browser", "api_call"},
    "main": {"read", "write", "execute"},  # Brain pipeline session agent
}

# Dangerous tools that require explicit allowlist
DANGEROUS_TOOLS: set[str] = {
    "bash", "exec", "ssh", "docker", "rm", "kill",
    "system", "eval", "deploy", "restart", "reboot",
}

# Brain-only tools (no agent can use these)
BRAIN_ONLY_TOOLS: set[str] = {
    "agent_dispatch", "workflow_create", "approval_gate",
    "pipeline_run", "task_create", "agent_kill",
}


class AgentToolGuard:
    """Enforces per-agent tool access control."""

    def __init__(self, custom_allowlists: dict[str, set[str]] | None = None):
        self._allowlists = {k: set(v) for k, v in AGENT_TOOL_ALLOWLISTS.items()}
        if custom_allowlists:
            for agent_id, tools in custom_allowlists.items():
                self._allowlists[agent_id] = set(tools)
        self._violations: list[ToolAccessResult] = []
        self._total_checks: int = 0
        self._total_denied: int = 0

    def check_access(self, agent_id: str, tool_name: str) -> ToolAccessResult:
        """Check if agent is allowed to use a tool."""
        self._total_checks += 1

        # Brain-only tools
        if tool_name in BRAIN_ONLY_TOOLS:
            result = ToolAccessResult(
                allowed=False, agent_id=agent_id, tool_name=tool_name,
                reason=f"Tool '{tool_name}' is Brain-only, agents cannot use it",
            )
            self._record_violation(result)
            return result

        # Unknown agent
        if agent_id not in self._allowlists:
            result = ToolAccessResult(
                allowed=False, agent_id=agent_id, tool_name=tool_name,
                reason=f"Unknown agent '{agent_id}' — no allowlist defined",
            )
            self._record_violation(result)
            return result

        # Check allowlist
        allowed_tools = self._allowlists[agent_id]
        if tool_name not in allowed_tools:
            is_dangerous = tool_name in DANGEROUS_TOOLS
            result = ToolAccessResult(
                allowed=False, agent_id=agent_id, tool_name=tool_name,
                reason=f"Tool '{tool_name}' not in {agent_id} allowlist"
                       + (" (DANGEROUS)" if is_dangerous else ""),
            )
            self._record_violation(result)
            return result

        return ToolAccessResult(allowed=True, agent_id=agent_id, tool_name=tool_name)

    def get_allowlist(self, agent_id: str) -> set[str]:
        """Return allowed tools for an agent."""
        return self._allowlists.get(agent_id, set())

    def add_tool(self, agent_id: str, tool_name: str) -> None:
        """Dynamically add a tool to an agent's allowlist."""
        if agent_id not in self._allowlists:
            self._allowlists[agent_id] = set()
        self._allowlists[agent_id].add(tool_name)

    def remove_tool(self, agent_id: str, tool_name: str) -> None:
        """Remove a tool from an agent's allowlist."""
        if agent_id in self._allowlists:
            self._allowlists[agent_id].discard(tool_name)

    @property
    def violations(self) -> list[ToolAccessResult]:
        return list(self._violations)

    @property
    def stats(self) -> dict[str, Any]:
        return {
            "total_checks": self._total_checks,
            "total_denied": self._total_denied,
            "deny_rate": self._total_denied / max(1, self._total_checks),
            "violation_count": len(self._violations),
            "agents_configured": len(self._allowlists),
        }

    def _record_violation(self, result: ToolAccessResult) -> None:
        self._total_denied += 1
        self._violations.append(result)
        logger.warning("TOOL DENIED: agent=%s tool=%s reason=%s",
                      result.agent_id, result.tool_name, result.reason)
