"""Verified Autonomy Pipeline (VAP): Plan → Gate → Execute → Validate → Ship."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Protocol

from orchestrator.exceptions import (
    ExecutionError,
    GateRejectedError,
    ValidationError,
)
from orchestrator.models import PipelineResult, Task, TaskStatus

if TYPE_CHECKING:
    from orchestrator.adapter_registry import AdapterRegistry
    from policy_engine.engine import PolicyEngine

logger = logging.getLogger(__name__)

_STAGE_NAMES = ("plan", "gate", "execute", "validate", "ship")


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

    Features:
    - Per-stage wall-clock timing (``evidence["_timings"]``)
    - Configurable retry for the Execute stage (transient failures)
    - Optional :class:`AdapterRegistry` for per-agent-type adapter routing

    Usage::

        pipeline = Pipeline(
            planner=my_planner,
            policy_engine=my_policy_engine,
            executor=my_executor,
            validator=my_validator,
            shipper=my_shipper,
            adapter_registry=my_registry,
            execute_retries=2,
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
        adapter_registry: AdapterRegistry | None = None,
        execute_retries: int = 0,
    ) -> None:
        self._planner = planner
        self._policy_engine = policy_engine
        self._executor = executor
        self._validator = validator
        self._shipper = shipper
        self._registry = adapter_registry
        self._execute_retries = max(0, execute_retries)

    # -- Adapter resolution (registry-aware) --

    def _resolve_planner(self, agent_type: str) -> Planner:
        if self._registry:
            return self._registry.get_planner(agent_type)
        return self._planner

    def _resolve_executor(self, agent_type: str) -> Executor:
        if self._registry:
            return self._registry.get_executor(agent_type)
        return self._executor

    def _resolve_validator(self, agent_type: str) -> Validator:
        if self._registry:
            return self._registry.get_validator(agent_type)
        return self._validator

    def _resolve_shipper(self, agent_type: str) -> Shipper:
        if self._registry:
            return self._registry.get_shipper(agent_type)
        return self._shipper

    async def run(self, task: Task) -> PipelineResult:
        """Execute the full VAP pipeline for *task*."""
        started = datetime.now(timezone.utc)
        evidence: dict[str, Any] = {}
        timings: dict[str, float] = {}
        agent_type = task.agent_type

        # Record routing info when registry is available
        if self._registry:
            evidence["_routing"] = self._registry.get_routing_info(agent_type)

        try:
            # 1. Plan
            task.transition(TaskStatus.PLANNING)
            logger.info("Pipeline PLAN – task=%s agent_type=%s", task.id, agent_type)
            t0 = time.monotonic()
            planner = self._resolve_planner(agent_type)
            task.plan = await planner.create_plan(task)
            timings["plan"] = round(time.monotonic() - t0, 4)
            evidence["plan"] = task.plan

            # 2. Gate
            task.transition(TaskStatus.GATED)
            logger.info("Pipeline GATE – task=%s", task.id)
            t0 = time.monotonic()
            gate_result = await self._policy_engine.evaluate(task)
            timings["gate"] = round(time.monotonic() - t0, 4)
            if not gate_result.approved:
                raise GateRejectedError(task.id, gate_result.reason)
            evidence["gate"] = gate_result.__dict__

            # 3. Execute (with optional retry)
            task.transition(TaskStatus.EXECUTING)
            logger.info("Pipeline EXECUTE – task=%s agent_type=%s", task.id, agent_type)
            t0 = time.monotonic()
            exec_output = await self._execute_with_retry(task)
            timings["execute"] = round(time.monotonic() - t0, 4)
            evidence["execution"] = exec_output

            # 4. Validate
            task.transition(TaskStatus.VALIDATING)
            logger.info("Pipeline VALIDATE – task=%s", task.id)
            t0 = time.monotonic()
            validator = self._resolve_validator(agent_type)
            failures = await validator.validate(task)
            timings["validate"] = round(time.monotonic() - t0, 4)
            if failures:
                raise ValidationError(task.id, failures)
            evidence["validation"] = {"passed": True}

            # 5. Ship
            task.transition(TaskStatus.SHIPPING)
            logger.info("Pipeline SHIP – task=%s", task.id)
            t0 = time.monotonic()
            shipper = self._resolve_shipper(agent_type)
            ship_output = await shipper.ship(task)
            timings["ship"] = round(time.monotonic() - t0, 4)
            evidence["ship"] = ship_output

            task.transition(TaskStatus.COMPLETED)
            evidence["_timings"] = timings
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
            evidence["_timings"] = timings
            raise

        except (ExecutionError, ValidationError) as exc:
            task.transition(TaskStatus.FAILED)
            task.error = str(exc)
            evidence["_timings"] = timings
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
            evidence["_timings"] = timings
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

    async def _execute_with_retry(self, task: Task) -> dict[str, Any]:
        """Execute with retry on transient failures."""
        executor = self._resolve_executor(task.agent_type)
        last_exc: Exception | None = None
        for attempt in range(1 + self._execute_retries):
            try:
                return await executor.execute(task)
            except ExecutionError:
                raise  # Explicit execution failures are not retried
            except Exception as exc:
                last_exc = exc
                if attempt < self._execute_retries:
                    logger.warning(
                        "Execute attempt %d/%d failed for task=%s: %s – retrying",
                        attempt + 1,
                        1 + self._execute_retries,
                        task.id,
                        exc,
                    )
        raise ExecutionError(task.id, f"All {1 + self._execute_retries} attempts failed: {last_exc}")
