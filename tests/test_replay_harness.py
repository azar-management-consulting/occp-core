"""Tests for evaluation.replay_harness (L6 completion — real execution)."""

from __future__ import annotations

import asyncio

import pytest

from evaluation.replay_harness import (
    ReplayHarness,
    ReplayResult,
    ReplayScenario,
    get_replay_harness,
)


@pytest.fixture
def harness():
    return ReplayHarness()


@pytest.fixture
def baseline_scenario():
    return ReplayScenario(
        scenario_id="bl-001",
        source_execution_id="exec-001",
        workflow_definition={"task": "hello"},
        original_outcome="success",
        original_duration_seconds=0.1,
        original_stages=["plan", "gate", "execute", "validate", "ship"],
        original_output={"message": "hello world", "stages": ["plan", "gate", "execute", "validate", "ship"], "outcome": "success"},
    )


async def _stable_candidate(scenario: ReplayScenario) -> dict:
    """Candidate that matches the baseline exactly."""
    await asyncio.sleep(0.05)
    return {
        "message": "hello world",
        "stages": ["plan", "gate", "execute", "validate", "ship"],
        "outcome": "success",
    }


async def _slow_candidate(scenario: ReplayScenario) -> dict:
    """Candidate that is much slower than baseline."""
    await asyncio.sleep(0.5)  # 5x baseline
    return {
        "message": "hello world",
        "stages": ["plan", "gate", "execute", "validate", "ship"],
        "outcome": "success",
    }


async def _regressed_candidate(scenario: ReplayScenario) -> dict:
    """Candidate that changes the outcome to failed."""
    await asyncio.sleep(0.05)
    return {
        "message": "error",
        "stages": ["plan", "gate", "execute"],  # missing stages
        "outcome": "failed",
    }


async def _raising_candidate(scenario: ReplayScenario) -> dict:
    raise RuntimeError("candidate crashed")


# ── Basic scenario storage ────────────────────────────────────

class TestScenarioStorage:

    def test_register_and_get(self, harness, baseline_scenario):
        harness.register_scenario(baseline_scenario)
        assert harness.get_scenario("bl-001") is baseline_scenario
        assert harness.get_scenario("missing") is None

    def test_list_scenarios(self, harness, baseline_scenario):
        harness.register_scenario(baseline_scenario)
        assert len(harness.list_scenarios()) == 1

    def test_reset(self, harness, baseline_scenario):
        harness.register_scenario(baseline_scenario)
        harness.reset()
        assert harness.list_scenarios() == []


# ── Execution — stable candidate ─────────────────────────────

class TestStableCandidate:

    @pytest.mark.asyncio
    async def test_stable_candidate_success(self, harness, baseline_scenario):
        harness.register_scenario(baseline_scenario)
        result = await harness.run(
            baseline_scenario, _stable_candidate, candidate_ref="stable"
        )
        assert result.outcome == "success"
        assert result.stage_parity is True
        assert result.output_equivalent is True
        assert result.regressions == []
        assert not result.is_regression

    @pytest.mark.asyncio
    async def test_stable_candidate_result_recorded(self, harness, baseline_scenario):
        harness.register_scenario(baseline_scenario)
        await harness.run(baseline_scenario, _stable_candidate, candidate_ref="stable")
        results = harness.get_results("bl-001")
        assert len(results) == 1


# ── Execution — slow candidate ───────────────────────────────

class TestSlowCandidate:

    @pytest.mark.asyncio
    async def test_slow_candidate_flagged(self, harness, baseline_scenario):
        harness.register_scenario(baseline_scenario)
        result = await harness.run(
            baseline_scenario, _slow_candidate, candidate_ref="slow"
        )
        assert result.outcome == "regression"
        assert any("duration" in r for r in result.regressions)
        assert result.is_regression


# ── Execution — regressed candidate ──────────────────────────

class TestRegressedCandidate:

    @pytest.mark.asyncio
    async def test_regressed_outcome_detected(self, harness, baseline_scenario):
        harness.register_scenario(baseline_scenario)
        result = await harness.run(
            baseline_scenario, _regressed_candidate, candidate_ref="reg"
        )
        assert result.outcome == "regression"
        assert result.stage_parity is False
        assert result.output_equivalent is False


# ── Execution — raising candidate ────────────────────────────

class TestRaisingCandidate:

    @pytest.mark.asyncio
    async def test_raising_candidate_marks_failed(self, harness, baseline_scenario):
        harness.register_scenario(baseline_scenario)
        result = await harness.run(
            baseline_scenario, _raising_candidate, candidate_ref="crash"
        )
        assert result.outcome == "failed"
        assert result.is_regression
        assert any("candidate crashed" in r for r in result.regressions)


# ── Batch runs ───────────────────────────────────────────────

class TestRunAll:

    @pytest.mark.asyncio
    async def test_run_all_runs_every_scenario(self, harness):
        for i in range(3):
            harness.register_scenario(
                ReplayScenario(
                    scenario_id=f"s{i}",
                    source_execution_id=f"e{i}",
                    workflow_definition={},
                    original_outcome="success",
                    original_duration_seconds=0.1,
                    original_stages=["plan", "gate", "execute", "validate", "ship"],
                    # Full output including message (what the candidate returns)
                    original_output={
                        "message": "hello world",
                        "stages": ["plan", "gate", "execute", "validate", "ship"],
                        "outcome": "success",
                    },
                )
            )
        results = await harness.run_all(_stable_candidate, candidate_ref="s")
        assert len(results) == 3
        assert all(r.outcome == "success" for r in results)


# ── Stats ────────────────────────────────────────────────────

class TestStats:

    @pytest.mark.asyncio
    async def test_stats(self, harness, baseline_scenario):
        harness.register_scenario(baseline_scenario)
        await harness.run(baseline_scenario, _stable_candidate, "stable")
        await harness.run(baseline_scenario, _slow_candidate, "slow")
        stats = harness.stats
        assert stats["scenarios_registered"] == 1
        assert stats["total_runs"] == 2
        assert stats["total_regressions"] == 1
        assert stats["regression_rate"] == 0.5


# ── Output equivalence ───────────────────────────────────────

class TestOutputEquivalence:

    def test_ignores_volatile_fields(self, harness):
        a = {"message": "hi", "timestamp": "2026-01-01"}
        b = {"message": "hi", "timestamp": "2027-01-01"}
        assert harness._outputs_equivalent(a, b)

    def test_detects_real_differences(self, harness):
        a = {"message": "hi"}
        b = {"message": "bye"}
        assert not harness._outputs_equivalent(a, b)


# ── Singleton ────────────────────────────────────────────────

class TestSingleton:

    def test_singleton(self):
        h1 = get_replay_harness()
        h2 = get_replay_harness()
        assert h1 is h2
