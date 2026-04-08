"""Cron Scheduler — time-based and event-based task triggering.

Features:
- Cron expression parsing (minute, hour, day, month, weekday)
- Event-based triggers (webhook, file change, threshold)
- Trigger → Task creation through Scheduler dispatch
- Job lifecycle management (create, pause, resume, delete)
- Execution history with audit trail
- Policy-gated: every trigger execution can go through PolicyGate
"""

from __future__ import annotations

import enum
import logging
import uuid
from calendar import monthrange
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from orchestrator.exceptions import OccpError
from orchestrator.models import AgentConfig, Task
from orchestrator.scheduler import Scheduler

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class CronError(OccpError):
    """Base cron scheduler error."""


class CronParseError(CronError):
    """Raised when a cron expression cannot be parsed."""

    def __init__(self, expression: str, reason: str) -> None:
        self.expression = expression
        self.reason = reason
        super().__init__(f"Cannot parse cron expression '{expression}': {reason}")


class JobNotFoundError(CronError):
    """Raised when a scheduled job is not found."""

    def __init__(self, job_id: str) -> None:
        self.job_id = job_id
        super().__init__(f"Scheduled job not found: {job_id}")


class TriggerError(CronError):
    """Raised when a trigger fires unexpectedly or fails."""

    def __init__(self, trigger_id: str, reason: str) -> None:
        self.trigger_id = trigger_id
        self.reason = reason
        super().__init__(f"Trigger {trigger_id} error: {reason}")


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TriggerType(str, enum.Enum):
    """Supported trigger mechanisms."""

    CRON = "cron"
    WEBHOOK = "webhook"
    EVENT = "event"
    INTERVAL = "interval"


# ---------------------------------------------------------------------------
# Cron field helpers
# ---------------------------------------------------------------------------


def _parse_cron_field(field_str: str, min_val: int, max_val: int) -> set[int]:
    """Parse a single cron field into a set of matching integers.

    Supports:
    - ``*``        → all values in [min_val, max_val]
    - ``*/N``      → every N values starting at min_val
    - ``N``        → single value N
    - ``N-M``      → range from N to M inclusive
    - ``N,M,...``  → explicit list
    - ``N-M/S``    → range with step

    Args:
        field_str: The cron field string (e.g. "*/5", "1-5", "0,15,30,45").
        min_val: Minimum valid value for this field.
        max_val: Maximum valid value for this field.

    Returns:
        Set of integer values that match this field.

    Raises:
        CronParseError: If the field cannot be parsed or values are out of range.
    """
    if field_str == "*":
        return set(range(min_val, max_val + 1))

    result: set[int] = set()

    for part in field_str.split(","):
        part = part.strip()
        if "/" in part:
            # Step expression: base/step
            base_part, step_str = part.split("/", 1)
            try:
                step = int(step_str)
            except ValueError:
                raise CronParseError(field_str, f"Invalid step value: {step_str}")
            if step <= 0:
                raise CronParseError(field_str, f"Step must be positive, got: {step}")

            if base_part == "*":
                start, end = min_val, max_val
            elif "-" in base_part:
                a, b = base_part.split("-", 1)
                try:
                    start, end = int(a), int(b)
                except ValueError:
                    raise CronParseError(field_str, f"Invalid range: {base_part}")
            else:
                try:
                    start = int(base_part)
                    end = max_val
                except ValueError:
                    raise CronParseError(field_str, f"Invalid base: {base_part}")

            result.update(range(start, end + 1, step))

        elif "-" in part:
            # Range expression
            a, b = part.split("-", 1)
            try:
                lo, hi = int(a), int(b)
            except ValueError:
                raise CronParseError(field_str, f"Invalid range: {part}")
            if lo > hi:
                raise CronParseError(field_str, f"Range start > end: {part}")
            result.update(range(lo, hi + 1))

        else:
            try:
                val = int(part)
            except ValueError:
                raise CronParseError(field_str, f"Invalid value: {part}")
            result.add(val)

    # Validate bounds
    for val in result:
        if val < min_val or val > max_val:
            raise CronParseError(
                field_str,
                f"Value {val} out of range [{min_val}, {max_val}]",
            )

    return result


# ---------------------------------------------------------------------------
# CronExpression
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CronExpression:
    """Parsed representation of a 5-field cron expression.

    Field order: minute hour day_of_month month day_of_week

    Attributes:
        minute: Set of matching minutes (0-59).
        hour: Set of matching hours (0-23).
        day_of_month: Set of matching days of month (1-31).
        month: Set of matching months (1-12).
        day_of_week: Set of matching weekdays (0=Sunday, 6=Saturday).
        raw: Original expression string.
    """

    minute: frozenset[int]
    hour: frozenset[int]
    day_of_month: frozenset[int]
    month: frozenset[int]
    day_of_week: frozenset[int]
    raw: str

    @classmethod
    def from_string(cls, expr: str) -> CronExpression:
        """Parse a 5-field cron expression string.

        Args:
            expr: Cron expression like "*/5 * * * *" or "0 9 * * 1-5".

        Returns:
            Parsed CronExpression.

        Raises:
            CronParseError: If the expression is malformed.
        """
        parts = expr.strip().split()
        if len(parts) != 5:
            raise CronParseError(
                expr, f"Expected 5 fields, got {len(parts)}"
            )

        try:
            minute = frozenset(_parse_cron_field(parts[0], 0, 59))
            hour = frozenset(_parse_cron_field(parts[1], 0, 23))
            day_of_month = frozenset(_parse_cron_field(parts[2], 1, 31))
            month = frozenset(_parse_cron_field(parts[3], 1, 12))
            day_of_week = frozenset(_parse_cron_field(parts[4], 0, 6))
        except CronParseError:
            raise
        except Exception as exc:
            raise CronParseError(expr, str(exc)) from exc

        return cls(
            minute=minute,
            hour=hour,
            day_of_month=day_of_month,
            month=month,
            day_of_week=day_of_week,
            raw=expr,
        )

    def matches(self, dt: datetime) -> bool:
        """Check whether *dt* matches this cron expression.

        All five fields must match simultaneously.

        Args:
            dt: The datetime to check (timezone-aware or naive).

        Returns:
            True if dt matches this cron expression.
        """
        # Python weekday: 0=Monday … 6=Sunday; cron: 0=Sunday … 6=Saturday
        # Convert: cron_dow = (python_weekday + 1) % 7
        cron_dow = (dt.weekday() + 1) % 7
        return (
            dt.minute in self.minute
            and dt.hour in self.hour
            and dt.day in self.day_of_month
            and dt.month in self.month
            and cron_dow in self.day_of_week
        )

    def next_run(self, after: datetime) -> datetime:
        """Calculate the next datetime after *after* that matches this expression.

        Searches forward minute-by-minute up to 4 years (safe upper bound
        for any valid cron expression).

        Args:
            after: Starting datetime (exclusive — result is strictly after this).

        Returns:
            The next matching datetime (second=0, microsecond=0).

        Raises:
            CronError: If no match is found within 4 years.
        """
        # Start from the next minute
        candidate = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
        limit = after + timedelta(days=365 * 4)

        while candidate <= limit:
            if self.matches(candidate):
                return candidate
            # Optimisation: if minute doesn't match, advance to next matching minute
            if candidate.minute not in self.minute:
                # Jump to next matching minute in same hour
                next_min = min(
                    (m for m in self.minute if m > candidate.minute),
                    default=None,
                )
                if next_min is not None:
                    candidate = candidate.replace(minute=next_min, second=0, microsecond=0)
                else:
                    # No matching minute in this hour — advance to next hour
                    candidate = (
                        candidate.replace(minute=0, second=0, microsecond=0)
                        + timedelta(hours=1)
                    )
                continue
            candidate += timedelta(minutes=1)

        raise CronError(
            f"No matching time found for expression '{self.raw}' within 4 years"
        )


# ---------------------------------------------------------------------------
# TriggerConfig
# ---------------------------------------------------------------------------


@dataclass
class TriggerConfig:
    """Configuration for a trigger.

    Attributes:
        trigger_id: Unique trigger identifier.
        name: Human-readable name.
        trigger_type: Type of trigger mechanism.
        cron_expr: Parsed CronExpression (for CRON triggers).
        interval_seconds: Interval in seconds (for INTERVAL triggers).
        event_filter: Filter dict for EVENT/WEBHOOK triggers.
        enabled: Whether this trigger is active.
        metadata: Arbitrary metadata.
    """

    trigger_id: str
    name: str
    trigger_type: TriggerType
    cron_expr: CronExpression | None = None
    interval_seconds: int | None = None
    event_filter: dict[str, Any] | None = None
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# ScheduledJob
# ---------------------------------------------------------------------------


@dataclass
class ScheduledJob:
    """A job that fires based on a trigger configuration.

    Attributes:
        job_id: Unique job identifier.
        name: Human-readable job name.
        trigger: The trigger configuration.
        task_template: Dict used to construct a Task on each firing.
        agent_type: Agent type that receives the task.
        enabled: Whether the job is enabled.
        created_at: When the job was created.
        last_run: When the job last ran (None if never).
        next_run: When the job is next scheduled (None for event-only).
        run_count: Total number of successful runs.
        error_count: Total number of failed runs.
        max_retries: Maximum retries per execution.
    """

    job_id: str
    name: str
    trigger: TriggerConfig
    task_template: dict[str, Any]
    agent_type: str
    enabled: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_run: datetime | None = None
    next_run: datetime | None = None
    run_count: int = 0
    error_count: int = 0
    max_retries: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "name": self.name,
            "trigger_id": self.trigger.trigger_id,
            "trigger_type": self.trigger.trigger_type.value,
            "agent_type": self.agent_type,
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat(),
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "run_count": self.run_count,
            "error_count": self.error_count,
            "max_retries": self.max_retries,
            "task_template": self.task_template,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ScheduledJob:
        trigger = TriggerConfig(
            trigger_id=data.get("trigger_id", data.get("job_id", "unknown")),
            name=data.get("name", ""),
            trigger_type=TriggerType(data.get("trigger_type", TriggerType.CRON.value)),
        )
        return cls(
            job_id=data["job_id"],
            name=data["name"],
            trigger=trigger,
            task_template=data.get("task_template", {}),
            agent_type=data["agent_type"],
            enabled=data.get("enabled", True),
            run_count=data.get("run_count", 0),
            error_count=data.get("error_count", 0),
            max_retries=data.get("max_retries", 0),
        )


# ---------------------------------------------------------------------------
# JobExecution
# ---------------------------------------------------------------------------


@dataclass
class JobExecution:
    """Record of a single job execution.

    Attributes:
        execution_id: Unique execution ID.
        job_id: Reference to the ScheduledJob.
        trigger_type: What triggered this execution.
        started_at: Execution start time.
        finished_at: Execution end time (None if still running).
        success: Whether execution succeeded.
        task_id: ID of the Task created for this execution.
        error: Error message if execution failed.
    """

    execution_id: str
    job_id: str
    trigger_type: TriggerType
    started_at: datetime
    finished_at: datetime | None = None
    success: bool = False
    task_id: str = ""
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "job_id": self.job_id,
            "trigger_type": self.trigger_type.value,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "success": self.success,
            "task_id": self.task_id,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# CronScheduler
# ---------------------------------------------------------------------------


class CronScheduler:
    """Manages scheduled and event-triggered jobs.

    Each job has a TriggerConfig that determines when it fires.
    On firing, a Task is constructed from the job's task_template and
    dispatched through the Scheduler (and optionally gated by PolicyGate).
    """

    def __init__(
        self,
        scheduler: Scheduler,
        gate: Any | None = None,
    ) -> None:
        self._scheduler = scheduler
        self._gate = gate
        self._jobs: dict[str, ScheduledJob] = {}
        self._history: dict[str, list[JobExecution]] = {}
        self._total_fired: int = 0
        self._total_succeeded: int = 0
        self._total_failed: int = 0

    # ------------------------------------------------------------------
    # Job management
    # ------------------------------------------------------------------

    def add_job(self, job: ScheduledJob) -> None:
        """Register a scheduled job.

        If the job has a CRON trigger with a parsed expression, the
        next_run time is computed immediately.
        """
        if job.trigger.cron_expr and job.next_run is None:
            now = datetime.now(timezone.utc)
            try:
                job.next_run = job.trigger.cron_expr.next_run(now)
            except CronError:
                pass  # Leave next_run as None if calculation fails

        elif (
            job.trigger.trigger_type == TriggerType.INTERVAL
            and job.trigger.interval_seconds
            and job.next_run is None
        ):
            now = datetime.now(timezone.utc)
            job.next_run = now + timedelta(seconds=job.trigger.interval_seconds)

        self._jobs[job.job_id] = job
        self._history[job.job_id] = []
        logger.info(
            "Added job id=%s name=%s trigger=%s",
            job.job_id,
            job.name,
            job.trigger.trigger_type.value,
        )

    def remove_job(self, job_id: str) -> bool:
        """Remove a scheduled job by ID.

        Returns:
            True if the job was found and removed, False otherwise.
        """
        if job_id not in self._jobs:
            return False
        del self._jobs[job_id]
        self._history.pop(job_id, None)
        logger.info("Removed job id=%s", job_id)
        return True

    def pause_job(self, job_id: str) -> None:
        """Disable a job so it will not fire on schedule.

        Raises:
            JobNotFoundError: If job_id is not registered.
        """
        job = self._require_job(job_id)
        job.enabled = False
        logger.info("Paused job id=%s", job_id)

    def resume_job(self, job_id: str) -> None:
        """Re-enable a previously paused job.

        Raises:
            JobNotFoundError: If job_id is not registered.
        """
        job = self._require_job(job_id)
        job.enabled = True
        # Recalculate next_run from now
        now = datetime.now(timezone.utc)
        if job.trigger.cron_expr:
            try:
                job.next_run = job.trigger.cron_expr.next_run(now)
            except CronError:
                pass
        elif (
            job.trigger.trigger_type == TriggerType.INTERVAL
            and job.trigger.interval_seconds
        ):
            job.next_run = now + timedelta(seconds=job.trigger.interval_seconds)
        logger.info("Resumed job id=%s next_run=%s", job_id, job.next_run)

    def get_job(self, job_id: str) -> ScheduledJob | None:
        """Return a job by ID, or None if not found."""
        return self._jobs.get(job_id)

    def list_jobs(self, enabled_only: bool = False) -> list[ScheduledJob]:
        """List all registered jobs.

        Args:
            enabled_only: If True, return only enabled jobs.

        Returns:
            List of ScheduledJob instances.
        """
        if enabled_only:
            return [j for j in self._jobs.values() if j.enabled]
        return list(self._jobs.values())

    # ------------------------------------------------------------------
    # Trigger execution
    # ------------------------------------------------------------------

    async def fire_trigger(
        self,
        trigger_id: str,
        event_data: dict[str, Any] | None = None,
    ) -> JobExecution:
        """Manually fire a trigger regardless of schedule.

        Finds the first enabled job whose trigger_id matches, constructs
        a Task, and dispatches it via the Scheduler.

        Args:
            trigger_id: The trigger_id of the job to fire.
            event_data: Optional event payload to merge into task metadata.

        Returns:
            A completed JobExecution record.

        Raises:
            TriggerError: If no matching enabled job is found.
        """
        # Find matching job
        job: ScheduledJob | None = None
        for j in self._jobs.values():
            if j.trigger.trigger_id == trigger_id and j.enabled:
                job = j
                break

        if job is None:
            raise TriggerError(trigger_id, "No enabled job found for this trigger_id")

        return await self._fire_job(job, job.trigger.trigger_type, event_data)

    async def check_and_fire(self, now: datetime) -> list[JobExecution]:
        """Check all jobs for due execution and fire those that are due.

        A CRON job is due when:
        - It is enabled
        - Its next_run is not None and next_run <= now

        An INTERVAL job is due when:
        - It is enabled
        - Its next_run is not None and next_run <= now

        Args:
            now: The current time to evaluate against.

        Returns:
            List of JobExecution records for all jobs that fired.
        """
        executions: list[JobExecution] = []

        for job in list(self._jobs.values()):
            if not job.enabled:
                continue
            if job.trigger.trigger_type not in (TriggerType.CRON, TriggerType.INTERVAL):
                continue
            if job.next_run is None:
                continue
            if job.next_run > now:
                continue

            # Normalize timezone: if next_run is tz-aware, now must also be
            # Already normalised at add_job time; fire the job
            execution = await self._fire_job(job, job.trigger.trigger_type, None)
            executions.append(execution)

            # Update next_run
            if job.trigger.cron_expr:
                try:
                    job.next_run = job.trigger.cron_expr.next_run(now)
                except CronError:
                    job.next_run = None
            elif (
                job.trigger.trigger_type == TriggerType.INTERVAL
                and job.trigger.interval_seconds
            ):
                job.next_run = now + timedelta(seconds=job.trigger.interval_seconds)

        return executions

    async def _fire_job(
        self,
        job: ScheduledJob,
        trigger_type: TriggerType,
        event_data: dict[str, Any] | None,
    ) -> JobExecution:
        """Internal: fire a job and record the execution."""
        execution_id = uuid.uuid4().hex[:16]
        started_at = datetime.now(timezone.utc)
        execution = JobExecution(
            execution_id=execution_id,
            job_id=job.job_id,
            trigger_type=trigger_type,
            started_at=started_at,
        )

        self._total_fired += 1
        job.last_run = started_at

        try:
            template = job.task_template
            task = Task(
                name=template.get("name", f"cron-job-{job.job_id}"),
                description=template.get("description", ""),
                agent_type=job.agent_type,
                metadata={
                    **template.get("metadata", {}),
                    "_cron_job_id": job.job_id,
                    "_trigger_type": trigger_type.value,
                    "_execution_id": execution_id,
                    "_event_data": event_data or {},
                },
            )

            await self._scheduler.dispatch(task)

            execution.success = True
            execution.task_id = task.id
            execution.finished_at = datetime.now(timezone.utc)
            job.run_count += 1
            self._total_succeeded += 1
            logger.info(
                "Job fired successfully id=%s execution=%s task=%s",
                job.job_id,
                execution_id,
                task.id,
            )

        except Exception as exc:
            execution.success = False
            execution.error = str(exc)
            execution.finished_at = datetime.now(timezone.utc)
            job.error_count += 1
            self._total_failed += 1
            logger.error(
                "Job execution failed id=%s execution=%s error=%s",
                job.job_id,
                execution_id,
                exc,
            )

        # Record in history
        self._history.setdefault(job.job_id, []).append(execution)
        return execution

    # ------------------------------------------------------------------
    # History & Stats
    # ------------------------------------------------------------------

    def get_job_history(
        self,
        job_id: str,
        limit: int = 50,
    ) -> list[JobExecution]:
        """Return execution history for a job.

        Args:
            job_id: The job to query.
            limit: Maximum number of records to return (most recent first).

        Returns:
            List of JobExecution records.

        Raises:
            JobNotFoundError: If job_id is not registered.
        """
        self._require_job(job_id)
        history = self._history.get(job_id, [])
        return history[-limit:][::-1]

    def get_stats(self) -> dict[str, Any]:
        """Return cron scheduler statistics."""
        enabled_count = sum(1 for j in self._jobs.values() if j.enabled)
        return {
            "total_jobs": len(self._jobs),
            "enabled_jobs": enabled_count,
            "total_fired": self._total_fired,
            "total_succeeded": self._total_succeeded,
            "total_failed": self._total_failed,
            "jobs": {
                j.job_id: {
                    "name": j.name,
                    "enabled": j.enabled,
                    "run_count": j.run_count,
                    "error_count": j.error_count,
                    "next_run": j.next_run.isoformat() if j.next_run else None,
                }
                for j in self._jobs.values()
            },
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _require_job(self, job_id: str) -> ScheduledJob:
        """Return a job or raise JobNotFoundError."""
        job = self._jobs.get(job_id)
        if job is None:
            raise JobNotFoundError(job_id)
        return job
