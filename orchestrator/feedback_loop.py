"""Feedback Loop — agent performance tracking from Henry's feedback.

Complements the existing LearningLoop (skill-level) with agent-level
performance tracking, degradation detection, and actionable recommendations.

Integration:
- API: POST /api/v1/feedback records Henry's rating
- QualityGate: feeds check results into agent scores
- Brain: uses agent stats for trust-level decisions
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class AgentFeedback:
    """A single feedback entry from Henry or the system."""

    feedback_id: str
    task_id: str
    agent_id: str
    rating: int  # 1-5
    comment: str = ""
    source: str = "human"  # "human" | "system" | "quality_gate"
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def __post_init__(self) -> None:
        if not 1 <= self.rating <= 5:
            raise ValueError(f"Rating must be 1-5, got {self.rating}")
        if not self.task_id:
            raise ValueError("task_id must not be empty")
        if not self.agent_id:
            raise ValueError("agent_id must not be empty")

    def to_dict(self) -> dict[str, Any]:
        return {
            "feedback_id": self.feedback_id,
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "rating": self.rating,
            "comment": self.comment,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
        }


# ---------------------------------------------------------------------------
# FeedbackLoop
# ---------------------------------------------------------------------------


class FeedbackLoop:
    """Tracks agent performance and learns from Henry's feedback.

    Maintains per-agent statistics including:
    - Task completion count
    - Average score (from ratings)
    - Revision rate (how often quality gate requires revision)
    - Score trend for degradation detection
    """

    # Degradation: if recent average drops by this much vs historical
    DEGRADATION_DROP: float = 0.15
    # Minimum feedback entries before degradation detection kicks in
    MIN_ENTRIES_FOR_DETECTION: int = 5
    # Score thresholds for recommendations
    PAUSE_THRESHOLD: float = 1.5  # avg rating
    REDUCE_TRUST_THRESHOLD: float = 2.5
    CONTINUE_THRESHOLD: float = 3.5

    def __init__(self, *, window_size: int = 50) -> None:
        self._window_size = window_size
        # agent_id -> list of AgentFeedback
        self._feedback_store: dict[str, list[AgentFeedback]] = {}
        # agent_id -> revision count
        self._revision_counts: dict[str, int] = {}
        # agent_id -> task count
        self._task_counts: dict[str, int] = {}

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------

    async def record_feedback(
        self,
        task_id: str,
        agent_id: str,
        rating: int,
        comment: str = "",
        *,
        source: str = "human",
        feedback_id: str = "",
    ) -> AgentFeedback:
        """Record feedback for an agent's task output.

        Args:
            task_id: The task that was rated.
            agent_id: The agent that produced the output.
            rating: Score from 1 (terrible) to 5 (excellent).
            comment: Optional textual feedback.
            source: Who provided the feedback.
            feedback_id: Optional pre-set ID (auto-generated if empty).

        Returns:
            The recorded AgentFeedback.
        """
        import uuid

        if not feedback_id:
            feedback_id = uuid.uuid4().hex[:12]

        fb = AgentFeedback(
            feedback_id=feedback_id,
            task_id=task_id,
            agent_id=agent_id,
            rating=rating,
            comment=comment,
            source=source,
        )

        if agent_id not in self._feedback_store:
            self._feedback_store[agent_id] = []

        self._feedback_store[agent_id].append(fb)

        # Trim to window size
        if len(self._feedback_store[agent_id]) > self._window_size:
            self._feedback_store[agent_id] = self._feedback_store[agent_id][
                -self._window_size :
            ]

        logger.debug(
            "Feedback recorded: agent=%s task=%s rating=%d source=%s",
            agent_id,
            task_id,
            rating,
            source,
        )

        return fb

    async def record_revision(self, agent_id: str) -> None:
        """Record that an agent's output required revision."""
        self._revision_counts[agent_id] = (
            self._revision_counts.get(agent_id, 0) + 1
        )

    async def record_task_completion(self, agent_id: str) -> None:
        """Record that an agent completed a task."""
        self._task_counts[agent_id] = self._task_counts.get(agent_id, 0) + 1

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    async def get_agent_score(
        self, agent_id: str, window_days: int = 30
    ) -> float:
        """Get the agent's average rating within the time window.

        Returns 0.0 if no feedback exists.
        """
        entries = self._feedback_store.get(agent_id, [])
        if not entries:
            return 0.0

        if window_days > 0:
            cutoff = datetime.now(timezone.utc).timestamp() - (
                window_days * 86400
            )
            entries = [e for e in entries if e.timestamp.timestamp() >= cutoff]

        if not entries:
            return 0.0

        return sum(e.rating for e in entries) / len(entries)

    async def get_agent_stats(self, agent_id: str) -> dict[str, Any]:
        """Get comprehensive agent statistics.

        Returns:
            Dict with tasks_completed, avg_score, revision_rate,
            total_feedback, recent_trend.
        """
        entries = self._feedback_store.get(agent_id, [])
        tasks = self._task_counts.get(agent_id, 0)
        revisions = self._revision_counts.get(agent_id, 0)

        avg_score = 0.0
        if entries:
            avg_score = sum(e.rating for e in entries) / len(entries)

        revision_rate = 0.0
        if tasks > 0:
            revision_rate = revisions / tasks

        # Recent trend: last 5 ratings
        recent = [e.rating for e in entries[-5:]]

        return {
            "agent_id": agent_id,
            "tasks_completed": tasks,
            "avg_score": round(avg_score, 2),
            "revision_rate": round(revision_rate, 3),
            "total_feedback": len(entries),
            "total_revisions": revisions,
            "recent_trend": recent,
        }

    async def detect_degradation(self, agent_id: str) -> bool:
        """Detect if agent performance is degrading.

        Compares the first half of the feedback window against the
        second half. A drop >= DEGRADATION_DROP indicates degradation.
        """
        entries = self._feedback_store.get(agent_id, [])
        if len(entries) < self.MIN_ENTRIES_FOR_DETECTION:
            return False

        ratings = [e.rating for e in entries]
        mid = len(ratings) // 2
        early_avg = sum(ratings[:mid]) / mid
        late_avg = sum(ratings[mid:]) / (len(ratings) - mid)

        drop = (early_avg - late_avg) / 5.0  # Normalize to 0-1 scale
        return drop >= self.DEGRADATION_DROP

    async def recommend_action(self, agent_id: str) -> str:
        """Recommend an action based on agent performance.

        Returns one of: "continue", "reduce_trust", "pause", "retrain"
        """
        entries = self._feedback_store.get(agent_id, [])
        if not entries:
            return "continue"

        avg = sum(e.rating for e in entries) / len(entries)
        is_degrading = await self.detect_degradation(agent_id)

        if avg <= self.PAUSE_THRESHOLD:
            return "pause"
        if avg <= self.REDUCE_TRUST_THRESHOLD:
            return "retrain" if is_degrading else "reduce_trust"
        if is_degrading:
            return "reduce_trust"
        return "continue"

    # ------------------------------------------------------------------
    # Listing
    # ------------------------------------------------------------------

    def list_agents(self) -> list[str]:
        """Return all agent IDs with feedback."""
        return list(self._feedback_store.keys())

    def get_feedback(
        self, agent_id: str, limit: int = 20
    ) -> list[AgentFeedback]:
        """Return recent feedback for an agent."""
        entries = self._feedback_store.get(agent_id, [])
        return entries[-limit:]

    def get_global_stats(self) -> dict[str, Any]:
        """Return global feedback loop statistics."""
        total_feedback = sum(
            len(entries) for entries in self._feedback_store.values()
        )
        total_tasks = sum(self._task_counts.values())
        total_revisions = sum(self._revision_counts.values())

        return {
            "agents_tracked": len(self._feedback_store),
            "total_feedback": total_feedback,
            "total_tasks": total_tasks,
            "total_revisions": total_revisions,
        }
