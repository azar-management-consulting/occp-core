"""Tests for Trust Level enforcement — REQ-GOV-06.

Covers:
- TrustLevel enum values and ordering
- TrustConstraint hierarchy (L0–L5)
- TrustEnforcer.check_action — LLM, network, spawn, tool_category
- TrustEnforcer.inherit_level — parent minus 1
- TrustEnforcer.validate_spawn — depth checks, level ceiling
- Agent registration and lookup
- TrustCheckResult serialization
- Fuzz: 5,000 cross-level calls, 0 bypass
"""

from __future__ import annotations

import random

import pytest

from policy_engine.trust_levels import (
    TRUST_CONSTRAINTS,
    TrustCheckResult,
    TrustConstraint,
    TrustEnforcer,
    TrustLevel,
)


# ---------------------------------------------------------------------------
# TrustLevel enum
# ---------------------------------------------------------------------------


class TestTrustLevel:
    def test_values(self) -> None:
        assert TrustLevel.L0_DETERMINISTIC == 0
        assert TrustLevel.L1_CONSTRAINED == 1
        assert TrustLevel.L2_SUPERVISED == 2
        assert TrustLevel.L3_AUTONOMOUS == 3
        assert TrustLevel.L4_DELEGATING == 4
        assert TrustLevel.L5_ORCHESTRATOR == 5

    def test_ordering(self) -> None:
        assert TrustLevel.L0_DETERMINISTIC < TrustLevel.L5_ORCHESTRATOR
        assert TrustLevel.L3_AUTONOMOUS > TrustLevel.L2_SUPERVISED

    def test_all_six_levels(self) -> None:
        assert len(TrustLevel) == 6


# ---------------------------------------------------------------------------
# TrustConstraint table
# ---------------------------------------------------------------------------


class TestTrustConstraints:
    def test_all_levels_have_constraints(self) -> None:
        for level in TrustLevel:
            assert level in TRUST_CONSTRAINTS

    def test_l0_no_llm(self) -> None:
        c = TRUST_CONSTRAINTS[TrustLevel.L0_DETERMINISTIC]
        assert c.can_use_llm is False
        assert c.can_access_network is False
        assert c.can_spawn_children is False

    def test_l1_has_llm_no_network(self) -> None:
        c = TRUST_CONSTRAINTS[TrustLevel.L1_CONSTRAINED]
        assert c.can_use_llm is True
        assert c.can_access_network is False
        assert c.can_spawn_children is False

    def test_l2_has_network_requires_human(self) -> None:
        c = TRUST_CONSTRAINTS[TrustLevel.L2_SUPERVISED]
        assert c.can_access_network is True
        assert c.requires_human_approval is True

    def test_l3_autonomous_no_approval(self) -> None:
        c = TRUST_CONSTRAINTS[TrustLevel.L3_AUTONOMOUS]
        assert c.requires_human_approval is False
        assert c.can_spawn_children is False

    def test_l4_can_spawn(self) -> None:
        c = TRUST_CONSTRAINTS[TrustLevel.L4_DELEGATING]
        assert c.can_spawn_children is True
        assert c.max_child_depth == 2

    def test_l5_orchestrator_full(self) -> None:
        c = TRUST_CONSTRAINTS[TrustLevel.L5_ORCHESTRATOR]
        assert c.can_spawn_children is True
        assert c.max_child_depth == 5
        assert "orchestrate" in c.max_tool_categories

    def test_monotonic_output_tokens(self) -> None:
        """Higher trust levels should have >= output tokens."""
        prev = 0
        for level in TrustLevel:
            c = TRUST_CONSTRAINTS[level]
            # L0 has 0, L1 starts at 4096
            if level > TrustLevel.L0_DETERMINISTIC:
                assert c.max_output_tokens >= prev
            prev = c.max_output_tokens

    def test_frozen_constraint(self) -> None:
        c = TRUST_CONSTRAINTS[TrustLevel.L0_DETERMINISTIC]
        with pytest.raises(AttributeError):
            c.can_use_llm = True  # type: ignore[misc]


# ---------------------------------------------------------------------------
# TrustCheckResult
# ---------------------------------------------------------------------------


class TestTrustCheckResult:
    def test_allowed_result(self) -> None:
        r = TrustCheckResult(allowed=True, agent_id="a1", trust_level=TrustLevel.L3_AUTONOMOUS)
        assert r.allowed is True
        assert r.reason == ""

    def test_denied_result(self) -> None:
        r = TrustCheckResult(
            allowed=False,
            agent_id="a1",
            trust_level=TrustLevel.L0_DETERMINISTIC,
            reason="no LLM",
            constraint_violated="can_use_llm",
        )
        assert r.allowed is False
        assert r.constraint_violated == "can_use_llm"

    def test_to_dict(self) -> None:
        r = TrustCheckResult(
            allowed=True,
            agent_id="a1",
            trust_level=TrustLevel.L3_AUTONOMOUS,
        )
        d = r.to_dict()
        assert d["allowed"] is True
        assert d["trust_level"] == "L3_AUTONOMOUS"
        assert d["trust_level_value"] == 3


# ---------------------------------------------------------------------------
# TrustEnforcer — check_action
# ---------------------------------------------------------------------------


class TestTrustEnforcerCheckAction:
    def setup_method(self) -> None:
        self.enforcer = TrustEnforcer()

    def test_l0_allows_read(self) -> None:
        r = self.enforcer.check_action("a1", TrustLevel.L0_DETERMINISTIC, "read_file", tool_category="read")
        assert r.allowed is True

    def test_l0_denies_llm(self) -> None:
        r = self.enforcer.check_action("a1", TrustLevel.L0_DETERMINISTIC, "generate", requires_llm=True)
        assert r.allowed is False
        assert r.constraint_violated == "can_use_llm"

    def test_l0_denies_network(self) -> None:
        r = self.enforcer.check_action("a1", TrustLevel.L0_DETERMINISTIC, "fetch", requires_network=True)
        assert r.allowed is False
        assert r.constraint_violated == "can_access_network"

    def test_l1_denies_network(self) -> None:
        r = self.enforcer.check_action("a1", TrustLevel.L1_CONSTRAINED, "fetch", requires_network=True)
        assert r.allowed is False

    def test_l2_allows_network(self) -> None:
        r = self.enforcer.check_action("a1", TrustLevel.L2_SUPERVISED, "fetch", requires_network=True)
        assert r.allowed is True

    def test_l3_denies_spawn(self) -> None:
        r = self.enforcer.check_action("a1", TrustLevel.L3_AUTONOMOUS, "spawn", requires_spawn=True)
        assert r.allowed is False
        assert r.constraint_violated == "can_spawn_children"

    def test_l4_allows_spawn(self) -> None:
        r = self.enforcer.check_action("a1", TrustLevel.L4_DELEGATING, "spawn", requires_spawn=True)
        assert r.allowed is True

    def test_tool_category_denied(self) -> None:
        r = self.enforcer.check_action("a1", TrustLevel.L0_DETERMINISTIC, "admin_op", tool_category="admin")
        assert r.allowed is False
        assert r.constraint_violated == "tool_category"

    def test_l5_allows_orchestrate(self) -> None:
        r = self.enforcer.check_action("a1", TrustLevel.L5_ORCHESTRATOR, "orch", tool_category="orchestrate")
        assert r.allowed is True

    def test_l4_allows_admin(self) -> None:
        r = self.enforcer.check_action("a1", TrustLevel.L4_DELEGATING, "admin_op", tool_category="admin")
        assert r.allowed is True

    def test_l3_denies_admin(self) -> None:
        r = self.enforcer.check_action("a1", TrustLevel.L3_AUTONOMOUS, "admin_op", tool_category="admin")
        assert r.allowed is False

    def test_l1_allows_llm(self) -> None:
        r = self.enforcer.check_action("a1", TrustLevel.L1_CONSTRAINED, "gen", requires_llm=True)
        assert r.allowed is True

    def test_empty_tool_category_passes(self) -> None:
        """No tool_category specified means no category check."""
        r = self.enforcer.check_action("a1", TrustLevel.L0_DETERMINISTIC, "something")
        assert r.allowed is True


# ---------------------------------------------------------------------------
# TrustEnforcer — inherit_level
# ---------------------------------------------------------------------------


class TestInheritLevel:
    def test_l5_inherits_l4(self) -> None:
        assert TrustEnforcer.inherit_level(TrustLevel.L5_ORCHESTRATOR) == TrustLevel.L4_DELEGATING

    def test_l4_inherits_l3(self) -> None:
        assert TrustEnforcer.inherit_level(TrustLevel.L4_DELEGATING) == TrustLevel.L3_AUTONOMOUS

    def test_l1_inherits_l0(self) -> None:
        assert TrustEnforcer.inherit_level(TrustLevel.L1_CONSTRAINED) == TrustLevel.L0_DETERMINISTIC

    def test_l0_stays_l0(self) -> None:
        assert TrustEnforcer.inherit_level(TrustLevel.L0_DETERMINISTIC) == TrustLevel.L0_DETERMINISTIC


# ---------------------------------------------------------------------------
# TrustEnforcer — validate_spawn
# ---------------------------------------------------------------------------


class TestValidateSpawn:
    def setup_method(self) -> None:
        self.enforcer = TrustEnforcer()

    def test_l5_spawns_l4_ok(self) -> None:
        r = self.enforcer.validate_spawn("p1", TrustLevel.L5_ORCHESTRATOR, TrustLevel.L4_DELEGATING)
        assert r.allowed is True

    def test_l5_spawns_l3_ok(self) -> None:
        """Child can be lower than max."""
        r = self.enforcer.validate_spawn("p1", TrustLevel.L5_ORCHESTRATOR, TrustLevel.L3_AUTONOMOUS)
        assert r.allowed is True

    def test_l5_spawns_l5_denied(self) -> None:
        """Child cannot equal parent."""
        r = self.enforcer.validate_spawn("p1", TrustLevel.L5_ORCHESTRATOR, TrustLevel.L5_ORCHESTRATOR)
        assert r.allowed is False
        assert r.constraint_violated == "child_level_exceeded"

    def test_l4_spawns_l4_denied(self) -> None:
        r = self.enforcer.validate_spawn("p1", TrustLevel.L4_DELEGATING, TrustLevel.L4_DELEGATING)
        assert r.allowed is False

    def test_l3_cannot_spawn(self) -> None:
        r = self.enforcer.validate_spawn("p1", TrustLevel.L3_AUTONOMOUS, TrustLevel.L2_SUPERVISED)
        assert r.allowed is False
        assert r.constraint_violated == "can_spawn_children"

    def test_l0_cannot_spawn(self) -> None:
        r = self.enforcer.validate_spawn("p1", TrustLevel.L0_DETERMINISTIC, TrustLevel.L0_DETERMINISTIC)
        assert r.allowed is False

    def test_depth_exceeded(self) -> None:
        r = self.enforcer.validate_spawn(
            "p1", TrustLevel.L4_DELEGATING, TrustLevel.L3_AUTONOMOUS, current_depth=2,
        )
        assert r.allowed is False
        assert r.constraint_violated == "max_child_depth"

    def test_depth_at_limit_denied(self) -> None:
        """L4 max_child_depth=2, so depth=2 is AT limit → denied."""
        r = self.enforcer.validate_spawn(
            "p1", TrustLevel.L4_DELEGATING, TrustLevel.L3_AUTONOMOUS, current_depth=2,
        )
        assert r.allowed is False

    def test_l5_depth_ok(self) -> None:
        """L5 max_child_depth=5, so depth=4 is fine."""
        r = self.enforcer.validate_spawn(
            "p1", TrustLevel.L5_ORCHESTRATOR, TrustLevel.L4_DELEGATING, current_depth=4,
        )
        assert r.allowed is True


# ---------------------------------------------------------------------------
# TrustEnforcer — agent registration
# ---------------------------------------------------------------------------


class TestAgentRegistration:
    def setup_method(self) -> None:
        self.enforcer = TrustEnforcer()

    def test_register_and_get(self) -> None:
        self.enforcer.register_agent("a1", TrustLevel.L3_AUTONOMOUS)
        assert self.enforcer.get_level("a1") == TrustLevel.L3_AUTONOMOUS

    def test_unregistered_returns_none(self) -> None:
        assert self.enforcer.get_level("unknown") is None

    def test_update_level(self) -> None:
        self.enforcer.register_agent("a1", TrustLevel.L1_CONSTRAINED)
        self.enforcer.register_agent("a1", TrustLevel.L3_AUTONOMOUS)
        assert self.enforcer.get_level("a1") == TrustLevel.L3_AUTONOMOUS

    def test_invalid_level_rejected(self) -> None:
        with pytest.raises(ValueError):
            self.enforcer.register_agent("a1", "not_a_level")  # type: ignore[arg-type]

    def test_registered_agents_property(self) -> None:
        self.enforcer.register_agent("a1", TrustLevel.L2_SUPERVISED)
        self.enforcer.register_agent("a2", TrustLevel.L4_DELEGATING)
        agents = self.enforcer.registered_agents
        assert len(agents) == 2
        assert agents["a1"] == TrustLevel.L2_SUPERVISED

    def test_get_constraint(self) -> None:
        c = self.enforcer.get_constraint(TrustLevel.L5_ORCHESTRATOR)
        assert c is not None
        assert c.can_spawn_children is True

    def test_custom_constraints(self) -> None:
        custom = {
            TrustLevel.L0_DETERMINISTIC: TrustConstraint(
                level=TrustLevel.L0_DETERMINISTIC,
                can_use_llm=True,  # Override default
            ),
        }
        enforcer = TrustEnforcer(constraints=custom)
        r = enforcer.check_action("a1", TrustLevel.L0_DETERMINISTIC, "gen", requires_llm=True)
        assert r.allowed is True


# ---------------------------------------------------------------------------
# Fuzz: 5,000 cross-level calls, 0 bypass — REQ-GOV-06
# ---------------------------------------------------------------------------


class TestTrustLevelFuzz:
    def test_fuzz_5000_cross_level_no_bypass(self) -> None:
        """No combination of agent/level/action should bypass constraints."""
        enforcer = TrustEnforcer()
        rng = random.Random(42)  # Deterministic seed

        all_categories = ["read", "compute", "generate", "write", "network", "execute", "admin", "orchestrate", "unknown"]
        levels = list(TrustLevel)
        bypass_count = 0

        for _ in range(5000):
            level = rng.choice(levels)
            cat = rng.choice(all_categories)
            req_llm = rng.random() < 0.3
            req_net = rng.random() < 0.3
            req_spawn = rng.random() < 0.3

            result = enforcer.check_action(
                f"agent-{rng.randint(0, 99)}",
                level,
                f"action-{rng.randint(0, 50)}",
                tool_category=cat,
                requires_llm=req_llm,
                requires_network=req_net,
                requires_spawn=req_spawn,
            )

            constraint = TRUST_CONSTRAINTS[level]

            # Verify: if action was allowed, all constraints must be satisfied
            if result.allowed:
                if req_llm and not constraint.can_use_llm:
                    bypass_count += 1
                if req_net and not constraint.can_access_network:
                    bypass_count += 1
                if req_spawn and not constraint.can_spawn_children:
                    bypass_count += 1
                if cat and cat not in constraint.max_tool_categories:
                    bypass_count += 1

        assert bypass_count == 0, f"BYPASS DETECTED: {bypass_count} constraint violations in 5000 calls"
