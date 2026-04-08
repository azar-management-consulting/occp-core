"""Tests for Quality Gate and Feedback Loop.

Covers:
- QualityCheck dataclass and serialization
- QualityGate automated checks per agent type
- Cross-review routing and handler delegation
- Brain final review (pass/fail/override)
- Revision detection and instruction generation
- Full quality gate pipeline
- FeedbackLoop recording and scoring
- Degradation detection
- Action recommendations
- Pipeline integration with quality gate
- API endpoint coverage
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from orchestrator.quality_gate import QualityCheck, QualityGate
from orchestrator.feedback_loop import AgentFeedback, FeedbackLoop


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def gate() -> QualityGate:
    return QualityGate()


@pytest.fixture
def feedback_loop() -> FeedbackLoop:
    return FeedbackLoop()


def _make_output(**extra: Any) -> dict[str, Any]:
    defaults = {
        "content": "This is a valid output with enough content to pass minimum length checks easily.",
        "result": "ok",
    }
    defaults.update(extra)
    return defaults


# ===========================================================================
# 1. QualityCheck dataclass
# ===========================================================================


class TestQualityCheck:
    def test_quality_check_creation(self) -> None:
        qc = QualityCheck(
            check_id="chk-001",
            agent_id="eng-core",
            task_id="task-001",
            check_type="automated",
            status="passed",
            score=1.0,
            feedback="All good",
            reviewer="automated",
        )
        assert qc.check_id == "chk-001"
        assert qc.agent_id == "eng-core"
        assert qc.status == "passed"
        assert qc.score == 1.0

    def test_quality_check_to_dict(self) -> None:
        qc = QualityCheck(
            check_id="chk-002",
            agent_id="wp-web",
            task_id="task-002",
            check_type="cross_review",
            status="failed",
            score=0.3,
            feedback="Needs work",
            reviewer="eng-core",
        )
        d = qc.to_dict()
        assert d["check_id"] == "chk-002"
        assert d["check_type"] == "cross_review"
        assert d["score"] == 0.3
        assert "timestamp" in d


# ===========================================================================
# 2. Automated checks — per agent type
# ===========================================================================


class TestAutomatedChecks:
    @pytest.mark.asyncio
    async def test_eng_core_checks_pass(self, gate: QualityGate) -> None:
        output = _make_output(content="function hello() { return 42; }")
        checks = await gate.run_automated_checks("eng-core", "t1", output)
        # eng-core has 4 checks: syntax_valid, tests_pass, no_secrets, lint_clean
        assert len(checks) == 4
        assert all(c.check_type == "automated" for c in checks)
        assert all(c.agent_id == "eng-core" for c in checks)

    @pytest.mark.asyncio
    async def test_no_secrets_fails_on_api_key(self, gate: QualityGate) -> None:
        output = _make_output(content='api_key = "sk-abcdefghijklmnopqrstuvwxyz123456"')
        checks = await gate.run_automated_checks("eng-core", "t2", output)
        secret_check = [c for c in checks if "secret" in c.feedback.lower() or "no secrets" in c.feedback.lower()]
        failed = [c for c in secret_check if c.status == "failed"]
        assert len(failed) >= 1

    @pytest.mark.asyncio
    async def test_no_destructive_commands(self, gate: QualityGate) -> None:
        output = _make_output(content="rm -rf / && echo done")
        checks = await gate.run_automated_checks("infra-ops", "t3", output)
        destructive = [c for c in checks if c.status == "failed" and "destructive" in c.feedback.lower()]
        assert len(destructive) >= 1

    @pytest.mark.asyncio
    async def test_content_forge_placeholder_fail(self, gate: QualityGate) -> None:
        output = _make_output(content="This is [PLACEHOLDER] text that needs to be replaced")
        checks = await gate.run_automated_checks("content-forge", "t4", output)
        placeholder = [c for c in checks if c.status == "failed" and "placeholder" in c.feedback.lower()]
        assert len(placeholder) >= 1

    @pytest.mark.asyncio
    async def test_social_growth_cta_missing(self, gate: QualityGate) -> None:
        output = _make_output(content="Here is some generic text about our product with no action items at all")
        checks = await gate.run_automated_checks("social-growth", "t5", output)
        cta = [c for c in checks if c.status == "failed" and "call-to-action" in c.feedback.lower()]
        assert len(cta) >= 1

    @pytest.mark.asyncio
    async def test_social_growth_cta_present(self, gate: QualityGate) -> None:
        output = _make_output(content="Click here to sign up for our amazing product today!")
        checks = await gate.run_automated_checks("social-growth", "t6", output)
        cta = [c for c in checks if "call-to-action" in c.feedback.lower() or "CTA" in c.feedback]
        passed_cta = [c for c in cta if c.status == "passed"]
        assert len(passed_cta) >= 1

    @pytest.mark.asyncio
    async def test_intel_research_no_sources(self, gate: QualityGate) -> None:
        output = _make_output(content="The market is growing rapidly but I have no evidence for this claim.")
        checks = await gate.run_automated_checks("intel-research", "t7", output)
        source_fail = [c for c in checks if c.status == "failed" and "source" in c.feedback.lower()]
        assert len(source_fail) >= 1

    @pytest.mark.asyncio
    async def test_intel_research_hallucination_marker(self, gate: QualityGate) -> None:
        output = _make_output(content="As an AI language model, I cannot actually browse the internet.")
        checks = await gate.run_automated_checks("intel-research", "t8", output)
        hall = [c for c in checks if c.status == "failed" and "hallucination" in c.feedback.lower()]
        assert len(hall) >= 1

    @pytest.mark.asyncio
    async def test_biz_strategy_missing_pricing(self, gate: QualityGate) -> None:
        output = _make_output(content="We propose a comprehensive strategy with great ROI and value.")
        checks = await gate.run_automated_checks("biz-strategy", "t9", output)
        pricing = [c for c in checks if c.status == "failed" and "pricing" in c.feedback.lower()]
        assert len(pricing) >= 1

    @pytest.mark.asyncio
    async def test_unknown_agent_no_checks(self, gate: QualityGate) -> None:
        output = _make_output()
        checks = await gate.run_automated_checks("unknown-agent", "t10", output)
        assert checks == []

    @pytest.mark.asyncio
    async def test_wp_standards_raw_query(self, gate: QualityGate) -> None:
        output = _make_output(content='$wpdb->query("SELECT * FROM users WHERE id = $id")')
        checks = await gate.run_automated_checks("wp-web", "t11", output)
        wp_fail = [c for c in checks if c.status == "failed" and "prepare" in c.feedback.lower()]
        assert len(wp_fail) >= 1


# ===========================================================================
# 3. Cross-review routing
# ===========================================================================


class TestCrossReview:
    @pytest.mark.asyncio
    async def test_cross_review_routing(self, gate: QualityGate) -> None:
        result = await gate.request_cross_review("eng-core", "t1", _make_output())
        assert result is not None
        assert result.reviewer == "wp-web"
        assert result.check_type == "cross_review"

    @pytest.mark.asyncio
    async def test_cross_review_unknown_agent(self, gate: QualityGate) -> None:
        result = await gate.request_cross_review("unknown", "t1", _make_output())
        assert result is None

    @pytest.mark.asyncio
    async def test_cross_review_with_handler(self) -> None:
        handler_check = QualityCheck(
            check_id="cr-001",
            agent_id="eng-core",
            task_id="t1",
            check_type="cross_review",
            status="passed",
            score=0.9,
            feedback="Looks good",
            reviewer="wp-web",
        )
        handler = AsyncMock(return_value=handler_check)
        gate = QualityGate(cross_review_handler=handler)

        result = await gate.request_cross_review("eng-core", "t1", _make_output())
        assert result is not None
        assert result.status == "passed"
        assert result.score == 0.9
        handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_cross_review_handler_failure(self) -> None:
        handler = AsyncMock(side_effect=RuntimeError("connection failed"))
        gate = QualityGate(cross_review_handler=handler)

        result = await gate.request_cross_review("eng-core", "t1", _make_output())
        # Fallback to pending check
        assert result is not None
        assert result.status == "pending"


# ===========================================================================
# 4. Brain final review
# ===========================================================================


class TestBrainReview:
    @pytest.mark.asyncio
    async def test_brain_review_all_pass(self, gate: QualityGate) -> None:
        checks = [
            QualityCheck(
                check_id=f"c{i}", agent_id="eng-core", task_id="t1",
                check_type="automated", status="passed", score=1.0,
                feedback="OK", reviewer="automated",
            )
            for i in range(3)
        ]
        result = await gate.brain_final_review("t1", checks)
        assert result is True

    @pytest.mark.asyncio
    async def test_brain_review_hard_failure(self, gate: QualityGate) -> None:
        checks = [
            QualityCheck(
                check_id="c1", agent_id="eng-core", task_id="t1",
                check_type="automated", status="failed", score=0.0,
                feedback="Secret found", reviewer="automated",
            ),
            QualityCheck(
                check_id="c2", agent_id="eng-core", task_id="t1",
                check_type="automated", status="failed", score=0.0,
                feedback="Lint errors", reviewer="automated",
            ),
        ]
        result = await gate.brain_final_review("t1", checks)
        assert result is False

    @pytest.mark.asyncio
    async def test_brain_review_override_single_failure(self, gate: QualityGate) -> None:
        """Single failure with high enough average can be overridden."""
        checks = [
            QualityCheck(
                check_id="c1", agent_id="eng-core", task_id="t1",
                check_type="automated", status="passed", score=1.0,
                feedback="OK", reviewer="automated",
            ),
            QualityCheck(
                check_id="c2", agent_id="eng-core", task_id="t1",
                check_type="automated", status="failed", score=0.0,
                feedback="Minor issue", reviewer="automated",
            ),
        ]
        # avg = 0.5, 1 hard failure, override threshold is 0.5
        result = await gate.brain_final_review("t1", checks)
        assert result is True  # Override kicks in

    @pytest.mark.asyncio
    async def test_brain_review_empty_checks(self, gate: QualityGate) -> None:
        result = await gate.brain_final_review("t1", [])
        assert result is True

    @pytest.mark.asyncio
    async def test_brain_review_only_pending(self, gate: QualityGate) -> None:
        checks = [
            QualityCheck(
                check_id="c1", agent_id="eng-core", task_id="t1",
                check_type="cross_review", status="pending", score=0.0,
                feedback="Pending", reviewer="wp-web",
            ),
        ]
        result = await gate.brain_final_review("t1", checks)
        assert result is True  # Only pending = optimistic pass


# ===========================================================================
# 5. Revision detection and instructions
# ===========================================================================


class TestRevision:
    def test_needs_revision_on_failure(self, gate: QualityGate) -> None:
        checks = [
            QualityCheck(
                check_id="c1", agent_id="eng-core", task_id="t1",
                check_type="automated", status="failed", score=0.0,
                feedback="Secret found", reviewer="automated",
            ),
        ]
        assert gate.needs_revision(checks) is True

    def test_no_revision_on_pass(self, gate: QualityGate) -> None:
        checks = [
            QualityCheck(
                check_id="c1", agent_id="eng-core", task_id="t1",
                check_type="automated", status="passed", score=1.0,
                feedback="OK", reviewer="automated",
            ),
        ]
        assert gate.needs_revision(checks) is False

    def test_no_revision_empty(self, gate: QualityGate) -> None:
        assert gate.needs_revision([]) is False

    def test_revision_instructions(self, gate: QualityGate) -> None:
        checks = [
            QualityCheck(
                check_id="c1", agent_id="eng-core", task_id="t1",
                check_type="automated", status="failed", score=0.0,
                feedback="Secret detected in output", reviewer="automated",
            ),
            QualityCheck(
                check_id="c2", agent_id="eng-core", task_id="t1",
                check_type="automated", status="passed", score=1.0,
                feedback="OK", reviewer="automated",
            ),
        ]
        instructions = gate.get_revision_instructions(checks)
        assert "Secret detected" in instructions
        assert "OK" not in instructions  # Only failed checks


# ===========================================================================
# 6. Full quality gate pipeline
# ===========================================================================


class TestFullPipeline:
    @pytest.mark.asyncio
    async def test_full_gate_eng_core(self, gate: QualityGate) -> None:
        output = _make_output(content="function hello() { return 42; }")
        checks = await gate.run_quality_gate("eng-core", "task-full-1", output)
        # Should have automated checks + cross-review
        assert len(checks) >= 4  # 4 automated + 1 cross-review
        # Check types present
        types = {c.check_type for c in checks}
        assert "automated" in types
        assert "cross_review" in types

    @pytest.mark.asyncio
    async def test_get_checks_stored(self, gate: QualityGate) -> None:
        output = _make_output(content="function hello() { return 42; }")
        await gate.run_quality_gate("eng-core", "task-stored", output)
        stored = gate.get_checks("task-stored")
        assert len(stored) >= 4

    @pytest.mark.asyncio
    async def test_stats(self, gate: QualityGate) -> None:
        output = _make_output(content="function hello() { return 42; }")
        await gate.run_quality_gate("eng-core", "task-stats", output)
        await gate.brain_final_review("task-stats", gate.get_checks("task-stats"))
        stats = gate.get_stats()
        assert stats["total_checks"] > 0
        assert stats["tasks_tracked"] >= 1


# ===========================================================================
# 7. FeedbackLoop — recording and scoring
# ===========================================================================


class TestFeedbackLoop:
    @pytest.mark.asyncio
    async def test_record_feedback(self, feedback_loop: FeedbackLoop) -> None:
        fb = await feedback_loop.record_feedback("t1", "eng-core", 4, "Good work")
        assert fb.rating == 4
        assert fb.agent_id == "eng-core"
        assert fb.feedback_id

    @pytest.mark.asyncio
    async def test_invalid_rating(self, feedback_loop: FeedbackLoop) -> None:
        with pytest.raises(ValueError, match="Rating must be 1-5"):
            await feedback_loop.record_feedback("t1", "eng-core", 6)

    @pytest.mark.asyncio
    async def test_invalid_rating_zero(self, feedback_loop: FeedbackLoop) -> None:
        with pytest.raises(ValueError, match="Rating must be 1-5"):
            await feedback_loop.record_feedback("t1", "eng-core", 0)

    @pytest.mark.asyncio
    async def test_get_agent_score(self, feedback_loop: FeedbackLoop) -> None:
        await feedback_loop.record_feedback("t1", "eng-core", 4)
        await feedback_loop.record_feedback("t2", "eng-core", 5)
        await feedback_loop.record_feedback("t3", "eng-core", 3)
        score = await feedback_loop.get_agent_score("eng-core")
        assert score == pytest.approx(4.0, abs=0.01)

    @pytest.mark.asyncio
    async def test_get_agent_score_no_feedback(self, feedback_loop: FeedbackLoop) -> None:
        score = await feedback_loop.get_agent_score("unknown")
        assert score == 0.0

    @pytest.mark.asyncio
    async def test_get_agent_stats(self, feedback_loop: FeedbackLoop) -> None:
        await feedback_loop.record_feedback("t1", "eng-core", 4)
        await feedback_loop.record_task_completion("eng-core")
        await feedback_loop.record_revision("eng-core")
        stats = await feedback_loop.get_agent_stats("eng-core")
        assert stats["agent_id"] == "eng-core"
        assert stats["tasks_completed"] == 1
        assert stats["total_revisions"] == 1
        assert stats["revision_rate"] == 1.0

    @pytest.mark.asyncio
    async def test_agent_feedback_to_dict(self) -> None:
        fb = AgentFeedback(
            feedback_id="fb-001",
            task_id="t1",
            agent_id="eng-core",
            rating=5,
            comment="Excellent",
        )
        d = fb.to_dict()
        assert d["rating"] == 5
        assert d["comment"] == "Excellent"
        assert "timestamp" in d


# ===========================================================================
# 8. Degradation detection
# ===========================================================================


class TestDegradation:
    @pytest.mark.asyncio
    async def test_no_degradation_insufficient_data(self, feedback_loop: FeedbackLoop) -> None:
        await feedback_loop.record_feedback("t1", "eng-core", 4)
        await feedback_loop.record_feedback("t2", "eng-core", 3)
        degrading = await feedback_loop.detect_degradation("eng-core")
        assert degrading is False  # Not enough data

    @pytest.mark.asyncio
    async def test_degradation_detected(self, feedback_loop: FeedbackLoop) -> None:
        # Early: high ratings
        for i in range(5):
            await feedback_loop.record_feedback(f"t{i}", "eng-core", 5)
        # Late: low ratings
        for i in range(5, 10):
            await feedback_loop.record_feedback(f"t{i}", "eng-core", 1)
        degrading = await feedback_loop.detect_degradation("eng-core")
        assert degrading is True

    @pytest.mark.asyncio
    async def test_no_degradation_stable(self, feedback_loop: FeedbackLoop) -> None:
        for i in range(10):
            await feedback_loop.record_feedback(f"t{i}", "eng-core", 4)
        degrading = await feedback_loop.detect_degradation("eng-core")
        assert degrading is False


# ===========================================================================
# 9. Action recommendations
# ===========================================================================


class TestRecommendations:
    @pytest.mark.asyncio
    async def test_continue_recommendation(self, feedback_loop: FeedbackLoop) -> None:
        for i in range(5):
            await feedback_loop.record_feedback(f"t{i}", "eng-core", 4)
        action = await feedback_loop.recommend_action("eng-core")
        assert action == "continue"

    @pytest.mark.asyncio
    async def test_pause_recommendation(self, feedback_loop: FeedbackLoop) -> None:
        for i in range(5):
            await feedback_loop.record_feedback(f"t{i}", "eng-core", 1)
        action = await feedback_loop.recommend_action("eng-core")
        assert action == "pause"

    @pytest.mark.asyncio
    async def test_reduce_trust_recommendation(self, feedback_loop: FeedbackLoop) -> None:
        for i in range(5):
            await feedback_loop.record_feedback(f"t{i}", "eng-core", 2)
        action = await feedback_loop.recommend_action("eng-core")
        assert action in ("reduce_trust", "retrain")

    @pytest.mark.asyncio
    async def test_no_feedback_continues(self, feedback_loop: FeedbackLoop) -> None:
        action = await feedback_loop.recommend_action("unknown")
        assert action == "continue"


# ===========================================================================
# 10. Pipeline integration
# ===========================================================================


class TestPipelineIntegration:
    """Test that quality gate integrates into the Pipeline correctly."""

    @pytest.mark.asyncio
    async def test_pipeline_with_quality_gate_pass(self) -> None:
        from orchestrator.models import Task
        from orchestrator.pipeline import Pipeline
        from policy_engine.engine import GateResult

        planner = MagicMock()
        planner.create_plan = AsyncMock(return_value={"steps": ["a"]})

        engine = MagicMock()
        engine.evaluate = AsyncMock(return_value=GateResult(approved=True, reason=""))

        executor = MagicMock()
        executor.execute = AsyncMock(return_value={"content": "valid code output"})

        validator = MagicMock()
        validator.validate = AsyncMock(return_value=[])

        shipper = MagicMock()
        shipper.ship = AsyncMock(return_value={"shipped": True})

        # Quality gate that always passes
        qgate = QualityGate()

        pipeline = Pipeline(
            planner=planner,
            policy_engine=engine,
            executor=executor,
            validator=validator,
            shipper=shipper,
            quality_gate=qgate,
        )

        task = Task(name="test", description="test", agent_type="eng-core")
        result = await pipeline.run(task)
        assert result.success is True
        assert "quality_gate" in result.evidence
        assert result.evidence["quality_gate"]["passed"] is True

    @pytest.mark.asyncio
    async def test_pipeline_without_quality_gate(self) -> None:
        """Pipeline works normally without quality gate."""
        from orchestrator.models import Task
        from orchestrator.pipeline import Pipeline
        from policy_engine.engine import GateResult

        planner = MagicMock()
        planner.create_plan = AsyncMock(return_value={"steps": ["a"]})

        engine = MagicMock()
        engine.evaluate = AsyncMock(return_value=GateResult(approved=True, reason=""))

        executor = MagicMock()
        executor.execute = AsyncMock(return_value={"result": "ok"})

        validator = MagicMock()
        validator.validate = AsyncMock(return_value=[])

        shipper = MagicMock()
        shipper.ship = AsyncMock(return_value={"shipped": True})

        pipeline = Pipeline(
            planner=planner,
            policy_engine=engine,
            executor=executor,
            validator=validator,
            shipper=shipper,
        )

        task = Task(name="test", description="test", agent_type="default")
        result = await pipeline.run(task)
        assert result.success is True
        assert "quality_gate" not in result.evidence

    @pytest.mark.asyncio
    async def test_pipeline_quality_gate_revision_loop(self) -> None:
        """Pipeline retries execution when quality gate fails initially."""
        from orchestrator.models import Task
        from orchestrator.pipeline import Pipeline
        from policy_engine.engine import GateResult

        planner = MagicMock()
        planner.create_plan = AsyncMock(return_value={"steps": ["a"]})

        engine = MagicMock()
        engine.evaluate = AsyncMock(return_value=GateResult(approved=True, reason=""))

        # First call returns bad output (with secret), second returns clean
        call_count = 0
        async def _execute(task: Any) -> dict[str, Any]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {"content": 'api_key = "sk-abcdefghijklmnopqrstuvwxyz123456"'}
            return {"content": "clean code without any secrets at all here"}

        executor = MagicMock()
        executor.execute = AsyncMock(side_effect=_execute)

        validator = MagicMock()
        validator.validate = AsyncMock(return_value=[])

        shipper = MagicMock()
        shipper.ship = AsyncMock(return_value={"shipped": True})

        qgate = QualityGate()

        pipeline = Pipeline(
            planner=planner,
            policy_engine=engine,
            executor=executor,
            validator=validator,
            shipper=shipper,
            quality_gate=qgate,
            quality_max_revisions=2,
        )

        task = Task(name="test", description="test", agent_type="eng-core")
        result = await pipeline.run(task)
        # Should pass on second attempt after revision
        assert result.success is True
        assert call_count == 2


# ===========================================================================
# 11. API endpoint coverage (unit-level)
# ===========================================================================


class TestAPIEndpoints:
    """Test the quality API route functions directly."""

    @pytest.mark.asyncio
    async def test_feedback_request_validation(self) -> None:
        """FeedbackRequest validates fields."""
        from api.routes.quality import FeedbackRequest
        fb = FeedbackRequest(task_id="t1", agent_id="eng-core", rating=5)
        assert fb.rating == 5

    @pytest.mark.asyncio
    async def test_feedback_request_invalid_rating(self) -> None:
        from api.routes.quality import FeedbackRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            FeedbackRequest(task_id="t1", agent_id="eng-core", rating=10)

    @pytest.mark.asyncio
    async def test_quality_stats_response_model(self) -> None:
        from api.routes.quality import QualityStatsResponse
        resp = QualityStatsResponse(total_checks=10, total_passed=8, total_failed=2, tasks_tracked=5)
        assert resp.total_checks == 10

    @pytest.mark.asyncio
    async def test_agent_stats_response_model(self) -> None:
        from api.routes.quality import AgentStatsResponse
        resp = AgentStatsResponse(
            agent_id="eng-core",
            tasks_completed=10,
            avg_score=4.2,
            revision_rate=0.1,
        )
        assert resp.agent_id == "eng-core"
        assert resp.recommendation == "continue"  # default


# ===========================================================================
# 12. FeedbackLoop global stats and listing
# ===========================================================================


class TestFeedbackLoopExtra:
    @pytest.mark.asyncio
    async def test_list_agents(self, feedback_loop: FeedbackLoop) -> None:
        await feedback_loop.record_feedback("t1", "eng-core", 4)
        await feedback_loop.record_feedback("t2", "wp-web", 3)
        agents = feedback_loop.list_agents()
        assert "eng-core" in agents
        assert "wp-web" in agents

    @pytest.mark.asyncio
    async def test_get_feedback(self, feedback_loop: FeedbackLoop) -> None:
        for i in range(5):
            await feedback_loop.record_feedback(f"t{i}", "eng-core", 4)
        entries = feedback_loop.get_feedback("eng-core", limit=3)
        assert len(entries) == 3

    @pytest.mark.asyncio
    async def test_global_stats(self, feedback_loop: FeedbackLoop) -> None:
        await feedback_loop.record_feedback("t1", "eng-core", 4)
        await feedback_loop.record_task_completion("eng-core")
        stats = feedback_loop.get_global_stats()
        assert stats["agents_tracked"] == 1
        assert stats["total_feedback"] == 1
        assert stats["total_tasks"] == 1

    @pytest.mark.asyncio
    async def test_window_trimming(self) -> None:
        loop = FeedbackLoop(window_size=5)
        for i in range(10):
            await loop.record_feedback(f"t{i}", "eng-core", 3)
        entries = loop.get_feedback("eng-core", limit=100)
        assert len(entries) == 5  # Trimmed to window

    @pytest.mark.asyncio
    async def test_record_revision(self, feedback_loop: FeedbackLoop) -> None:
        await feedback_loop.record_revision("eng-core")
        await feedback_loop.record_revision("eng-core")
        stats = await feedback_loop.get_agent_stats("eng-core")
        assert stats["total_revisions"] == 2
