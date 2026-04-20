"""Tests for ``adapters.model_router`` — task → model routing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from adapters.model_router import (
    DEFAULT_MODEL,
    ENV_OVERRIDE,
    HAIKU,
    OPUS,
    SONNET,
    ModelRouter,
    RoutingDecision,
)
from orchestrator.models import RiskLevel, Task


@dataclass
class _FakeTask:
    """Lightweight stand-in for Task — the router only reads attributes."""

    agent_type: str = "default"
    risk_level: str = "low"
    description: str = ""
    description_tokens: int | None = None
    id: str = "fake-1"


@pytest.fixture
def router() -> ModelRouter:
    return ModelRouter()


@pytest.fixture(autouse=True)
def _clear_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENV_OVERRIDE, raising=False)


# ---------------------------------------------------------------------------
# Haiku routes
# ---------------------------------------------------------------------------


class TestHaikuRouting:
    def test_classify_low_risk_routes_to_haiku(self, router: ModelRouter) -> None:
        task = _FakeTask(
            agent_type="classify",
            risk_level="low",
            description_tokens=100,
        )
        assert router.route(task) == HAIKU

    def test_classify_agent_type_always_haiku_regardless_of_size(
        self, router: ModelRouter
    ) -> None:
        task = _FakeTask(
            agent_type="classify",
            risk_level="low",
            description_tokens=10_000,
        )
        assert router.route(task) == HAIKU


# ---------------------------------------------------------------------------
# Sonnet routes
# ---------------------------------------------------------------------------


class TestSonnetRouting:
    def test_deep_research_routes_to_sonnet(self, router: ModelRouter) -> None:
        task = _FakeTask(agent_type="deep-research", risk_level="low")
        assert router.route(task) == SONNET

    @pytest.mark.parametrize(
        "agent", ["content-forge", "seo", "intel-research"]
    )
    def test_other_sonnet_agents(self, router: ModelRouter, agent: str) -> None:
        task = _FakeTask(agent_type=agent, risk_level="low")
        assert router.route(task) == SONNET

    def test_unknown_agent_type_defaults_sonnet(self, router: ModelRouter) -> None:
        task = _FakeTask(agent_type="unknown-agent-xyz", risk_level="low")
        assert router.route(task) == DEFAULT_MODEL == SONNET


# ---------------------------------------------------------------------------
# Opus routes
# ---------------------------------------------------------------------------


class TestOpusRouting:
    def test_eng_core_routes_to_opus(self, router: ModelRouter) -> None:
        task = _FakeTask(agent_type="eng-core", risk_level="low")
        assert router.route(task) == OPUS

    @pytest.mark.parametrize("agent", ["architect", "autodev"])
    def test_other_opus_agents(self, router: ModelRouter, agent: str) -> None:
        task = _FakeTask(agent_type=agent, risk_level="low")
        assert router.route(task) == OPUS

    def test_high_risk_always_opus(self, router: ModelRouter) -> None:
        # Even a normally-Sonnet agent becomes Opus under high risk.
        task = _FakeTask(agent_type="content-forge", risk_level="high")
        assert router.route(task) == OPUS

    def test_critical_risk_routes_to_opus(self, router: ModelRouter) -> None:
        task = _FakeTask(agent_type="deep-research", risk_level="critical")
        assert router.route(task) == OPUS


# ---------------------------------------------------------------------------
# Environment override
# ---------------------------------------------------------------------------


class TestEnvOverride:
    def test_env_override_forces_model(
        self, router: ModelRouter, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ENV_OVERRIDE, "claude-haiku-4-5")
        task = _FakeTask(agent_type="eng-core", risk_level="high")
        # Without override this would be Opus; env flag forces Haiku.
        assert router.route(task) == "claude-haiku-4-5"

    def test_env_override_empty_string_ignored(
        self, router: ModelRouter, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ENV_OVERRIDE, "   ")
        task = _FakeTask(agent_type="architect", risk_level="low")
        assert router.route(task) == OPUS

    def test_decide_marks_override_flag(
        self, router: ModelRouter, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ENV_OVERRIDE, "claude-sonnet-4-6")
        task = _FakeTask(agent_type="autodev", risk_level="critical")
        decision = router.decide(task)
        assert decision.model_id == "claude-sonnet-4-6"
        assert decision.override is True


# ---------------------------------------------------------------------------
# Task dataclass integration
# ---------------------------------------------------------------------------


class TestTaskIntegration:
    def test_router_accepts_orchestrator_task(self, router: ModelRouter) -> None:
        task = Task(
            name="build landing",
            description="small",
            agent_type="architect",
            risk_level=RiskLevel.LOW,
        )
        assert router.route(task) == OPUS

    def test_router_reads_enum_risk_level(self, router: ModelRouter) -> None:
        task = Task(
            name="fix",
            description="hot",
            agent_type="content-forge",
            risk_level=RiskLevel.HIGH,
        )
        assert router.route(task) == OPUS

    def test_router_uses_description_length_approximation(
        self, router: ModelRouter
    ) -> None:
        """Without explicit description_tokens the router approximates
        from description length (len/4)."""
        task = _FakeTask(
            agent_type="classify",
            risk_level="low",
            description="a" * 4_000,  # ~1 000 tokens
        )
        # classify always routes to haiku regardless of tokens — just
        # verifies the code path runs without error.
        assert router.route(task) == HAIKU


# ---------------------------------------------------------------------------
# Decision dataclass
# ---------------------------------------------------------------------------


class TestDecision:
    def test_decision_to_dict(self, router: ModelRouter) -> None:
        task = _FakeTask(agent_type="eng-core", risk_level="low")
        d = router.decide(task).to_dict()
        assert d["model_id"] == OPUS
        assert "reason" in d
        assert d["override"] is False

    def test_decision_reason_contains_agent_or_risk(self, router: ModelRouter) -> None:
        task = _FakeTask(agent_type="content-forge", risk_level="high")
        decision = router.decide(task)
        assert "high" in decision.reason or "opus" in decision.reason.lower()


# ---------------------------------------------------------------------------
# Dict-like tasks (compat with message-bus payloads)
# ---------------------------------------------------------------------------


class TestDictTaskCompat:
    def test_router_accepts_plain_dict(self, router: ModelRouter) -> None:
        task: dict[str, Any] = {
            "agent_type": "eng-core",
            "risk_level": "low",
            "description": "",
        }
        assert router.route(task) == OPUS

    def test_router_defaults_when_fields_missing(self, router: ModelRouter) -> None:
        assert router.route({}) == DEFAULT_MODEL
