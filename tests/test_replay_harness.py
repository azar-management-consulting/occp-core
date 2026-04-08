"""Tests for evaluation.replay_harness (L6 foundation skeleton)."""

from __future__ import annotations

import pytest

from evaluation.replay_harness import (
    ReplayHarness,
    ReplayResult,
    ReplayScenario,
    get_replay_harness,
)


class TestReplayScenario:

    def test_create_scenario(self):
        s = ReplayScenario(
            scenario_id="test-001",
            source_execution_id="abc123",
            workflow_definition={"nodes": []},
            original_outcome="success",
            original_duration_seconds=5.0,
            original_stages=["plan", "gate", "execute", "validate", "ship"],
        )
        assert s.scenario_id == "test-001"
        assert s.original_outcome == "success"


class TestReplayHarness:

    @pytest.fixture
    def harness(self):
        return ReplayHarness()

    def test_register_and_get(self, harness):
        s = ReplayScenario(
            scenario_id="s1",
            source_execution_id="e1",
            workflow_definition={},
            original_outcome="success",
            original_duration_seconds=1.0,
            original_stages=["plan"],
        )
        harness.register_scenario(s)
        assert harness.get_scenario("s1") is s
        assert harness.get_scenario("missing") is None

    def test_list_scenarios(self, harness):
        for i in range(3):
            harness.register_scenario(ReplayScenario(
                scenario_id=f"s{i}",
                source_execution_id=f"e{i}",
                workflow_definition={},
                original_outcome="success",
                original_duration_seconds=0.1,
                original_stages=[],
            ))
        assert len(harness.list_scenarios()) == 3

    @pytest.mark.asyncio
    async def test_run_is_stub_in_v0_10(self, harness):
        s = ReplayScenario(
            scenario_id="stub-test",
            source_execution_id="e1",
            workflow_definition={},
            original_outcome="success",
            original_duration_seconds=1.0,
            original_stages=[],
        )
        harness.register_scenario(s)
        result = await harness.run(s, candidate_ref="feat/test")
        assert result.outcome == "skipped"
        assert "stub" in result.improvements[0].lower()

    def test_record_and_get_results(self, harness):
        s = ReplayScenario(
            scenario_id="s1",
            source_execution_id="e1",
            workflow_definition={},
            original_outcome="success",
            original_duration_seconds=1.0,
            original_stages=[],
        )
        harness.register_scenario(s)
        r1 = ReplayResult(
            scenario_id="s1",
            candidate_ref="sha1",
            outcome="success",
            duration_seconds=1.1,
            delta_seconds=0.1,
            stage_parity=True,
            output_equivalent=True,
        )
        harness.record_result(r1)
        results = harness.get_results("s1")
        assert len(results) == 1
        assert results[0].candidate_ref == "sha1"

    def test_is_regression_property(self, harness):
        r_ok = ReplayResult(
            scenario_id="s1",
            candidate_ref="ok",
            outcome="success",
            duration_seconds=1.0,
            delta_seconds=0.0,
            stage_parity=True,
            output_equivalent=True,
        )
        r_bad = ReplayResult(
            scenario_id="s1",
            candidate_ref="bad",
            outcome="regression",
            duration_seconds=5.0,
            delta_seconds=4.0,
            stage_parity=False,
            output_equivalent=False,
            regressions=["stage parity broken"],
        )
        assert not r_ok.is_regression
        assert r_bad.is_regression


class TestSingleton:

    def test_singleton(self):
        h1 = get_replay_harness()
        h2 = get_replay_harness()
        assert h1 is h2
