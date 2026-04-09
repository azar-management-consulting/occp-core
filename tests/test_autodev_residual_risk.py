"""Tests for autodev.residual_risk."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from autodev.residual_risk import (
    ResidualRiskCalculator,
    RiskAssessment,
    get_residual_risk_calculator,
)
from autodev.verification_gate import StageResult, VerificationReport
from evaluation.self_modifier import SelfModifier
import pathlib


@pytest.fixture
def calc():
    return ResidualRiskCalculator()


def _passing_report():
    report = VerificationReport(
        run_id="r1",
        worktree_path=pathlib.Path("/tmp/test"),
        stages=[
            StageResult(stage="lint", verdict="pass", duration_seconds=1.0),
            StageResult(stage="targeted_test", verdict="pass", duration_seconds=5.0),
            StageResult(stage="regression", verdict="pass", duration_seconds=10.0),
        ],
    )
    return report


def _failing_report():
    report = VerificationReport(
        run_id="r1",
        worktree_path=pathlib.Path("/tmp/test"),
        stages=[
            StageResult(stage="lint", verdict="fail", duration_seconds=1.0),
        ],
    )
    return report


class TestVerificationFailure:

    def test_failed_verification_is_critical(self, calc):
        result = calc.assess(
            verification=_failing_report(),
            affected_paths=["architecture/services.yaml"],
            diff_size_lines=10,
        )
        assert result.score >= 8.0
        assert result.recommendation == "reject"


class TestGovernanceBoundary:

    def test_immutable_path_is_critical(self, calc):
        result = calc.assess(
            verification=_passing_report(),
            affected_paths=["security/agent_allowlist.py"],
            diff_size_lines=5,
        )
        assert result.score >= 8.0
        assert result.recommendation == "reject"
        factor_names = [f.name for f in result.factors]
        assert "immutable_path" in factor_names

    def test_human_review_path_is_medium(self, calc):
        result = calc.assess(
            verification=_passing_report(),
            affected_paths=["orchestrator/pipeline.py"],
            diff_size_lines=10,
        )
        assert result.score >= 2.0
        assert result.recommendation == "review"


class TestSafeChanges:

    def test_small_autonomous_safe_is_low(self, calc):
        result = calc.assess(
            verification=_passing_report(),
            affected_paths=["architecture/services.yaml"],
            diff_size_lines=5,
        )
        assert result.score < 2.0
        assert result.risk_level == "low"
        assert result.recommendation == "auto_merge"

    def test_tests_only_is_low(self, calc):
        result = calc.assess(
            verification=_passing_report(),
            affected_paths=["tests/test_example.py"],
            diff_size_lines=20,
        )
        assert result.score < 2.0


class TestSizeAndCount:

    def test_large_diff_adds_risk(self, calc):
        small = calc.assess(
            verification=_passing_report(),
            affected_paths=["architecture/services.yaml"],
            diff_size_lines=50,
        )
        large = calc.assess(
            verification=_passing_report(),
            affected_paths=["architecture/services.yaml"],
            diff_size_lines=500,
        )
        assert large.score > small.score

    def test_multi_file_adds_risk(self, calc):
        few = calc.assess(
            verification=_passing_report(),
            affected_paths=["architecture/services.yaml"],
            diff_size_lines=10,
        )
        many = calc.assess(
            verification=_passing_report(),
            affected_paths=[
                f"architecture/services_{i}.yaml" for i in range(10)
            ],
            diff_size_lines=10,
        )
        assert many.score > few.score


class TestSerialization:

    def test_to_dict(self, calc):
        result = calc.assess(
            verification=_passing_report(),
            affected_paths=["architecture/services.yaml"],
            diff_size_lines=5,
        )
        d = result.to_dict()
        assert "score" in d
        assert "risk_level" in d
        assert "recommendation" in d
        assert "factors" in d


class TestSingleton:

    def test_singleton(self):
        c1 = get_residual_risk_calculator()
        c2 = get_residual_risk_calculator()
        assert c1 is c2
