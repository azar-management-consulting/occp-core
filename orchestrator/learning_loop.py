"""Learning Loop — Adaptive feedback system for skill performance.

Captures execution outcomes, feeds them into memory, and enables
adaptive behavior improvement based on historical performance data.

Acceptance Tests (ACC-LEARN-01 through ACC-LEARN-05):
  (1) Feedback recorded and performance updated correctly.
  (2) Degrading skill detected when score trend drops.
  (3) Auto-disable recommended for extremely low-performing skill.
  (4) Recommendations generated based on performance data.
  (5) Stats report accurate global metrics.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class LearningError(Exception):
    """Base error for learning loop operations."""


class FeedbackValidationError(LearningError):
    """Feedback data failed validation."""


class SkillPerformanceNotFoundError(LearningError):
    """No performance record found for the given skill_id."""

    def __init__(self, skill_id: str) -> None:
        self.skill_id = skill_id
        super().__init__(f"No performance record found for skill: {skill_id}")


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class FeedbackType(str, Enum):
    """Classification of execution outcome feedback."""

    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    PARTIAL = "partial"
    USER_CORRECTION = "user_correction"


class LearningStrategy(str, Enum):
    """Strategy for interpreting and acting on feedback data."""

    NONE = "none"
    FREQUENCY_BOOST = "frequency_boost"
    SCORE_THRESHOLD = "score_threshold"
    ADAPTIVE = "adaptive"


# ---------------------------------------------------------------------------
# ExecutionFeedback
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExecutionFeedback:
    """Immutable record of an execution outcome.

    Args:
        feedback_id: Auto-generated unique identifier.
        skill_id: Identifier of the skill that was executed.
        execution_id: Identifier of the specific execution run.
        feedback_type: Classification of the outcome.
        score: Normalized score in [0.0, 1.0].
        context: Input parameters that led to this outcome.
        correction: User-provided correction text (if applicable).
        timestamp: Unix timestamp when feedback was recorded.
        agent_id: Agent that performed the execution.
        session_id: Session in which the execution occurred.
    """

    skill_id: str
    execution_id: str
    feedback_type: FeedbackType
    score: float
    feedback_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    context: dict[str, Any] = field(default_factory=dict)
    correction: str = ""
    timestamp: float = field(default_factory=time.time)
    agent_id: str = ""
    session_id: str = ""

    def __post_init__(self) -> None:
        if not 0.0 <= self.score <= 1.0:
            raise FeedbackValidationError(
                f"Score must be in [0.0, 1.0], got {self.score}"
            )
        if not self.skill_id:
            raise FeedbackValidationError("skill_id must not be empty")
        if not self.execution_id:
            raise FeedbackValidationError("execution_id must not be empty")

    def to_dict(self) -> dict[str, Any]:
        return {
            "feedbackId": self.feedback_id,
            "skillId": self.skill_id,
            "executionId": self.execution_id,
            "feedbackType": self.feedback_type.value,
            "score": self.score,
            "context": dict(self.context),
            "correction": self.correction,
            "timestamp": self.timestamp,
            "agentId": self.agent_id,
            "sessionId": self.session_id,
        }


# ---------------------------------------------------------------------------
# SkillPerformanceRecord
# ---------------------------------------------------------------------------


@dataclass
class SkillPerformanceRecord:
    """Aggregated performance metrics for a single skill.

    Args:
        skill_id: Identifier of the skill being tracked.
        total_executions: Total number of executions recorded.
        success_count: Number of SUCCESS feedback entries.
        failure_count: Number of FAILURE/TIMEOUT feedback entries.
        avg_score: Rolling average score across all feedback.
        avg_duration_ms: Average execution duration in milliseconds.
        last_feedback: Most recently recorded feedback entry.
        score_trend: Rolling window of the last N scores.
    """

    skill_id: str
    total_executions: int = 0
    success_count: int = 0
    failure_count: int = 0
    avg_score: float = 0.0
    avg_duration_ms: float = 0.0
    last_feedback: ExecutionFeedback | None = None
    score_trend: list[float] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "skillId": self.skill_id,
            "totalExecutions": self.total_executions,
            "successCount": self.success_count,
            "failureCount": self.failure_count,
            "avgScore": round(self.avg_score, 6),
            "avgDurationMs": round(self.avg_duration_ms, 2),
            "lastFeedback": self.last_feedback.to_dict() if self.last_feedback else None,
            "scoreTrend": list(self.score_trend),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SkillPerformanceRecord:
        last_fb_data = data.get("lastFeedback")
        last_fb: ExecutionFeedback | None = None
        if last_fb_data is not None:
            last_fb = ExecutionFeedback(
                feedback_id=last_fb_data.get("feedbackId", uuid.uuid4().hex[:16]),
                skill_id=last_fb_data["skillId"],
                execution_id=last_fb_data["executionId"],
                feedback_type=FeedbackType(last_fb_data["feedbackType"]),
                score=last_fb_data["score"],
                context=last_fb_data.get("context", {}),
                correction=last_fb_data.get("correction", ""),
                timestamp=last_fb_data.get("timestamp", time.time()),
                agent_id=last_fb_data.get("agentId", ""),
                session_id=last_fb_data.get("sessionId", ""),
            )

        return cls(
            skill_id=data["skillId"],
            total_executions=data.get("totalExecutions", 0),
            success_count=data.get("successCount", 0),
            failure_count=data.get("failureCount", 0),
            avg_score=data.get("avgScore", 0.0),
            avg_duration_ms=data.get("avgDurationMs", 0.0),
            last_feedback=last_fb,
            score_trend=list(data.get("scoreTrend", [])),
        )


# ---------------------------------------------------------------------------
# LearningConfig
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LearningConfig:
    """Immutable configuration for the LearningLoop.

    Args:
        strategy: Learning strategy to apply when evaluating feedback.
        score_window_size: Number of recent scores to retain for trend analysis.
        min_score_threshold: Below this avg score the skill is flagged for review.
        degradation_threshold: Score drop amount that triggers a degradation alert.
        auto_disable_threshold: Avg score below this triggers auto-disable.
        feedback_retention_days: Days to retain feedback records.
        enable_cross_session: Whether to persist performance to cross-session memory.
    """

    strategy: LearningStrategy = LearningStrategy.ADAPTIVE
    score_window_size: int = 50
    min_score_threshold: float = 0.3
    degradation_threshold: float = 0.2
    auto_disable_threshold: float = 0.1
    feedback_retention_days: int = 90
    enable_cross_session: bool = True


# ---------------------------------------------------------------------------
# LearningLoop
# ---------------------------------------------------------------------------


class LearningLoop:
    """Adaptive feedback engine for skill performance tracking.

    Records execution outcomes (feedback), maintains rolling performance
    metrics per skill, detects degradation trends, and generates
    actionable recommendations.

    Integration points:
    - ``memory``: Optional CrossSessionKnowledge / KnowledgeStore for
      persisting performance across sessions.
    - ``audit_callback``: Optional callable invoked on every feedback event
      with signature ``(event: str, data: dict) -> None``.

    Usage::

        loop = LearningLoop(config=LearningConfig())
        feedback = ExecutionFeedback(
            skill_id="skill-abc",
            execution_id="exec-001",
            feedback_type=FeedbackType.SUCCESS,
            score=0.9,
        )
        loop.record_feedback(feedback)
        perf = loop.get_performance("skill-abc")
    """

    def __init__(
        self,
        config: LearningConfig | None = None,
        memory: Any = None,
        audit_callback: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> None:
        self._config = config or LearningConfig()
        self._memory = memory
        self._audit_callback = audit_callback

        # skill_id → SkillPerformanceRecord
        self._performance: dict[str, SkillPerformanceRecord] = {}
        # All feedback in insertion order
        self._feedback_log: list[ExecutionFeedback] = []

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------

    def record_feedback(self, feedback: ExecutionFeedback) -> None:
        """Record an execution outcome and update performance metrics.

        Args:
            feedback: The ``ExecutionFeedback`` to record.
        """
        skill_id = feedback.skill_id

        # Append to global log
        self._feedback_log.append(feedback)

        # Get or create performance record
        if skill_id not in self._performance:
            self._performance[skill_id] = SkillPerformanceRecord(skill_id=skill_id)

        record = self._performance[skill_id]

        # Update counters
        record.total_executions += 1

        if feedback.feedback_type == FeedbackType.SUCCESS:
            record.success_count += 1
        elif feedback.feedback_type in (FeedbackType.FAILURE, FeedbackType.TIMEOUT):
            record.failure_count += 1

        # Update rolling average score (incremental mean)
        n = record.total_executions
        record.avg_score = record.avg_score + (feedback.score - record.avg_score) / n

        # Update score trend window
        record.score_trend.append(feedback.score)
        if len(record.score_trend) > self._config.score_window_size:
            record.score_trend = record.score_trend[-self._config.score_window_size:]

        # Update last feedback
        record.last_feedback = feedback

        # Emit audit event
        if self._audit_callback is not None:
            try:
                self._audit_callback(
                    "learning.feedback.recorded",
                    {
                        "feedbackId": feedback.feedback_id,
                        "skillId": skill_id,
                        "feedbackType": feedback.feedback_type.value,
                        "score": feedback.score,
                        "timestamp": feedback.timestamp,
                    },
                )
            except Exception:
                logger.warning("Audit callback raised an exception", exc_info=True)

        # Persist to cross-session memory if configured
        if self._memory is not None and self._config.enable_cross_session:
            self._persist_to_memory(skill_id, record)

        logger.debug(
            "Feedback recorded: skill=%s type=%s score=%.3f",
            skill_id,
            feedback.feedback_type.value,
            feedback.score,
        )

    # ------------------------------------------------------------------
    # Performance queries
    # ------------------------------------------------------------------

    def get_performance(self, skill_id: str) -> SkillPerformanceRecord | None:
        """Return the performance record for a skill, or None if not tracked."""
        return self._performance.get(skill_id)

    def get_all_performance(self) -> list[SkillPerformanceRecord]:
        """Return performance records for all tracked skills."""
        return list(self._performance.values())

    # ------------------------------------------------------------------
    # Recommendations
    # ------------------------------------------------------------------

    def get_recommendations(self, skill_id: str) -> list[str]:
        """Return recommendation strings based on current performance data.

        Returns an empty list if no data is available for the skill.
        """
        record = self._performance.get(skill_id)
        if record is None or record.total_executions == 0:
            return []

        recommendations: list[str] = []
        cfg = self._config

        if record.avg_score <= cfg.auto_disable_threshold:
            recommendations.append(
                f"Auto-disable recommended: avg_score={record.avg_score:.3f} is at or below "
                f"auto_disable_threshold={cfg.auto_disable_threshold}"
            )

        if record.avg_score <= cfg.min_score_threshold and record.avg_score > cfg.auto_disable_threshold:
            recommendations.append(
                f"Skill flagged for review: avg_score={record.avg_score:.3f} is at or below "
                f"min_score_threshold={cfg.min_score_threshold}"
            )

        if self.is_degrading(skill_id):
            recommendations.append(
                "Performance degradation detected: score trend is declining — "
                "consider investigating recent changes"
            )

        if record.failure_count > 0 and record.total_executions > 0:
            failure_rate = record.failure_count / record.total_executions
            if failure_rate >= 0.5:
                recommendations.append(
                    f"High failure rate: {failure_rate:.1%} of executions failed — "
                    f"review skill implementation"
                )

        if record.avg_score >= 0.8 and record.total_executions >= 5:
            recommendations.append(
                f"Skill performing well: avg_score={record.avg_score:.3f} — "
                "consider increasing usage"
            )

        return recommendations

    # ------------------------------------------------------------------
    # Health checks
    # ------------------------------------------------------------------

    def should_disable_skill(self, skill_id: str) -> bool:
        """Return True if performance is below auto_disable_threshold."""
        record = self._performance.get(skill_id)
        if record is None or record.total_executions == 0:
            return False
        return record.avg_score <= self._config.auto_disable_threshold

    def is_degrading(self, skill_id: str) -> bool:
        """Return True if score trend is declining by at least degradation_threshold.

        Compares the average of the first half of the trend window against
        the average of the second half. A drop >= degradation_threshold
        is considered degradation.
        """
        record = self._performance.get(skill_id)
        if record is None or len(record.score_trend) < 4:
            return False

        trend = record.score_trend
        mid = len(trend) // 2
        early_avg = sum(trend[:mid]) / mid
        late_avg = sum(trend[mid:]) / (len(trend) - mid)

        return (early_avg - late_avg) >= self._config.degradation_threshold

    # ------------------------------------------------------------------
    # Ranking
    # ------------------------------------------------------------------

    def get_top_skills(self, n: int = 5) -> list[SkillPerformanceRecord]:
        """Return top-N skills by avg_score (descending)."""
        sorted_records = sorted(
            self._performance.values(),
            key=lambda r: r.avg_score,
            reverse=True,
        )
        return sorted_records[:n]

    def get_worst_skills(self, n: int = 5) -> list[SkillPerformanceRecord]:
        """Return worst-N skills by avg_score (ascending)."""
        sorted_records = sorted(
            self._performance.values(),
            key=lambda r: r.avg_score,
        )
        return sorted_records[:n]

    # ------------------------------------------------------------------
    # Management
    # ------------------------------------------------------------------

    def reset_performance(self, skill_id: str) -> bool:
        """Clear performance metrics for a skill. Returns True if found and cleared."""
        if skill_id not in self._performance:
            return False
        del self._performance[skill_id]
        # Also remove from feedback log
        self._feedback_log = [f for f in self._feedback_log if f.skill_id != skill_id]
        return True

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """Return global learning loop statistics."""
        skills_tracked = len(self._performance)
        total_feedback = len(self._feedback_log)

        if skills_tracked > 0:
            avg_global_score = sum(
                r.avg_score for r in self._performance.values()
            ) / skills_tracked
        else:
            avg_global_score = 0.0

        degrading_count = sum(
            1 for skill_id in self._performance
            if self.is_degrading(skill_id)
        )

        return {
            "total_feedback": total_feedback,
            "skills_tracked": skills_tracked,
            "avg_global_score": round(avg_global_score, 6),
            "degrading_skills": degrading_count,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _persist_to_memory(
        self,
        skill_id: str,
        record: SkillPerformanceRecord,
    ) -> None:
        """Persist performance record to cross-session memory store."""
        try:
            content = (
                f"skill_performance:{skill_id} "
                f"avg_score={record.avg_score:.4f} "
                f"executions={record.total_executions} "
                f"success={record.success_count} "
                f"failure={record.failure_count}"
            )
            # Support KnowledgeStore.extract_and_add interface
            if hasattr(self._memory, "extract_and_add"):
                self._memory.extract_and_add(
                    content,
                    knowledge_type="procedure",
                    tags=["learning", "skill_performance", skill_id],
                    metadata=record.to_dict(),
                )
            # Support MemoryStore.add_text interface
            elif hasattr(self._memory, "add_text"):
                self._memory.add_text(
                    content,
                    tags=["learning", "skill_performance", skill_id],
                    metadata=record.to_dict(),
                )
        except Exception:
            logger.warning(
                "Failed to persist performance to memory for skill=%s",
                skill_id,
                exc_info=True,
            )
