"""Tests for Dashboard API, BrainStats, and Telegram formatter.

Covers:
- BrainStats activity recording and ring buffer
- BrainStats agent status tracking
- BrainStats overview with ProjectManager/QualityGate/FeedbackLoop integration
- BrainStats agent detail
- BrainStats timeline filtering
- BrainStats metrics
- BrainStats completion time recording
- Telegram formatter output
- Telegram status command detection
- Dashboard API endpoints (overview, agent, timeline, metrics, telegram)
- Empty state handling
- Invalid agent ID handling
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from orchestrator.brain_stats import (
    Activity,
    BrainStats,
    BRAIN_AGENTS,
    BRAIN_AGENT_IDS,
)
from orchestrator.feedback_loop import FeedbackLoop
from orchestrator.quality_gate import QualityGate
from orchestrator.telegram_formatter import format_telegram_status, is_status_command


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def brain_stats() -> BrainStats:
    return BrainStats()


@pytest.fixture
def feedback_loop() -> FeedbackLoop:
    return FeedbackLoop()


@pytest.fixture
def quality_gate() -> QualityGate:
    return QualityGate()


# ---------------------------------------------------------------------------
# BrainStats: Activity recording
# ---------------------------------------------------------------------------


class TestBrainStatsRecording:
    def test_record_activity_returns_activity(self, brain_stats: BrainStats) -> None:
        activity = brain_stats.record_activity(
            "task_started", "eng-core", "proj_001", "API endpoint"
        )
        assert isinstance(activity, Activity)
        assert activity.activity_type == "task_started"
        assert activity.agent_id == "eng-core"
        assert activity.project_id == "proj_001"
        assert activity.description == "API endpoint"

    def test_record_task_started_increments_count(self, brain_stats: BrainStats) -> None:
        brain_stats.record_activity("task_started", "eng-core")
        brain_stats.record_activity("task_started", "eng-core")
        assert brain_stats._task_counts["eng-core"] == 2

    def test_record_task_started_sets_busy(self, brain_stats: BrainStats) -> None:
        brain_stats.record_activity("task_started", "wp-web", description="Landing page")
        assert brain_stats.get_agent_status("wp-web") == "busy"
        assert brain_stats._agent_current_tasks["wp-web"] == "Landing page"

    def test_record_task_completed_sets_idle(self, brain_stats: BrainStats) -> None:
        brain_stats.record_activity("task_started", "eng-core", description="API")
        brain_stats.record_activity("task_completed", "eng-core")
        assert brain_stats.get_agent_status("eng-core") == "idle"
        assert "eng-core" not in brain_stats._agent_current_tasks

    def test_record_task_failed_sets_error(self, brain_stats: BrainStats) -> None:
        brain_stats.record_activity("task_started", "infra-ops")
        brain_stats.record_activity("task_failed", "infra-ops")
        assert brain_stats.get_agent_status("infra-ops") == "error"

    def test_ring_buffer_max_size(self) -> None:
        stats = BrainStats()
        for i in range(1100):
            stats.record_activity("task_started", "eng-core", description=f"task_{i}")
        assert len(stats._activities) == BrainStats.MAX_ACTIVITIES

    def test_record_updates_last_active(self, brain_stats: BrainStats) -> None:
        brain_stats.record_activity("task_started", "design-lab")
        assert "design-lab" in brain_stats._agent_last_active

    def test_total_tasks_all_time(self, brain_stats: BrainStats) -> None:
        brain_stats.record_activity("task_started", "eng-core")
        brain_stats.record_activity("task_started", "wp-web")
        brain_stats.record_activity("task_started", "eng-core")
        assert brain_stats._total_tasks_all_time == 3


# ---------------------------------------------------------------------------
# BrainStats: Agent status
# ---------------------------------------------------------------------------


class TestBrainStatsAgentStatus:
    def test_default_status_is_idle(self, brain_stats: BrainStats) -> None:
        for agent_id in BRAIN_AGENT_IDS:
            assert brain_stats.get_agent_status(agent_id) == "idle"

    def test_unknown_agent_returns_offline(self, brain_stats: BrainStats) -> None:
        assert brain_stats.get_agent_status("unknown-agent") == "offline"

    def test_set_agent_status(self, brain_stats: BrainStats) -> None:
        brain_stats.set_agent_status("eng-core", "busy")
        assert brain_stats.get_agent_status("eng-core") == "busy"

    def test_set_agent_status_clears_task_on_non_busy(self, brain_stats: BrainStats) -> None:
        brain_stats.record_activity("task_started", "wp-web", description="Test")
        brain_stats.set_agent_status("wp-web", "idle")
        assert "wp-web" not in brain_stats._agent_current_tasks

    def test_set_invalid_status_raises(self, brain_stats: BrainStats) -> None:
        with pytest.raises(ValueError, match="Invalid agent status"):
            brain_stats.set_agent_status("eng-core", "sleeping")


# ---------------------------------------------------------------------------
# BrainStats: Completion time
# ---------------------------------------------------------------------------


class TestBrainStatsCompletionTime:
    def test_record_completion_time(self, brain_stats: BrainStats) -> None:
        brain_stats.record_completion_time(120.5)
        brain_stats.record_completion_time(45.0)
        assert len(brain_stats._completion_times) == 2

    def test_completion_time_trimming(self, brain_stats: BrainStats) -> None:
        for i in range(1100):
            brain_stats.record_completion_time(float(i))
        assert len(brain_stats._completion_times) == 1000


# ---------------------------------------------------------------------------
# BrainStats: Overview
# ---------------------------------------------------------------------------


class TestBrainStatsOverview:
    def test_empty_overview(self, brain_stats: BrainStats) -> None:
        overview = brain_stats.get_overview()
        assert overview["brain"]["status"] == "active"
        assert overview["brain"]["total_tasks_today"] == 0
        assert overview["brain"]["total_tasks_completed"] == 0
        assert overview["brain"]["active_conversations"] == 0
        assert len(overview["agents"]) == 8
        assert overview["projects"] == []
        assert overview["recent_activity"] == []

    def test_overview_with_activity(self, brain_stats: BrainStats) -> None:
        brain_stats.record_activity("task_started", "eng-core", "proj_1", "API work")
        brain_stats.record_activity("task_completed", "eng-core", "proj_1", "API done")
        brain_stats.record_activity("task_started", "wp-web", "proj_2", "Landing page")

        overview = brain_stats.get_overview()
        assert overview["brain"]["total_tasks_today"] == 2
        assert overview["brain"]["total_tasks_completed"] == 1
        assert overview["brain"]["active_conversations"] == 1
        assert len(overview["recent_activity"]) == 3

    def test_overview_with_project_manager(self, brain_stats: BrainStats) -> None:
        from orchestrator.project_manager import ProjectManager

        pm = ProjectManager(max_projects=10)
        loop = asyncio.new_event_loop()
        projects = loop.run_until_complete(pm.seed_defaults())
        loop.close()

        overview = brain_stats.get_overview(project_manager=pm)
        assert overview["brain"]["active_projects"] == 5
        assert len(overview["projects"]) == 5

    def test_overview_with_feedback_loop(
        self, brain_stats: BrainStats, feedback_loop: FeedbackLoop
    ) -> None:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(
            feedback_loop.record_feedback("t1", "eng-core", 4, source="human")
        )
        loop.run_until_complete(
            feedback_loop.record_feedback("t2", "eng-core", 5, source="human")
        )
        loop.close()

        overview = brain_stats.get_overview(feedback_loop=feedback_loop)
        eng = next(a for a in overview["agents"] if a["id"] == "eng-core")
        assert eng["avg_quality_score"] == 4.5

    def test_overview_with_quality_gate(
        self, brain_stats: BrainStats, quality_gate: QualityGate
    ) -> None:
        # Manually set stats
        quality_gate._total_passed = 18
        quality_gate._total_failed = 2

        overview = brain_stats.get_overview(quality_gate=quality_gate)
        assert overview["stats"]["quality_gate_pass_rate"] == 0.9

    def test_overview_avg_completion_time_minutes(self, brain_stats: BrainStats) -> None:
        brain_stats.record_completion_time(720.0)  # 12 minutes
        overview = brain_stats.get_overview()
        assert overview["stats"]["avg_completion_time"] == "12m"

    def test_overview_avg_completion_time_seconds(self, brain_stats: BrainStats) -> None:
        brain_stats.record_completion_time(30.0)
        overview = brain_stats.get_overview()
        assert overview["stats"]["avg_completion_time"] == "30s"

    def test_overview_agents_list_has_8(self, brain_stats: BrainStats) -> None:
        overview = brain_stats.get_overview()
        assert len(overview["agents"]) == 8
        agent_ids = {a["id"] for a in overview["agents"]}
        assert agent_ids == BRAIN_AGENT_IDS


# ---------------------------------------------------------------------------
# BrainStats: Agent detail
# ---------------------------------------------------------------------------


class TestBrainStatsAgentDetail:
    def test_valid_agent_detail(self, brain_stats: BrainStats) -> None:
        brain_stats.record_activity("task_started", "eng-core", description="API work")
        detail = brain_stats.get_agent_detail("eng-core")
        assert detail["id"] == "eng-core"
        assert detail["name"] == "Engineering Agent"
        assert detail["status"] == "busy"
        assert detail["current_task"] == "API work"
        assert detail["tasks_today"] == 1
        assert "capabilities" in detail

    def test_unknown_agent_detail(self, brain_stats: BrainStats) -> None:
        detail = brain_stats.get_agent_detail("nonexistent")
        assert "error" in detail

    def test_agent_detail_with_feedback(
        self, brain_stats: BrainStats, feedback_loop: FeedbackLoop
    ) -> None:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(
            feedback_loop.record_feedback("t1", "wp-web", 3, source="human")
        )
        loop.run_until_complete(
            feedback_loop.record_feedback("t2", "wp-web", 5, source="human")
        )
        loop.close()

        detail = brain_stats.get_agent_detail("wp-web", feedback_loop=feedback_loop)
        assert detail["avg_score"] == 4.0
        assert detail["total_feedback"] == 2
        assert detail["recent_ratings"] == [3, 5]

    def test_agent_detail_recent_activities(self, brain_stats: BrainStats) -> None:
        brain_stats.record_activity("task_started", "eng-core")
        brain_stats.record_activity("task_completed", "eng-core")
        brain_stats.record_activity("task_started", "wp-web")

        detail = brain_stats.get_agent_detail("eng-core")
        assert len(detail["recent_activities"]) == 2


# ---------------------------------------------------------------------------
# BrainStats: Timeline
# ---------------------------------------------------------------------------


class TestBrainStatsTimeline:
    def test_timeline_returns_recent(self, brain_stats: BrainStats) -> None:
        brain_stats.record_activity("task_started", "eng-core")
        brain_stats.record_activity("task_completed", "eng-core")

        timeline = brain_stats.get_timeline(hours=24)
        assert len(timeline) == 2

    def test_timeline_empty(self, brain_stats: BrainStats) -> None:
        timeline = brain_stats.get_timeline(hours=1)
        assert timeline == []

    def test_timeline_ordering(self, brain_stats: BrainStats) -> None:
        brain_stats.record_activity("task_started", "eng-core", description="first")
        brain_stats.record_activity("task_completed", "eng-core", description="second")

        timeline = brain_stats.get_timeline(hours=24)
        # Newest first
        assert timeline[0]["description"] == "second"
        assert timeline[1]["description"] == "first"


# ---------------------------------------------------------------------------
# BrainStats: Metrics
# ---------------------------------------------------------------------------


class TestBrainStatsMetrics:
    def test_metrics_structure(self, brain_stats: BrainStats) -> None:
        metrics = brain_stats.get_metrics()
        assert "agent_performance" in metrics
        assert "completion_time_distribution" in metrics
        assert "quality_distribution" in metrics
        assert "total_tasks_all_time" in metrics
        assert len(metrics["agent_performance"]) == 8

    def test_metrics_completion_time_buckets(self, brain_stats: BrainStats) -> None:
        brain_stats.record_completion_time(30.0)    # under 1m
        brain_stats.record_completion_time(120.0)   # 1m-5m
        brain_stats.record_completion_time(600.0)   # 5m-15m
        brain_stats.record_completion_time(1200.0)  # 15m-30m
        brain_stats.record_completion_time(3600.0)  # over 30m

        metrics = brain_stats.get_metrics()
        dist = metrics["completion_time_distribution"]
        assert dist["under_1m"] == 1
        assert dist["1m_5m"] == 1
        assert dist["5m_15m"] == 1
        assert dist["15m_30m"] == 1
        assert dist["over_30m"] == 1


# ---------------------------------------------------------------------------
# Activity dataclass
# ---------------------------------------------------------------------------


class TestActivity:
    def test_to_dict(self) -> None:
        now = datetime.now(timezone.utc)
        activity = Activity(
            timestamp=now,
            activity_type="task_completed",
            agent_id="wp-web",
            project_id="proj_001",
            description="Landing page update",
        )
        d = activity.to_dict()
        assert d["type"] == "task_completed"
        assert d["agent"] == "wp-web"
        assert d["project"] == "proj_001"
        assert d["description"] == "Landing page update"
        assert "timestamp" in d


# ---------------------------------------------------------------------------
# Telegram formatter
# ---------------------------------------------------------------------------


class TestTelegramFormatter:
    def test_format_empty_overview(self, brain_stats: BrainStats) -> None:
        overview = brain_stats.get_overview()
        msg = format_telegram_status(overview)
        assert "Brian the Brain" in msg
        assert "Ma: 0 feladat" in msg
        assert "Agentek:" in msg

    def test_format_with_activity(self, brain_stats: BrainStats) -> None:
        brain_stats.record_activity("task_started", "wp-web", description="azar.hu landing")
        brain_stats.record_activity("task_started", "content-forge", description="blog cikk")

        from orchestrator.project_manager import ProjectManager
        pm = ProjectManager(max_projects=10)
        loop = asyncio.new_event_loop()
        loop.run_until_complete(pm.seed_defaults())
        loop.close()

        overview = brain_stats.get_overview(project_manager=pm)
        msg = format_telegram_status(overview)

        assert "wp-web" in msg
        assert "busy" in msg
        assert "azar.hu landing" in msg
        assert "content-forge" in msg
        assert "blog cikk" in msg
        assert "2 feladat" in msg  # 2 tasks today

    def test_format_all_agents_present(self, brain_stats: BrainStats) -> None:
        overview = brain_stats.get_overview()
        msg = format_telegram_status(overview)
        for agent in BRAIN_AGENTS:
            assert agent["id"] in msg

    def test_format_projects_section(self, brain_stats: BrainStats) -> None:
        from orchestrator.project_manager import ProjectManager
        pm = ProjectManager(max_projects=10)
        loop = asyncio.new_event_loop()
        loop.run_until_complete(pm.seed_defaults())
        loop.close()

        overview = brain_stats.get_overview(project_manager=pm)
        msg = format_telegram_status(overview)
        assert "projektek: 5" in msg.lower() or "projektek: 5" in msg


# ---------------------------------------------------------------------------
# Telegram status command detection
# ---------------------------------------------------------------------------


class TestIsStatusCommand:
    @pytest.mark.parametrize("cmd", [
        "status", "Status", "STATUS",
        "st\u00e1tusz", "St\u00e1tusz",
        "staatusz", "STAATUSZ",
        "mi a helyzet", "Mi a helyzet",
        "brain status", "Brain Status",
        "dashboard", "Dashboard",
    ])
    def test_recognized_commands(self, cmd: str) -> None:
        assert is_status_command(cmd) is True

    @pytest.mark.parametrize("cmd", [
        "hello", "help", "k\u00f6sz\u00f6n\u00f6m", "feladat",
        "status check", "get status", "",
    ])
    def test_unrecognized_commands(self, cmd: str) -> None:
        assert is_status_command(cmd) is False

    def test_whitespace_stripping(self) -> None:
        assert is_status_command("  status  ") is True
        assert is_status_command("\tstatus\n") is True


# ---------------------------------------------------------------------------
# BRAIN_AGENTS constant
# ---------------------------------------------------------------------------


class TestBrainAgentsConstant:
    def test_eight_agents(self) -> None:
        assert len(BRAIN_AGENTS) == 8

    def test_agent_ids_unique(self) -> None:
        ids = [a["id"] for a in BRAIN_AGENTS]
        assert len(ids) == len(set(ids))

    def test_expected_agent_ids(self) -> None:
        expected = {
            "eng-core", "wp-web", "infra-ops", "design-lab",
            "content-forge", "social-growth", "intel-research", "biz-strategy",
        }
        assert BRAIN_AGENT_IDS == expected


# ---------------------------------------------------------------------------
# Dashboard API endpoints (integration with real app)
# ---------------------------------------------------------------------------


@pytest.fixture
async def dashboard_client(tmp_path):
    """Create test client with dashboard router registered."""
    db_path = tmp_path / "test_dashboard.db"
    os.environ["OCCP_DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"
    os.environ["OCCP_ADMIN_USER"] = "testadmin"
    os.environ["OCCP_ADMIN_PASSWORD"] = "testpass123"
    try:
        from api.app import create_app
        app = create_app()
        async with app.router.lifespan_context(app):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                yield ac
    finally:
        os.environ.pop("OCCP_DATABASE_URL", None)
        os.environ.pop("OCCP_ADMIN_USER", None)
        os.environ.pop("OCCP_ADMIN_PASSWORD", None)


async def _get_token(client: AsyncClient) -> str:
    resp = await client.post("/api/v1/auth/login", json={
        "username": "testadmin",
        "password": "testpass123",
    })
    assert resp.status_code == 200
    return resp.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class TestDashboardAPI:
    @pytest.mark.asyncio
    async def test_overview_endpoint(self, dashboard_client: AsyncClient) -> None:
        token = await _get_token(dashboard_client)
        resp = await dashboard_client.get(
            "/api/v1/dashboard/overview", headers=_auth(token)
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "brain" in data
        assert "agents" in data
        assert "projects" in data
        assert "recent_activity" in data
        assert "stats" in data
        assert data["brain"]["status"] == "active"
        assert len(data["agents"]) == 8

    @pytest.mark.asyncio
    async def test_agent_detail_endpoint(self, dashboard_client: AsyncClient) -> None:
        token = await _get_token(dashboard_client)
        resp = await dashboard_client.get(
            "/api/v1/dashboard/agent/eng-core", headers=_auth(token)
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "eng-core"
        assert data["name"] == "Engineering Agent"
        assert "capabilities" in data

    @pytest.mark.asyncio
    async def test_agent_detail_404(self, dashboard_client: AsyncClient) -> None:
        token = await _get_token(dashboard_client)
        resp = await dashboard_client.get(
            "/api/v1/dashboard/agent/nonexistent", headers=_auth(token)
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_timeline_endpoint(self, dashboard_client: AsyncClient) -> None:
        token = await _get_token(dashboard_client)
        resp = await dashboard_client.get(
            "/api/v1/dashboard/timeline", headers=_auth(token)
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "hours" in data
        assert data["hours"] == 24
        assert "total" in data
        assert "activities" in data

    @pytest.mark.asyncio
    async def test_timeline_custom_hours(self, dashboard_client: AsyncClient) -> None:
        token = await _get_token(dashboard_client)
        resp = await dashboard_client.get(
            "/api/v1/dashboard/timeline?hours=6", headers=_auth(token)
        )
        assert resp.status_code == 200
        assert resp.json()["hours"] == 6

    @pytest.mark.asyncio
    async def test_metrics_endpoint(self, dashboard_client: AsyncClient) -> None:
        token = await _get_token(dashboard_client)
        resp = await dashboard_client.get(
            "/api/v1/dashboard/metrics", headers=_auth(token)
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "agent_performance" in data
        assert "completion_time_distribution" in data
        assert "quality_distribution" in data
        assert len(data["agent_performance"]) == 8

    @pytest.mark.asyncio
    async def test_telegram_endpoint(self, dashboard_client: AsyncClient) -> None:
        token = await _get_token(dashboard_client)
        resp = await dashboard_client.get(
            "/api/v1/dashboard/telegram", headers=_auth(token)
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "message" in data
        assert "Brian the Brain" in data["message"]
        assert "Agentek:" in data["message"]

    @pytest.mark.asyncio
    async def test_unauthenticated_returns_401(self, dashboard_client: AsyncClient) -> None:
        resp = await dashboard_client.get("/api/v1/dashboard/overview")
        assert resp.status_code in (401, 403)
