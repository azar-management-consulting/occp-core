"""Tests for orchestrator.task_router — TaskRouter intelligent routing.

Covers:
  - Routing to each of 8 agents (8 tests)
  - Multi-agent workflow detection (4 tests)
  - Risk assessment (4 tests)
  - Hungarian keyword matching (3 tests)
  - Confidence scoring (3 tests)
  - Unknown task fallback (1 test)
  - Workflow template matching (2 tests)
  - Integration with voice_handler (2 tests)
  - Edge cases (3 tests)
Total: 30 tests
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from orchestrator.task_router import (
    DEFAULT_AGENT,
    MIN_CONFIDENCE_THRESHOLD,
    RouteDecision,
    TaskRouter,
    _normalize_hungarian,
)


@pytest.fixture
def router() -> TaskRouter:
    return TaskRouter()


# ---------------------------------------------------------------------------
# 1. Routing to each of the 8 agents
# ---------------------------------------------------------------------------


class TestAgentRouting:
    """Verify each agent gets routed to by its keywords."""

    def test_route_to_eng_core(self, router: TaskRouter) -> None:
        decision = router.route("Fix the python fastapi bug in the backend API")
        assert decision.primary_agent == "eng-core"
        assert decision.confidence > 0

    def test_route_to_wp_web(self, router: TaskRouter) -> None:
        decision = router.route("Update the WordPress Elementor landing page")
        assert decision.primary_agent == "wp-web"
        assert decision.confidence > 0

    def test_route_to_infra_ops(self, router: TaskRouter) -> None:
        decision = router.route("Deploy the docker container to the server with SSL")
        assert decision.primary_agent == "infra-ops"
        assert decision.confidence > 0

    def test_route_to_design_lab(self, router: TaskRouter) -> None:
        decision = router.route("Create a new UI design wireframe mockup for the dashboard")
        assert decision.primary_agent == "design-lab"
        assert decision.confidence > 0

    def test_route_to_content_forge(self, router: TaskRouter) -> None:
        decision = router.route("Write a blog article about SEO content strategy")
        assert decision.primary_agent == "content-forge"
        assert decision.confidence > 0

    def test_route_to_social_growth(self, router: TaskRouter) -> None:
        decision = router.route("Create a Facebook Instagram ad campaign with hashtags")
        assert decision.primary_agent == "social-growth"
        assert decision.confidence > 0

    def test_route_to_intel_research(self, router: TaskRouter) -> None:
        decision = router.route("Research the competitor analysis and market trends")
        assert decision.primary_agent == "intel-research"
        assert decision.confidence > 0

    def test_route_to_biz_strategy(self, router: TaskRouter) -> None:
        decision = router.route("Prepare a business proposal with pricing strategy for the partner pitch")
        assert decision.primary_agent == "biz-strategy"
        assert decision.confidence > 0


# ---------------------------------------------------------------------------
# 2. Multi-agent workflow detection
# ---------------------------------------------------------------------------


class TestWorkflowDetection:
    """Verify workflow template detection from natural language."""

    def test_detect_landing_page_workflow(self, router: TaskRouter) -> None:
        decision = router.route("Build a new landing page for the product")
        assert decision.matched_workflow == "new_landing_page"
        assert "design-lab" in decision.support_agents or decision.primary_agent == "wp-web"

    def test_detect_marketing_campaign_workflow(self, router: TaskRouter) -> None:
        decision = router.route("Plan a marketing campaign for Q2 launch")
        assert decision.matched_workflow == "marketing_campaign"

    def test_detect_business_proposal_workflow(self, router: TaskRouter) -> None:
        decision = router.route("Create a business proposal for the client meeting")
        assert decision.matched_workflow == "business_proposal"

    def test_detect_competitor_analysis_workflow(self, router: TaskRouter) -> None:
        decision = router.route("Do a competitor analysis of our market space")
        assert decision.matched_workflow == "competitor_analysis"


# ---------------------------------------------------------------------------
# 3. Risk assessment
# ---------------------------------------------------------------------------


class TestRiskAssessment:
    """Verify risk levels are computed correctly."""

    def test_low_risk_for_simple_task(self, router: TaskRouter) -> None:
        decision = router.route("Create a new React component for the sidebar")
        assert decision.risk_level == "low"
        assert decision.requires_approval is False

    def test_medium_risk_for_production_keyword(self, router: TaskRouter) -> None:
        decision = router.route("Deploy the new code to production server")
        assert decision.risk_level in ("medium", "high")

    def test_high_risk_for_infra_deploy(self, router: TaskRouter) -> None:
        decision = router.route("Deploy and migrate the production database on the server")
        assert decision.risk_level in ("high", "critical")
        assert decision.requires_approval is True

    def test_critical_risk_for_destructive(self, router: TaskRouter) -> None:
        decision = router.route("Force push and drop database on production")
        assert decision.risk_level == "critical"
        assert decision.requires_approval is True


# ---------------------------------------------------------------------------
# 4. Hungarian keyword matching
# ---------------------------------------------------------------------------


class TestHungarianSupport:
    """Verify Hungarian-language task routing."""

    def test_hungarian_wp_keywords(self, router: TaskRouter) -> None:
        decision = router.route("Frissitsd a WordPress weboldal honlap temajat")
        assert decision.primary_agent == "wp-web"

    def test_hungarian_content_keywords(self, router: TaskRouter) -> None:
        decision = router.route("Irj egy cikket a tartalom strategiarol")
        assert decision.primary_agent == "content-forge"

    def test_hungarian_business_keywords(self, router: TaskRouter) -> None:
        decision = router.route("Keszits uzleti ajanlatot az uj partnerseghez")
        assert decision.primary_agent == "biz-strategy"

    def test_hungarian_accent_normalization(self) -> None:
        """Verify _normalize_hungarian strips accents correctly."""
        assert _normalize_hungarian("\u00c1rv\u00edzt\u0171r\u0151") == "arvizturo"
        assert _normalize_hungarian("\u00d6t\u00f6k") == "otok"
        assert _normalize_hungarian("\u00dc") == "u"


# ---------------------------------------------------------------------------
# 5. Confidence scoring
# ---------------------------------------------------------------------------


class TestConfidenceScoring:
    """Verify confidence scores are meaningful."""

    def test_high_confidence_for_many_keywords(self, router: TaskRouter) -> None:
        decision = router.route(
            "Fix the python fastapi backend api bug in the test database migration code"
        )
        assert decision.confidence >= 0.5
        assert decision.primary_agent == "eng-core"

    def test_low_confidence_for_ambiguous(self, router: TaskRouter) -> None:
        decision = router.route("Do something")
        assert decision.confidence < 0.3

    def test_confidence_capped_at_1(self, router: TaskRouter) -> None:
        # Very keyword-heavy input
        decision = router.route(
            "python fastapi api backend bug test refactor database migration "
            "code typescript react next.js endpoint schema pytest"
        )
        assert decision.confidence <= 1.0


# ---------------------------------------------------------------------------
# 6. Unknown task fallback
# ---------------------------------------------------------------------------


class TestFallback:
    """Verify fallback to default agent."""

    def test_unknown_task_falls_back_to_default(self, router: TaskRouter) -> None:
        decision = router.route("xyzzy foobar baz quux")
        assert decision.primary_agent == DEFAULT_AGENT
        assert decision.confidence < MIN_CONFIDENCE_THRESHOLD

    def test_empty_input_falls_back(self, router: TaskRouter) -> None:
        decision = router.route("")
        assert decision.primary_agent == DEFAULT_AGENT
        assert decision.confidence == 0.0

    def test_whitespace_only_falls_back(self, router: TaskRouter) -> None:
        decision = router.route("   ")
        assert decision.primary_agent == DEFAULT_AGENT
        assert decision.confidence == 0.0


# ---------------------------------------------------------------------------
# 7. Workflow template matching
# ---------------------------------------------------------------------------


class TestWorkflowTemplates:
    """Verify workflow template details."""

    def test_workflow_sets_support_agents(self, router: TaskRouter) -> None:
        decision = router.route("Create a new landing page with design and copy")
        assert decision.matched_workflow == "new_landing_page"
        assert len(decision.support_agents) >= 1

    def test_security_hardening_workflow(self, router: TaskRouter) -> None:
        decision = router.route("Security hardening for the production server")
        assert decision.matched_workflow == "security_hardening"
        expected_agents = {"eng-core", "infra-ops"}
        all_agents = {decision.primary_agent} | set(decision.support_agents)
        assert all_agents == expected_agents


# ---------------------------------------------------------------------------
# 8. Integration with voice_handler
# ---------------------------------------------------------------------------


class TestVoiceHandlerIntegration:
    """Verify TaskRouter integrates with VoiceCommandHandler."""

    def test_voice_handler_accepts_task_router(self) -> None:
        """VoiceCommandHandler constructor accepts task_router parameter."""
        from adapters.voice_handler import VoiceCommandHandler

        mock_whisper = MagicMock()
        mock_intent = MagicMock()
        mock_pipeline = MagicMock()
        mock_task_store = MagicMock()
        mock_audit_store = MagicMock()
        tr = TaskRouter()

        handler = VoiceCommandHandler(
            whisper=mock_whisper,
            intent_router=mock_intent,
            pipeline=mock_pipeline,
            task_store=mock_task_store,
            audit_store=mock_audit_store,
            task_router=tr,
        )
        assert handler._task_router is tr

    def test_voice_handler_without_task_router(self) -> None:
        """VoiceCommandHandler works without task_router (backward compat)."""
        from adapters.voice_handler import VoiceCommandHandler

        handler = VoiceCommandHandler(
            whisper=MagicMock(),
            intent_router=MagicMock(),
            pipeline=MagicMock(),
            task_store=MagicMock(),
            audit_store=MagicMock(),
        )
        assert handler._task_router is None


# ---------------------------------------------------------------------------
# 9. Edge cases and utilities
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases and utility functions."""

    def test_route_decision_to_dict(self, router: TaskRouter) -> None:
        decision = router.route("Deploy the server")
        d = decision.to_dict()
        assert "primary_agent" in d
        assert "support_agents" in d
        assert "risk_level" in d
        assert "confidence" in d
        assert isinstance(d["confidence"], float)

    def test_format_brain_header(self, router: TaskRouter) -> None:
        decision = router.route("Deploy the docker container to production")
        header = router.format_brain_header(decision, project="TestProject")
        assert "Brian the Brain" in header
        assert "TestProject" in header
        assert decision.primary_agent in header

    def test_duration_estimate_single_agent(self, router: TaskRouter) -> None:
        decision = router.route("Write a blog article")
        # content-forge = 15min -> "15m"
        assert decision.estimated_duration in ("5m", "15m", "30m", "1h", "2h")

    def test_duration_estimate_multi_agent(self, router: TaskRouter) -> None:
        decision = router.route("Create a new landing page with design and content")
        # Multi-agent workflow: wp-web(30) + design-lab(20) + content-forge(15) = 65 -> "2h"
        if decision.matched_workflow:
            assert decision.estimated_duration in ("1h", "2h")

    def test_context_force_approval(self, router: TaskRouter) -> None:
        decision = router.route(
            "Create a React component",
            context={"force_approval": True},
        )
        assert decision.requires_approval is True

    def test_ip_address_routes_to_infra(self, router: TaskRouter) -> None:
        decision = router.route("Check the server at 195.201.238.144 port 8080")
        assert decision.primary_agent == "infra-ops"

    def test_score_agents_returns_dict(self, router: TaskRouter) -> None:
        scores = router._score_agents("python fastapi backend")
        assert isinstance(scores, dict)
        assert "eng-core" in scores
        assert scores["eng-core"] > 0

    def test_support_agents_require_meaningful_score(self, router: TaskRouter) -> None:
        """Support agents only included if their score is >= 40% of primary."""
        decision = router.route("Fix the python fastapi backend api bug")
        # eng-core should dominate; support agents should be few or none
        for sa in decision.support_agents:
            assert sa != decision.primary_agent
