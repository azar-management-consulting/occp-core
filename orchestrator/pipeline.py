"""Verified Autonomy Pipeline (VAP): Plan → Gate → Execute → Validate → Ship."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Protocol

from orchestrator.exceptions import (
    ExecutionError,
    GateRejectedError,
    ValidationError,
)
from orchestrator.models import PipelineResult, Task, TaskStatus

if TYPE_CHECKING:
    from policy_engine.engine import PolicyEngine

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Protocols – adapters implement these
# ---------------------------------------------------------------------------

class Planner(Protocol):
    """Creates an execution plan for a task."""

    async def create_plan(self, task: Task) -> dict[str, Any]: ...


class Executor(Protocol):
    """Runs a task inside a sandbox."""

    async def execute(self, task: Task) -> dict[str, Any]: ...


class Validator(Protocol):
    """Runs post-execution checks (tests, static analysis, diff)."""

    async def validate(self, task: Task) -> list[str]: ...


class Shipper(Protocol):
    """Ships the result (PR, release, deploy)."""

    async def ship(self, task: Task) -> dict[str, Any]: ...


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

class Pipeline:
    """Orchestrates the full VAP lifecycle for a single :class:`Task`.

    Usage::

        pipeline = Pipeline(
            planner=my_planner,
            policy_engine=my_policy_engine,
            executor=my_executor,
            validator=my_validator,
            shipper=my_shipper,
        )
        result = await pipeline.run(task)
    """

    def __init__(
        self,
        *,
        planner: Planner,
        policy_engine: PolicyEngine,
        executor: Executor,
        validator: Validator,
        shipper: Shipper,
    ) -> None:
        self._planner = planner
        self._policy_engine = policy_engine
        self._executor = executor
        self._validator = validator
        self._shipper = shipper

    async def run(self, task: Task) -> PipelineResult:
        """Execute the full VAP pipeline for *task*."""
        started = datetime.now(timezone.utc)
        evidence: dict[str, Any] = {}

        try:
            # 1. Plan
            task.transition(TaskStatus.PLANNING)
            logger.info("Pipeline PLAN – task=%s", task.id)
            task.plan = await self._planner.create_plan(task)
            evidence["plan"] = task.plan

            # 2. Gate
            task.transition(TaskStatus.GATED)
            logger.info("Pipeline GATE – task=%s", task.id)
            gate_result = await self._policy_engine.evaluate(task)
            if not gate_result.approved:
                raise GateRejectedError(task.id, gate_result.reason)
            evidence["gate"] = gate_result.__dict__

            # 3. Execute
            task.transition(TaskStatus.EXECUTING)
            logger.info("Pipeline EXECUTE – task=%s", task.id)
            exec_output = await self._executor.execute(task)
            evidence["execution"] = exec_output

            # 4. Validate
            task.transition(TaskStatus.VALIDATING)
            logger.info("Pipeline VALIDATE – task=%s", task.id)
            failures = await self._validator.validate(task)
            if failures:
                raise ValidationError(task.id, failures)
            evidence["validation"] = {"passed": True}

            # 5. Ship
            task.transition(TaskStatus.SHIPPING)
            logger.info("Pipeline SHIP – task=%s", task.id)
            ship_output = await self._shipper.ship(task)
            evidence["ship"] = ship_output

            task.transition(TaskStatus.COMPLETED)
            return PipelineResult(
                task_id=task.id,
                success=True,
                status=TaskStatus.COMPLETED,
                started_at=started,
                finished_at=datetime.now(timezone.utc),
                evidence=evidence,
            )

        except GateRejectedError:
            task.transition(TaskStatus.REJECTED)
            raise

        except (ExecutionError, ValidationError) as exc:
            task.transition(TaskStatus.FAILED)
            task.error = str(exc)
            return PipelineResult(
                task_id=task.id,
                success=False,
                status=TaskStatus.FAILED,
                started_at=started,
                finished_at=datetime.now(timezone.utc),
                evidence=evidence,
                error=str(exc),
            )

        except Exception as exc:
            task.transition(TaskStatus.FAILED)
            task.error = str(exc)
            logger.exception("Unexpected pipeline error for task=%s", task.id)
            return PipelineResult(
                task_id=task.id,
                success=False,
                status=TaskStatus.FAILED,
                started_at=started,
                finished_at=datetime.now(timezone.utc),
                evidence=evidence,
                error=str(exc),
            )
