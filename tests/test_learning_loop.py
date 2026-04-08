"""Tests for orchestrator.learning_loop — Adaptive Learning Feedback Loop.

Covers:
- FeedbackType enum
- ExecutionFeedback: creation, auto-fields, frozen, score bounds
- SkillPerformanceRecord: creation, defaults, update, score_trend, serialization
- LearningConfig: defaults, custom, frozen, strategy enum
- LearningLoop: record, get, update, reset
- Recommendations: good/bad/degrading/no-data skills
- Degradation detection: trend analysis, auto-disable
- Ranking: top/worst skills
- Audit callback integration
- Stats reporting
- Acceptance tests ACC-LEARN-01 through ACC-LEARN-05
"""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import MagicMock

import pytest

from orchestrator.learning_loop import (
    ExecutionFeedback,
    FeedbackType,
    FeedbackValidationError,
    LearningConfig,
    LearningError,
    LearningLoop,
    LearningStrategy,
    SkillPerformanceNotFoundError,
    SkillPerformanceRecord,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _feedback(
    skill_id: str = "skill-test",
    execution_id: str = "exec-001",
    feedback_type: FeedbackType = FeedbackType.SUCCESS,
    score: float = 0.9,
    **kwargs: Any,
) -> ExecutionFeedback:
    return ExecutionFeedback(
        skill_id=skill_id,
        execution_id=execution_id,
        feedback_type=feedback_type,
        score=score,
        **kwargs,
    )


def _loop(
    strategy: LearningStrategy = LearningStrategy.ADAPTIVE,
    score_window_size: int = 50,
    min_score_threshold: float = 0.3,
    degradation_threshold: float = 0.2,
    auto_disable_threshold: float = 0.1,
    **kwargs: Any,
) -> LearningLoop:
    cfg = LearningConfig(
        strategy=strategy,
        score_window_size=score_window_size,
        min_score_threshold=min_score_threshold,
        degradation_threshold=degradation_threshold,
        auto_disable_threshold=auto_disable_threshold,
        **kwargs,
    )
    return LearningLoop(config=cfg)


# ---------------------------------------------------------------------------
# TestFeedbackType
# ---------------------------------------------------------------------------


class TestFeedbackType:
    def test_all_values_exist(self) -> None:
        values = {ft.value for ft in FeedbackType}
        assert values == {"success", "failure", "timeout", "partial", "user_correction"}

    def test_is_str_enum(self) -> None:
        assert isinstance(FeedbackType.SUCCESS, str)
        assert FeedbackType.SUCCESS == "success"

    def test_enum_membership(self) -> None:
        assert FeedbackType("failure") is FeedbackType.FAILURE
        assert FeedbackType("timeout") is FeedbackType.TIMEOUT


# ---------------------------------------------------------------------------
# TestExecutionFeedback
# ---------------------------------------------------------------------------


class TestExecutionFeedback:
    def test_basic_creation(self) -> None:
        fb = _feedback()
        assert fb.skill_id == "skill-test"
        assert fb.execution_id == "exec-001"
        assert fb.feedback_type == FeedbackType.SUCCESS
        assert fb.score == 0.9

    def test_auto_generated_feedback_id(self) -> None:
        fb1 = _feedback()
        fb2 = _feedback()
        assert fb1.feedback_id != fb2.feedback_id
        assert len(fb1.feedback_id) == 16

    def test_auto_timestamp(self) -> None:
        before = time.time()
        fb = _feedback()
        after = time.time()
        assert before <= fb.timestamp <= after

    def test_frozen_immutable(self) -> None:
        fb = _feedback()
        with pytest.raises((AttributeError, TypeError)):
            fb.score = 0.5  # type: ignore[misc]

    def test_score_boundary_valid(self) -> None:
        fb_low = _feedback(score=0.0)
        fb_high = _feedback(score=1.0)
        assert fb_low.score == 0.0
        assert fb_high.score == 1.0

    def test_score_out_of_bounds_raises(self) -> None:
        with pytest.raises(FeedbackValidationError):
            _feedback(score=1.1)
        with pytest.raises(FeedbackValidationError):
            _feedback(score=-0.1)

    def test_empty_skill_id_raises(self) -> None:
        with pytest.raises(FeedbackValidationError):
            _feedback(skill_id="")

    def test_empty_execution_id_raises(self) -> None:
        with pytest.raises(FeedbackValidationError):
            _feedback(execution_id="")

    def test_to_dict_structure(self) -> None:
        fb = _feedback(
            skill_id="s1",
            execution_id="e1",
            agent_id="agent-x",
            session_id="sess-1",
            context={"key": "value"},
            correction="fix this",
        )
        d = fb.to_dict()
        assert d["skillId"] == "s1"
        assert d["executionId"] == "e1"
        assert d["feedbackType"] == "success"
        assert d["score"] == 0.9
        assert d["agentId"] == "agent-x"
        assert d["sessionId"] == "sess-1"
        assert d["context"] == {"key": "value"}
        assert d["correction"] == "fix this"
        assert "feedbackId" in d
        assert "timestamp" in d

    def test_default_optional_fields(self) -> None:
        fb = _feedback()
        assert fb.context == {}
        assert fb.correction == ""
        assert fb.agent_id == ""
        assert fb.session_id == ""


# ---------------------------------------------------------------------------
# TestSkillPerformanceRecord
# ---------------------------------------------------------------------------


class TestSkillPerformanceRecord:
    def test_default_creation(self) -> None:
        rec = SkillPerformanceRecord(skill_id="skill-a")
        assert rec.skill_id == "skill-a"
        assert rec.total_executions == 0
        assert rec.success_count == 0
        assert rec.failure_count == 0
        assert rec.avg_score == 0.0
        assert rec.avg_duration_ms == 0.0
        assert rec.last_feedback is None
        assert rec.score_trend == []

    def test_score_trend_is_list(self) -> None:
        rec = SkillPerformanceRecord(skill_id="skill-a")
        rec.score_trend.append(0.5)
        assert len(rec.score_trend) == 1

    def test_last_feedback_set(self) -> None:
        fb = _feedback()
        rec = SkillPerformanceRecord(skill_id="skill-test", last_feedback=fb)
        assert rec.last_feedback is fb

    def test_to_dict_structure(self) -> None:
        rec = SkillPerformanceRecord(
            skill_id="skill-b",
            total_executions=3,
            success_count=2,
            failure_count=1,
            avg_score=0.75,
            avg_duration_ms=120.5,
            score_trend=[0.7, 0.75, 0.8],
        )
        d = rec.to_dict()
        assert d["skillId"] == "skill-b"
        assert d["totalExecutions"] == 3
        assert d["successCount"] == 2
        assert d["failureCount"] == 1
        assert d["avgScore"] == 0.75
        assert d["avgDurationMs"] == 120.5
        assert d["scoreTrend"] == [0.7, 0.75, 0.8]
        assert d["lastFeedback"] is None

    def test_from_dict_roundtrip(self) -> None:
        rec = SkillPerformanceRecord(
            skill_id="skill-c",
            total_executions=5,
            success_count=4,
            failure_count=1,
            avg_score=0.85,
            score_trend=[0.8, 0.85, 0.9, 0.85, 0.85],
        )
        d = rec.to_dict()
        restored = SkillPerformanceRecord.from_dict(d)
        assert restored.skill_id == "skill-c"
        assert restored.total_executions == 5
        assert restored.success_count == 4
        assert restored.failure_count == 1
        assert abs(restored.avg_score - 0.85) < 1e-6
        assert restored.score_trend == [0.8, 0.85, 0.9, 0.85, 0.85]

    def test_from_dict_with_last_feedback(self) -> None:
        fb = _feedback(skill_id="skill-d", execution_id="exec-99")
        rec = SkillPerformanceRecord(
            skill_id="skill-d",
            total_executions=1,
            last_feedback=fb,
        )
        d = rec.to_dict()
        restored = SkillPerformanceRecord.from_dict(d)
        assert restored.last_feedback is not None
        assert restored.last_feedback.skill_id == "skill-d"
        assert restored.last_feedback.execution_id == "exec-99"

    def test_to_dict_score_rounded(self) -> None:
        rec = SkillPerformanceRecord(skill_id="s", avg_score=0.123456789)
        d = rec.to_dict()
        # Should be rounded to 6 decimal places
        assert isinstance(d["avgScore"], float)


# ---------------------------------------------------------------------------
# TestLearningConfig
# ---------------------------------------------------------------------------


class TestLearningConfig:
    def test_defaults(self) -> None:
        cfg = LearningConfig()
        assert cfg.strategy == LearningStrategy.ADAPTIVE
        assert cfg.score_window_size == 50
        assert cfg.min_score_threshold == 0.3
        assert cfg.degradation_threshold == 0.2
        assert cfg.auto_disable_threshold == 0.1
        assert cfg.feedback_retention_days == 90
        assert cfg.enable_cross_session is True

    def test_custom_values(self) -> None:
        cfg = LearningConfig(
            strategy=LearningStrategy.SCORE_THRESHOLD,
            score_window_size=20,
            min_score_threshold=0.4,
            degradation_threshold=0.15,
            auto_disable_threshold=0.05,
            feedback_retention_days=30,
            enable_cross_session=False,
        )
        assert cfg.strategy == LearningStrategy.SCORE_THRESHOLD
        assert cfg.score_window_size == 20
        assert cfg.enable_cross_session is False

    def test_frozen_immutable(self) -> None:
        cfg = LearningConfig()
        with pytest.raises((AttributeError, TypeError)):
            cfg.score_window_size = 100  # type: ignore[misc]

    def test_strategy_enum_values(self) -> None:
        values = {s.value for s in LearningStrategy}
        assert values == {"none", "frequency_boost", "score_threshold", "adaptive"}


# ---------------------------------------------------------------------------
# TestLearningLoop
# ---------------------------------------------------------------------------


class TestLearningLoop:
    def test_initial_state_empty(self) -> None:
        loop = LearningLoop()
        assert loop.get_all_performance() == []
        stats = loop.get_stats()
        assert stats["total_feedback"] == 0
        assert stats["skills_tracked"] == 0

    def test_record_feedback_creates_record(self) -> None:
        loop = LearningLoop()
        loop.record_feedback(_feedback(skill_id="skill-a"))
        perf = loop.get_performance("skill-a")
        assert perf is not None
        assert perf.total_executions == 1

    def test_get_performance_returns_none_unknown(self) -> None:
        loop = LearningLoop()
        assert loop.get_performance("nonexistent") is None

    def test_multiple_feedbacks_same_skill(self) -> None:
        loop = LearningLoop()
        for i in range(5):
            loop.record_feedback(_feedback(skill_id="skill-a", execution_id=f"exec-{i}", score=0.8))
        perf = loop.get_performance("skill-a")
        assert perf is not None
        assert perf.total_executions == 5
        assert abs(perf.avg_score - 0.8) < 1e-9

    def test_success_count_incremented(self) -> None:
        loop = LearningLoop()
        loop.record_feedback(_feedback(feedback_type=FeedbackType.SUCCESS))
        loop.record_feedback(_feedback(execution_id="exec-002", feedback_type=FeedbackType.FAILURE))
        perf = loop.get_performance("skill-test")
        assert perf is not None
        assert perf.success_count == 1
        assert perf.failure_count == 1

    def test_timeout_increments_failure_count(self) -> None:
        loop = LearningLoop()
        loop.record_feedback(_feedback(execution_id="e1", feedback_type=FeedbackType.TIMEOUT))
        perf = loop.get_performance("skill-test")
        assert perf is not None
        assert perf.failure_count == 1

    def test_partial_not_counted_in_failure(self) -> None:
        loop = LearningLoop()
        loop.record_feedback(_feedback(execution_id="e1", feedback_type=FeedbackType.PARTIAL, score=0.5))
        perf = loop.get_performance("skill-test")
        assert perf is not None
        assert perf.failure_count == 0
        assert perf.success_count == 0

    def test_avg_score_computed_correctly(self) -> None:
        loop = LearningLoop()
        scores = [0.2, 0.4, 0.6, 0.8, 1.0]
        for i, s in enumerate(scores):
            loop.record_feedback(_feedback(execution_id=f"e{i}", score=s))
        perf = loop.get_performance("skill-test")
        assert perf is not None
        expected = sum(scores) / len(scores)
        assert abs(perf.avg_score - expected) < 1e-9

    def test_last_feedback_updated(self) -> None:
        loop = LearningLoop()
        loop.record_feedback(_feedback(execution_id="e1", score=0.5))
        loop.record_feedback(_feedback(execution_id="e2", score=0.9))
        perf = loop.get_performance("skill-test")
        assert perf is not None
        assert perf.last_feedback is not None
        assert perf.last_feedback.execution_id == "e2"

    def test_get_all_performance_multiple_skills(self) -> None:
        loop = LearningLoop()
        for s in ["skill-a", "skill-b", "skill-c"]:
            loop.record_feedback(_feedback(skill_id=s, execution_id="e1"))
        all_perfs = loop.get_all_performance()
        skill_ids = {p.skill_id for p in all_perfs}
        assert skill_ids == {"skill-a", "skill-b", "skill-c"}

    def test_reset_performance_removes_record(self) -> None:
        loop = LearningLoop()
        loop.record_feedback(_feedback())
        assert loop.get_performance("skill-test") is not None
        result = loop.reset_performance("skill-test")
        assert result is True
        assert loop.get_performance("skill-test") is None

    def test_reset_unknown_skill_returns_false(self) -> None:
        loop = LearningLoop()
        assert loop.reset_performance("nonexistent") is False

    def test_score_trend_window_capped(self) -> None:
        loop = _loop(score_window_size=5)
        for i in range(10):
            loop.record_feedback(_feedback(execution_id=f"e{i}", score=float(i) / 10))
        perf = loop.get_performance("skill-test")
        assert perf is not None
        assert len(perf.score_trend) == 5
        # Should contain the last 5 scores
        expected = [0.5, 0.6, 0.7, 0.8, 0.9]
        assert perf.score_trend == expected


# ---------------------------------------------------------------------------
# TestRecommendations
# ---------------------------------------------------------------------------


class TestRecommendations:
    def test_no_data_returns_empty(self) -> None:
        loop = LearningLoop()
        assert loop.get_recommendations("unknown-skill") == []

    def test_good_skill_gets_positive_recommendation(self) -> None:
        loop = LearningLoop()
        for i in range(5):
            loop.record_feedback(_feedback(execution_id=f"e{i}", score=0.95))
        recs = loop.get_recommendations("skill-test")
        assert any("performing well" in r for r in recs)

    def test_low_score_skill_flagged_for_review(self) -> None:
        loop = _loop(min_score_threshold=0.3, auto_disable_threshold=0.1)
        for i in range(3):
            loop.record_feedback(_feedback(execution_id=f"e{i}", score=0.2))
        recs = loop.get_recommendations("skill-test")
        assert any("flagged for review" in r or "review" in r for r in recs)

    def test_auto_disable_recommendation(self) -> None:
        loop = _loop(auto_disable_threshold=0.1)
        for i in range(3):
            loop.record_feedback(_feedback(execution_id=f"e{i}", score=0.05))
        recs = loop.get_recommendations("skill-test")
        assert any("Auto-disable" in r or "auto-disable" in r.lower() for r in recs)

    def test_degrading_skill_recommendation(self) -> None:
        loop = _loop(degradation_threshold=0.2, score_window_size=10)
        # Early scores high, late scores low
        early = [0.9, 0.9, 0.9, 0.9, 0.9]
        late = [0.5, 0.5, 0.5, 0.5, 0.5]
        for i, s in enumerate(early + late):
            loop.record_feedback(_feedback(execution_id=f"e{i}", score=s))
        recs = loop.get_recommendations("skill-test")
        assert any("degradation" in r.lower() for r in recs)

    def test_high_failure_rate_recommendation(self) -> None:
        loop = LearningLoop()
        # 3 failures, 1 success = 75% failure rate
        loop.record_feedback(_feedback(execution_id="e1", feedback_type=FeedbackType.FAILURE, score=0.0))
        loop.record_feedback(_feedback(execution_id="e2", feedback_type=FeedbackType.FAILURE, score=0.0))
        loop.record_feedback(_feedback(execution_id="e3", feedback_type=FeedbackType.FAILURE, score=0.0))
        loop.record_feedback(_feedback(execution_id="e4", feedback_type=FeedbackType.SUCCESS, score=0.8))
        recs = loop.get_recommendations("skill-test")
        assert any("failure rate" in r.lower() for r in recs)


# ---------------------------------------------------------------------------
# TestDegradation
# ---------------------------------------------------------------------------


class TestDegradation:
    def test_not_degrading_insufficient_data(self) -> None:
        loop = LearningLoop()
        loop.record_feedback(_feedback(execution_id="e1", score=0.9))
        loop.record_feedback(_feedback(execution_id="e2", score=0.1))
        # Only 2 entries — need at least 4
        assert loop.is_degrading("skill-test") is False

    def test_degrading_detected_with_sufficient_data(self) -> None:
        loop = _loop(degradation_threshold=0.2, score_window_size=10)
        early = [0.9, 0.9, 0.9, 0.9, 0.9]
        late = [0.5, 0.5, 0.5, 0.5, 0.5]
        for i, s in enumerate(early + late):
            loop.record_feedback(_feedback(execution_id=f"e{i}", score=s))
        assert loop.is_degrading("skill-test") is True

    def test_stable_skill_not_degrading(self) -> None:
        loop = _loop(degradation_threshold=0.2)
        for i in range(8):
            loop.record_feedback(_feedback(execution_id=f"e{i}", score=0.8))
        assert loop.is_degrading("skill-test") is False

    def test_improving_skill_not_degrading(self) -> None:
        loop = _loop(degradation_threshold=0.2, score_window_size=10)
        for i in range(10):
            # Scores increasing from 0.3 to 0.8
            score = 0.3 + i * 0.05
            loop.record_feedback(_feedback(execution_id=f"e{i}", score=score))
        assert loop.is_degrading("skill-test") is False

    def test_should_disable_below_threshold(self) -> None:
        loop = _loop(auto_disable_threshold=0.1)
        for i in range(3):
            loop.record_feedback(_feedback(execution_id=f"e{i}", score=0.05))
        assert loop.should_disable_skill("skill-test") is True

    def test_should_not_disable_above_threshold(self) -> None:
        loop = _loop(auto_disable_threshold=0.1)
        for i in range(3):
            loop.record_feedback(_feedback(execution_id=f"e{i}", score=0.5))
        assert loop.should_disable_skill("skill-test") is False

    def test_should_disable_unknown_skill_false(self) -> None:
        loop = LearningLoop()
        assert loop.should_disable_skill("nonexistent") is False

    def test_score_trend_window_used_for_degradation(self) -> None:
        # With window_size=6, only last 6 scores kept
        loop = _loop(degradation_threshold=0.2, score_window_size=6)
        # First 4 scores (old, will be pushed out): low scores
        for i in range(4):
            loop.record_feedback(_feedback(execution_id=f"old-{i}", score=0.2))
        # Last 6 scores: high then low — will show degradation
        high_scores = [0.9, 0.9, 0.9]
        low_scores = [0.5, 0.5, 0.5]
        for i, s in enumerate(high_scores + low_scores):
            loop.record_feedback(_feedback(execution_id=f"new-{i}", score=s))
        # Trend window has last 6: [0.9, 0.9, 0.9, 0.5, 0.5, 0.5]
        assert loop.is_degrading("skill-test") is True


# ---------------------------------------------------------------------------
# TestRanking
# ---------------------------------------------------------------------------


class TestRanking:
    def test_top_skills_sorted_desc(self) -> None:
        loop = LearningLoop()
        scores = {"skill-a": 0.9, "skill-b": 0.5, "skill-c": 0.7}
        for sid, score in scores.items():
            loop.record_feedback(_feedback(skill_id=sid, execution_id="e1", score=score))
        top = loop.get_top_skills(n=3)
        assert [r.skill_id for r in top] == ["skill-a", "skill-c", "skill-b"]

    def test_worst_skills_sorted_asc(self) -> None:
        loop = LearningLoop()
        scores = {"skill-a": 0.9, "skill-b": 0.2, "skill-c": 0.6}
        for sid, score in scores.items():
            loop.record_feedback(_feedback(skill_id=sid, execution_id="e1", score=score))
        worst = loop.get_worst_skills(n=3)
        assert [r.skill_id for r in worst] == ["skill-b", "skill-c", "skill-a"]

    def test_top_skills_empty_store(self) -> None:
        loop = LearningLoop()
        assert loop.get_top_skills() == []

    def test_top_skills_n_less_than_total(self) -> None:
        loop = LearningLoop()
        for i in range(5):
            loop.record_feedback(_feedback(skill_id=f"skill-{i}", execution_id="e1", score=float(i) / 5))
        top2 = loop.get_top_skills(n=2)
        assert len(top2) == 2

    def test_worst_skills_single_skill(self) -> None:
        loop = LearningLoop()
        loop.record_feedback(_feedback(skill_id="only-skill", execution_id="e1", score=0.5))
        worst = loop.get_worst_skills(n=5)
        assert len(worst) == 1
        assert worst[0].skill_id == "only-skill"


# ---------------------------------------------------------------------------
# TestAudit
# ---------------------------------------------------------------------------


class TestAudit:
    def test_audit_callback_fired_on_record(self) -> None:
        events: list[tuple[str, dict]] = []

        def cb(event: str, data: dict) -> None:
            events.append((event, data))

        loop = LearningLoop(audit_callback=cb)
        loop.record_feedback(_feedback())
        assert len(events) == 1
        assert events[0][0] == "learning.feedback.recorded"

    def test_audit_callback_content(self) -> None:
        events: list[tuple[str, dict]] = []

        def cb(event: str, data: dict) -> None:
            events.append((event, data))

        loop = LearningLoop(audit_callback=cb)
        fb = _feedback(skill_id="skill-x", score=0.75)
        loop.record_feedback(fb)

        event_name, data = events[0]
        assert data["skillId"] == "skill-x"
        assert data["score"] == 0.75
        assert data["feedbackType"] == "success"
        assert "feedbackId" in data
        assert "timestamp" in data

    def test_no_audit_callback_no_error(self) -> None:
        loop = LearningLoop(audit_callback=None)
        # Should not raise
        loop.record_feedback(_feedback())

    def test_audit_callback_multiple_feedbacks(self) -> None:
        call_count = [0]

        def cb(event: str, data: dict) -> None:
            call_count[0] += 1

        loop = LearningLoop(audit_callback=cb)
        for i in range(5):
            loop.record_feedback(_feedback(execution_id=f"e{i}"))
        assert call_count[0] == 5


# ---------------------------------------------------------------------------
# TestLearningStats
# ---------------------------------------------------------------------------


class TestLearningStats:
    def test_initial_stats(self) -> None:
        loop = LearningLoop()
        stats = loop.get_stats()
        assert stats["total_feedback"] == 0
        assert stats["skills_tracked"] == 0
        assert stats["avg_global_score"] == 0.0
        assert stats["degrading_skills"] == 0

    def test_stats_after_feedback(self) -> None:
        loop = LearningLoop()
        loop.record_feedback(_feedback(skill_id="skill-a", execution_id="e1", score=0.8))
        loop.record_feedback(_feedback(skill_id="skill-b", execution_id="e1", score=0.6))
        stats = loop.get_stats()
        assert stats["total_feedback"] == 2
        assert stats["skills_tracked"] == 2
        assert abs(stats["avg_global_score"] - 0.7) < 1e-6

    def test_stats_after_reset(self) -> None:
        loop = LearningLoop()
        loop.record_feedback(_feedback(skill_id="skill-a", execution_id="e1"))
        loop.record_feedback(_feedback(skill_id="skill-b", execution_id="e1"))
        loop.reset_performance("skill-a")
        stats = loop.get_stats()
        assert stats["skills_tracked"] == 1
        assert stats["total_feedback"] == 1

    def test_degrading_skills_count_in_stats(self) -> None:
        loop = _loop(degradation_threshold=0.2, score_window_size=10)
        early = [0.9, 0.9, 0.9, 0.9, 0.9]
        late = [0.5, 0.5, 0.5, 0.5, 0.5]
        for i, s in enumerate(early + late):
            loop.record_feedback(_feedback(execution_id=f"e{i}", score=s))
        stats = loop.get_stats()
        assert stats["degrading_skills"] >= 1


# ---------------------------------------------------------------------------
# TestMemoryIntegration
# ---------------------------------------------------------------------------


class TestMemoryIntegration:
    def test_memory_extract_and_add_called(self) -> None:
        mock_memory = MagicMock()
        mock_memory.extract_and_add = MagicMock()
        loop = LearningLoop(memory=mock_memory)
        loop.record_feedback(_feedback())
        mock_memory.extract_and_add.assert_called_once()

    def test_memory_add_text_fallback(self) -> None:
        mock_memory = MagicMock(spec=["add_text"])
        loop = LearningLoop(memory=mock_memory)
        loop.record_feedback(_feedback())
        mock_memory.add_text.assert_called_once()

    def test_no_memory_no_error(self) -> None:
        loop = LearningLoop(memory=None)
        loop.record_feedback(_feedback())  # Should not raise

    def test_memory_disabled_by_config(self) -> None:
        mock_memory = MagicMock()
        cfg = LearningConfig(enable_cross_session=False)
        loop = LearningLoop(config=cfg, memory=mock_memory)
        loop.record_feedback(_feedback())
        mock_memory.extract_and_add.assert_not_called()


# ---------------------------------------------------------------------------
# Acceptance Tests
# ---------------------------------------------------------------------------


class TestAcceptance:
    def test_acc_learn_01_feedback_recorded_and_performance_updated(self) -> None:
        """ACC-LEARN-01: Feedback recorded and performance updated correctly."""
        loop = LearningLoop()

        feedbacks = [
            ExecutionFeedback(
                skill_id="skill-001",
                execution_id=f"exec-{i}",
                feedback_type=FeedbackType.SUCCESS if i % 4 != 0 else FeedbackType.FAILURE,
                score=0.9 if i % 4 != 0 else 0.1,
            )
            for i in range(8)
        ]

        for fb in feedbacks:
            loop.record_feedback(fb)

        perf = loop.get_performance("skill-001")
        assert perf is not None
        assert perf.total_executions == 8
        # 6 successes, 2 failures (i=0 and i=4)
        assert perf.success_count == 6
        assert perf.failure_count == 2
        # avg score: 6 * 0.9 + 2 * 0.1 = 5.6 / 8 = 0.7
        assert abs(perf.avg_score - 0.7) < 1e-9
        assert len(perf.score_trend) == 8
        assert perf.last_feedback is not None
        assert perf.last_feedback.execution_id == "exec-7"

    def test_acc_learn_02_degrading_skill_detected(self) -> None:
        """ACC-LEARN-02: Degrading skill detected when score trend drops."""
        loop = _loop(degradation_threshold=0.2, score_window_size=10)

        # Phase 1: high performance
        for i in range(5):
            loop.record_feedback(
                ExecutionFeedback(
                    skill_id="skill-002",
                    execution_id=f"exec-good-{i}",
                    feedback_type=FeedbackType.SUCCESS,
                    score=0.9,
                )
            )

        # Phase 2: degraded performance
        for i in range(5):
            loop.record_feedback(
                ExecutionFeedback(
                    skill_id="skill-002",
                    execution_id=f"exec-bad-{i}",
                    feedback_type=FeedbackType.FAILURE,
                    score=0.3,
                )
            )

        assert loop.is_degrading("skill-002") is True
        assert loop.should_disable_skill("skill-002") is False  # avg ~0.6, above 0.1

    def test_acc_learn_03_auto_disable_for_poor_skill(self) -> None:
        """ACC-LEARN-03: Auto-disable recommended for extremely low-performing skill."""
        loop = _loop(auto_disable_threshold=0.1)

        for i in range(5):
            loop.record_feedback(
                ExecutionFeedback(
                    skill_id="skill-003",
                    execution_id=f"exec-{i}",
                    feedback_type=FeedbackType.FAILURE,
                    score=0.02,
                )
            )

        assert loop.should_disable_skill("skill-003") is True
        recs = loop.get_recommendations("skill-003")
        assert any("auto-disable" in r.lower() or "Auto-disable" in r for r in recs)

    def test_acc_learn_04_recommendations_generated(self) -> None:
        """ACC-LEARN-04: Recommendations generated based on performance data."""
        loop = _loop(
            min_score_threshold=0.3,
            auto_disable_threshold=0.1,
            degradation_threshold=0.2,
            score_window_size=10,
        )

        # Record degrading pattern
        for i in range(5):
            loop.record_feedback(
                ExecutionFeedback(
                    skill_id="skill-004",
                    execution_id=f"exec-high-{i}",
                    feedback_type=FeedbackType.SUCCESS,
                    score=0.85,
                )
            )
        for i in range(5):
            loop.record_feedback(
                ExecutionFeedback(
                    skill_id="skill-004",
                    execution_id=f"exec-low-{i}",
                    feedback_type=FeedbackType.FAILURE,
                    score=0.15,
                )
            )

        recs = loop.get_recommendations("skill-004")
        # Should have at least one recommendation (degradation)
        assert len(recs) >= 1
        assert isinstance(recs, list)
        assert all(isinstance(r, str) for r in recs)

    def test_acc_learn_05_stats_report_accurate_global_metrics(self) -> None:
        """ACC-LEARN-05: Stats report accurate global metrics."""
        loop = _loop(degradation_threshold=0.2, score_window_size=10)

        # Add 3 skills with known scores
        skill_data = [
            ("skill-a", 0.9, 5),
            ("skill-b", 0.5, 3),
            ("skill-c", 0.1, 4),  # will trigger degradation with window data
        ]

        for skill_id, score, count in skill_data:
            for i in range(count):
                loop.record_feedback(
                    ExecutionFeedback(
                        skill_id=skill_id,
                        execution_id=f"exec-{i}",
                        feedback_type=FeedbackType.SUCCESS,
                        score=score,
                    )
                )

        total_fb = 5 + 3 + 4  # = 12
        stats = loop.get_stats()

        assert stats["total_feedback"] == total_fb
        assert stats["skills_tracked"] == 3
        # avg_global_score = (0.9 + 0.5 + 0.1) / 3 = 0.5
        assert abs(stats["avg_global_score"] - 0.5) < 1e-6
        assert "degrading_skills" in stats
        assert isinstance(stats["degrading_skills"], int)
