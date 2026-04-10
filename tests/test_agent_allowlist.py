"""Tests for per-agent tool allowlist enforcement."""

from __future__ import annotations

import logging

import pytest

from security.agent_allowlist import (
    AGENT_TOOL_ALLOWLISTS,
    BRAIN_ONLY_TOOLS,
    DANGEROUS_TOOLS,
    AgentToolGuard,
    ToolAccessResult,
)


@pytest.fixture
def guard() -> AgentToolGuard:
    return AgentToolGuard()


# --- Basic allow/deny ---

class TestEngCore:
    def test_bash_allowed(self, guard: AgentToolGuard):
        r = guard.check_access("eng-core", "bash")
        assert r.allowed is True

    def test_deploy_denied(self, guard: AgentToolGuard):
        r = guard.check_access("eng-core", "deploy")
        assert r.allowed is False
        assert "not in eng-core allowlist" in r.reason

    def test_exec_allowed(self, guard: AgentToolGuard):
        r = guard.check_access("eng-core", "exec")
        assert r.allowed is True

    def test_write_allowed(self, guard: AgentToolGuard):
        r = guard.check_access("eng-core", "write")
        assert r.allowed is True


class TestDesignLab:
    def test_bash_denied(self, guard: AgentToolGuard):
        r = guard.check_access("design-lab", "bash")
        assert r.allowed is False
        assert "DANGEROUS" in r.reason

    def test_read_allowed(self, guard: AgentToolGuard):
        r = guard.check_access("design-lab", "read")
        assert r.allowed is True

    def test_exec_denied(self, guard: AgentToolGuard):
        r = guard.check_access("design-lab", "exec")
        assert r.allowed is False

    def test_screenshot_allowed(self, guard: AgentToolGuard):
        r = guard.check_access("design-lab", "screenshot")
        assert r.allowed is True


class TestIntelResearch:
    def test_write_denied(self, guard: AgentToolGuard):
        """intel-research is read-only — no write access."""
        r = guard.check_access("intel-research", "write")
        assert r.allowed is False

    def test_read_allowed(self, guard: AgentToolGuard):
        r = guard.check_access("intel-research", "read")
        assert r.allowed is True

    def test_web_search_allowed(self, guard: AgentToolGuard):
        r = guard.check_access("intel-research", "web_search")
        assert r.allowed is True

    def test_bash_denied(self, guard: AgentToolGuard):
        r = guard.check_access("intel-research", "bash")
        assert r.allowed is False


class TestInfraOps:
    def test_ssh_allowed(self, guard: AgentToolGuard):
        r = guard.check_access("infra-ops", "ssh")
        assert r.allowed is True

    def test_docker_allowed(self, guard: AgentToolGuard):
        r = guard.check_access("infra-ops", "docker")
        assert r.allowed is True

    def test_deploy_denied(self, guard: AgentToolGuard):
        r = guard.check_access("infra-ops", "deploy")
        assert r.allowed is False
        assert "DANGEROUS" in r.reason

    def test_write_denied(self, guard: AgentToolGuard):
        r = guard.check_access("infra-ops", "write")
        assert r.allowed is False


# --- Brain-only tools ---

class TestBrainOnly:
    @pytest.mark.parametrize("agent_id", list(AGENT_TOOL_ALLOWLISTS.keys()))
    def test_agent_dispatch_denied_all(self, guard: AgentToolGuard, agent_id: str):
        r = guard.check_access(agent_id, "agent_dispatch")
        assert r.allowed is False
        assert "Brain-only" in r.reason

    @pytest.mark.parametrize("agent_id", list(AGENT_TOOL_ALLOWLISTS.keys()))
    def test_pipeline_run_denied_all(self, guard: AgentToolGuard, agent_id: str):
        r = guard.check_access(agent_id, "pipeline_run")
        assert r.allowed is False
        assert "Brain-only" in r.reason

    def test_all_brain_tools_blocked(self, guard: AgentToolGuard):
        for tool in BRAIN_ONLY_TOOLS:
            r = guard.check_access("eng-core", tool)
            assert r.allowed is False, f"Brain-only tool '{tool}' was not blocked"


# --- Unknown agent ---

class TestUnknownAgent:
    def test_unknown_agent_denied(self, guard: AgentToolGuard):
        r = guard.check_access("rogue-agent", "read")
        assert r.allowed is False
        assert "Unknown agent" in r.reason

    def test_empty_string_agent_denied(self, guard: AgentToolGuard):
        r = guard.check_access("", "read")
        assert r.allowed is False


# --- Custom allowlists ---

class TestCustomAllowlists:
    def test_override_existing(self):
        guard = AgentToolGuard(custom_allowlists={"eng-core": {"read"}})
        assert guard.check_access("eng-core", "read").allowed is True
        assert guard.check_access("eng-core", "bash").allowed is False

    def test_add_new_agent(self):
        guard = AgentToolGuard(custom_allowlists={"custom-agent": {"read", "write"}})
        assert guard.check_access("custom-agent", "read").allowed is True
        assert guard.check_access("custom-agent", "bash").allowed is False


# --- Dynamic add/remove ---

class TestDynamicMutation:
    def test_add_tool(self, guard: AgentToolGuard):
        assert guard.check_access("design-lab", "bash").allowed is False
        guard.add_tool("design-lab", "bash")
        assert guard.check_access("design-lab", "bash").allowed is True

    def test_remove_tool(self, guard: AgentToolGuard):
        assert guard.check_access("eng-core", "bash").allowed is True
        guard.remove_tool("eng-core", "bash")
        assert guard.check_access("eng-core", "bash").allowed is False

    def test_add_tool_new_agent(self, guard: AgentToolGuard):
        guard.add_tool("new-agent", "read")
        assert guard.check_access("new-agent", "read").allowed is True

    def test_remove_nonexistent_no_error(self, guard: AgentToolGuard):
        guard.remove_tool("eng-core", "nonexistent_tool")  # no-op, no crash

    def test_remove_from_unknown_agent_no_error(self, guard: AgentToolGuard):
        guard.remove_tool("ghost-agent", "read")  # no-op, no crash


# --- Violation logging ---

class TestViolationLogging:
    def test_violations_recorded(self, guard: AgentToolGuard):
        guard.check_access("design-lab", "bash")
        guard.check_access("intel-research", "write")
        assert len(guard.violations) == 2

    def test_violations_are_copies(self, guard: AgentToolGuard):
        guard.check_access("design-lab", "bash")
        v1 = guard.violations
        v2 = guard.violations
        assert v1 is not v2  # returns a copy each time

    def test_allowed_not_in_violations(self, guard: AgentToolGuard):
        guard.check_access("eng-core", "bash")
        assert len(guard.violations) == 0

    def test_log_warning_emitted(self, guard: AgentToolGuard, caplog):
        with caplog.at_level(logging.WARNING):
            guard.check_access("design-lab", "exec")
        assert "TOOL DENIED" in caplog.text


# --- Stats ---

class TestStats:
    def test_initial_stats(self, guard: AgentToolGuard):
        s = guard.stats
        assert s["total_checks"] == 0
        assert s["total_denied"] == 0
        assert s["deny_rate"] == 0.0
        # 8 specialists + 'brain' orchestrator + 12 seeded defaults = 21
        assert s["agents_configured"] == 21

    def test_stats_after_mixed(self, guard: AgentToolGuard):
        guard.check_access("eng-core", "bash")       # allowed
        guard.check_access("eng-core", "read")        # allowed
        guard.check_access("design-lab", "bash")      # denied
        guard.check_access("unknown", "read")          # denied
        s = guard.stats
        assert s["total_checks"] == 4
        assert s["total_denied"] == 2
        assert s["deny_rate"] == 0.5
        assert s["violation_count"] == 2


# --- Structural assertions ---

class TestStructure:
    def test_all_8_agents_defined(self):
        # 8 specialist agents + 'brain' orchestrator + 12 seeded pipeline agents
        specialists = {"eng-core", "wp-web", "infra-ops", "design-lab",
                       "content-forge", "social-growth", "intel-research", "biz-strategy"}
        orchestrator = {"brain"}
        seeded = {"general", "demo", "code-reviewer", "onboarding-wizard",
                  "mcp-installer", "llm-setup", "skills-manager", "session-policy",
                  "ux-copy", "openclaw", "remote-agent", "main"}
        expected = specialists | orchestrator | seeded
        assert set(AGENT_TOOL_ALLOWLISTS.keys()) == expected

    def test_dangerous_tools_set_not_empty(self):
        assert len(DANGEROUS_TOOLS) > 0

    def test_brain_only_tools_set_not_empty(self):
        assert len(BRAIN_ONLY_TOOLS) > 0

    def test_dangerous_detection_in_reason(self, guard: AgentToolGuard):
        """Denied dangerous tool should have DANGEROUS in reason."""
        r = guard.check_access("design-lab", "bash")
        assert "DANGEROUS" in r.reason

    def test_non_dangerous_denied_no_tag(self, guard: AgentToolGuard):
        """Denied non-dangerous tool should NOT have DANGEROUS in reason."""
        r = guard.check_access("intel-research", "write")
        assert "DANGEROUS" not in r.reason


# --- Empty allowlist ---

class TestEmptyAllowlist:
    def test_empty_allowlist_denies_everything(self):
        guard = AgentToolGuard(custom_allowlists={"locked-agent": set()})
        assert guard.check_access("locked-agent", "read").allowed is False
        assert guard.check_access("locked-agent", "write").allowed is False
        assert guard.check_access("locked-agent", "bash").allowed is False

    def test_get_allowlist_empty(self):
        guard = AgentToolGuard(custom_allowlists={"locked-agent": set()})
        assert guard.get_allowlist("locked-agent") == set()

    def test_get_allowlist_unknown(self, guard: AgentToolGuard):
        assert guard.get_allowlist("nonexistent") == set()


# --- ToolAccessResult dataclass ---

class TestToolAccessResult:
    def test_default_reason_empty(self):
        r = ToolAccessResult(allowed=True, agent_id="x", tool_name="y")
        assert r.reason == ""

    def test_fields(self):
        r = ToolAccessResult(allowed=False, agent_id="a", tool_name="b", reason="test")
        assert r.agent_id == "a"
        assert r.tool_name == "b"
        assert r.reason == "test"
        assert r.allowed is False
