"""Tests for the Orchestrator module."""

from __future__ import annotations

import pytest
from orchestrator.models import Task, TaskStatus, RiskLevel, AgentConfig, PipelineResult
from orchestrator.exceptions import (
    GateRejectedError,
    ValidationError,
    ExecutionError,
    AgentNotFoundError,
)
from orchestrator.scheduler import Scheduler
from orchestrator.pipeline import Pipeline


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class TestTask:
    def test_default_status_is_pending(self) -> None:
        task = Task(name="test", description="desc", agent_type="test")
        assert task.status == TaskStatus.PENDING

    def test_transition_updates_status(self) -> None:
        task = Task(name="test", description="desc", agent_type="test")
        task.transition(TaskStatus.PLANNING)
        assert task.status == TaskStatus.PLANNING

    def test_invalid_transition_raises(self) -> None:
        task = Task(name="test", description="desc", agent_type="test")
        task.transition(TaskStatus.PLANNING)
        task.transition(TaskStatus.GATED)
        task.transition(TaskStatus.EXECUTING)
        task.transition(TaskStatus.VALIDATING)
        task.transition(TaskStatus.SHIPPING)
        task.transition(TaskStatus.COMPLETED)
        with pytest.raises(ValueError, match="Invalid transition"):
            task.transition(TaskStatus.PENDING)

    def test_failed_is_terminal(self) -> None:
        task = Task(name="test", description="desc", agent_type="test")
        task.transition(TaskStatus.PLANNING)
        task.transition(TaskStatus.FAILED)
        with pytest.raises(ValueError, match="Invalid transition"):
            task.transition(TaskStatus.PLANNING)

    def test_rejected_is_terminal(self) -> None:
        task = Task(name="test", description="desc", agent_type="test")
        task.transition(TaskStatus.PLANNING)
        task.transition(TaskStatus.GATED)
        task.transition(TaskStatus.REJECTED)
        with pytest.raises(ValueError, match="Invalid transition"):
            task.transition(TaskStatus.EXECUTING)

    def test_id_is_generated(self) -> None:
        t1 = Task(name="a", description="b", agent_type="test")
        t2 = Task(name="a", description="b", agent_type="test")
        assert t1.id != t2.id

    def test_risk_level_default(self) -> None:
        task = Task(name="test", description="desc", agent_type="test")
        assert task.risk_level == RiskLevel.LOW


class TestAgentConfig:
    def test_defaults(self) -> None:
        cfg = AgentConfig(agent_type="claude", display_name="Claude Code")
        assert cfg.max_concurrent == 1
        assert cfg.timeout_seconds == 300


class TestPipelineResult:
    def test_success_result(self) -> None:
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        result = PipelineResult(
            task_id="t1",
            success=True,
            status=TaskStatus.COMPLETED,
            started_at=now,
            finished_at=now,
        )
        assert result.success
        assert result.error is None


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class TestExceptions:
    def test_gate_rejected(self) -> None:
        exc = GateRejectedError("t1", "PII detected")
        assert "t1" in str(exc)
        assert "PII detected" in str(exc)

    def test_validation_error(self) -> None:
        exc = ValidationError("t2", ["test failed", "lint failed"])
        assert "t2" in str(exc)
        assert "test failed" in str(exc)

    def test_execution_error(self) -> None:
        exc = ExecutionError("t3", "sandbox crash")
        assert "sandbox crash" in str(exc)

    def test_agent_not_found(self) -> None:
        exc = AgentNotFoundError("unknown_agent")
        assert "unknown_agent" in str(exc)


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------

class TestScheduler:
    def test_register_and_list(self) -> None:
        sched = Scheduler()
        cfg = AgentConfig(agent_type="test", display_name="Test Agent")
        sched.register(cfg, _dummy_factory)
        assert "test" in sched.registered_types

    def test_unregister(self) -> None:
        sched = Scheduler()
        cfg = AgentConfig(agent_type="test", display_name="Test Agent")
        sched.register(cfg, _dummy_factory)
        sched.unregister("test")
        assert "test" not in sched.registered_types

    @pytest.mark.asyncio
    async def test_dispatch_unknown_agent_raises(self) -> None:
        sched = Scheduler()
        task = Task(name="t", description="d", agent_type="nonexistent")
        with pytest.raises(AgentNotFoundError):
            await sched.dispatch(task)

    @pytest.mark.asyncio
    async def test_dispatch_success(self) -> None:
        sched = Scheduler()
        cfg = AgentConfig(agent_type="echo", display_name="Echo")
        sched.register(cfg, _dummy_factory)
        task = Task(name="t", description="d", agent_type="echo")
        result = await sched.dispatch(task)
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_dispatch_many(self) -> None:
        sched = Scheduler()
        cfg = AgentConfig(
            agent_type="echo", display_name="Echo", max_concurrent=5
        )
        sched.register(cfg, _dummy_factory)
        tasks = [
            Task(name=f"t{i}", description="d", agent_type="echo")
            for i in range(3)
        ]
        results = await sched.dispatch_many(tasks)
        assert len(results) == 3
        assert all(r == "ok" for r in results)


# ---------------------------------------------------------------------------
# Pipeline (VAP full lifecycle)
# ---------------------------------------------------------------------------

class _MockPlanner:
    async def create_plan(self, task: Task) -> dict:
        return {"steps": ["step1", "step2"]}


class _MockExecutor:
    async def execute(self, task: Task) -> dict:
        return {"output": "done"}


class _MockFailingExecutor:
    async def execute(self, task: Task) -> dict:
        raise ExecutionError(task.id, "sandbox crash")


class _MockValidator:
    async def validate(self, task: Task) -> list[str]:
        return []  # no failures


class _MockFailingValidator:
    async def validate(self, task: Task) -> list[str]:
        return ["test_foo failed"]


class _MockShipper:
    async def ship(self, task: Task) -> dict:
        return {"pr": "#1"}


class _ApprovingPolicyEngine:
    async def evaluate(self, task):
        from policy_engine.engine import GateResult
        return GateResult(approved=True)


class _RejectingPolicyEngine:
    async def evaluate(self, task):
        from policy_engine.engine import GateResult
        return GateResult(approved=False, reason="PII detected")


class TestPipeline:
    def _make_pipeline(self, **overrides):
        defaults = dict(
            planner=_MockPlanner(),
            policy_engine=_ApprovingPolicyEngine(),
            executor=_MockExecutor(),
            validator=_MockValidator(),
            shipper=_MockShipper(),
        )
        defaults.update(overrides)
        return Pipeline(**defaults)

    @pytest.mark.asyncio
    async def test_full_success_pipeline(self) -> None:
        pipe = self._make_pipeline()
        task = Task(name="build", description="test build", agent_type="claude")
        result = await pipe.run(task)
        assert result.success is True
        assert result.status == TaskStatus.COMPLETED
        assert "plan" in result.evidence
        assert "gate" in result.evidence
        assert "execution" in result.evidence
        assert "validation" in result.evidence
        assert "ship" in result.evidence

    @pytest.mark.asyncio
    async def test_gate_rejection(self) -> None:
        pipe = self._make_pipeline(policy_engine=_RejectingPolicyEngine())
        task = Task(name="risky", description="has PII", agent_type="claude")
        with pytest.raises(GateRejectedError):
            await pipe.run(task)
        assert task.status == TaskStatus.REJECTED

    @pytest.mark.asyncio
    async def test_execution_failure(self) -> None:
        pipe = self._make_pipeline(executor=_MockFailingExecutor())
        task = Task(name="crash", description="will crash", agent_type="claude")
        result = await pipe.run(task)
        assert result.success is False
        assert result.status == TaskStatus.FAILED
        assert "sandbox crash" in result.error

    @pytest.mark.asyncio
    async def test_validation_failure(self) -> None:
        pipe = self._make_pipeline(validator=_MockFailingValidator())
        task = Task(name="bad", description="fails validation", agent_type="claude")
        result = await pipe.run(task)
        assert result.success is False
        assert result.status == TaskStatus.FAILED
        assert "test_foo failed" in result.error


async def _dummy_factory(_cfg: AgentConfig) -> str:
    return "ok"
