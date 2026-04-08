"""Tests for BRAIN session tier, concurrent pipeline execution,
batch dispatch endpoint, semaphore limits, and wave execution with 10+ nodes.

Covers:
- BRAIN tier creation and constraints
- 10+ concurrent pipeline executions (asyncio.gather)
- Batch dispatch endpoint
- Semaphore limits respected
- Wave execution with 10+ nodes
- Backward compatibility: MAIN/DM/GROUP unchanged
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from orchestrator.sessions import (
    Session,
    SessionCapacityError,
    SessionManager,
    SessionState,
    SessionTier,
    TIER_CONSTRAINTS,
    TierConstraints,
)
from orchestrator.multi_agent import (
    AgentNode,
    MAX_CONCURRENT_AGENTS,
    MultiAgentOrchestrator,
    WorkflowDefinition,
    WorkflowStatus,
)
from orchestrator.pipeline import (
    Pipeline,
    PipelineRunner,
)
from orchestrator.models import (
    AgentConfig,
    PipelineResult,
    Task,
    TaskStatus,
)
from orchestrator.scheduler import Scheduler


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_scheduler(return_value: Any = None) -> Scheduler:
    if return_value is None:
        return_value = {"result": "ok"}
    scheduler = Scheduler()
    factory = AsyncMock(return_value=return_value)
    config = AgentConfig(
        agent_type="test-agent",
        display_name="Test Agent",
        max_concurrent=20,
    )
    scheduler.register(config, factory)
    return scheduler


def _simple_node(
    node_id: str,
    agent_type: str = "test-agent",
    depends_on: list[str] | None = None,
) -> AgentNode:
    return AgentNode(
        node_id=node_id,
        agent_type=agent_type,
        task_template={"name": f"task-{node_id}", "description": f"Node {node_id}"},
        depends_on=depends_on or [],
    )


class _MockPlanner:
    async def create_plan(self, task: Task) -> dict[str, Any]:
        return {"steps": ["step1"]}


class _MockPolicyEngine:
    async def evaluate(self, task: Any) -> Any:
        return MagicMock(approved=True, reason="ok")


class _MockExecutor:
    async def execute(self, task: Task) -> dict[str, Any]:
        return {"output": "done"}


class _MockValidator:
    async def validate(self, task: Task) -> list[str]:
        return []


class _MockShipper:
    async def ship(self, task: Task) -> dict[str, Any]:
        return {"shipped": True}


def _make_pipeline() -> Pipeline:
    return Pipeline(
        planner=_MockPlanner(),
        policy_engine=_MockPolicyEngine(),
        executor=_MockExecutor(),
        validator=_MockValidator(),
        shipper=_MockShipper(),
    )


# ---------------------------------------------------------------------------
# BRAIN Tier Tests
# ---------------------------------------------------------------------------


class TestBrainTier:
    def test_brain_enum_value(self) -> None:
        assert SessionTier.BRAIN == "brain"

    def test_brain_in_tier_constraints(self) -> None:
        assert SessionTier.BRAIN in TIER_CONSTRAINTS

    def test_brain_constraints_values(self) -> None:
        c = TIER_CONSTRAINTS[SessionTier.BRAIN]
        assert c.allowed_stages == ("plan", "gate", "execute", "validate", "ship")
        assert c.max_concurrent_tasks == 20
        assert c.max_history_messages == 5000
        assert c.can_execute is True
        assert c.can_ship is True
        assert c.max_participants == 1

    def test_brain_session_creation(self) -> None:
        mgr = SessionManager()
        s = mgr.create("brain-user", tier=SessionTier.BRAIN)
        assert s.tier == SessionTier.BRAIN
        assert s.state == SessionState.CREATED
        assert s.constraints.max_concurrent_tasks == 20

    def test_brain_all_stages_allowed(self) -> None:
        mgr = SessionManager()
        s = mgr.create("brain-user", tier=SessionTier.BRAIN)
        for stage in ("plan", "gate", "execute", "validate", "ship"):
            assert mgr.check_stage_allowed(s.session_id, stage)

    def test_brain_high_task_capacity(self) -> None:
        """BRAIN tier supports 20 concurrent tasks."""
        mgr = SessionManager()
        s = mgr.create("brain-user", tier=SessionTier.BRAIN)
        for i in range(20):
            mgr.register_task(s.session_id, f"task-{i}")
        assert len(s.active_tasks) == 20

    def test_brain_task_capacity_exceeded(self) -> None:
        mgr = SessionManager()
        s = mgr.create("brain-user", tier=SessionTier.BRAIN)
        for i in range(20):
            mgr.register_task(s.session_id, f"task-{i}")
        with pytest.raises(SessionCapacityError, match="max concurrent tasks"):
            mgr.register_task(s.session_id, "task-20")

    def test_brain_high_message_limit(self) -> None:
        """BRAIN tier supports 5000 history messages."""
        c = TIER_CONSTRAINTS[SessionTier.BRAIN]
        assert c.max_history_messages == 5000

    def test_brain_single_participant(self) -> None:
        """BRAIN tier is single-participant (orchestrator only)."""
        mgr = SessionManager()
        s = mgr.create("brain-user", tier=SessionTier.BRAIN)
        with pytest.raises(SessionCapacityError, match="max participants"):
            mgr.add_participant(s.session_id, "user-2")

    def test_brain_serialization(self) -> None:
        mgr = SessionManager()
        s = mgr.create("brain-user", tier=SessionTier.BRAIN)
        d = s.to_dict()
        assert d["tier"] == "brain"


# ---------------------------------------------------------------------------
# Backward Compatibility — existing tiers unchanged
# ---------------------------------------------------------------------------


class TestBackwardCompatibility:
    def test_four_tiers(self) -> None:
        assert len(SessionTier) == 4

    def test_all_tiers_have_constraints(self) -> None:
        for tier in SessionTier:
            assert tier in TIER_CONSTRAINTS

    def test_main_unchanged(self) -> None:
        c = TIER_CONSTRAINTS[SessionTier.MAIN]
        assert c.max_concurrent_tasks == 5
        assert c.max_history_messages == 1000
        assert c.max_participants == 1

    def test_dm_unchanged(self) -> None:
        c = TIER_CONSTRAINTS[SessionTier.DM]
        assert c.max_concurrent_tasks == 2
        assert c.can_execute is False
        assert c.can_ship is False

    def test_group_unchanged(self) -> None:
        c = TIER_CONSTRAINTS[SessionTier.GROUP]
        assert c.max_concurrent_tasks == 3
        assert c.max_participants == 50


# ---------------------------------------------------------------------------
# Concurrent Pipeline Execution Tests
# ---------------------------------------------------------------------------


class TestPipelineRunner:
    @pytest.mark.asyncio
    async def test_runner_creation(self) -> None:
        pipeline = _make_pipeline()
        runner = PipelineRunner(pipeline, max_concurrent=10)
        assert runner.max_concurrent == 10

    @pytest.mark.asyncio
    async def test_run_single_task(self) -> None:
        pipeline = _make_pipeline()
        runner = PipelineRunner(pipeline, max_concurrent=10)
        task = Task(name="t1", description="test", agent_type="test")
        result = await runner.run_one(task)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_run_10_concurrent_pipelines(self) -> None:
        """Verify 10+ concurrent pipeline runs complete successfully."""
        pipeline = _make_pipeline()
        runner = PipelineRunner(pipeline, max_concurrent=10)

        tasks = [
            Task(name=f"task-{i}", description=f"test-{i}", agent_type="test")
            for i in range(12)
        ]
        results = await runner.run_batch(tasks)

        assert len(results) == 12
        assert all(r.success for r in results)
        stats = runner.get_stats()
        assert stats["total_runs"] == 12
        assert stats["total_success"] == 12

    @pytest.mark.asyncio
    async def test_semaphore_limits_concurrency(self) -> None:
        """Verify semaphore limits the number of concurrent pipeline runs."""
        max_concurrent = 3
        active_count = 0
        peak_concurrent = 0

        class _TrackingExecutor:
            async def execute(self, task: Task) -> dict[str, Any]:
                nonlocal active_count, peak_concurrent
                active_count += 1
                peak_concurrent = max(peak_concurrent, active_count)
                await asyncio.sleep(0.01)
                active_count -= 1
                return {"output": "done"}

        pipeline = Pipeline(
            planner=_MockPlanner(),
            policy_engine=_MockPolicyEngine(),
            executor=_TrackingExecutor(),
            validator=_MockValidator(),
            shipper=_MockShipper(),
        )
        runner = PipelineRunner(pipeline, max_concurrent=max_concurrent)

        tasks = [
            Task(name=f"t-{i}", description=f"test-{i}", agent_type="test")
            for i in range(10)
        ]
        results = await runner.run_batch(tasks)

        assert len(results) == 10
        assert all(r.success for r in results)
        # Semaphore should limit concurrent runs to max_concurrent
        assert peak_concurrent <= max_concurrent

    @pytest.mark.asyncio
    async def test_batch_partial_failure(self) -> None:
        """Failures in one pipeline run don't affect others."""
        call_count = 0

        class _FailingExecutor:
            async def execute(self, task: Task) -> dict[str, Any]:
                nonlocal call_count
                call_count += 1
                if "fail" in task.name:
                    raise RuntimeError("intentional failure")
                return {"output": "done"}

        pipeline = Pipeline(
            planner=_MockPlanner(),
            policy_engine=_MockPolicyEngine(),
            executor=_FailingExecutor(),
            validator=_MockValidator(),
            shipper=_MockShipper(),
        )
        runner = PipelineRunner(pipeline, max_concurrent=5)

        tasks = [
            Task(name="ok-1", description="test", agent_type="test"),
            Task(name="fail-1", description="test", agent_type="test"),
            Task(name="ok-2", description="test", agent_type="test"),
        ]
        results = await runner.run_batch(tasks)

        assert len(results) == 3
        assert results[0].success is True
        assert results[1].success is False
        assert results[2].success is True


# ---------------------------------------------------------------------------
# Wave Execution with 10+ Nodes
# ---------------------------------------------------------------------------


class TestWaveExecution:
    @pytest.mark.asyncio
    async def test_wave_with_12_parallel_nodes(self) -> None:
        """12 independent nodes in a single wave execute in parallel."""
        nodes = [_simple_node(f"n-{i}") for i in range(12)]
        wf = WorkflowDefinition(
            workflow_id="wf-12",
            name="12-node parallel",
            nodes=nodes,
        )

        # All nodes should be in wave 0
        waves = wf.topological_sort()
        assert len(waves) == 1
        assert len(waves[0]) == 12

        scheduler = _make_scheduler()
        orch = MultiAgentOrchestrator(scheduler, max_concurrent=12)
        orch.register_workflow(wf)

        result = await orch.start_workflow("wf-12", {"test": True})
        assert result.status == WorkflowStatus.COMPLETED
        assert len(result.node_results) == 12

    @pytest.mark.asyncio
    async def test_wave_with_15_parallel_nodes(self) -> None:
        """15 independent nodes — larger than default max_concurrent."""
        nodes = [_simple_node(f"n-{i}") for i in range(15)]
        wf = WorkflowDefinition(
            workflow_id="wf-15",
            name="15-node parallel",
            nodes=nodes,
        )

        waves = wf.topological_sort()
        assert len(waves) == 1
        assert len(waves[0]) == 15

        scheduler = _make_scheduler()
        orch = MultiAgentOrchestrator(scheduler, max_concurrent=15)
        orch.register_workflow(wf)

        result = await orch.start_workflow("wf-15", {"test": True})
        assert result.status == WorkflowStatus.COMPLETED
        assert len(result.node_results) == 15

    @pytest.mark.asyncio
    async def test_wave_semaphore_bounds_parallel_nodes(self) -> None:
        """Semaphore in orchestrator limits actual concurrency within a wave."""
        active_count = 0
        peak_concurrent = 0

        async def _tracking_factory(config: Any, task: Any) -> dict[str, Any]:
            nonlocal active_count, peak_concurrent
            active_count += 1
            peak_concurrent = max(peak_concurrent, active_count)
            await asyncio.sleep(0.01)
            active_count -= 1
            return {"result": "ok"}

        scheduler = Scheduler()
        config = AgentConfig(
            agent_type="test-agent",
            display_name="Test Agent",
            max_concurrent=20,
        )
        scheduler.register(config, _tracking_factory)

        nodes = [_simple_node(f"n-{i}") for i in range(10)]
        wf = WorkflowDefinition(
            workflow_id="wf-sem",
            name="Semaphore test",
            nodes=nodes,
        )

        orch = MultiAgentOrchestrator(scheduler, max_concurrent=4)
        orch.register_workflow(wf)

        result = await orch.start_workflow("wf-sem", {})
        assert result.status == WorkflowStatus.COMPLETED
        assert peak_concurrent <= 4

    @pytest.mark.asyncio
    async def test_multi_wave_with_fan_out(self) -> None:
        """Wave 1: root, Wave 2: 10 parallel nodes, Wave 3: aggregator."""
        children = [
            _simple_node(f"child-{i}", depends_on=["root"])
            for i in range(10)
        ]
        nodes = [
            _simple_node("root"),
            *children,
            _simple_node("agg", depends_on=[f"child-{i}" for i in range(10)]),
        ]
        wf = WorkflowDefinition(
            workflow_id="wf-fan",
            name="Fan-out 10",
            nodes=nodes,
        )

        waves = wf.topological_sort()
        assert len(waves) == 3
        assert len(waves[0]) == 1  # root
        assert len(waves[1]) == 10  # children
        assert len(waves[2]) == 1  # aggregator

        scheduler = _make_scheduler()
        orch = MultiAgentOrchestrator(scheduler, max_concurrent=12)
        orch.register_workflow(wf)

        result = await orch.start_workflow("wf-fan", {"input": "data"})
        assert result.status == WorkflowStatus.COMPLETED
        assert len(result.node_results) == 12


# ---------------------------------------------------------------------------
# MAX_CONCURRENT_AGENTS Config
# ---------------------------------------------------------------------------


class TestMaxConcurrentConfig:
    def test_default_value(self) -> None:
        assert MAX_CONCURRENT_AGENTS == 12

    def test_orchestrator_accepts_custom_max_concurrent(self) -> None:
        scheduler = _make_scheduler()
        orch = MultiAgentOrchestrator(scheduler, max_concurrent=20)
        assert orch._max_concurrent == 20


# ---------------------------------------------------------------------------
# Batch Dispatch Models
# ---------------------------------------------------------------------------


class TestBatchDispatchModels:
    def test_batch_dispatch_request_model(self) -> None:
        from api.models import BatchDispatchRequest, BatchDispatchItem

        item = BatchDispatchItem(
            agent_id="eng-core",
            task_name="test",
            description="test desc",
        )
        req = BatchDispatchRequest(items=[item])
        assert len(req.items) == 1

    def test_batch_dispatch_response_model(self) -> None:
        from api.models import BatchDispatchResponse, BatchDispatchResultItem

        result = BatchDispatchResultItem(
            agent_id="eng-core",
            task_id="abc123",
            status="dispatched",
        )
        resp = BatchDispatchResponse(
            results=[result],
            total=1,
            dispatched=1,
            failed=0,
        )
        assert resp.dispatched == 1
        assert resp.failed == 0

    def test_batch_dispatch_error_item(self) -> None:
        from api.models import BatchDispatchResultItem

        result = BatchDispatchResultItem(
            agent_id="unknown",
            status="error",
            error="Agent not found",
        )
        assert result.task_id is None
        assert result.error == "Agent not found"


# ---------------------------------------------------------------------------
# Settings Tests
# ---------------------------------------------------------------------------


class TestBrainSettings:
    def test_settings_defaults(self) -> None:
        from config.settings import Settings

        s = Settings(
            occp_env="development",
            _env_file=None,
        )
        assert s.max_concurrent_agents == 12
        assert s.max_concurrent_pipelines == 10
        assert s.brain_session_timeout == 3600
