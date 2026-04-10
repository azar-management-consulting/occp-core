"""Tests for autodev.rate_budget_tracker."""

from __future__ import annotations

import pytest

from autodev.rate_budget_tracker import (
    BudgetExhausted,
    BudgetLimits,
    RateBudgetTracker,
    get_rate_budget_tracker,
)


@pytest.fixture
def strict_tracker():
    return RateBudgetTracker(
        limits=BudgetLimits(
            max_runs_per_day=2,
            max_low_risk_merges_per_day=1,
            max_medium_plus_proposals_per_day=1,
            max_compute_seconds_per_day=60.0,
        )
    )


class TestRunLimit:

    def test_can_start_within_limit(self, strict_tracker):
        strict_tracker.check_can_start_run()
        strict_tracker.record_run_started()
        strict_tracker.check_can_start_run()  # still OK

    def test_exhausts_run_limit(self, strict_tracker):
        strict_tracker.record_run_started()
        strict_tracker.record_run_started()
        with pytest.raises(BudgetExhausted) as exc:
            strict_tracker.check_can_start_run()
        assert "max_runs_per_day" in str(exc.value)


class TestMergeLimit:

    def test_low_risk_merge_limit(self, strict_tracker):
        strict_tracker.check_can_auto_merge_low()
        strict_tracker.record_low_risk_merge()
        with pytest.raises(BudgetExhausted):
            strict_tracker.check_can_auto_merge_low()


class TestMediumPlusLimit:

    def test_medium_plus_limit(self, strict_tracker):
        strict_tracker.check_can_submit_medium_plus()
        strict_tracker.record_medium_plus_proposal()
        with pytest.raises(BudgetExhausted):
            strict_tracker.check_can_submit_medium_plus()


class TestComputeBudget:

    def test_compute_within_budget(self, strict_tracker):
        strict_tracker.check_compute_available(30.0)
        strict_tracker.record_compute_seconds(30.0)
        strict_tracker.check_compute_available(20.0)

    def test_compute_exhausted(self, strict_tracker):
        strict_tracker.record_compute_seconds(55.0)
        with pytest.raises(BudgetExhausted):
            strict_tracker.check_compute_available(20.0)  # 55+20=75 > 60


class TestSnapshot:

    def test_snapshot_structure(self, strict_tracker):
        strict_tracker.record_run_started()
        snap = strict_tracker.snapshot()
        assert "date" in snap
        assert "usage" in snap
        assert "limits" in snap
        assert "remaining" in snap
        assert snap["usage"]["runs_started"] == 1
        assert snap["remaining"]["runs"] == 1  # 2 limit - 1 used

    def test_reset(self, strict_tracker):
        strict_tracker.record_run_started()
        strict_tracker.record_run_started()
        strict_tracker.reset()
        snap = strict_tracker.snapshot()
        assert snap["usage"]["runs_started"] == 0


class TestSingleton:

    def test_singleton(self):
        t1 = get_rate_budget_tracker()
        t2 = get_rate_budget_tracker()
        assert t1 is t2
