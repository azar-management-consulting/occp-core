"""Tests for engine.py REQ-POL-02 + REQ-GOV-02 upgrades.

Covers:
- YAML policy loading alongside JSON
- ABAC integration into PolicyEngine.evaluate()
- Structured decision records (to_decision_record)
- Policy hash tracking and determinism
- Decision replay (same input + same policy = same output)
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Any

import pytest

from policy_engine.abac import (
    ABACCondition,
    ABACEvaluator,
    ABACRule,
    Effect,
    RequestContext,
)
from policy_engine.engine import GateResult, PolicyEngine
from policy_engine.models import Policy, PolicyRule, RuleAction


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeTask:
    def __init__(
        self,
        name: str = "test",
        description: str = "safe",
        agent_type: str = "test",
        **meta: Any,
    ) -> None:
        self.id = "fake_001"
        self.name = name
        self.description = description
        self.agent_type = agent_type
        self.plan = None
        self.metadata: dict[str, Any] = meta


# ---------------------------------------------------------------------------
# GateResult.to_decision_record
# ---------------------------------------------------------------------------


class TestDecisionRecord:
    def test_basic_record(self) -> None:
        result = GateResult(
            approved=True,
            policy_hash="abc123",
        )
        record = result.to_decision_record()
        assert record["approved"] is True
        assert record["policy_hash"] == "abc123"
        assert record["violated_rules"] == []
        assert "abac" not in record

    def test_record_includes_abac(self) -> None:
        from policy_engine.abac import ABACDecision

        abac = ABACDecision(
            effect=Effect.ALLOW,
            matched_rules=["rule-1"],
            reason="test",
            policy_hash="def456",
        )
        result = GateResult(
            approved=True,
            abac_decision=abac,
            policy_hash="combined_hash",
        )
        record = result.to_decision_record()
        assert "abac" in record
        assert record["abac"]["effect"] == "allow"
        assert "rule-1" in record["abac"]["matched_rules"]

    def test_record_includes_guard_details(self) -> None:
        from policy_engine.guards import GuardResult

        gr = GuardResult(guard_name="pii_guard", passed=False, detail="email detected")
        result = GateResult(
            approved=False,
            reason="Guards failed: pii_guard",
            guard_results=[gr],
            policy_hash="hash",
        )
        record = result.to_decision_record()
        assert len(record["guards"]) == 1
        assert record["guards"][0]["name"] == "pii_guard"
        assert record["guards"][0]["passed"] is False


# ---------------------------------------------------------------------------
# PolicyEngine — policy hash tracking (REQ-GOV-02)
# ---------------------------------------------------------------------------


class TestPolicyHash:
    def test_empty_engine_has_hash(self) -> None:
        engine = PolicyEngine()
        assert isinstance(engine.policy_hash, str)

    def test_hash_changes_on_policy_add(self) -> None:
        engine = PolicyEngine()
        h1 = engine.policy_hash
        engine.add_policy(Policy(
            name="test", version="1.0",
            rules=[PolicyRule(id="r1", description="", action=RuleAction.ALLOW)],
        ))
        h2 = engine.policy_hash
        assert h1 != h2

    def test_hash_deterministic(self) -> None:
        e1 = PolicyEngine()
        e2 = PolicyEngine()
        policy = Policy(
            name="test", version="1.0",
            rules=[PolicyRule(id="r1", description="d", action=RuleAction.DENY,
                              conditions={"agent_type": "bad"})],
        )
        e1.add_policy(policy)
        e2.add_policy(Policy(
            name="test", version="1.0",
            rules=[PolicyRule(id="r1", description="d", action=RuleAction.DENY,
                              conditions={"agent_type": "bad"})],
        ))
        assert e1.policy_hash == e2.policy_hash

    def test_hash_changes_with_abac(self) -> None:
        engine = PolicyEngine()
        h1 = engine.policy_hash
        abac = ABACEvaluator()
        abac.add_rule(ABACRule(id="r1", effect=Effect.ALLOW))
        engine.set_abac_evaluator(abac)
        h2 = engine.policy_hash
        assert h1 != h2

    def test_hash_is_sha256(self) -> None:
        engine = PolicyEngine()
        engine.add_policy(Policy(name="t", version="1", rules=[]))
        assert len(engine.policy_hash) == 64  # SHA-256 hex


# ---------------------------------------------------------------------------
# PolicyEngine — ABAC integration
# ---------------------------------------------------------------------------


class TestABACIntegration:
    @pytest.mark.asyncio
    async def test_abac_deny_blocks_task(self) -> None:
        engine = PolicyEngine()
        abac = ABACEvaluator()
        abac.add_rule(ABACRule(
            id="deny-dangerous",
            effect=Effect.DENY,
            conditions=[ABACCondition("agent_type", "eq", "dangerous")],
        ))
        engine.set_abac_evaluator(abac)

        task = _FakeTask(agent_type="dangerous")
        result = await engine.evaluate(task)
        assert not result.approved
        assert "deny-dangerous" in result.violated_rules
        assert result.abac_decision is not None
        assert result.abac_decision.denied

    @pytest.mark.asyncio
    async def test_abac_allow_passes(self) -> None:
        engine = PolicyEngine()
        abac = ABACEvaluator()
        abac.add_rule(ABACRule(
            id="allow-safe",
            effect=Effect.ALLOW,
            conditions=[ABACCondition("agent_type", "eq", "test")],
        ))
        engine.set_abac_evaluator(abac)

        task = _FakeTask(agent_type="test")
        result = await engine.evaluate(task)
        assert result.approved
        assert result.abac_decision is not None
        assert result.abac_decision.allowed

    @pytest.mark.asyncio
    async def test_abac_require_approval(self) -> None:
        engine = PolicyEngine()
        abac = ABACEvaluator()
        abac.add_rule(ABACRule(
            id="approve-shell",
            effect=Effect.REQUIRE_APPROVAL,
            conditions=[ABACCondition("agent_type", "eq", "test")],
        ))
        engine.set_abac_evaluator(abac)

        task = _FakeTask()
        result = await engine.evaluate(task)
        assert not result.approved
        assert "approval" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_no_abac_evaluator_still_works(self) -> None:
        """Backward compat: engine without ABAC evaluator works fine."""
        engine = PolicyEngine()
        task = _FakeTask()
        result = await engine.evaluate(task)
        assert result.approved
        assert result.abac_decision is None

    @pytest.mark.asyncio
    async def test_abac_decision_in_audit(self) -> None:
        engine = PolicyEngine()
        abac = ABACEvaluator()
        abac.add_rule(ABACRule(
            id="allow-all",
            effect=Effect.ALLOW,
        ))
        engine.set_abac_evaluator(abac)

        task = _FakeTask()
        await engine.evaluate(task)

        log = engine.audit_log
        assert len(log) == 1
        detail = log[0].detail
        assert "abac" in detail
        assert detail["abac"]["effect"] == "allow"

    @pytest.mark.asyncio
    async def test_guard_failure_takes_precedence(self) -> None:
        """Guard failure should block even if ABAC allows."""
        engine = PolicyEngine()
        abac = ABACEvaluator()
        abac.add_rule(ABACRule(id="allow-all", effect=Effect.ALLOW))
        engine.set_abac_evaluator(abac)

        # Trigger PII guard
        task = _FakeTask(description="email: user@example.com")
        result = await engine.evaluate(task)
        assert not result.approved
        assert "pii_guard" in result.reason


# ---------------------------------------------------------------------------
# PolicyEngine — YAML loading (REQ-GOV-02)
# ---------------------------------------------------------------------------


class TestYAMLPolicyLoading:
    def test_load_yaml_abac_rules(self, tmp_path: Path) -> None:
        yaml_content = textwrap.dedent("""\
            name: abac_policy
            version: "2.0"
            rules:
              - id: allow-admin
                effect: allow
                conditions:
                  user_role: admin
              - id: deny-guest
                effect: deny
                conditions:
                  user_role: guest
        """)
        yaml_file = tmp_path / "policy.yaml"
        yaml_file.write_text(yaml_content)

        engine = PolicyEngine()
        policy = engine.load_policy_file(yaml_file)
        assert policy.name == "abac_policy"
        assert policy.version == "2.0"
        assert engine.abac_evaluator is not None
        assert engine.abac_evaluator.rule_count == 2

    def test_load_yaml_with_yml_extension(self, tmp_path: Path) -> None:
        yaml_content = textwrap.dedent("""\
            name: test
            rules:
              - id: r1
                effect: allow
                conditions:
                  user_role: admin
        """)
        yaml_file = tmp_path / "policy.yml"
        yaml_file.write_text(yaml_content)

        engine = PolicyEngine()
        policy = engine.load_policy_file(yaml_file)
        assert policy.name == "test"

    def test_load_json_still_works(self, tmp_path: Path) -> None:
        json_content = {
            "name": "json_policy",
            "version": "1.0",
            "rules": [
                {"id": "r1", "description": "", "action": "allow", "conditions": {}}
            ],
        }
        json_file = tmp_path / "policy.json"
        json_file.write_text(json.dumps(json_content))

        engine = PolicyEngine()
        policy = engine.load_policy_file(json_file)
        assert policy.name == "json_policy"

    def test_load_yaml_missing_file(self) -> None:
        engine = PolicyEngine()
        with pytest.raises(Exception):
            engine.load_policy_file("/nonexistent/policy.yaml")

    def test_load_yaml_empty_raises(self, tmp_path: Path) -> None:
        yaml_file = tmp_path / "empty.yaml"
        yaml_file.write_text("")

        engine = PolicyEngine()
        with pytest.raises(Exception):
            engine.load_policy_file(yaml_file)

    @pytest.mark.asyncio
    async def test_yaml_abac_rules_enforce(self, tmp_path: Path) -> None:
        """End-to-end: YAML → ABAC evaluator → evaluate()."""
        yaml_content = textwrap.dedent("""\
            name: e2e_test
            rules:
              - id: deny-dangerous
                effect: deny
                conditions:
                  agent_type: dangerous
        """)
        yaml_file = tmp_path / "e2e.yaml"
        yaml_file.write_text(yaml_content)

        engine = PolicyEngine()
        engine.load_policy_file(yaml_file)

        task = _FakeTask(agent_type="dangerous")
        result = await engine.evaluate(task)
        assert not result.approved
        assert "deny-dangerous" in result.violated_rules

    def test_policy_hash_includes_yaml(self, tmp_path: Path) -> None:
        yaml_content = textwrap.dedent("""\
            name: hash_test
            rules:
              - id: r1
                effect: allow
                conditions:
                  user_role: admin
        """)
        yaml_file = tmp_path / "hash.yaml"
        yaml_file.write_text(yaml_content)

        engine = PolicyEngine()
        h1 = engine.policy_hash
        engine.load_policy_file(yaml_file)
        h2 = engine.policy_hash
        assert h1 != h2
        assert len(h2) == 64


# ---------------------------------------------------------------------------
# Decision replay (REQ-GOV-02)
# ---------------------------------------------------------------------------


class TestDecisionReplay:
    @pytest.mark.asyncio
    async def test_same_input_same_policy_same_output(self) -> None:
        """Decision replay: identical input + policy hash → identical result."""
        engine = PolicyEngine()
        abac = ABACEvaluator()
        abac.add_rule(ABACRule(
            id="allow-test",
            effect=Effect.ALLOW,
            conditions=[ABACCondition("agent_type", "eq", "test")],
        ))
        engine.set_abac_evaluator(abac)

        task = _FakeTask(agent_type="test")
        r1 = await engine.evaluate(task)
        r2 = await engine.evaluate(task)

        assert r1.approved == r2.approved
        assert r1.policy_hash == r2.policy_hash
        assert r1.to_decision_record()["approved"] == r2.to_decision_record()["approved"]

    @pytest.mark.asyncio
    async def test_policy_hash_in_result(self) -> None:
        engine = PolicyEngine()
        engine.add_policy(Policy(name="p", version="1", rules=[]))
        task = _FakeTask()
        result = await engine.evaluate(task)
        assert result.policy_hash == engine.policy_hash
        assert len(result.policy_hash) == 64

    @pytest.mark.asyncio
    async def test_audit_chain_with_decision_records(self) -> None:
        """Audit entries contain full decision records."""
        engine = PolicyEngine()
        task = _FakeTask()
        await engine.evaluate(task)
        await engine.evaluate(task)

        assert len(engine.audit_log) == 2
        assert engine.verify_audit_chain()

        for entry in engine.audit_log:
            assert "approved" in entry.detail
            assert "policy_hash" in entry.detail
            assert "guards" in entry.detail


