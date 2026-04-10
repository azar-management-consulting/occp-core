"""Tests for Pipeline — REQ-GOV-01: VAP Lifecycle Enforcement.

Covers:
- PipelineConfigError on missing handlers (startup validation)
- StageSkipError detection and rejection
- stage_names immutable property
- validate_stage_sequence utility
- Full pipeline success (all 5 stages)
- Gate rejection → GateRejectedError
- Validation failure → PipelineResult(success=False)
- Execution failure → PipelineResult(success=False)
- Execute retry (transient failures)
- Execute retry: ExecutionError NOT retried
- Unexpected error handling
- Evidence collection: timings, completed_stages, routing
- Adapter registry routing
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from orchestrator.adapter_registry import AdapterRegistry
from orchestrator.exceptions import ExecutionError, GateRejectedError, ValidationError
from orchestrator.models import PipelineResult, Task, TaskStatus
from orchestrator.pipeline import (
    Pipeline,
    PipelineConfigError,
    StageSkipError,
    _STAGE_NAMES,
    _STAGE_SEQUENCE,
)
from policy_engine.engine import GateResult, PolicyEngine


# ---------------------------------------------------------------------------
# Fixtures — mock adapters
# ---------------------------------------------------------------------------


def _make_planner(plan: dict[str, Any] | None = None) -> MagicMock:
    p = MagicMock()
    p.create_plan = AsyncMock(return_value=plan or {"steps": ["a", "b"]})
    return p


def _make_executor(output: dict[str, Any] | None = None) -> MagicMock:
    e = MagicMock()
    e.execute = AsyncMock(return_value=output or {"result": "ok"})
    return e


def _make_validator(failures: list[str] | None = None) -> MagicMock:
    v = MagicMock()
    v.validate = AsyncMock(return_value=failures or [])
    return v


def _make_shipper(output: dict[str, Any] | None = None) -> MagicMock:
    s = MagicMock()
    s.ship = AsyncMock(return_value=output or {"shipped": True})
    return s


def _make_engine(approved: bool = True, reason: str = "") -> MagicMock:
    engine = MagicMock(spec=PolicyEngine)
    engine.evaluate = AsyncMock(return_value=GateResult(approved=approved, reason=reason))
    return engine


def _make_task(**kw: Any) -> Task:
    defaults = {
        "name": "test-task",
        "description": "test description",
        "agent_type": "default",
    }
    defaults.update(kw)
    return Task(**defaults)


def _make_pipeline(**kw: Any) -> Pipeline:
    defaults = {
        "planner": _make_planner(),
        "policy_engine": _make_engine(),
        "executor": _make_executor(),
        "validator": _make_validator(),
        "shipper": _make_shipper(),
    }
    defaults.update(kw)
    return Pipeline(**defaults)


# ---------------------------------------------------------------------------
# PipelineConfigError — startup validation
# ---------------------------------------------------------------------------


class TestPipelineConfigError:
    def test_missing_planner(self) -> None:
        with pytest.raises(PipelineConfigError, match="plan"):
            Pipeline(
                planner=None,  # type: ignore[arg-type]
                policy_engine=_make_engine(),
                executor=_make_executor(),
                validator=_make_validator(),
                shipper=_make_shipper(),
            )

    def test_missing_executor(self) -> None:
        with pytest.raises(PipelineConfigError, match="execute"):
            Pipeline(
                planner=_make_planner(),
                policy_engine=_make_engine(),
                executor=None,  # type: ignore[arg-type]
                validator=_make_validator(),
                shipper=_make_shipper(),
            )

    def test_missing_validator(self) -> None:
        with pytest.raises(PipelineConfigError, match="validate"):
            Pipeline(
                planner=_make_planner(),
                policy_engine=_make_engine(),
                executor=_make_executor(),
                validator=None,  # type: ignore[arg-type]
                shipper=_make_shipper(),
            )

    def test_missing_shipper(self) -> None:
        with pytest.raises(PipelineConfigError, match="ship"):
            Pipeline(
                planner=_make_planner(),
                policy_engine=_make_engine(),
                executor=_make_executor(),
                validator=_make_validator(),
                shipper=None,  # type: ignore[arg-type]
            )

    def test_missing_engine(self) -> None:
        with pytest.raises(PipelineConfigError, match="gate"):
            Pipeline(
                planner=_make_planner(),
                policy_engine=None,  # type: ignore[arg-type]
                executor=_make_executor(),
                validator=_make_validator(),
                shipper=_make_shipper(),
            )

    def test_missing_multiple(self) -> None:
        with pytest.raises(PipelineConfigError, match="plan.*gate"):
            Pipeline(
                planner=None,  # type: ignore[arg-type]
                policy_engine=None,  # type: ignore[arg-type]
                executor=_make_executor(),
                validator=_make_validator(),
                shipper=_make_shipper(),
            )

    def test_all_present_no_error(self) -> None:
        pipeline = _make_pipeline()
        assert pipeline is not None


# ---------------------------------------------------------------------------
# Stage sequence constants
# ---------------------------------------------------------------------------


class TestStageConstants:
    def test_stage_names(self) -> None:
        assert _STAGE_NAMES == ("plan", "gate", "execute", "validate", "ship")

    def test_stage_sequence_matches_names(self) -> None:
        for i, name in enumerate(_STAGE_NAMES):
            assert _STAGE_SEQUENCE[name] == i

    def test_stage_names_property(self) -> None:
        pipeline = _make_pipeline()
        assert pipeline.stage_names == ("plan", "gate", "execute", "validate", "ship")


# ---------------------------------------------------------------------------
# _assert_stage_order
# ---------------------------------------------------------------------------


class TestAssertStageOrder:
    def test_plan_first_ok(self) -> None:
        # No exception
        Pipeline._assert_stage_order("plan", [])

    def test_plan_not_first_error(self) -> None:
        with pytest.raises(StageSkipError, match="must be first"):
            Pipeline._assert_stage_order("plan", ["gate"])

    def test_gate_after_plan_ok(self) -> None:
        Pipeline._assert_stage_order("gate", ["plan"])

    def test_gate_without_plan_error(self) -> None:
        with pytest.raises(StageSkipError, match="plan"):
            Pipeline._assert_stage_order("gate", [])

    def test_execute_after_gate_ok(self) -> None:
        Pipeline._assert_stage_order("execute", ["plan", "gate"])

    def test_execute_skip_gate_error(self) -> None:
        with pytest.raises(StageSkipError, match="gate"):
            Pipeline._assert_stage_order("execute", ["plan"])

    def test_validate_after_execute_ok(self) -> None:
        Pipeline._assert_stage_order("validate", ["plan", "gate", "execute"])

    def test_ship_after_validate_ok(self) -> None:
        Pipeline._assert_stage_order("ship", ["plan", "gate", "execute", "validate"])

    def test_ship_skip_validate_error(self) -> None:
        with pytest.raises(StageSkipError, match="validate"):
            Pipeline._assert_stage_order("ship", ["plan", "gate", "execute"])


# ---------------------------------------------------------------------------
# validate_stage_sequence
# ---------------------------------------------------------------------------


class TestValidateStageSequence:
    def test_full_valid(self) -> None:
        assert Pipeline.validate_stage_sequence(
            ["plan", "gate", "execute", "validate", "ship"]
        ) is True

    def test_partial_valid(self) -> None:
        assert Pipeline.validate_stage_sequence(["plan", "gate"]) is True

    def test_single_valid(self) -> None:
        assert Pipeline.validate_stage_sequence(["plan"]) is True

    def test_empty_valid(self) -> None:
        assert Pipeline.validate_stage_sequence([]) is True

    def test_wrong_order_invalid(self) -> None:
        assert Pipeline.validate_stage_sequence(["gate", "plan"]) is False

    def test_skip_invalid(self) -> None:
        assert Pipeline.validate_stage_sequence(["plan", "execute"]) is False

    def test_unknown_stage_invalid(self) -> None:
        assert Pipeline.validate_stage_sequence(["plan", "unknown"]) is False

    def test_duplicate_invalid(self) -> None:
        assert Pipeline.validate_stage_sequence(["plan", "plan"]) is False


# ---------------------------------------------------------------------------
# Full pipeline success
# ---------------------------------------------------------------------------


class TestPipelineSuccess:
    @pytest.mark.asyncio
    async def test_full_run_success(self) -> None:
        pipeline = _make_pipeline()
        task = _make_task()
        result = await pipeline.run(task)

        assert result.success is True
        assert result.status == TaskStatus.COMPLETED
        assert result.task_id == task.id
        assert result.error is None
        assert result.started_at is not None
        assert result.finished_at is not None
        assert result.finished_at >= result.started_at

    @pytest.mark.asyncio
    async def test_task_transitions_to_completed(self) -> None:
        pipeline = _make_pipeline()
        task = _make_task()
        await pipeline.run(task)
        assert task.status == TaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_evidence_contains_all_stages(self) -> None:
        pipeline = _make_pipeline()
        task = _make_task()
        result = await pipeline.run(task)

        assert "plan" in result.evidence
        assert "gate" in result.evidence
        assert "execution" in result.evidence
        assert "validation" in result.evidence
        assert "ship" in result.evidence

    @pytest.mark.asyncio
    async def test_evidence_timings(self) -> None:
        pipeline = _make_pipeline()
        task = _make_task()
        result = await pipeline.run(task)

        timings = result.evidence.get("_timings", {})
        assert "plan" in timings
        assert "gate" in timings
        assert "execute" in timings
        assert "validate" in timings
        assert "ship" in timings
        for v in timings.values():
            assert isinstance(v, float)
            assert v >= 0

    @pytest.mark.asyncio
    async def test_evidence_completed_stages(self) -> None:
        pipeline = _make_pipeline()
        task = _make_task()
        result = await pipeline.run(task)

        stages = result.evidence.get("_completed_stages", [])
        assert stages == ["plan", "gate", "execute", "validate", "ship"]

    @pytest.mark.asyncio
    async def test_plan_attached_to_task(self) -> None:
        plan_data = {"steps": ["x", "y", "z"]}
        pipeline = _make_pipeline(planner=_make_planner(plan_data))
        task = _make_task()
        await pipeline.run(task)
        assert task.plan == plan_data


# ---------------------------------------------------------------------------
# Gate rejection
# ---------------------------------------------------------------------------


class TestPipelineGateRejection:
    @pytest.mark.asyncio
    async def test_gate_rejected_raises(self) -> None:
        pipeline = _make_pipeline(
            policy_engine=_make_engine(approved=False, reason="high risk")
        )
        task = _make_task()
        with pytest.raises(GateRejectedError) as exc_info:
            await pipeline.run(task)
        assert exc_info.value.reason == "high risk"
        assert task.status == TaskStatus.REJECTED

    @pytest.mark.asyncio
    async def test_gate_rejected_evidence(self) -> None:
        pipeline = _make_pipeline(
            policy_engine=_make_engine(approved=False, reason="denied")
        )
        task = _make_task()
        try:
            await pipeline.run(task)
        except GateRejectedError:
            pass
        # Plan should have completed before gate
        assert task.plan is not None


# ---------------------------------------------------------------------------
# Validation failure
# ---------------------------------------------------------------------------


class TestPipelineValidationFailure:
    @pytest.mark.asyncio
    async def test_validation_failure_returns_failed(self) -> None:
        pipeline = _make_pipeline(
            validator=_make_validator(failures=["test_a failed", "lint error"])
        )
        task = _make_task()
        result = await pipeline.run(task)
        assert result.success is False
        assert result.status == TaskStatus.FAILED
        assert "test_a failed" in result.error

    @pytest.mark.asyncio
    async def test_validation_failure_task_state(self) -> None:
        pipeline = _make_pipeline(
            validator=_make_validator(failures=["fail"])
        )
        task = _make_task()
        await pipeline.run(task)
        assert task.status == TaskStatus.FAILED
        assert task.error is not None

    @pytest.mark.asyncio
    async def test_validation_failure_completed_stages(self) -> None:
        pipeline = _make_pipeline(
            validator=_make_validator(failures=["fail"])
        )
        task = _make_task()
        result = await pipeline.run(task)
        stages = result.evidence.get("_completed_stages", [])
        # validate stage itself fails so it's not in completed
        assert "plan" in stages
        assert "gate" in stages
        assert "execute" in stages
        assert "validate" not in stages
        assert "ship" not in stages


# ---------------------------------------------------------------------------
# Execution failure
# ---------------------------------------------------------------------------


class TestPipelineExecutionFailure:
    @pytest.mark.asyncio
    async def test_execution_error_returns_failed(self) -> None:
        executor = _make_executor()
        executor.execute = AsyncMock(
            side_effect=ExecutionError("t1", "sandbox crash")
        )
        pipeline = _make_pipeline(executor=executor)
        task = _make_task()
        result = await pipeline.run(task)
        assert result.success is False
        assert result.status == TaskStatus.FAILED
        assert "sandbox crash" in result.error

    @pytest.mark.asyncio
    async def test_execution_error_completed_stages(self) -> None:
        executor = _make_executor()
        executor.execute = AsyncMock(
            side_effect=ExecutionError("t1", "fail")
        )
        pipeline = _make_pipeline(executor=executor)
        task = _make_task()
        result = await pipeline.run(task)
        stages = result.evidence.get("_completed_stages", [])
        assert stages == ["plan", "gate"]


# ---------------------------------------------------------------------------
# Execute retry
# ---------------------------------------------------------------------------


class TestPipelineRetry:
    @pytest.mark.asyncio
    async def test_retry_succeeds_after_transient(self) -> None:
        executor = _make_executor()
        call_count = 0

        async def flaky_execute(task: Any) -> dict[str, Any]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("transient")
            return {"result": "ok"}

        executor.execute = flaky_execute
        pipeline = _make_pipeline(executor=executor, execute_retries=2)
        task = _make_task()
        result = await pipeline.run(task)
        assert result.success is True
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_retry_exhausted_fails(self) -> None:
        executor = _make_executor()
        executor.execute = AsyncMock(side_effect=RuntimeError("always fails"))
        pipeline = _make_pipeline(executor=executor, execute_retries=2)
        task = _make_task()
        result = await pipeline.run(task)
        assert result.success is False
        assert "All 3 attempts failed" in result.error

    @pytest.mark.asyncio
    async def test_execution_error_not_retried(self) -> None:
        """ExecutionError is explicit — should NOT be retried."""
        executor = _make_executor()
        executor.execute = AsyncMock(
            side_effect=ExecutionError("t1", "explicit fail")
        )
        pipeline = _make_pipeline(executor=executor, execute_retries=3)
        task = _make_task()
        result = await pipeline.run(task)
        assert result.success is False
        assert executor.execute.call_count == 1  # Not retried

    @pytest.mark.asyncio
    async def test_zero_retries(self) -> None:
        executor = _make_executor()
        executor.execute = AsyncMock(side_effect=RuntimeError("fail"))
        pipeline = _make_pipeline(executor=executor, execute_retries=0)
        task = _make_task()
        result = await pipeline.run(task)
        assert result.success is False
        assert executor.execute.call_count == 1

    @pytest.mark.asyncio
    async def test_negative_retries_treated_as_zero(self) -> None:
        pipeline = _make_pipeline(execute_retries=-5)
        # Should just clamp to 0
        task = _make_task()
        result = await pipeline.run(task)
        assert result.success is True


# ---------------------------------------------------------------------------
# Unexpected errors
# ---------------------------------------------------------------------------


class TestPipelineUnexpectedError:
    @pytest.mark.asyncio
    async def test_unexpected_error_handled(self) -> None:
        planner = _make_planner()
        planner.create_plan = AsyncMock(side_effect=TypeError("unexpected"))
        pipeline = _make_pipeline(planner=planner)
        task = _make_task()
        result = await pipeline.run(task)
        assert result.success is False
        assert result.status == TaskStatus.FAILED
        assert "unexpected" in result.error


# ---------------------------------------------------------------------------
# Adapter registry routing
# ---------------------------------------------------------------------------


class TestPipelineAdapterRegistry:
    @pytest.mark.asyncio
    async def test_registry_routes_planner(self) -> None:
        custom_plan = {"custom": True}
        default_planner = _make_planner({"default": True})
        custom_planner = _make_planner(custom_plan)

        registry = AdapterRegistry(
            default_planner=default_planner,
            default_executor=_make_executor(),
            default_validator=_make_validator(),
            default_shipper=_make_shipper(),
        )
        registry.register("custom-agent", planner=custom_planner)

        pipeline = _make_pipeline(
            planner=default_planner,
            adapter_registry=registry,
        )
        task = _make_task(agent_type="custom-agent")
        result = await pipeline.run(task)
        assert result.success is True
        assert task.plan == custom_plan

    @pytest.mark.asyncio
    async def test_registry_routing_info_in_evidence(self) -> None:
        registry = AdapterRegistry(
            default_planner=_make_planner(),
            default_executor=_make_executor(),
            default_validator=_make_validator(),
            default_shipper=_make_shipper(),
        )
        pipeline = _make_pipeline(adapter_registry=registry)
        task = _make_task()
        result = await pipeline.run(task)
        assert "_routing" in result.evidence

    @pytest.mark.asyncio
    async def test_fallback_to_default_adapter(self) -> None:
        default_plan = {"from": "default"}
        registry = AdapterRegistry(
            default_planner=_make_planner(default_plan),
            default_executor=_make_executor(),
            default_validator=_make_validator(),
            default_shipper=_make_shipper(),
        )
        pipeline = _make_pipeline(
            planner=_make_planner(default_plan),
            adapter_registry=registry,
        )
        task = _make_task(agent_type="unregistered")
        result = await pipeline.run(task)
        assert result.success is True
        assert task.plan == default_plan


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestPipelineEdgeCases:
    @pytest.mark.asyncio
    async def test_empty_validation_passes(self) -> None:
        pipeline = _make_pipeline(validator=_make_validator(failures=[]))
        task = _make_task()
        result = await pipeline.run(task)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_ship_output_in_evidence(self) -> None:
        ship_data = {"pr_url": "https://github.com/org/repo/pull/42"}
        pipeline = _make_pipeline(shipper=_make_shipper(ship_data))
        task = _make_task()
        result = await pipeline.run(task)
        assert result.evidence["ship"] == ship_data
