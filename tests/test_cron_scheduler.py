"""Tests for Cron Scheduler — orchestrator/cron_scheduler.py.

Covers:
- TriggerType enum values
- CronExpression parsing (various formats)
- CronExpression.matches() against datetimes
- CronExpression.next_run() calculation
- Edge cases: */5, 1-5, 1,3,5, wildcards, step in range
- TriggerConfig creation
- ScheduledJob creation and serialization
- JobExecution creation
- CronScheduler add/remove/pause/resume jobs
- check_and_fire() with simulated time
- fire_trigger() manual firing
- Execution history tracking
- Error types
- Acceptance tests (5 scenarios)
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock

import pytest

from orchestrator.cron_scheduler import (
    CronError,
    CronExpression,
    CronParseError,
    CronScheduler,
    JobExecution,
    JobNotFoundError,
    ScheduledJob,
    TriggerConfig,
    TriggerError,
    TriggerType,
    _parse_cron_field,
)
from orchestrator.models import AgentConfig
from orchestrator.scheduler import Scheduler


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_scheduler(return_value: Any = {"result": "ok"}) -> Scheduler:
    scheduler = Scheduler()
    factory = AsyncMock(return_value=return_value)
    config = AgentConfig(
        agent_type="cron-agent",
        display_name="Cron Agent",
        max_concurrent=10,
    )
    scheduler.register(config, factory)
    return scheduler


def _dt(year: int, month: int, day: int, hour: int, minute: int) -> datetime:
    """Create a UTC datetime."""
    return datetime(year, month, day, hour, minute, 0, tzinfo=timezone.utc)


def _make_job(
    job_id: str = "job-1",
    cron_expr_str: str | None = "*/5 * * * *",
    trigger_type: TriggerType = TriggerType.CRON,
    enabled: bool = True,
    next_run: datetime | None = None,
    agent_type: str = "cron-agent",
) -> ScheduledJob:
    cron_expr = CronExpression.from_string(cron_expr_str) if cron_expr_str else None
    trigger = TriggerConfig(
        trigger_id=f"trigger-{job_id}",
        name=f"Trigger {job_id}",
        trigger_type=trigger_type,
        cron_expr=cron_expr,
    )
    return ScheduledJob(
        job_id=job_id,
        name=f"Job {job_id}",
        trigger=trigger,
        task_template={"name": f"task-{job_id}", "description": "test"},
        agent_type=agent_type,
        enabled=enabled,
        next_run=next_run,
    )


def _make_webhook_job(job_id: str = "wh-job") -> ScheduledJob:
    trigger = TriggerConfig(
        trigger_id=f"trigger-{job_id}",
        name=f"Webhook {job_id}",
        trigger_type=TriggerType.WEBHOOK,
    )
    return ScheduledJob(
        job_id=job_id,
        name=f"Webhook Job {job_id}",
        trigger=trigger,
        task_template={"name": f"wh-task-{job_id}", "description": "webhook"},
        agent_type="cron-agent",
    )


# ---------------------------------------------------------------------------
# TestTriggerType
# ---------------------------------------------------------------------------


class TestTriggerType:
    def test_values(self) -> None:
        assert TriggerType.CRON == "cron"
        assert TriggerType.WEBHOOK == "webhook"
        assert TriggerType.EVENT == "event"
        assert TriggerType.INTERVAL == "interval"

    def test_four_types(self) -> None:
        assert len(TriggerType) == 4

    def test_is_str_enum(self) -> None:
        assert isinstance(TriggerType.CRON, str)


# ---------------------------------------------------------------------------
# TestCronParsing
# ---------------------------------------------------------------------------


class TestCronParsing:
    def test_wildcard_all(self) -> None:
        result = _parse_cron_field("*", 0, 59)
        assert len(result) == 60
        assert 0 in result
        assert 59 in result

    def test_single_value(self) -> None:
        result = _parse_cron_field("5", 0, 59)
        assert result == {5}

    def test_range(self) -> None:
        result = _parse_cron_field("1-5", 0, 59)
        assert result == {1, 2, 3, 4, 5}

    def test_list(self) -> None:
        result = _parse_cron_field("1,3,5", 0, 59)
        assert result == {1, 3, 5}

    def test_step_wildcard(self) -> None:
        result = _parse_cron_field("*/5", 0, 59)
        assert 0 in result
        assert 5 in result
        assert 10 in result
        assert 55 in result
        assert 3 not in result

    def test_step_from_value(self) -> None:
        result = _parse_cron_field("2/10", 0, 59)
        assert 2 in result
        assert 12 in result

    def test_range_with_step(self) -> None:
        result = _parse_cron_field("0-30/10", 0, 59)
        assert result == {0, 10, 20, 30}

    def test_invalid_value_raises(self) -> None:
        with pytest.raises(CronParseError):
            _parse_cron_field("abc", 0, 59)

    def test_out_of_range_raises(self) -> None:
        with pytest.raises(CronParseError):
            _parse_cron_field("60", 0, 59)

    def test_range_reversed_raises(self) -> None:
        with pytest.raises(CronParseError):
            _parse_cron_field("10-5", 0, 59)

    def test_zero_step_raises(self) -> None:
        with pytest.raises(CronParseError):
            _parse_cron_field("*/0", 0, 59)


# ---------------------------------------------------------------------------
# TestCronExpression
# ---------------------------------------------------------------------------


class TestCronExpression:
    def test_parse_all_wildcards(self) -> None:
        expr = CronExpression.from_string("* * * * *")
        assert len(expr.minute) == 60
        assert len(expr.hour) == 24
        assert len(expr.day_of_month) == 31
        assert len(expr.month) == 12
        assert len(expr.day_of_week) == 7

    def test_parse_specific(self) -> None:
        expr = CronExpression.from_string("30 9 * * *")
        assert expr.minute == frozenset({30})
        assert expr.hour == frozenset({9})

    def test_parse_every_5_minutes(self) -> None:
        expr = CronExpression.from_string("*/5 * * * *")
        assert 0 in expr.minute
        assert 5 in expr.minute
        assert 55 in expr.minute
        assert 3 not in expr.minute

    def test_parse_weekdays_only(self) -> None:
        # 0=Sunday, 1=Monday, ..., 5=Friday in cron
        expr = CronExpression.from_string("0 9 * * 1-5")
        assert 1 in expr.day_of_week
        assert 5 in expr.day_of_week
        assert 0 not in expr.day_of_week
        assert 6 not in expr.day_of_week

    def test_parse_wrong_fields_raises(self) -> None:
        with pytest.raises(CronParseError):
            CronExpression.from_string("* * *")

    def test_parse_too_many_fields_raises(self) -> None:
        with pytest.raises(CronParseError):
            CronExpression.from_string("* * * * * *")

    def test_raw_preserved(self) -> None:
        raw = "*/15 6-18 * * 1-5"
        expr = CronExpression.from_string(raw)
        assert expr.raw == raw

    def test_frozen(self) -> None:
        expr = CronExpression.from_string("* * * * *")
        with pytest.raises((AttributeError, TypeError)):
            expr.minute = frozenset()  # type: ignore[misc]


# ---------------------------------------------------------------------------
# TestCronMatching
# ---------------------------------------------------------------------------


class TestCronMatching:
    def test_wildcard_matches_any(self) -> None:
        expr = CronExpression.from_string("* * * * *")
        assert expr.matches(_dt(2026, 1, 15, 10, 30))

    def test_specific_minute_matches(self) -> None:
        expr = CronExpression.from_string("30 * * * *")
        assert expr.matches(_dt(2026, 1, 15, 10, 30))
        assert not expr.matches(_dt(2026, 1, 15, 10, 31))

    def test_specific_hour_matches(self) -> None:
        expr = CronExpression.from_string("0 9 * * *")
        assert expr.matches(_dt(2026, 1, 15, 9, 0))
        assert not expr.matches(_dt(2026, 1, 15, 10, 0))

    def test_every_5_minutes_match(self) -> None:
        expr = CronExpression.from_string("*/5 * * * *")
        assert expr.matches(_dt(2026, 1, 15, 10, 0))
        assert expr.matches(_dt(2026, 1, 15, 10, 5))
        assert expr.matches(_dt(2026, 1, 15, 10, 55))
        assert not expr.matches(_dt(2026, 1, 15, 10, 3))

    def test_weekday_monday(self) -> None:
        # 2026-03-02 is a Monday: Python weekday() = 0 → cron_dow = 1
        expr = CronExpression.from_string("0 9 * * 1")  # Monday in cron
        assert expr.matches(_dt(2026, 3, 2, 9, 0))

    def test_weekday_sunday(self) -> None:
        # 2026-03-01 is a Sunday: Python weekday() = 6 → cron_dow = 0
        expr = CronExpression.from_string("0 9 * * 0")  # Sunday in cron
        assert expr.matches(_dt(2026, 3, 1, 9, 0))

    def test_specific_dom_matches(self) -> None:
        expr = CronExpression.from_string("0 0 15 * *")
        assert expr.matches(_dt(2026, 3, 15, 0, 0))
        assert not expr.matches(_dt(2026, 3, 16, 0, 0))

    def test_specific_month_matches(self) -> None:
        expr = CronExpression.from_string("0 0 1 6 *")
        assert expr.matches(_dt(2026, 6, 1, 0, 0))
        assert not expr.matches(_dt(2026, 7, 1, 0, 0))

    def test_complex_expression_matches(self) -> None:
        # Every 15 minutes during business hours on weekdays
        expr = CronExpression.from_string("*/15 9-17 * * 1-5")
        # 2026-03-02 10:15 Monday — should match
        assert expr.matches(_dt(2026, 3, 2, 10, 15))
        # 2026-03-02 10:16 — should not match
        assert not expr.matches(_dt(2026, 3, 2, 10, 16))


# ---------------------------------------------------------------------------
# TestNextRun
# ---------------------------------------------------------------------------


class TestNextRun:
    def test_next_run_minute_boundary(self) -> None:
        expr = CronExpression.from_string("*/5 * * * *")
        after = _dt(2026, 1, 1, 0, 0)  # Exactly minute 0
        nxt = expr.next_run(after)
        assert nxt.minute == 5
        assert nxt.hour == 0

    def test_next_run_skips_to_next_hour(self) -> None:
        expr = CronExpression.from_string("0 * * * *")
        after = _dt(2026, 1, 1, 10, 1)  # Past the :00 mark for this hour
        nxt = expr.next_run(after)
        assert nxt.hour == 11
        assert nxt.minute == 0

    def test_next_run_daily(self) -> None:
        expr = CronExpression.from_string("0 9 * * *")
        after = _dt(2026, 1, 1, 9, 0)  # Same time today
        nxt = expr.next_run(after)
        assert nxt.hour == 9
        assert nxt.minute == 0
        assert nxt.day == 2  # Next day

    def test_next_run_strictly_after(self) -> None:
        """next_run is STRICTLY after 'after', never equal."""
        expr = CronExpression.from_string("* * * * *")
        after = _dt(2026, 1, 1, 12, 30)
        nxt = expr.next_run(after)
        assert nxt > after

    def test_next_run_list_expression(self) -> None:
        expr = CronExpression.from_string("0,30 * * * *")
        after = _dt(2026, 1, 1, 10, 0)
        nxt = expr.next_run(after)
        assert nxt.minute == 30
        assert nxt.hour == 10

    def test_next_run_month_boundary(self) -> None:
        expr = CronExpression.from_string("0 0 1 * *")
        after = _dt(2026, 2, 1, 0, 0)
        nxt = expr.next_run(after)
        assert nxt.day == 1
        assert nxt.month == 3


# ---------------------------------------------------------------------------
# TestTriggerConfig
# ---------------------------------------------------------------------------


class TestTriggerConfig:
    def test_creation(self) -> None:
        trigger = TriggerConfig(
            trigger_id="t-1",
            name="My Trigger",
            trigger_type=TriggerType.CRON,
        )
        assert trigger.trigger_id == "t-1"
        assert trigger.name == "My Trigger"
        assert trigger.trigger_type == TriggerType.CRON
        assert trigger.enabled is True
        assert trigger.cron_expr is None

    def test_with_cron_expr(self) -> None:
        expr = CronExpression.from_string("*/5 * * * *")
        trigger = TriggerConfig(
            trigger_id="t-2",
            name="Every 5 Min",
            trigger_type=TriggerType.CRON,
            cron_expr=expr,
        )
        assert trigger.cron_expr is expr

    def test_interval_trigger(self) -> None:
        trigger = TriggerConfig(
            trigger_id="t-3",
            name="Interval",
            trigger_type=TriggerType.INTERVAL,
            interval_seconds=300,
        )
        assert trigger.interval_seconds == 300

    def test_webhook_with_event_filter(self) -> None:
        trigger = TriggerConfig(
            trigger_id="t-4",
            name="Webhook",
            trigger_type=TriggerType.WEBHOOK,
            event_filter={"event_type": "push"},
        )
        assert trigger.event_filter == {"event_type": "push"}


# ---------------------------------------------------------------------------
# TestScheduledJob
# ---------------------------------------------------------------------------


class TestScheduledJob:
    def test_creation(self) -> None:
        job = _make_job("job-x")
        assert job.job_id == "job-x"
        assert job.enabled is True
        assert job.run_count == 0
        assert job.error_count == 0

    def test_to_dict(self) -> None:
        job = _make_job("j1")
        d = job.to_dict()
        assert d["job_id"] == "j1"
        assert d["enabled"] is True
        assert "trigger_type" in d
        assert "task_template" in d

    def test_from_dict_roundtrip(self) -> None:
        job = _make_job("j2")
        d = job.to_dict()
        # from_dict is a basic reconstruction
        job2 = ScheduledJob.from_dict(d)
        assert job2.job_id == "j2"
        assert job2.agent_type == "cron-agent"

    def test_disabled_job(self) -> None:
        job = _make_job("j-disabled", enabled=False)
        assert job.enabled is False


# ---------------------------------------------------------------------------
# TestJobExecution
# ---------------------------------------------------------------------------


class TestJobExecution:
    def test_creation(self) -> None:
        now = datetime.now(timezone.utc)
        je = JobExecution(
            execution_id="exec-1",
            job_id="job-1",
            trigger_type=TriggerType.CRON,
            started_at=now,
        )
        assert je.execution_id == "exec-1"
        assert je.job_id == "job-1"
        assert je.success is False
        assert je.finished_at is None

    def test_to_dict(self) -> None:
        now = datetime.now(timezone.utc)
        je = JobExecution(
            execution_id="exec-2",
            job_id="job-2",
            trigger_type=TriggerType.WEBHOOK,
            started_at=now,
            success=True,
            task_id="task-abc",
        )
        d = je.to_dict()
        assert d["success"] is True
        assert d["trigger_type"] == "webhook"
        assert d["task_id"] == "task-abc"


# ---------------------------------------------------------------------------
# TestCronScheduler
# ---------------------------------------------------------------------------


class TestCronScheduler:
    def test_add_job(self) -> None:
        scheduler = _make_scheduler()
        cs = CronScheduler(scheduler)
        job = _make_job()
        cs.add_job(job)
        assert cs.get_job("job-1") is job

    def test_add_job_computes_next_run(self) -> None:
        scheduler = _make_scheduler()
        cs = CronScheduler(scheduler)
        job = _make_job(next_run=None)
        cs.add_job(job)
        assert job.next_run is not None

    def test_remove_job(self) -> None:
        scheduler = _make_scheduler()
        cs = CronScheduler(scheduler)
        job = _make_job()
        cs.add_job(job)
        result = cs.remove_job("job-1")
        assert result is True
        assert cs.get_job("job-1") is None

    def test_remove_nonexistent_job(self) -> None:
        cs = CronScheduler(_make_scheduler())
        result = cs.remove_job("no-such-job")
        assert result is False

    def test_pause_job(self) -> None:
        scheduler = _make_scheduler()
        cs = CronScheduler(scheduler)
        job = _make_job()
        cs.add_job(job)
        cs.pause_job("job-1")
        assert cs.get_job("job-1").enabled is False

    def test_resume_job(self) -> None:
        scheduler = _make_scheduler()
        cs = CronScheduler(scheduler)
        job = _make_job(enabled=False)
        cs.add_job(job)
        cs.resume_job("job-1")
        assert cs.get_job("job-1").enabled is True

    def test_pause_nonexistent_raises(self) -> None:
        cs = CronScheduler(_make_scheduler())
        with pytest.raises(JobNotFoundError):
            cs.pause_job("nope")

    def test_resume_nonexistent_raises(self) -> None:
        cs = CronScheduler(_make_scheduler())
        with pytest.raises(JobNotFoundError):
            cs.resume_job("nope")

    def test_list_jobs_all(self) -> None:
        scheduler = _make_scheduler()
        cs = CronScheduler(scheduler)
        cs.add_job(_make_job("j1"))
        cs.add_job(_make_job("j2", enabled=False))
        jobs = cs.list_jobs()
        assert len(jobs) == 2

    def test_list_jobs_enabled_only(self) -> None:
        scheduler = _make_scheduler()
        cs = CronScheduler(scheduler)
        cs.add_job(_make_job("j1"))
        cs.add_job(_make_job("j2", enabled=False))
        jobs = cs.list_jobs(enabled_only=True)
        assert len(jobs) == 1
        assert jobs[0].job_id == "j1"

    def test_get_job_none_when_missing(self) -> None:
        cs = CronScheduler(_make_scheduler())
        assert cs.get_job("missing") is None

    def test_initial_stats(self) -> None:
        cs = CronScheduler(_make_scheduler())
        stats = cs.get_stats()
        assert stats["total_jobs"] == 0
        assert stats["total_fired"] == 0


# ---------------------------------------------------------------------------
# TestCheckAndFire
# ---------------------------------------------------------------------------


class TestCheckAndFire:
    @pytest.mark.asyncio
    async def test_due_job_fires(self) -> None:
        scheduler = _make_scheduler()
        cs = CronScheduler(scheduler)

        past = _dt(2026, 1, 1, 10, 0) - timedelta(minutes=1)
        job = _make_job("j1", next_run=past)
        job.next_run = past  # Override next_run directly
        cs.add_job(job)

        now = _dt(2026, 1, 1, 10, 0)
        executions = await cs.check_and_fire(now)
        assert len(executions) == 1
        assert executions[0].job_id == "j1"

    @pytest.mark.asyncio
    async def test_future_job_does_not_fire(self) -> None:
        scheduler = _make_scheduler()
        cs = CronScheduler(scheduler)

        future = _dt(2026, 1, 1, 10, 5)
        job = _make_job("j2", next_run=future)
        job.next_run = future
        cs.add_job(job)

        now = _dt(2026, 1, 1, 10, 0)
        executions = await cs.check_and_fire(now)
        assert len(executions) == 0

    @pytest.mark.asyncio
    async def test_disabled_job_does_not_fire(self) -> None:
        scheduler = _make_scheduler()
        cs = CronScheduler(scheduler)

        past = _dt(2026, 1, 1, 9, 55)
        job = _make_job("j3", enabled=False, next_run=past)
        job.next_run = past
        cs.add_job(job)

        now = _dt(2026, 1, 1, 10, 0)
        executions = await cs.check_and_fire(now)
        assert len(executions) == 0

    @pytest.mark.asyncio
    async def test_next_run_updated_after_fire(self) -> None:
        scheduler = _make_scheduler()
        cs = CronScheduler(scheduler)

        past = _dt(2026, 1, 1, 9, 55)
        job = _make_job("j4", cron_expr_str="*/5 * * * *", next_run=past)
        job.next_run = past
        cs.add_job(job)

        now = _dt(2026, 1, 1, 10, 0)
        await cs.check_and_fire(now)

        # next_run should be updated to next matching time after now
        assert job.next_run is not None
        assert job.next_run > now

    @pytest.mark.asyncio
    async def test_multiple_jobs_fire(self) -> None:
        scheduler = _make_scheduler()
        cs = CronScheduler(scheduler)

        past = _dt(2026, 1, 1, 9, 55)
        for i in range(3):
            job = _make_job(f"j{i}", next_run=past)
            job.next_run = past
            cs.add_job(job)

        now = _dt(2026, 1, 1, 10, 0)
        executions = await cs.check_and_fire(now)
        assert len(executions) == 3


# ---------------------------------------------------------------------------
# TestManualTrigger
# ---------------------------------------------------------------------------


class TestManualTrigger:
    @pytest.mark.asyncio
    async def test_fire_trigger_by_id(self) -> None:
        scheduler = _make_scheduler()
        cs = CronScheduler(scheduler)

        job = _make_webhook_job("wh1")
        cs.add_job(job)

        execution = await cs.fire_trigger("trigger-wh1")
        assert execution.job_id == "wh1"
        assert execution.success is True

    @pytest.mark.asyncio
    async def test_fire_trigger_not_found_raises(self) -> None:
        cs = CronScheduler(_make_scheduler())
        with pytest.raises(TriggerError):
            await cs.fire_trigger("no-such-trigger")

    @pytest.mark.asyncio
    async def test_fire_trigger_disabled_job_raises(self) -> None:
        scheduler = _make_scheduler()
        cs = CronScheduler(scheduler)

        job = _make_webhook_job("wh2")
        job.enabled = False
        cs.add_job(job)

        with pytest.raises(TriggerError):
            await cs.fire_trigger("trigger-wh2")

    @pytest.mark.asyncio
    async def test_fire_trigger_with_event_data(self) -> None:
        captured: list[Any] = []

        async def capture_factory(config: Any, task: Any) -> dict[str, Any]:
            captured.append(task)
            return {"result": "ok"}

        scheduler = Scheduler()
        config = AgentConfig(
            agent_type="cron-agent",
            display_name="Capture",
            max_concurrent=10,
        )
        scheduler.register(config, capture_factory)

        cs = CronScheduler(scheduler)
        job = _make_webhook_job("wh3")
        cs.add_job(job)

        event_data = {"payload": "test-event", "source": "github"}
        await cs.fire_trigger("trigger-wh3", event_data=event_data)

        assert len(captured) == 1
        assert captured[0].metadata["_event_data"] == event_data

    @pytest.mark.asyncio
    async def test_fire_trigger_increments_run_count(self) -> None:
        scheduler = _make_scheduler()
        cs = CronScheduler(scheduler)

        job = _make_webhook_job("wh4")
        cs.add_job(job)

        await cs.fire_trigger("trigger-wh4")
        await cs.fire_trigger("trigger-wh4")

        assert job.run_count == 2


# ---------------------------------------------------------------------------
# TestJobHistory
# ---------------------------------------------------------------------------


class TestJobHistory:
    @pytest.mark.asyncio
    async def test_history_tracked(self) -> None:
        scheduler = _make_scheduler()
        cs = CronScheduler(scheduler)
        job = _make_webhook_job("h1")
        cs.add_job(job)

        await cs.fire_trigger("trigger-h1")
        history = cs.get_job_history("h1")
        assert len(history) == 1
        assert history[0].job_id == "h1"

    @pytest.mark.asyncio
    async def test_history_most_recent_first(self) -> None:
        scheduler = _make_scheduler()
        cs = CronScheduler(scheduler)
        job = _make_webhook_job("h2")
        cs.add_job(job)

        await cs.fire_trigger("trigger-h2")
        await cs.fire_trigger("trigger-h2")

        history = cs.get_job_history("h2", limit=2)
        assert len(history) == 2
        # Most recent first
        assert history[0].started_at >= history[1].started_at

    @pytest.mark.asyncio
    async def test_history_limit_respected(self) -> None:
        scheduler = _make_scheduler()
        cs = CronScheduler(scheduler)
        job = _make_webhook_job("h3")
        cs.add_job(job)

        for _ in range(10):
            await cs.fire_trigger("trigger-h3")

        history = cs.get_job_history("h3", limit=5)
        assert len(history) == 5

    def test_history_not_found_raises(self) -> None:
        cs = CronScheduler(_make_scheduler())
        with pytest.raises(JobNotFoundError):
            cs.get_job_history("nonexistent")

    @pytest.mark.asyncio
    async def test_stats_reflect_history(self) -> None:
        scheduler = _make_scheduler()
        cs = CronScheduler(scheduler)
        job = _make_webhook_job("h4")
        cs.add_job(job)

        await cs.fire_trigger("trigger-h4")
        await cs.fire_trigger("trigger-h4")

        stats = cs.get_stats()
        assert stats["total_fired"] == 2
        assert stats["total_succeeded"] == 2
        assert stats["total_failed"] == 0


# ---------------------------------------------------------------------------
# TestCronErrors
# ---------------------------------------------------------------------------


class TestCronErrors:
    def test_cron_parse_error(self) -> None:
        exc = CronParseError("bad expr", "too many fields")
        assert exc.expression == "bad expr"
        assert exc.reason == "too many fields"
        assert "bad expr" in str(exc)

    def test_job_not_found_error(self) -> None:
        exc = JobNotFoundError("job-xyz")
        assert exc.job_id == "job-xyz"
        assert "job-xyz" in str(exc)

    def test_trigger_error(self) -> None:
        exc = TriggerError("trigger-1", "no handler")
        assert exc.trigger_id == "trigger-1"
        assert "no handler" in str(exc)

    def test_cron_error_is_base(self) -> None:
        from orchestrator.exceptions import OccpError
        exc = CronError("base error")
        assert isinstance(exc, OccpError)

    def test_parse_error_inheritance(self) -> None:
        exc = CronParseError("e", "r")
        assert isinstance(exc, CronError)


# ---------------------------------------------------------------------------
# TestAcceptanceCron
# ---------------------------------------------------------------------------


class TestAcceptanceCron:
    """5 acceptance tests for CronScheduler."""

    @pytest.mark.asyncio
    async def test_acc_1_cron_every_5_min_fires_correctly(self) -> None:
        """*/5 * * * * fires at :00, :05, :10, ... and not at :01, :03 etc."""
        fired_at: list[datetime] = []

        async def recording_factory(config: Any, task: Any) -> dict[str, Any]:
            return {"result": "ok"}

        scheduler = Scheduler()
        config = AgentConfig(
            agent_type="cron-agent",
            display_name="Recording",
            max_concurrent=10,
        )
        scheduler.register(config, recording_factory)

        cs = CronScheduler(scheduler)
        expr = CronExpression.from_string("*/5 * * * *")

        base = _dt(2026, 3, 2, 10, 0)
        # Verify expression matches :00, :05, :10 but not :01, :03
        assert expr.matches(base.replace(minute=0))
        assert expr.matches(base.replace(minute=5))
        assert expr.matches(base.replace(minute=10))
        assert not expr.matches(base.replace(minute=1))
        assert not expr.matches(base.replace(minute=3))
        assert not expr.matches(base.replace(minute=7))

    @pytest.mark.asyncio
    async def test_acc_2_paused_job_not_fired_then_resumed(self) -> None:
        """Paused job: check_and_fire does not fire it. After resume, fires again."""
        scheduler = _make_scheduler()
        cs = CronScheduler(scheduler)

        past = _dt(2026, 1, 1, 9, 55)
        job = _make_job("pause-job", next_run=past)
        job.next_run = past
        cs.add_job(job)

        # Pause the job
        cs.pause_job("pause-job")
        now = _dt(2026, 1, 1, 10, 0)
        executions = await cs.check_and_fire(now)
        # Should NOT fire
        assert len(executions) == 0
        assert job.run_count == 0

        # Resume
        cs.resume_job("pause-job")
        # Set next_run to past again to ensure it fires
        job.next_run = past
        executions2 = await cs.check_and_fire(now)
        assert len(executions2) == 1
        assert executions2[0].success is True

    @pytest.mark.asyncio
    async def test_acc_3_webhook_trigger_fires_on_event(self) -> None:
        """Webhook trigger: fire_trigger sends event_data to the task."""
        received_data: list[dict[str, Any]] = []

        async def webhook_factory(config: Any, task: Any) -> dict[str, Any]:
            received_data.append(task.metadata.get("_event_data", {}))
            return {"processed": True}

        scheduler = Scheduler()
        config = AgentConfig(
            agent_type="cron-agent",
            display_name="Webhook",
            max_concurrent=10,
        )
        scheduler.register(config, webhook_factory)

        cs = CronScheduler(scheduler)
        job = _make_webhook_job("webhook-acc")
        cs.add_job(job)

        event_payload = {"ref": "refs/heads/main", "pusher": "henry"}
        execution = await cs.fire_trigger("trigger-webhook-acc", event_data=event_payload)

        assert execution.success is True
        assert len(received_data) == 1
        assert received_data[0]["ref"] == "refs/heads/main"
        assert received_data[0]["pusher"] == "henry"

    @pytest.mark.asyncio
    async def test_acc_4_execution_history_tracked_per_job(self) -> None:
        """Each job maintains its own execution history."""
        scheduler = _make_scheduler()
        cs = CronScheduler(scheduler)

        job_a = _make_webhook_job("hist-a")
        job_b = _make_webhook_job("hist-b")
        cs.add_job(job_a)
        cs.add_job(job_b)

        # Fire job A 3 times, job B 1 time
        for _ in range(3):
            await cs.fire_trigger("trigger-hist-a")
        await cs.fire_trigger("trigger-hist-b")

        history_a = cs.get_job_history("hist-a")
        history_b = cs.get_job_history("hist-b")

        assert len(history_a) == 3
        assert len(history_b) == 1
        assert all(h.job_id == "hist-a" for h in history_a)
        assert all(h.job_id == "hist-b" for h in history_b)

    @pytest.mark.asyncio
    async def test_acc_5_stats_report_accurate_counts(self) -> None:
        """get_stats() reports accurate fired/succeeded/failed counts."""
        fail_next = [True]

        async def sometimes_failing_factory(config: Any, task: Any) -> dict[str, Any]:
            if fail_next[0]:
                fail_next[0] = False
                raise RuntimeError("deliberate failure")
            return {"result": "ok"}

        scheduler = Scheduler()
        config = AgentConfig(
            agent_type="cron-agent",
            display_name="Flaky",
            max_concurrent=10,
        )
        scheduler.register(config, sometimes_failing_factory)

        cs = CronScheduler(scheduler)
        job = _make_webhook_job("stats-job")
        cs.add_job(job)

        # First call fails, second succeeds
        await cs.fire_trigger("trigger-stats-job")
        await cs.fire_trigger("trigger-stats-job")

        stats = cs.get_stats()
        assert stats["total_fired"] == 2
        assert stats["total_succeeded"] == 1
        assert stats["total_failed"] == 1
        assert stats["total_jobs"] == 1
        assert stats["enabled_jobs"] == 1
        assert "stats-job" in stats["jobs"]
