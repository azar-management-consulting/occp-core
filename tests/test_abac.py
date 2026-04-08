"""Tests for ABAC (Attribute-Based Access Control) evaluator — REQ-POL-01."""

from __future__ import annotations

import textwrap
from datetime import time
from pathlib import Path

import pytest

from policy_engine.abac import (
    ABACCondition,
    ABACDecision,
    ABACEvaluator,
    ABACRule,
    CombineAlgorithm,
    Effect,
    RequestContext,
    _parse_conditions,
)


# ---------------------------------------------------------------------------
# ABACCondition — operator coverage
# ---------------------------------------------------------------------------


class TestABACCondition:
    def test_eq_match(self) -> None:
        cond = ABACCondition("user_role", "eq", "admin")
        assert cond.matches("admin") is True

    def test_eq_no_match(self) -> None:
        cond = ABACCondition("user_role", "eq", "admin")
        assert cond.matches("viewer") is False

    def test_eq_none_returns_false(self) -> None:
        cond = ABACCondition("user_role", "eq", "admin")
        assert cond.matches(None) is False

    def test_not_eq(self) -> None:
        cond = ABACCondition("data_classification", "not_eq", "top_secret")
        assert cond.matches("public") is True
        assert cond.matches("top_secret") is False

    def test_in_match(self) -> None:
        cond = ABACCondition("user_role", "in", ["operator", "admin"])
        assert cond.matches("operator") is True
        assert cond.matches("viewer") is False

    def test_not_in(self) -> None:
        cond = ABACCondition("user_role", "not_in", ["viewer", "guest"])
        assert cond.matches("admin") is True
        assert cond.matches("viewer") is False

    def test_time_range_inside(self) -> None:
        cond = ABACCondition("time_of_day", "time_range", {"after": "09:00", "before": "17:00"})
        assert cond.matches(time(12, 0)) is True
        assert cond.matches(time(8, 0)) is False
        assert cond.matches(time(17, 30)) is False

    def test_time_range_string_input(self) -> None:
        cond = ABACCondition("time_of_day", "time_range", {"after": "09:00", "before": "17:00"})
        assert cond.matches("12:00") is True
        assert cond.matches("08:00") is False

    def test_time_range_midnight_wrap(self) -> None:
        cond = ABACCondition("time_of_day", "time_range", {"after": "22:00", "before": "06:00"})
        assert cond.matches(time(23, 0)) is True
        assert cond.matches(time(3, 0)) is True
        assert cond.matches(time(12, 0)) is False

    def test_cidr_ipv4(self) -> None:
        cond = ABACCondition("source_ip", "cidr", "10.0.0.0/8")
        assert cond.matches("10.1.2.3") is True
        assert cond.matches("192.168.1.1") is False

    def test_cidr_ipv6(self) -> None:
        cond = ABACCondition("source_ip", "cidr", "2001:db8::/32")
        assert cond.matches("2001:db8::1") is True
        assert cond.matches("2001:db9::1") is False

    def test_cidr_invalid_ip(self) -> None:
        cond = ABACCondition("source_ip", "cidr", "10.0.0.0/8")
        assert cond.matches("not-an-ip") is False

    def test_regex_match(self) -> None:
        cond = ABACCondition("agent_type", "regex", "^code_.*")
        assert cond.matches("code_reviewer") is True
        assert cond.matches("data_analyst") is False

    def test_unknown_operator(self) -> None:
        cond = ABACCondition("x", "nonexistent", "y")
        assert cond.matches("y") is False


# ---------------------------------------------------------------------------
# RequestContext — factory methods
# ---------------------------------------------------------------------------


class TestRequestContext:
    def test_from_dict_basic(self) -> None:
        ctx = RequestContext.from_dict({
            "user_role": "operator",
            "agent_type": "code_gen",
            "tool_category": "shell",
        })
        assert ctx.user_role == "operator"
        assert ctx.agent_type == "code_gen"
        assert ctx.tool_category == "shell"

    def test_from_dict_extra_attrs(self) -> None:
        ctx = RequestContext.from_dict({
            "user_role": "admin",
            "custom_field": "some_value",
        })
        assert ctx.get_attribute("user_role") == "admin"
        assert ctx.get_attribute("custom_field") == "some_value"

    def test_from_dict_time_of_day_string(self) -> None:
        ctx = RequestContext.from_dict({"time_of_day": "14:30"})
        assert ctx.time_of_day == time(14, 30)

    def test_from_dict_trust_level(self) -> None:
        ctx = RequestContext.from_dict({"trust_level": "3"})
        assert ctx.trust_level == 3

    def test_get_attribute_returns_none_for_missing(self) -> None:
        ctx = RequestContext()
        assert ctx.get_attribute("nonexistent") is None

    def test_get_attribute_skips_default_values(self) -> None:
        ctx = RequestContext()  # All defaults
        assert ctx.get_attribute("user_role") is None  # "" is treated as unset
        assert ctx.get_attribute("trust_level") is None  # -1 is treated as unset


# ---------------------------------------------------------------------------
# ABACRule — matching
# ---------------------------------------------------------------------------


class TestABACRule:
    def test_empty_conditions_always_matches(self) -> None:
        rule = ABACRule(id="catch-all", effect=Effect.ALLOW)
        ctx = RequestContext(user_role="viewer")
        assert rule.matches(ctx) is True

    def test_all_conditions_must_match(self) -> None:
        rule = ABACRule(
            id="restricted",
            effect=Effect.ALLOW,
            conditions=[
                ABACCondition("user_role", "eq", "operator"),
                ABACCondition("tool_category", "eq", "shell"),
            ],
        )
        ctx_ok = RequestContext(user_role="operator", tool_category="shell")
        ctx_fail = RequestContext(user_role="operator", tool_category="browser")
        assert rule.matches(ctx_ok) is True
        assert rule.matches(ctx_fail) is False


# ---------------------------------------------------------------------------
# ABACEvaluator — combination algorithms
# ---------------------------------------------------------------------------


class TestABACEvaluator:
    def _make_evaluator(
        self,
        algorithm: CombineAlgorithm = CombineAlgorithm.DENY_OVERRIDES,
        default_effect: Effect = Effect.DENY,
    ) -> ABACEvaluator:
        ev = ABACEvaluator(algorithm=algorithm, default_effect=default_effect)
        return ev

    def test_no_rules_returns_default(self) -> None:
        ev = self._make_evaluator()
        ctx = RequestContext(user_role="admin")
        decision = ev.evaluate(ctx)
        assert decision.denied is True
        assert "No matching rules" in decision.reason

    def test_single_allow_rule(self) -> None:
        ev = self._make_evaluator()
        ev.add_rule(ABACRule(
            id="allow-admin",
            effect=Effect.ALLOW,
            conditions=[ABACCondition("user_role", "eq", "admin")],
        ))
        ctx = RequestContext(user_role="admin")
        decision = ev.evaluate(ctx)
        assert decision.allowed is True
        assert "allow-admin" in decision.matched_rules

    def test_deny_overrides(self) -> None:
        ev = self._make_evaluator(algorithm=CombineAlgorithm.DENY_OVERRIDES)
        ev.add_rule(ABACRule(
            id="allow-all",
            effect=Effect.ALLOW,
            conditions=[ABACCondition("user_role", "eq", "admin")],
        ))
        ev.add_rule(ABACRule(
            id="deny-shell",
            effect=Effect.DENY,
            conditions=[ABACCondition("user_role", "eq", "admin")],
        ))
        ctx = RequestContext(user_role="admin")
        decision = ev.evaluate(ctx)
        assert decision.denied is True

    def test_allow_overrides(self) -> None:
        ev = self._make_evaluator(algorithm=CombineAlgorithm.ALLOW_OVERRIDES)
        ev.add_rule(ABACRule(
            id="deny-all",
            effect=Effect.DENY,
            conditions=[ABACCondition("user_role", "eq", "admin")],
        ))
        ev.add_rule(ABACRule(
            id="allow-admin",
            effect=Effect.ALLOW,
            conditions=[ABACCondition("user_role", "eq", "admin")],
        ))
        ctx = RequestContext(user_role="admin")
        decision = ev.evaluate(ctx)
        assert decision.allowed is True

    def test_first_match_uses_priority(self) -> None:
        ev = self._make_evaluator(algorithm=CombineAlgorithm.FIRST_MATCH)
        ev.add_rule(ABACRule(
            id="low-prio-deny",
            effect=Effect.DENY,
            conditions=[ABACCondition("user_role", "eq", "admin")],
            priority=1,
        ))
        ev.add_rule(ABACRule(
            id="high-prio-allow",
            effect=Effect.ALLOW,
            conditions=[ABACCondition("user_role", "eq", "admin")],
            priority=10,
        ))
        ctx = RequestContext(user_role="admin")
        decision = ev.evaluate(ctx)
        assert decision.allowed is True  # high-prio wins

    def test_require_approval_in_deny_overrides(self) -> None:
        ev = self._make_evaluator(algorithm=CombineAlgorithm.DENY_OVERRIDES)
        ev.add_rule(ABACRule(
            id="allow-base",
            effect=Effect.ALLOW,
            conditions=[ABACCondition("user_role", "eq", "operator")],
        ))
        ev.add_rule(ABACRule(
            id="approve-shell",
            effect=Effect.REQUIRE_APPROVAL,
            conditions=[ABACCondition("user_role", "eq", "operator")],
        ))
        ctx = RequestContext(user_role="operator")
        decision = ev.evaluate(ctx)
        assert decision.effect == Effect.REQUIRE_APPROVAL

    def test_policy_hash_changes_on_rule_add(self) -> None:
        ev = self._make_evaluator()
        h1 = ev.policy_hash
        ev.add_rule(ABACRule(id="r1", effect=Effect.ALLOW))
        h2 = ev.policy_hash
        assert h1 != h2
        ev.add_rule(ABACRule(id="r2", effect=Effect.DENY))
        h3 = ev.policy_hash
        assert h2 != h3

    def test_policy_hash_deterministic(self) -> None:
        ev1 = self._make_evaluator()
        ev2 = self._make_evaluator()
        rule = ABACRule(id="r1", effect=Effect.ALLOW, conditions=[
            ABACCondition("user_role", "eq", "admin"),
        ])
        ev1.add_rule(rule)
        ev2.add_rule(ABACRule(id="r1", effect=Effect.ALLOW, conditions=[
            ABACCondition("user_role", "eq", "admin"),
        ]))
        assert ev1.policy_hash == ev2.policy_hash

    def test_clear_resets_state(self) -> None:
        ev = self._make_evaluator()
        ev.add_rule(ABACRule(id="r1", effect=Effect.ALLOW))
        ev.clear()
        assert ev.rule_count == 0
        assert ev.policy_hash == ""

    def test_decision_audit_dict(self) -> None:
        ev = self._make_evaluator()
        ev.add_rule(ABACRule(
            id="allow-admin",
            effect=Effect.ALLOW,
            conditions=[ABACCondition("user_role", "eq", "admin")],
        ))
        ctx = RequestContext(user_role="admin", source_ip="10.0.0.1")
        decision = ev.evaluate(ctx)
        audit = decision.to_audit_dict()
        assert audit["effect"] == "allow"
        assert "allow-admin" in audit["matched_rules"]
        assert audit["context"]["user_role"] == "admin"
        assert audit["context"]["source_ip"] == "10.0.0.1"
        assert len(audit["policy_hash"]) == 64  # SHA-256 hex

    def test_context_snapshot_excludes_defaults(self) -> None:
        ev = self._make_evaluator()
        ev.add_rule(ABACRule(id="r1", effect=Effect.ALLOW))
        ctx = RequestContext(user_role="admin")
        decision = ev.evaluate(ctx)
        snap = decision.context_snapshot
        assert "user_role" in snap
        assert "trust_level" not in snap  # -1 is default
        assert "source_ip" not in snap  # "" is default

    def test_unmatched_context_gets_default_deny(self) -> None:
        ev = self._make_evaluator(default_effect=Effect.DENY)
        ev.add_rule(ABACRule(
            id="allow-admin",
            effect=Effect.ALLOW,
            conditions=[ABACCondition("user_role", "eq", "admin")],
        ))
        ctx = RequestContext(user_role="viewer")
        decision = ev.evaluate(ctx)
        assert decision.denied is True


# ---------------------------------------------------------------------------
# YAML loading
# ---------------------------------------------------------------------------


class TestYAMLLoading:
    def test_load_rules_from_yaml(self, tmp_path: Path) -> None:
        yaml_content = textwrap.dedent("""\
            rules:
              - id: allow-admin-shell
                effect: allow
                description: Admins can use shell tools
                priority: 10
                conditions:
                  user_role: admin
                  tool_category: shell
              - id: deny-guest-all
                effect: deny
                description: Guests denied everything
                conditions:
                  user_role: guest
        """)
        yaml_file = tmp_path / "test_policy.yaml"
        yaml_file.write_text(yaml_content)

        ev = ABACEvaluator()
        count = ev.load_rules_from_yaml(yaml_file)
        assert count == 2
        assert ev.rule_count == 2

        # Admin + shell → allowed
        ctx_ok = RequestContext(user_role="admin", tool_category="shell")
        assert ev.evaluate(ctx_ok).allowed is True

        # Guest → denied
        ctx_deny = RequestContext(user_role="guest")
        assert ev.evaluate(ctx_deny).denied is True

    def test_load_yaml_complex_conditions(self, tmp_path: Path) -> None:
        yaml_content = textwrap.dedent("""\
            rules:
              - id: business-hours-only
                effect: allow
                conditions:
                  user_role:
                    - operator
                    - admin
                  time_of_day:
                    after: "09:00"
                    before: "17:00"
                  source_ip:
                    cidr: "10.0.0.0/8"
              - id: deny-classified
                effect: deny
                conditions:
                  data_classification:
                    not: public
        """)
        yaml_file = tmp_path / "complex_policy.yaml"
        yaml_file.write_text(yaml_content)

        ev = ABACEvaluator()
        count = ev.load_rules_from_yaml(yaml_file)
        assert count == 2

        ctx_ok = RequestContext.from_dict({
            "user_role": "operator",
            "time_of_day": "12:00",
            "source_ip": "10.1.2.3",
        })
        assert ev.evaluate(ctx_ok).allowed is True

    def test_load_yaml_missing_file_raises(self) -> None:
        ev = ABACEvaluator()
        with pytest.raises(FileNotFoundError):
            ev.load_rules_from_yaml("/nonexistent/path.yaml")

    def test_load_yaml_empty_file(self, tmp_path: Path) -> None:
        yaml_file = tmp_path / "empty.yaml"
        yaml_file.write_text("")
        ev = ABACEvaluator()
        count = ev.load_rules_from_yaml(yaml_file)
        assert count == 0


# ---------------------------------------------------------------------------
# _parse_conditions — YAML dict → ABACCondition list
# ---------------------------------------------------------------------------


class TestParseConditions:
    def test_simple_equality(self) -> None:
        conds = _parse_conditions({"user_role": "admin"})
        assert len(conds) == 1
        assert conds[0].operator == "eq"

    def test_list_becomes_in(self) -> None:
        conds = _parse_conditions({"user_role": ["admin", "operator"]})
        assert conds[0].operator == "in"

    def test_time_range(self) -> None:
        conds = _parse_conditions({"time_of_day": {"after": "09:00", "before": "17:00"}})
        assert conds[0].operator == "time_range"

    def test_cidr(self) -> None:
        conds = _parse_conditions({"source_ip": {"cidr": "10.0.0.0/8"}})
        assert conds[0].operator == "cidr"

    def test_pattern_regex(self) -> None:
        conds = _parse_conditions({"agent_type": {"pattern": "^code_.*"}})
        assert conds[0].operator == "regex"

    def test_negation(self) -> None:
        conds = _parse_conditions({"data_classification": {"not": "top_secret"}})
        assert conds[0].operator == "not_eq"

    def test_not_in_list(self) -> None:
        conds = _parse_conditions({"user_role": {"not_in": ["guest", "viewer"]}})
        assert conds[0].operator == "not_in"

    def test_explicit_in_dict(self) -> None:
        conds = _parse_conditions({"user_role": {"in": ["admin", "operator"]}})
        assert conds[0].operator == "in"
