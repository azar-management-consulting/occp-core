"""Brain Stats — aggregates real-time status from all Brain components.

Collects data from ProjectManager, QualityGate, FeedbackLoop, and agent
registries to provide a unified dashboard view for Henry.

Integration:
- Dashboard API: GET /api/v1/dashboard/* endpoints
- Telegram: status command formatting
- WebSocket: real-time push (future)
"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Brain agent definitions (the 8 OpenClaw agents)
# ---------------------------------------------------------------------------

BRAIN_AGENTS: list[dict[str, Any]] = [
    {
        "id": "eng-core",
        "name": "Engineering Agent",
        "capabilities": ["backend", "API", "architecture", "testing"],
    },
    {
        "id": "wp-web",
        "name": "WordPress & Web Agent",
        "capabilities": ["WordPress", "Elementor", "frontend", "SEO"],
    },
    {
        "id": "infra-ops",
        "name": "Infrastructure & DevOps Agent",
        "capabilities": ["servers", "CI/CD", "monitoring", "security"],
    },
    {
        "id": "design-lab",
        "name": "Design Lab Agent",
        "capabilities": ["UI/UX", "branding", "graphics", "responsive"],
    },
    {
        "id": "content-forge",
        "name": "Content Forge Agent",
        "capabilities": ["copywriting", "blog", "translation", "SEO content"],
    },
    {
        "id": "social-growth",
        "name": "Social Growth Agent",
        "capabilities": ["social media", "campaigns", "analytics", "growth"],
    },
    {
        "id": "intel-research",
        "name": "Intelligence & Research Agent",
        "capabilities": ["market research", "competitor analysis", "trends"],
    },
    {
        "id": "biz-strategy",
        "name": "Business Strategy Agent",
        "capabilities": ["pricing", "ROI", "proposals", "consulting"],
    },
]

BRAIN_AGENT_IDS: set[str] = {a["id"] for a in BRAIN_AGENTS}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class Activity:
    """A single activity entry in the activity stream."""

    timestamp: datetime
    activity_type: str  # task_completed|task_started|task_failed|revision_requested|agent_status_change
    agent_id: str
    project_id: str = ""
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "type": self.activity_type,
            "agent": self.agent_id,
            "project": self.project_id,
            "description": self.description,
        }


# ---------------------------------------------------------------------------
# BrainStats
# ---------------------------------------------------------------------------


class BrainStats:
    """Aggregates stats from all Brain components for dashboard and Telegram.

    Maintains:
    - Activity ring buffer (max 1000 entries)
    - Per-agent task counts and status tracking
    - Completion time measurements
    """

    MAX_ACTIVITIES: int = 1000

    def __init__(self) -> None:
        self._activities: deque[Activity] = deque(maxlen=self.MAX_ACTIVITIES)
        self._task_counts: dict[str, int] = {}  # agent_id -> tasks today
        self._task_completed_counts: dict[str, int] = {}  # agent_id -> completed today
        self._completion_times: list[float] = []  # seconds
        self._agent_statuses: dict[str, str] = {}  # agent_id -> idle|busy|error|offline
        self._agent_current_tasks: dict[str, str] = {}  # agent_id -> current task description
        self._agent_last_active: dict[str, datetime] = {}  # agent_id -> last active timestamp
        self._total_tasks_all_time: int = 0

        # Initialize all agents as idle
        for agent_id in BRAIN_AGENT_IDS:
            self._agent_statuses[agent_id] = "idle"

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record_activity(
        self,
        activity_type: str,
        agent_id: str,
        project_id: str = "",
        description: str = "",
    ) -> Activity:
        """Record an activity event.

        Args:
            activity_type: One of task_completed, task_started, task_failed,
                          revision_requested, agent_status_change.
            agent_id: The agent involved.
            project_id: Optional project context.
            description: Human-readable description.

        Returns:
            The recorded Activity.
        """
        now = datetime.now(timezone.utc)
        activity = Activity(
            timestamp=now,
            activity_type=activity_type,
            agent_id=agent_id,
            project_id=project_id,
            description=description,
        )
        self._activities.append(activity)
        self._agent_last_active[agent_id] = now

        # Update counters based on activity type
        if activity_type == "task_started":
            self._task_counts[agent_id] = self._task_counts.get(agent_id, 0) + 1
            self._agent_statuses[agent_id] = "busy"
            self._agent_current_tasks[agent_id] = description
            self._total_tasks_all_time += 1

        elif activity_type == "task_completed":
            self._task_completed_counts[agent_id] = (
                self._task_completed_counts.get(agent_id, 0) + 1
            )
            self._agent_statuses[agent_id] = "idle"
            self._agent_current_tasks.pop(agent_id, None)

        elif activity_type == "task_failed":
            self._agent_statuses[agent_id] = "error"
            self._agent_current_tasks.pop(agent_id, None)

        logger.debug(
            "Activity recorded: type=%s agent=%s project=%s",
            activity_type,
            agent_id,
            project_id,
        )

        return activity

    def record_completion_time(self, seconds: float) -> None:
        """Record a task completion time in seconds."""
        self._completion_times.append(seconds)
        # Keep last 1000
        if len(self._completion_times) > 1000:
            self._completion_times = self._completion_times[-1000:]

    def set_agent_status(self, agent_id: str, status: str) -> None:
        """Manually set an agent's status (idle|busy|error|offline)."""
        valid = {"idle", "busy", "error", "offline"}
        if status not in valid:
            raise ValueError(f"Invalid agent status: {status}. Must be one of {valid}")
        self._agent_statuses[agent_id] = status
        if status != "busy":
            self._agent_current_tasks.pop(agent_id, None)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_agent_status(self, agent_id: str) -> str:
        """Get agent status: idle|busy|error|offline."""
        return self._agent_statuses.get(agent_id, "offline")

    def get_overview(
        self,
        project_manager: Any = None,
        quality_gate: Any = None,
        feedback_loop: Any = None,
    ) -> dict[str, Any]:
        """Build the full dashboard overview.

        Args:
            project_manager: Optional ProjectManager for project data.
            quality_gate: Optional QualityGate for quality stats.
            feedback_loop: Optional FeedbackLoop for agent scores.

        Returns:
            Complete dashboard overview dict.
        """
        total_tasks_today = sum(self._task_counts.values())
        total_completed = sum(self._task_completed_counts.values())

        # Brain status
        active_conversations = sum(
            1 for s in self._agent_statuses.values() if s == "busy"
        )

        brain_data: dict[str, Any] = {
            "status": "active",
            "active_conversations": active_conversations,
            "active_projects": 0,
            "total_tasks_today": total_tasks_today,
            "total_tasks_completed": total_completed,
        }

        # Agents
        agents_data: list[dict[str, Any]] = []
        for agent_def in BRAIN_AGENTS:
            agent_id = agent_def["id"]
            avg_score = 0.0
            if feedback_loop:
                entries = feedback_loop._feedback_store.get(agent_id, [])
                if entries:
                    avg_score = round(
                        sum(e.rating for e in entries) / len(entries), 1
                    )

            agents_data.append({
                "id": agent_id,
                "name": agent_def["name"],
                "status": self.get_agent_status(agent_id),
                "current_task": self._agent_current_tasks.get(agent_id, ""),
                "tasks_today": self._task_counts.get(agent_id, 0),
                "avg_quality_score": avg_score,
                "last_active": (
                    self._agent_last_active[agent_id].isoformat()
                    if agent_id in self._agent_last_active
                    else ""
                ),
            })

        # Projects
        projects_data: list[dict[str, Any]] = []
        if project_manager is not None:
            for proj in project_manager._projects.values():
                if proj.status == "active":
                    task_ids = project_manager._project_tasks.get(
                        proj.project_id, []
                    )
                    projects_data.append({
                        "id": proj.project_id,
                        "name": proj.name,
                        "status": proj.status,
                        "active_tasks": len(task_ids),
                        "completed_tasks": 0,
                        "agents_assigned": list(proj.assigned_agents),
                    })
            brain_data["active_projects"] = len(projects_data)

        # Recent activity (last 20)
        recent = list(self._activities)[-20:]
        recent.reverse()
        recent_data = [a.to_dict() for a in recent]

        # Stats
        avg_time = "0m"
        if self._completion_times:
            avg_secs = sum(self._completion_times) / len(self._completion_times)
            avg_time = f"{int(avg_secs // 60)}m" if avg_secs >= 60 else f"{int(avg_secs)}s"

        qg_stats: dict[str, Any] = {"total_checks": 0, "total_passed": 0, "total_failed": 0}
        if quality_gate is not None:
            qg_stats = quality_gate.get_stats()

        pass_rate = 0.0
        if qg_stats["total_passed"] + qg_stats["total_failed"] > 0:
            pass_rate = round(
                qg_stats["total_passed"]
                / (qg_stats["total_passed"] + qg_stats["total_failed"]),
                2,
            )

        revision_rate = 0.0
        if feedback_loop is not None:
            global_fb = feedback_loop.get_global_stats()
            if global_fb["total_tasks"] > 0:
                revision_rate = round(
                    global_fb["total_revisions"] / global_fb["total_tasks"], 2
                )

        stats_data: dict[str, Any] = {
            "total_tasks_all_time": self._total_tasks_all_time,
            "avg_completion_time": avg_time,
            "quality_gate_pass_rate": pass_rate,
            "revision_rate": revision_rate,
        }

        return {
            "brain": brain_data,
            "agents": agents_data,
            "projects": projects_data,
            "recent_activity": recent_data,
            "stats": stats_data,
        }

    def get_agent_detail(
        self,
        agent_id: str,
        feedback_loop: Any = None,
    ) -> dict[str, Any]:
        """Get detailed view for a single agent.

        Args:
            agent_id: The agent to query.
            feedback_loop: Optional FeedbackLoop for score data.

        Returns:
            Detailed agent dict.
        """
        agent_def = None
        for a in BRAIN_AGENTS:
            if a["id"] == agent_id:
                agent_def = a
                break

        if agent_def is None:
            return {"error": f"Agent '{agent_id}' not found"}

        detail: dict[str, Any] = {
            "id": agent_id,
            "name": agent_def["name"],
            "capabilities": agent_def["capabilities"],
            "status": self.get_agent_status(agent_id),
            "current_task": self._agent_current_tasks.get(agent_id, ""),
            "tasks_today": self._task_counts.get(agent_id, 0),
            "tasks_completed_today": self._task_completed_counts.get(agent_id, 0),
            "last_active": (
                self._agent_last_active[agent_id].isoformat()
                if agent_id in self._agent_last_active
                else ""
            ),
        }

        # Feedback data
        if feedback_loop is not None:
            entries = feedback_loop._feedback_store.get(agent_id, [])
            if entries:
                detail["avg_score"] = round(
                    sum(e.rating for e in entries) / len(entries), 2
                )
                detail["total_feedback"] = len(entries)
                detail["recent_ratings"] = [e.rating for e in entries[-10:]]
            else:
                detail["avg_score"] = 0.0
                detail["total_feedback"] = 0
                detail["recent_ratings"] = []
        else:
            detail["avg_score"] = 0.0
            detail["total_feedback"] = 0
            detail["recent_ratings"] = []

        # Recent activities for this agent
        agent_activities = [
            a.to_dict()
            for a in self._activities
            if a.agent_id == agent_id
        ]
        detail["recent_activities"] = agent_activities[-20:]

        return detail

    def get_timeline(self, hours: int = 24) -> list[dict[str, Any]]:
        """Get activity timeline for the last N hours.

        Args:
            hours: Number of hours to look back.

        Returns:
            List of activity dicts, newest first.
        """
        cutoff = datetime.now(timezone.utc).timestamp() - (hours * 3600)
        filtered = [
            a.to_dict()
            for a in self._activities
            if a.timestamp.timestamp() >= cutoff
        ]
        filtered.reverse()
        return filtered

    def get_metrics(
        self,
        quality_gate: Any = None,
        feedback_loop: Any = None,
    ) -> dict[str, Any]:
        """Get performance metrics suitable for charts.

        Returns:
            Dict with agent_performance, completion_times, quality_distribution.
        """
        # Per-agent performance
        agent_perf: list[dict[str, Any]] = []
        for agent_def in BRAIN_AGENTS:
            agent_id = agent_def["id"]
            score = 0.0
            if feedback_loop:
                entries = feedback_loop._feedback_store.get(agent_id, [])
                if entries:
                    score = round(
                        sum(e.rating for e in entries) / len(entries), 2
                    )
            agent_perf.append({
                "agent_id": agent_id,
                "name": agent_def["name"],
                "tasks_today": self._task_counts.get(agent_id, 0),
                "completed_today": self._task_completed_counts.get(agent_id, 0),
                "avg_score": score,
                "status": self.get_agent_status(agent_id),
            })

        # Completion time distribution
        time_buckets: dict[str, int] = {
            "under_1m": 0,
            "1m_5m": 0,
            "5m_15m": 0,
            "15m_30m": 0,
            "over_30m": 0,
        }
        for t in self._completion_times:
            if t < 60:
                time_buckets["under_1m"] += 1
            elif t < 300:
                time_buckets["1m_5m"] += 1
            elif t < 900:
                time_buckets["5m_15m"] += 1
            elif t < 1800:
                time_buckets["15m_30m"] += 1
            else:
                time_buckets["over_30m"] += 1

        # Quality distribution
        quality_dist: dict[str, int] = {"passed": 0, "failed": 0, "pending": 0}
        if quality_gate is not None:
            qg_stats = quality_gate.get_stats()
            quality_dist["passed"] = qg_stats["total_passed"]
            quality_dist["failed"] = qg_stats["total_failed"]

        return {
            "agent_performance": agent_perf,
            "completion_time_distribution": time_buckets,
            "quality_distribution": quality_dist,
            "total_tasks_all_time": self._total_tasks_all_time,
        }
