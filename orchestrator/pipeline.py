"""Verified Autonomy Pipeline: Plan → Gate → Execute → Validate → Ship.

REQ-GOV-01: VAP Lifecycle Enforcement
- Startup validation: all 5 stages must have handlers
- Stage-skip detection and rejection
- Immutable stage sequence
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Protocol
from uuid import uuid4

from security.agent_allowlist import AgentToolGuard

from adapters.confirmation_gate import (
    ConfirmationTimeoutError,
    HumanRejectedError,
)
from orchestrator.exceptions import (
    ExecutionError,
    GateRejectedError,
    ValidationError,
)
from orchestrator.event_emitter import EventEmitter
from orchestrator.models import PipelineResult, Task, TaskStatus

# L6 observability — lazy import-safe (observability has no side effects)
try:
    from observability import get_collector as _get_metrics_collector
except Exception:  # noqa: BLE001
    _get_metrics_collector = None  # type: ignore[assignment]

if TYPE_CHECKING:
    from adapters.confirmation_gate import ConfirmationGate
    from orchestrator.adapter_registry import AdapterRegistry
    from orchestrator.quality_gate import QualityGate
    from policy_engine.engine import PolicyEngine

logger = logging.getLogger(__name__)

_STAGE_NAMES = ("plan", "gate", "execute", "validate", "ship")
_STAGE_SEQUENCE = {
    "plan": 0,
    "gate": 1,
    "execute": 2,
    "validate": 3,
    "ship": 4,
}


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
# Pipeline errors — REQ-GOV-01
# ---------------------------------------------------------------------------


class PipelineConfigError(Exception):
    """Raised when pipeline is misconfigured at startup."""


class StageSkipError(Exception):
    """Raised when a stage-skip attempt is detected."""


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

class Pipeline:
    """Orchestrates the full Verified Autonomy Pipeline lifecycle for a single :class:`Task`.

    REQ-GOV-01 enforcement:
    - Startup validation: all 5 stages must have handlers
    - Stage-skip detection and rejection during run()
    - Immutable stage sequence: plan → gate → execute → validate → ship

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
        confirmation_gate: ConfirmationGate | None = None,
        quality_gate: QualityGate | None = None,
        quality_max_revisions: int = 2,
        event_emitter: EventEmitter | None = None,
        agent_tool_guard: AgentToolGuard | None = None,
    ) -> None:
        self._planner = planner
        self._policy_engine = policy_engine
        self._executor = executor
        self._validator = validator
        self._shipper = shipper
        self._registry = adapter_registry
        self._execute_retries = max(0, execute_retries)
        self._confirmation_gate = confirmation_gate
        self._quality_gate = quality_gate
        self._quality_max_revisions = max(0, quality_max_revisions)
        self._event_emitter = event_emitter
        self._agent_tool_guard = agent_tool_guard

        # REQ-GOV-01: Startup validation
        self._validate_handlers()

    def _validate_handlers(self) -> None:
        """REQ-GOV-01: Verify all 5 stages have handlers at startup.

        Raises :class:`PipelineConfigError` if any stage is missing a handler.
        """
        missing: list[str] = []
        if self._planner is None:
            missing.append("plan")
        if self._policy_engine is None:
            missing.append("gate")
        if self._executor is None:
            missing.append("execute")
        if self._validator is None:
            missing.append("validate")
        if self._shipper is None:
            missing.append("ship")
        if missing:
            raise PipelineConfigError(
                f"Missing handlers for stages: {', '.join(missing)}. "
                f"All 5 VAP stages must have handlers (REQ-GOV-01)."
            )

    @property
    def stage_names(self) -> tuple[str, ...]:
        """Immutable stage sequence."""
        return _STAGE_NAMES

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
        """Execute the full Verified Autonomy Pipeline for *task*.

        REQ-GOV-01: Stages execute in strict sequence with skip detection.
        """
        started = datetime.now(timezone.utc)
        evidence: dict[str, Any] = {}
        timings: dict[str, float] = {}
        agent_type = task.agent_type
        completed_stages: list[str] = []

        # Generate correlation_id for event tracking
        correlation_id = f"pipe-{task.id[:8]}-{uuid4().hex[:6]}"
        evidence["_correlation_id"] = correlation_id
        emitter = self._event_emitter

        if emitter:
            emitter.emit_status(task.id, correlation_id, "started")

        # Record routing info when registry is available
        if self._registry:
            evidence["_routing"] = self._registry.get_routing_info(agent_type)

        try:
            # 1. Plan
            self._assert_stage_order("plan", completed_stages)
            task.transition(TaskStatus.PLANNING)
            logger.info("Pipeline PLAN – task=%s agent_type=%s", task.id, agent_type)
            if emitter:
                emitter.emit_progress(task.id, correlation_id, "plan", "Creating execution plan", 10)
            t0 = time.monotonic()
            planner = self._resolve_planner(agent_type)
            task.plan = await planner.create_plan(task)
            timings["plan"] = round(time.monotonic() - t0, 4)
            evidence["plan"] = task.plan
            completed_stages.append("plan")

            # 1.5 Human confirmation gate (between PLAN and GATE)
            if self._confirmation_gate is not None:
                t0 = time.monotonic()
                confirmation_result = await self._request_human_confirmation(
                    task, evidence
                )
                timings["confirm"] = round(time.monotonic() - t0, 4)
                evidence["confirmation"] = {
                    "status": confirmation_result,
                    "risk_level": task.risk_level.value,
                }
                if confirmation_result not in ("approved", "auto_approved"):
                    task.transition(TaskStatus.REJECTED)
                    evidence["_timings"] = timings
                    evidence["_completed_stages"] = completed_stages
                    if confirmation_result == "timeout":
                        raise ConfirmationTimeoutError(task.id)
                    raise HumanRejectedError(
                        task.id,
                        f"Human rejected task (response: {confirmation_result})",
                    )

            # 2. Gate
            self._assert_stage_order("gate", completed_stages)
            task.transition(TaskStatus.GATED)
            logger.info("Pipeline GATE – task=%s", task.id)
            if emitter:
                emitter.emit_progress(task.id, correlation_id, "gate", "Policy gate evaluation", 30)
            t0 = time.monotonic()
            gate_result = await self._policy_engine.evaluate(task)
            timings["gate"] = round(time.monotonic() - t0, 4)
            if not gate_result.approved:
                raise GateRejectedError(task.id, gate_result.reason)
            evidence["gate"] = gate_result.__dict__
            completed_stages.append("gate")

            # 3. Execute (with optional retry)
            self._assert_stage_order("execute", completed_stages)
            task.transition(TaskStatus.EXECUTING)
            logger.info("Pipeline EXECUTE – task=%s agent_type=%s", task.id, agent_type)
            if emitter:
                emitter.emit_progress(task.id, correlation_id, "execute", "Executing in sandbox", 50)
            t0 = time.monotonic()
            exec_output = await self._execute_with_retry(task)
            timings["execute"] = round(time.monotonic() - t0, 4)
            evidence["execution"] = exec_output
            completed_stages.append("execute")

            # 3.5 Quality Gate (between EXECUTE and VALIDATE)
            if self._quality_gate is not None:
                t0 = time.monotonic()
                quality_passed = await self._run_quality_gate(
                    task, exec_output, evidence
                )
                timings["quality_gate"] = round(time.monotonic() - t0, 4)
                if not quality_passed:
                    raise ValidationError(
                        task.id,
                        ["Quality gate failed after "
                         f"{self._quality_max_revisions} revision attempts"],
                    )

            # 4. Validate
            self._assert_stage_order("validate", completed_stages)
            task.transition(TaskStatus.VALIDATING)
            logger.info("Pipeline VALIDATE – task=%s", task.id)
            if emitter:
                emitter.emit_progress(task.id, correlation_id, "validate", "Running validation checks", 75)
            t0 = time.monotonic()
            validator = self._resolve_validator(agent_type)
            failures = await validator.validate(task)
            timings["validate"] = round(time.monotonic() - t0, 4)
            if failures:
                raise ValidationError(task.id, failures)
            evidence["validation"] = {"passed": True}
            completed_stages.append("validate")

            # 5. Ship
            self._assert_stage_order("ship", completed_stages)
            task.transition(TaskStatus.SHIPPING)
            logger.info("Pipeline SHIP – task=%s", task.id)
            if emitter:
                emitter.emit_progress(task.id, correlation_id, "ship", "Shipping result", 90)
            t0 = time.monotonic()
            shipper = self._resolve_shipper(agent_type)
            ship_output = await shipper.ship(task)
            timings["ship"] = round(time.monotonic() - t0, 4)
            evidence["ship"] = ship_output
            completed_stages.append("ship")

            task.transition(TaskStatus.COMPLETED)
            if emitter:
                emitter.emit_completion(task.id, correlation_id, "Pipeline completed successfully")
            evidence["_timings"] = timings
            evidence["_completed_stages"] = completed_stages

            # L6 observability: emit success metrics
            self._emit_metrics(
                task=task,
                agent_type=agent_type,
                outcome="success",
                timings=timings,
            )

            return PipelineResult(
                task_id=task.id,
                success=True,
                status=TaskStatus.COMPLETED,
                started_at=started,
                finished_at=datetime.now(timezone.utc),
                evidence=evidence,
            )

        except GateRejectedError as exc:
            task.transition(TaskStatus.REJECTED)
            if emitter:
                emitter.emit_error(task.id, correlation_id, f"Gate rejected: {exc}")
            evidence["_timings"] = timings
            evidence["_completed_stages"] = completed_stages
            self._emit_metrics(task, agent_type, "gate_rejected", timings)
            raise

        except (HumanRejectedError, ConfirmationTimeoutError):
            # Task already transitioned to REJECTED in the confirm block
            evidence["_timings"] = timings
            evidence["_completed_stages"] = completed_stages
            self._emit_metrics(task, agent_type, "human_rejected", timings)
            raise

        except (ExecutionError, ValidationError) as exc:
            task.transition(TaskStatus.FAILED)
            task.error = str(exc)
            if emitter:
                emitter.emit_error(task.id, correlation_id, str(exc))
            evidence["_timings"] = timings
            evidence["_completed_stages"] = completed_stages
            self._emit_metrics(task, agent_type, "failed", timings)
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
            if emitter:
                emitter.emit_error(task.id, correlation_id, str(exc))
            evidence["_timings"] = timings
            evidence["_completed_stages"] = completed_stages
            logger.exception("Unexpected pipeline error for task=%s", task.id)
            self._emit_metrics(task, agent_type, "error", timings)
            return PipelineResult(
                task_id=task.id,
                success=False,
                status=TaskStatus.FAILED,
                started_at=started,
                finished_at=datetime.now(timezone.utc),
                evidence=evidence,
                error=str(exc),
            )

    def _emit_metrics(
        self,
        task: Task,
        agent_type: str,
        outcome: str,
        timings: dict[str, float],
    ) -> None:
        """L6 observability — emit pipeline metrics to the collector.

        Called on every terminal path (success + 4 exception types).
        Fully non-blocking and best-effort: never raises.
        """
        if _get_metrics_collector is None:
            return
        try:
            coll = _get_metrics_collector()
            base_labels = {"agent_type": agent_type, "outcome": outcome}
            coll.counter(
                "occp.pipeline.tasks",
                1,
                base_labels,
                help_text="Total pipeline tasks by agent_type and outcome",
            )
            for stage, secs in timings.items():
                if not isinstance(secs, (int, float)):
                    continue
                coll.histogram(
                    "occp.pipeline.stage_duration_ms",
                    float(secs) * 1000.0,
                    {"stage": stage, "agent_type": agent_type},
                    help_text="Pipeline stage duration in milliseconds",
                )
        except Exception as exc:  # noqa: BLE001 — metrics must not break pipeline
            logger.debug("Failed to emit pipeline metrics: %s", exc)

    async def _request_human_confirmation(
        self, task: Task, evidence: dict[str, Any]
    ) -> str:
        """Request human confirmation via the ConfirmationGate.

        Returns the confirmation status string:
        'approved', 'auto_approved', 'rejected', 'timeout'.
        """
        from adapters.confirmation_gate import ConfirmationGate as CG

        gate = self._confirmation_gate
        assert gate is not None  # caller checks

        # Build plan summary
        plan_summary = CG.format_plan_summary(task.plan or {})

        # Get chat_id from task metadata
        chat_id = task.metadata.get("chat_id", 0)

        task.transition(TaskStatus.AWAITING_CONFIRMATION)
        logger.info(
            "Pipeline CONFIRM – task=%s risk=%s chat_id=%d",
            task.id,
            task.risk_level.value,
            chat_id,
        )

        result = await gate.request_confirmation(
            task_id=task.id,
            chat_id=chat_id,
            plan_summary=plan_summary,
            risk_level=task.risk_level.value,
            agent_type=task.agent_type,
        )

        # On approval, task stays in AWAITING_CONFIRMATION.
        # The next GATE step will transition it to GATED.
        return result.value

    @staticmethod
    def _assert_stage_order(stage: str, completed: list[str]) -> None:
        """REQ-GOV-01: Verify stage is next in sequence — no skipping.

        Raises :class:`StageSkipError` if the stage is out of order.
        """
        expected_index = _STAGE_SEQUENCE[stage]

        if expected_index == 0:
            # First stage — nothing to check
            if completed:
                raise StageSkipError(
                    f"Stage '{stage}' must be first but "
                    f"{completed} already completed"
                )
            return

        # Previous stage must be the last completed
        expected_prev = _STAGE_NAMES[expected_index - 1]
        if not completed or completed[-1] != expected_prev:
            raise StageSkipError(
                f"Stage '{stage}' requires '{expected_prev}' to be completed first. "
                f"Completed stages: {completed}"
            )

    @staticmethod
    def validate_stage_sequence(stages: list[str]) -> bool:
        """Check if a list of stage names follows the correct order.

        Useful for external validation of stage sequences.
        """
        for i, stage in enumerate(stages):
            if stage not in _STAGE_SEQUENCE:
                return False
            if _STAGE_SEQUENCE[stage] != i:
                return False
        return True

    async def _run_quality_gate(
        self,
        task: Task,
        exec_output: dict[str, Any],
        evidence: dict[str, Any],
    ) -> bool:
        """Run quality gate checks on execution output.

        Supports a revision loop: if the gate fails, the executor is
        re-run up to ``_quality_max_revisions`` times.

        Returns True if quality gate passes.
        """
        gate = self._quality_gate
        assert gate is not None

        output = exec_output
        for attempt in range(1 + self._quality_max_revisions):
            checks = await gate.run_quality_gate(
                task.agent_type, task.id, output
            )
            passed = await gate.brain_final_review(task.id, checks)

            evidence[f"quality_gate_attempt_{attempt}"] = {
                "checks": [c.to_dict() for c in checks],
                "passed": passed,
            }

            if passed:
                evidence["quality_gate"] = {"passed": True, "attempts": attempt + 1}
                return True

            if attempt < self._quality_max_revisions:
                logger.info(
                    "Quality gate failed for task=%s attempt=%d/%d — requesting revision",
                    task.id,
                    attempt + 1,
                    1 + self._quality_max_revisions,
                )
                # Re-execute with revision instructions in metadata
                instructions = gate.get_revision_instructions(checks)
                task.metadata["_revision_instructions"] = instructions
                task.metadata["_revision_attempt"] = attempt + 1
                executor = self._resolve_executor(task.agent_type)
                output = await executor.execute(task)
                evidence[f"execution_revision_{attempt + 1}"] = output

        evidence["quality_gate"] = {
            "passed": False,
            "attempts": 1 + self._quality_max_revisions,
        }
        return False

    async def _execute_with_retry(self, task: Task) -> dict[str, Any]:
        """Execute with retry on transient failures."""
        # Agent tool guard — enforce mode if OCCP_AGENT_TOOL_GUARD_ENFORCE=true
        if self._agent_tool_guard:
            check = self._agent_tool_guard.check_access(task.agent_type, "execute")
            if not check.allowed:
                logger.warning(
                    "AgentToolGuard DENIED: agent=%s tool=execute reason=%s",
                    task.agent_type, check.reason,
                )
                enforce = os.getenv("OCCP_AGENT_TOOL_GUARD_ENFORCE", "").lower() in ("1", "true", "yes")
                if enforce:
                    raise ExecutionError(
                        task.id,
                        f"AgentToolGuard denied: {check.reason}",
                    )

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


# ---------------------------------------------------------------------------
# PipelineRunner — concurrent pipeline execution with semaphore control
# ---------------------------------------------------------------------------

# Default max concurrent pipelines from env or 10
_MAX_CONCURRENT_PIPELINES: int = int(
    os.environ.get("OCCP_MAX_CONCURRENT_PIPELINES", "10")
)


class PipelineRunner:
    """Run multiple Pipeline executions concurrently with bounded parallelism.

    Uses an ``asyncio.Semaphore`` to limit the number of pipeline runs that
    execute at the same time.  Each run is fully independent — no shared
    mutable state between pipeline executions.

    Usage::

        runner = PipelineRunner(pipeline, max_concurrent=10)
        results = await runner.run_batch(tasks)
    """

    def __init__(
        self,
        pipeline: Pipeline,
        *,
        max_concurrent: int = _MAX_CONCURRENT_PIPELINES,
    ) -> None:
        self._pipeline = pipeline
        self._max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._total_runs: int = 0
        self._total_success: int = 0
        self._total_failed: int = 0

    @property
    def max_concurrent(self) -> int:
        return self._max_concurrent

    async def run_one(self, task: Task) -> PipelineResult:
        """Run a single pipeline execution, respecting the concurrency semaphore."""
        async with self._semaphore:
            self._total_runs += 1
            result = await self._pipeline.run(task)
            if result.success:
                self._total_success += 1
            else:
                self._total_failed += 1
            return result

    async def run_batch(self, tasks: list[Task]) -> list[PipelineResult]:
        """Run multiple tasks through the pipeline concurrently.

        Each task runs independently.  The semaphore limits how many
        execute at the same time.

        Args:
            tasks: List of tasks to execute.

        Returns:
            List of PipelineResult in the same order as the input tasks.
        """
        coros = [self.run_one(task) for task in tasks]
        results = await asyncio.gather(*coros, return_exceptions=True)

        # Convert exceptions to failed PipelineResult
        final: list[PipelineResult] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self._total_failed += 1
                final.append(
                    PipelineResult(
                        task_id=tasks[i].id,
                        success=False,
                        status=TaskStatus.FAILED,
                        started_at=datetime.now(timezone.utc),
                        finished_at=datetime.now(timezone.utc),
                        evidence={},
                        error=str(result),
                    )
                )
            else:
                final.append(result)
        return final

    def get_stats(self) -> dict[str, Any]:
        """Return runner statistics."""
        return {
            "max_concurrent": self._max_concurrent,
            "total_runs": self._total_runs,
            "total_success": self._total_success,
            "total_failed": self._total_failed,
        }
