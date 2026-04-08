"""Tests for evaluation.self_modifier (L6 governance enforcement).

Critical: these tests guard the runtime enforcement of architecture/boundaries.yaml.
Any change here MUST be reviewed — the self-modifier is a security boundary.
"""

from __future__ import annotations

import pytest

from evaluation.self_modifier import (
    ModificationVerdict,
    SelfModifier,
    get_self_modifier,
)


@pytest.fixture
def modifier():
    return SelfModifier()


# ── Immutable enforcement — red-line tests ───────────────────

class TestImmutableEnforcement:
    """These tests enforce the invariant: Claude Code may NEVER touch
    security/, policy_engine/, api/auth.py, migrations/, .env* autonomously.
    """

    def test_agent_allowlist_is_immutable(self, modifier):
        v = modifier.check("security/agent_allowlist.py")
        assert v.allowed is False
        assert v.tier == "immutable"

    def test_policy_guards_are_immutable(self, modifier):
        v = modifier.check("policy_engine/guards.py")
        assert v.allowed is False
        assert v.tier == "immutable"

    def test_policy_engine_is_immutable(self, modifier):
        v = modifier.check("policy_engine/engine.py")
        assert v.allowed is False
        assert v.tier == "immutable"

    def test_auth_is_immutable(self, modifier):
        v = modifier.check("api/auth.py")
        assert v.allowed is False
        assert v.tier == "immutable"

    def test_rbac_is_immutable(self, modifier):
        v = modifier.check("api/rbac.py")
        assert v.allowed is False
        assert v.tier == "immutable"

    def test_migrations_are_immutable(self, modifier):
        v = modifier.check("migrations/versions/001_initial.py")
        assert v.allowed is False
        assert v.tier == "immutable"

    def test_env_file_is_immutable(self, modifier):
        v = modifier.check(".env.production")
        assert v.allowed is False
        assert v.tier == "immutable"

    def test_governance_yaml_is_immutable(self, modifier):
        v = modifier.check("architecture/governance.yaml")
        assert v.allowed is False
        assert v.tier == "immutable"

    def test_master_protocol_is_immutable(self, modifier):
        v = modifier.check(".planning/protocol/MASTER_PROTOCOL_v1.md")
        assert v.allowed is False
        assert v.tier == "immutable"


# ── Human review tier ────────────────────────────────────────

class TestHumanReviewTier:

    def test_orchestrator_requires_review(self, modifier):
        v = modifier.check("orchestrator/pipeline.py")
        assert v.allowed is False
        assert v.tier == "human_review_required"
        assert v.required_reviewers >= 1

    def test_api_routes_require_review(self, modifier):
        v = modifier.check("api/routes/auth.py")
        assert v.allowed is False
        # auth.py is already in immutable bucket → immutable wins

    def test_config_files_require_review(self, modifier):
        v = modifier.check("config/rbac_policy.csv")
        assert v.allowed is False
        assert v.tier == "human_review_required"


# ── Autonomous-safe tier ─────────────────────────────────────

class TestAutonomousSafeTier:

    def test_architecture_yaml_is_safe(self, modifier):
        v = modifier.check("architecture/services.yaml")
        assert v.allowed is True
        assert v.tier == "autonomous_safe"

    def test_rfc_markdown_is_safe(self, modifier):
        v = modifier.check(".planning/rfc/0001-baseline.md")
        assert v.allowed is True
        assert v.tier == "autonomous_safe"

    def test_observability_module_is_safe(self, modifier):
        v = modifier.check("observability/metrics_collector.py")
        assert v.allowed is True
        assert v.tier == "autonomous_safe"

    def test_evaluation_module_is_safe(self, modifier):
        v = modifier.check("evaluation/replay_harness.py")
        assert v.allowed is True
        assert v.tier == "autonomous_safe"


# ── Unknown path fail-secure ─────────────────────────────────

class TestUnknownPath:

    def test_unknown_path_fails_secure(self, modifier):
        v = modifier.check("random/unknown/file.txt")
        assert v.allowed is False
        assert v.tier == "unknown"

    def test_malicious_path_traversal(self, modifier):
        # fnmatch won't match ../../ but our fallback is still fail-secure
        v = modifier.check("../../etc/passwd")
        assert v.allowed is False


# ── Bulk validation ──────────────────────────────────────────

class TestBulkValidation:

    def test_check_many_returns_dict(self, modifier):
        paths = [
            "architecture/services.yaml",
            "security/agent_allowlist.py",
            "observability/metrics_collector.py",
        ]
        results = modifier.check_many(paths)
        assert len(results) == 3
        assert results["architecture/services.yaml"].allowed is True
        assert results["security/agent_allowlist.py"].allowed is False

    def test_validate_proposal_all_safe(self, modifier):
        paths = [
            "architecture/services.yaml",
            "observability/metrics_collector.py",
        ]
        assert modifier.validate_proposal(paths) is True

    def test_validate_proposal_any_immutable(self, modifier):
        paths = [
            "architecture/services.yaml",
            "security/agent_allowlist.py",  # immutable
        ]
        assert modifier.validate_proposal(paths) is False


# ── Stats + history ──────────────────────────────────────────

class TestStatsAndHistory:

    def test_stats_after_checks(self, modifier):
        modifier.check("architecture/services.yaml")
        modifier.check("security/agent_allowlist.py")
        stats = modifier.stats
        assert stats["total_checks"] == 2
        assert stats["total_denied"] == 1
        assert stats["deny_rate"] == 0.5

    def test_recent_verdicts_captured(self, modifier):
        for i in range(5):
            modifier.check(f"architecture/services.yaml")
        assert len(modifier.recent_verdicts) == 5


# ── Rule listing ─────────────────────────────────────────────

class TestRuleListing:

    def test_list_immutable_globs_non_empty(self, modifier):
        globs = modifier.list_immutable_globs()
        assert len(globs) > 0
        assert "security/agent_allowlist.py" in globs

    def test_list_autonomous_safe_globs_non_empty(self, modifier):
        globs = modifier.list_autonomous_safe_globs()
        assert len(globs) > 0


# ── Singleton ────────────────────────────────────────────────

class TestSingleton:

    def test_singleton(self):
        m1 = get_self_modifier()
        m2 = get_self_modifier()
        assert m1 is m2
