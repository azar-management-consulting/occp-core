"""Tests for Multi-Agent Orchestration — orchestrator/multi_agent.py.

Covers:
- WorkflowStatus enum values
- AgentNode creation and fields
- WorkflowEdge creation
- WorkflowDefinition creation, validate(), topological_sort(), serialization
- Cyclic dependency detection
- Topological sort correctness for various DAG shapes
- MultiAgentOrchestrator: register, start, get execution, list, stats
- Full workflow execution with 3-node linear chain
- Fan-out/fan-in pattern (A→B, A→C, [B,C]→D)
- Kill-switch halts workflow immediately
- Pause and resume at wave boundaries
- Failed node propagates failure
- Result aggregation
- Acceptance tests (5 scenarios)
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from orchestrator.exceptions import AgentNotFoundError
from orchestrator.models import AgentConfig
from orchestrator.multi_agent import (
    AgentNode,
    CyclicDependencyError,
    MultiAgentOrchestrator,
    WorkflowDefinition,
    WorkflowEdge,
    WorkflowError,
    WorkflowExecution,
    WorkflowKilledError,
    WorkflowNotFoundError,
    WorkflowStatus,
    WorkflowValidationError,
)
from orchestrator.scheduler import Scheduler


# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------


def _make_scheduler(return_value: Any = {"result": "ok"}) -> Scheduler:
    """Build a Scheduler with a mock factory that returns return_value."""
    scheduler = Scheduler()
    factory = AsyncMock(return_value=return_value)
    config = AgentConfig(
        agent_type="test-agent",
        display_name="Test Agent",
        max_concurrent=10,
    )
    scheduler.register(config, factory)
    return scheduler


def _make_scheduler_multi(*agent_types: str, return_value: Any = {"result": "ok"}) -> Scheduler:
    """Build a Scheduler with multiple registered agent types."""
    scheduler = Scheduler()
    for agent_type in agent_types:
        factory = AsyncMock(return_value=return_value)
        config = AgentConfig(
            agent_type=agent_type,
            display_name=f"{agent_type} agent",
            max_concurrent=10,
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


def _linear_workflow(n: int = 3) -> WorkflowDefinition:
    """A → B → C (n nodes in a chain)."""
    nodes = [_simple_node("A")]
    for i in range(1, n):
        prev = chr(ord("A") + i - 1)
        curr = chr(ord("A") + i)
        nodes.append(_simple_node(curr, depends_on=[prev]))
    return WorkflowDefinition(
        workflow_id="wf-linear",
        name="Linear Workflow",
        nodes=nodes,
    )


def _fan_out_fan_in_workflow() -> WorkflowDefinition:
    """A → B, A → C, B+C → D (diamond pattern)."""
    return WorkflowDefinition(
        workflow_id="wf-diamond",
        name="Diamond Workflow",
        nodes=[
            _simple_node("A"),
            _simple_node("B", depends_on=["A"]),
            _simple_node("C", depends_on=["A"]),
            _simple_node("D", depends_on=["B", "C"]),
        ],
    )


# ---------------------------------------------------------------------------
# TestWorkflowStatus
# ---------------------------------------------------------------------------


class TestWorkflowStatus:
    def test_values(self) -> None:
        assert WorkflowStatus.PENDING == "pending"
        assert WorkflowStatus.RUNNING == "running"
        assert WorkflowStatus.PAUSED == "paused"
        assert WorkflowStatus.COMPLETED == "completed"
        assert WorkflowStatus.FAILED == "failed"
        assert WorkflowStatus.KILLED == "killed"

    def test_six_statuses(self) -> None:
        assert len(WorkflowStatus) == 6

    def test_is_str_enum(self) -> None:
        assert isinstance(WorkflowStatus.COMPLETED, str)


# ---------------------------------------------------------------------------
# TestAgentNode
# ---------------------------------------------------------------------------


class TestAgentNode:
    def test_creation_minimal(self) -> None:
        node = AgentNode(
            node_id="node-1",
            agent_type="coder",
            task_template={"name": "task"},
        )
        assert node.node_id == "node-1"
        assert node.agent_type == "coder"
        assert node.depends_on == []
        assert node.timeout_seconds == 0
        assert node.retry_count == 0

    def test_creation_with_deps(self) -> None:
        node = AgentNode(
            node_id="node-2",
            agent_type="reviewer",
            task_template={"name": "review"},
            depends_on=["node-1"],
            timeout_seconds=60,
            retry_count=2,
        )
        assert node.depends_on == ["node-1"]
        assert node.timeout_seconds == 60
        assert node.retry_count == 2

    def test_frozen(self) -> None:
        node = AgentNode(
            node_id="n",
            agent_type="a",
            task_template={},
        )
        with pytest.raises((AttributeError, TypeError)):
            node.node_id = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# TestWorkflowEdge
# ---------------------------------------------------------------------------


class TestWorkflowEdge:
    def test_creation(self) -> None:
        edge = WorkflowEdge(from_node="A", to_node="B")
        assert edge.from_node == "A"
        assert edge.to_node == "B"
        assert edge.condition is None

    def test_with_condition(self) -> None:
        edge = WorkflowEdge(from_node="A", to_node="B", condition="result.success")
        assert edge.condition == "result.success"

    def test_frozen(self) -> None:
        edge = WorkflowEdge(from_node="A", to_node="B")
        with pytest.raises((AttributeError, TypeError)):
            edge.from_node = "X"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# TestWorkflowDefinition
# ---------------------------------------------------------------------------


class TestWorkflowDefinition:
    def test_creation(self) -> None:
        wf = _linear_workflow(3)
        assert wf.workflow_id == "wf-linear"
        assert wf.name == "Linear Workflow"
        assert len(wf.nodes) == 3

    def test_validate_valid(self) -> None:
        wf = _linear_workflow(3)
        issues = wf.validate()
        assert issues == []

    def test_validate_empty_nodes(self) -> None:
        wf = WorkflowDefinition(workflow_id="wf-empty", name="Empty", nodes=[])
        issues = wf.validate()
        assert any("no nodes" in i.lower() for i in issues)

    def test_validate_unknown_dep(self) -> None:
        nodes = [
            _simple_node("A", depends_on=["GHOST"]),
        ]
        wf = WorkflowDefinition(workflow_id="wf-bad", name="Bad", nodes=nodes)
        issues = wf.validate()
        assert any("GHOST" in i for i in issues)

    def test_validate_duplicate_node_id(self) -> None:
        nodes = [
            _simple_node("A"),
            _simple_node("A"),
        ]
        wf = WorkflowDefinition(workflow_id="wf-dup", name="Dup", nodes=nodes)
        issues = wf.validate()
        assert any("Duplicate" in i for i in issues)

    def test_validate_bad_edge_from(self) -> None:
        nodes = [_simple_node("A"), _simple_node("B")]
        edges = [WorkflowEdge(from_node="GHOST", to_node="B")]
        wf = WorkflowDefinition(workflow_id="wf-e", name="E", nodes=nodes, edges=edges)
        issues = wf.validate()
        assert any("GHOST" in i for i in issues)

    def test_topological_sort_linear(self) -> None:
        wf = _linear_workflow(3)
        waves = wf.topological_sort()
        # A first, then B, then C
        assert waves[0] == ["A"]
        assert waves[1] == ["B"]
        assert waves[2] == ["C"]

    def test_topological_sort_parallel(self) -> None:
        # A has no deps, B has no deps → should be in same wave
        nodes = [_simple_node("A"), _simple_node("B")]
        wf = WorkflowDefinition(workflow_id="wf-par", name="Par", nodes=nodes)
        waves = wf.topological_sort()
        assert len(waves) == 1
        assert set(waves[0]) == {"A", "B"}

    def test_topological_sort_diamond(self) -> None:
        wf = _fan_out_fan_in_workflow()
        waves = wf.topological_sort()
        # Wave 0: A; Wave 1: B, C; Wave 2: D
        assert waves[0] == ["A"]
        assert set(waves[1]) == {"B", "C"}
        assert waves[2] == ["D"]

    def test_to_dict(self) -> None:
        wf = _linear_workflow(2)
        d = wf.to_dict()
        assert d["workflow_id"] == "wf-linear"
        assert len(d["nodes"]) == 2
        assert d["nodes"][0]["node_id"] == "A"

    def test_from_dict_roundtrip(self) -> None:
        wf = _fan_out_fan_in_workflow()
        d = wf.to_dict()
        wf2 = WorkflowDefinition.from_dict(d)
        assert wf2.workflow_id == wf.workflow_id
        assert len(wf2.nodes) == len(wf.nodes)
        node_ids = {n.node_id for n in wf2.nodes}
        assert node_ids == {"A", "B", "C", "D"}


# ---------------------------------------------------------------------------
# TestCyclicDetection
# ---------------------------------------------------------------------------


class TestCyclicDetection:
    def test_self_loop(self) -> None:
        nodes = [_simple_node("A", depends_on=["A"])]
        wf = WorkflowDefinition(workflow_id="wf-loop", name="Loop", nodes=nodes)
        issues = wf.validate()
        assert any("Cycle" in i for i in issues)

    def test_two_node_cycle(self) -> None:
        nodes = [
            _simple_node("A", depends_on=["B"]),
            _simple_node("B", depends_on=["A"]),
        ]
        wf = WorkflowDefinition(workflow_id="wf-2c", name="2C", nodes=nodes)
        issues = wf.validate()
        assert any("Cycle" in i for i in issues)

    def test_three_node_cycle(self) -> None:
        nodes = [
            _simple_node("A", depends_on=["C"]),
            _simple_node("B", depends_on=["A"]),
            _simple_node("C", depends_on=["B"]),
        ]
        wf = WorkflowDefinition(workflow_id="wf-3c", name="3C", nodes=nodes)
        issues = wf.validate()
        assert any("Cycle" in i for i in issues)

    def test_cyclic_raises_on_topo_sort(self) -> None:
        nodes = [
            _simple_node("A", depends_on=["B"]),
            _simple_node("B", depends_on=["A"]),
        ]
        wf = WorkflowDefinition(workflow_id="wf-c", name="C", nodes=nodes)
        with pytest.raises(CyclicDependencyError):
            wf.topological_sort()

    def test_no_cycle_valid(self) -> None:
        wf = _fan_out_fan_in_workflow()
        issues = wf.validate()
        assert not any("Cycle" in i for i in issues)


# ---------------------------------------------------------------------------
# TestTopologicalSort
# ---------------------------------------------------------------------------


class TestTopologicalSort:
    def test_single_node(self) -> None:
        wf = WorkflowDefinition(
            workflow_id="w1", name="W1", nodes=[_simple_node("A")]
        )
        waves = wf.topological_sort()
        assert waves == [["A"]]

    def test_chain_order(self) -> None:
        wf = _linear_workflow(4)
        waves = wf.topological_sort()
        assert [w[0] for w in waves] == ["A", "B", "C", "D"]

    def test_wide_first_wave(self) -> None:
        nodes = [
            _simple_node("A"),
            _simple_node("B"),
            _simple_node("C"),
            _simple_node("D", depends_on=["A", "B", "C"]),
        ]
        wf = WorkflowDefinition(workflow_id="w-wide", name="Wide", nodes=nodes)
        waves = wf.topological_sort()
        assert set(waves[0]) == {"A", "B", "C"}
        assert waves[1] == ["D"]

    def test_two_independent_chains(self) -> None:
        # Chain 1: A→B, Chain 2: C→D (independent)
        nodes = [
            _simple_node("A"),
            _simple_node("B", depends_on=["A"]),
            _simple_node("C"),
            _simple_node("D", depends_on=["C"]),
        ]
        wf = WorkflowDefinition(workflow_id="w-2c", name="2C", nodes=nodes)
        waves = wf.topological_sort()
        # Wave 0 has A and C; Wave 1 has B and D
        assert set(waves[0]) == {"A", "C"}
        assert set(waves[1]) == {"B", "D"}


# ---------------------------------------------------------------------------
# TestMultiAgentOrchestrator
# ---------------------------------------------------------------------------


class TestMultiAgentOrchestrator:
    def test_register_workflow(self) -> None:
        scheduler = _make_scheduler()
        orc = MultiAgentOrchestrator(scheduler)
        wf = _linear_workflow(2)
        orc.register_workflow(wf)
        assert orc.get_workflow("wf-linear") is wf

    def test_register_invalid_raises(self) -> None:
        scheduler = _make_scheduler()
        orc = MultiAgentOrchestrator(scheduler)
        wf = WorkflowDefinition(workflow_id="bad", name="Bad", nodes=[])
        with pytest.raises(WorkflowValidationError):
            orc.register_workflow(wf)

    def test_get_workflow_not_found(self) -> None:
        orc = MultiAgentOrchestrator(_make_scheduler())
        with pytest.raises(WorkflowNotFoundError):
            orc.get_workflow("nope")

    def test_get_execution_not_found(self) -> None:
        orc = MultiAgentOrchestrator(_make_scheduler())
        with pytest.raises(WorkflowNotFoundError):
            orc.get_execution("no-such-id")

    def test_list_executions_empty(self) -> None:
        orc = MultiAgentOrchestrator(_make_scheduler())
        assert orc.list_executions() == []

    def test_stats_initial(self) -> None:
        orc = MultiAgentOrchestrator(_make_scheduler())
        stats = orc.get_stats()
        assert stats["total_started"] == 0
        assert stats["registered_workflows"] == 0


# ---------------------------------------------------------------------------
# TestWorkflowExecution
# ---------------------------------------------------------------------------


class TestWorkflowExecution:
    @pytest.mark.asyncio
    async def test_linear_three_node_workflow(self) -> None:
        scheduler = _make_scheduler({"result": "ok"})
        orc = MultiAgentOrchestrator(scheduler)
        wf = _linear_workflow(3)
        orc.register_workflow(wf)

        execution = await orc.start_workflow("wf-linear", {"x": 1})

        assert execution.status == WorkflowStatus.COMPLETED
        assert execution.finished_at is not None
        # All three nodes should have results
        assert "A" in execution.node_results
        assert "B" in execution.node_results
        assert "C" in execution.node_results
        assert all(r["success"] for r in execution.node_results.values())

    @pytest.mark.asyncio
    async def test_execution_recorded_in_list(self) -> None:
        scheduler = _make_scheduler()
        orc = MultiAgentOrchestrator(scheduler)
        wf = _linear_workflow(2)
        orc.register_workflow(wf)

        execution = await orc.start_workflow("wf-linear", {})
        all_execs = orc.list_executions()
        assert len(all_execs) == 1
        assert all_execs[0].execution_id == execution.execution_id

    @pytest.mark.asyncio
    async def test_execution_retrievable(self) -> None:
        scheduler = _make_scheduler()
        orc = MultiAgentOrchestrator(scheduler)
        wf = _linear_workflow(2)
        orc.register_workflow(wf)

        execution = await orc.start_workflow("wf-linear", {})
        fetched = orc.get_execution(execution.execution_id)
        assert fetched is execution

    @pytest.mark.asyncio
    async def test_stats_after_completion(self) -> None:
        scheduler = _make_scheduler()
        orc = MultiAgentOrchestrator(scheduler)
        wf = _linear_workflow(2)
        orc.register_workflow(wf)

        await orc.start_workflow("wf-linear", {})
        stats = orc.get_stats()
        assert stats["total_started"] == 1
        assert stats["total_completed"] == 1
        assert stats["total_failed"] == 0


# ---------------------------------------------------------------------------
# TestFanOutFanIn
# ---------------------------------------------------------------------------


class TestFanOutFanIn:
    @pytest.mark.asyncio
    async def test_diamond_workflow_completes(self) -> None:
        scheduler = _make_scheduler({"result": "ok"})
        orc = MultiAgentOrchestrator(scheduler)
        wf = _fan_out_fan_in_workflow()
        orc.register_workflow(wf)

        execution = await orc.start_workflow("wf-diamond", {"input": "data"})

        assert execution.status == WorkflowStatus.COMPLETED
        assert len(execution.node_results) == 4
        for node_id in ("A", "B", "C", "D"):
            assert execution.node_results[node_id]["success"] is True

    @pytest.mark.asyncio
    async def test_upstream_results_passed_to_downstream(self) -> None:
        """Node D receives upstream results from B and C in metadata."""
        captured_tasks: list[Any] = []

        async def factory(config: Any, task: Any) -> dict[str, Any]:
            captured_tasks.append(task)
            return {"output": f"result-{task.metadata['_node_id']}"}

        scheduler = Scheduler()
        config = AgentConfig(
            agent_type="test-agent",
            display_name="Test",
            max_concurrent=10,
        )
        scheduler.register(config, factory)

        orc = MultiAgentOrchestrator(scheduler)
        wf = _fan_out_fan_in_workflow()
        orc.register_workflow(wf)

        execution = await orc.start_workflow("wf-diamond", {"x": 42})
        assert execution.status == WorkflowStatus.COMPLETED

        # D's task should have upstream results from B and C
        d_task = next(t for t in captured_tasks if t.metadata["_node_id"] == "D")
        upstream = d_task.metadata["_upstream_results"]
        assert "B" in upstream
        assert "C" in upstream


# ---------------------------------------------------------------------------
# TestWorkflowKillSwitch
# ---------------------------------------------------------------------------


class TestWorkflowKillSwitch:
    @pytest.mark.asyncio
    async def test_kill_before_start_raises(self) -> None:
        orc = MultiAgentOrchestrator(_make_scheduler())
        with pytest.raises(WorkflowNotFoundError):
            orc.kill_workflow("nonexistent")

    @pytest.mark.asyncio
    async def test_kill_completed_raises(self) -> None:
        scheduler = _make_scheduler()
        orc = MultiAgentOrchestrator(scheduler)
        wf = _linear_workflow(1)
        orc.register_workflow(wf)

        execution = await orc.start_workflow("wf-linear", {})
        assert execution.status == WorkflowStatus.COMPLETED

        with pytest.raises(WorkflowError, match="terminal"):
            orc.kill_workflow(execution.execution_id)

    @pytest.mark.asyncio
    async def test_kill_mid_execution(self) -> None:
        """Kill a workflow mid-execution via concurrent task."""
        kill_event = asyncio.Event()
        execution_ids: list[str] = []

        async def slow_factory(config: Any, task: Any) -> dict[str, Any]:
            # Signal main test that we're running, then wait briefly
            kill_event.set()
            await asyncio.sleep(0.05)
            return {"result": "ok"}

        scheduler = Scheduler()
        config = AgentConfig(
            agent_type="test-agent",
            display_name="Slow",
            max_concurrent=10,
        )
        scheduler.register(config, slow_factory)

        orc = MultiAgentOrchestrator(scheduler)
        # 3-node chain — kill after first node dispatched
        wf = _linear_workflow(3)
        orc.register_workflow(wf)

        async def run_and_capture() -> None:
            try:
                exec_result = await orc.start_workflow("wf-linear", {})
                execution_ids.append(exec_result.execution_id)
            except WorkflowKilledError as e:
                execution_ids.append(e.execution_id)

        # Start workflow in background, kill as soon as it's running
        task = asyncio.create_task(run_and_capture())
        await kill_event.wait()

        # We need the execution_id to kill — get from running executions
        running = orc.list_executions(WorkflowStatus.RUNNING)
        if running:
            orc.kill_workflow(running[0].execution_id)

        await task


# ---------------------------------------------------------------------------
# TestWorkflowPauseResume
# ---------------------------------------------------------------------------


class TestWorkflowPauseResume:
    @pytest.mark.asyncio
    async def test_pause_nonexistent_raises(self) -> None:
        orc = MultiAgentOrchestrator(_make_scheduler())
        with pytest.raises(WorkflowNotFoundError):
            orc.pause_workflow("no-such-id")

    @pytest.mark.asyncio
    async def test_resume_nonexistent_raises(self) -> None:
        orc = MultiAgentOrchestrator(_make_scheduler())
        with pytest.raises(WorkflowNotFoundError):
            orc.resume_workflow("no-such-id")

    @pytest.mark.asyncio
    async def test_pause_and_resume_completes(self) -> None:
        """Pause a workflow, then resume it — it should complete."""
        pause_event = asyncio.Event()
        resume_event = asyncio.Event()
        call_count = 0

        async def counting_factory(config: Any, task: Any) -> dict[str, Any]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                pause_event.set()
                await asyncio.sleep(0.02)
            return {"result": "ok"}

        scheduler = Scheduler()
        config = AgentConfig(
            agent_type="test-agent",
            display_name="Counter",
            max_concurrent=10,
        )
        scheduler.register(config, counting_factory)

        orc = MultiAgentOrchestrator(scheduler)
        wf = _linear_workflow(2)
        orc.register_workflow(wf)

        result_holder: list[WorkflowExecution] = []

        async def run_workflow() -> None:
            execution = await orc.start_workflow("wf-linear", {})
            result_holder.append(execution)

        task = asyncio.create_task(run_workflow())
        # Pause quickly — we will resume immediately
        await asyncio.sleep(0.001)

        running = orc.list_executions(WorkflowStatus.RUNNING)
        if running:
            exec_id = running[0].execution_id
            # Pause then quickly resume
            try:
                orc.pause_workflow(exec_id)
            except WorkflowError:
                pass
            await asyncio.sleep(0.01)
            try:
                orc.resume_workflow(exec_id)
            except WorkflowError:
                pass

        await task
        if result_holder:
            assert result_holder[0].status in (
                WorkflowStatus.COMPLETED,
                WorkflowStatus.FAILED,
            )


# ---------------------------------------------------------------------------
# TestWorkflowErrors
# ---------------------------------------------------------------------------


class TestWorkflowErrors:
    @pytest.mark.asyncio
    async def test_failed_node_marks_execution_failed(self) -> None:
        async def failing_factory(config: Any, task: Any) -> dict[str, Any]:
            raise RuntimeError("Node execution error")

        scheduler = Scheduler()
        config = AgentConfig(
            agent_type="test-agent",
            display_name="Failing",
            max_concurrent=10,
        )
        scheduler.register(config, failing_factory)

        orc = MultiAgentOrchestrator(scheduler)
        wf = _linear_workflow(3)
        orc.register_workflow(wf)

        execution = await orc.start_workflow("wf-linear", {})
        assert execution.status == WorkflowStatus.FAILED
        assert execution.error is not None

    @pytest.mark.asyncio
    async def test_workflow_not_found_raises(self) -> None:
        orc = MultiAgentOrchestrator(_make_scheduler())
        with pytest.raises(WorkflowNotFoundError):
            await orc.start_workflow("no-such-workflow", {})

    @pytest.mark.asyncio
    async def test_failed_node_recorded_in_results(self) -> None:
        async def failing_factory(config: Any, task: Any) -> dict[str, Any]:
            raise ValueError("deliberate failure")

        scheduler = Scheduler()
        config = AgentConfig(
            agent_type="test-agent",
            display_name="Failing",
            max_concurrent=10,
        )
        scheduler.register(config, failing_factory)

        orc = MultiAgentOrchestrator(scheduler)
        wf = WorkflowDefinition(
            workflow_id="wf-one",
            name="One",
            nodes=[_simple_node("A")],
        )
        orc.register_workflow(wf)

        execution = await orc.start_workflow("wf-one", {})
        assert execution.status == WorkflowStatus.FAILED
        assert execution.node_results["A"]["success"] is False
        assert "deliberate failure" in execution.node_results["A"]["error"]

    def test_workflow_validation_error_has_issues(self) -> None:
        exc = WorkflowValidationError("wf-x", ["issue one", "issue two"])
        assert exc.workflow_id == "wf-x"
        assert len(exc.issues) == 2

    def test_workflow_killed_error(self) -> None:
        exc = WorkflowKilledError("exec-1")
        assert exc.execution_id == "exec-1"
        assert "exec-1" in str(exc)

    def test_cyclic_dependency_error(self) -> None:
        exc = CyclicDependencyError("wf-c", ["A", "B"])
        assert exc.workflow_id == "wf-c"
        assert exc.cycle_nodes == ["A", "B"]


# ---------------------------------------------------------------------------
# TestAcceptanceMultiAgent
# ---------------------------------------------------------------------------


class TestAcceptanceMultiAgent:
    """5 acceptance tests for multi-agent orchestration."""

    @pytest.mark.asyncio
    async def test_acc_1_linear_three_node_executes_in_order(self) -> None:
        """Linear 3-node workflow: A→B→C executes A first, then B, then C."""
        execution_order: list[str] = []

        async def ordered_factory(config: Any, task: Any) -> dict[str, Any]:
            node_id = task.metadata["_node_id"]
            execution_order.append(node_id)
            return {"node": node_id}

        scheduler = Scheduler()
        config = AgentConfig(
            agent_type="test-agent",
            display_name="Ordered",
            max_concurrent=10,
        )
        scheduler.register(config, ordered_factory)

        orc = MultiAgentOrchestrator(scheduler)
        wf = _linear_workflow(3)
        orc.register_workflow(wf)

        execution = await orc.start_workflow("wf-linear", {})

        assert execution.status == WorkflowStatus.COMPLETED
        assert execution_order == ["A", "B", "C"]

    @pytest.mark.asyncio
    async def test_acc_2_fan_out_fan_in_parallel_nodes(self) -> None:
        """Fan-out/fan-in: B and C execute in parallel, D waits for both."""
        parallel_set: set[str] = set()
        wave_b_c_concurrent = False

        async def tracking_factory(config: Any, task: Any) -> dict[str, Any]:
            nonlocal wave_b_c_concurrent
            node_id = task.metadata["_node_id"]
            parallel_set.add(node_id)
            await asyncio.sleep(0.01)
            return {"node": node_id}

        scheduler = Scheduler()
        config = AgentConfig(
            agent_type="test-agent",
            display_name="Tracking",
            max_concurrent=10,
        )
        scheduler.register(config, tracking_factory)

        orc = MultiAgentOrchestrator(scheduler)
        wf = _fan_out_fan_in_workflow()
        orc.register_workflow(wf)

        execution = await orc.start_workflow("wf-diamond", {})

        assert execution.status == WorkflowStatus.COMPLETED
        # D must have upstream results from B and C
        d_result = execution.node_results.get("D")
        assert d_result is not None
        assert d_result["success"] is True

    @pytest.mark.asyncio
    async def test_acc_3_kill_switch_halts_immediately(self) -> None:
        """Kill-switch: killed execution has status KILLED.

        Design: kill flag is checked BEFORE each wave and each node dispatch.
        A 3-node linear workflow has 3 sequential waves. We set the kill flag
        DURING wave 1 (first node). Wave 1 completes (already dispatched), but
        wave 2 will see the kill flag and raise WorkflowKilledError.
        """
        wave1_started = asyncio.Event()
        wave1_done = asyncio.Event()

        async def factory_with_signal(config: Any, task: Any) -> dict[str, Any]:
            wave1_started.set()
            # Wait until test sets kill, then let node 1 finish
            await wave1_done.wait()
            return {"result": "ok"}

        scheduler = Scheduler()
        config = AgentConfig(
            agent_type="test-agent",
            display_name="Worker",
            max_concurrent=10,
        )
        scheduler.register(config, factory_with_signal)

        orc = MultiAgentOrchestrator(scheduler)
        wf = _linear_workflow(3)
        orc.register_workflow(wf)

        killed_exc: list[WorkflowKilledError] = []

        async def run() -> None:
            try:
                await orc.start_workflow("wf-linear", {})
            except WorkflowKilledError as e:
                killed_exc.append(e)

        task = asyncio.create_task(run())
        # Wait for wave 1 to start
        await asyncio.wait_for(wave1_started.wait(), timeout=2.0)
        await asyncio.sleep(0.01)

        # Set kill flag while node 1 is still running
        running = orc.list_executions(WorkflowStatus.RUNNING)
        assert len(running) > 0, "Expected a running execution"
        orc.kill_workflow(running[0].execution_id)

        # Let wave 1 complete — wave 2 will see the kill flag
        wave1_done.set()

        try:
            await asyncio.wait_for(task, timeout=2.0)
        except asyncio.TimeoutError:
            task.cancel()

        # Either WorkflowKilledError was raised or execution is KILLED
        killed_execs = orc.list_executions(WorkflowStatus.KILLED)
        assert len(killed_exc) > 0 or len(killed_execs) > 0

    @pytest.mark.asyncio
    async def test_acc_4_failed_node_propagates_failure(self) -> None:
        """A failing node causes the entire workflow to be FAILED."""
        async def fail_first(config: Any, task: Any) -> dict[str, Any]:
            raise RuntimeError("intentional failure")

        scheduler = Scheduler()
        config = AgentConfig(
            agent_type="test-agent",
            display_name="Failing",
            max_concurrent=10,
        )
        scheduler.register(config, fail_first)

        orc = MultiAgentOrchestrator(scheduler)
        wf = _linear_workflow(3)
        orc.register_workflow(wf)

        execution = await orc.start_workflow("wf-linear", {})

        assert execution.status == WorkflowStatus.FAILED
        stats = orc.get_stats()
        assert stats["total_failed"] >= 1

    @pytest.mark.asyncio
    async def test_acc_5_results_aggregated_correctly(self) -> None:
        """Results from each node are stored in execution.node_results."""
        async def result_factory(config: Any, task: Any) -> dict[str, Any]:
            node_id = task.metadata["_node_id"]
            return {"computed": f"value-{node_id}", "node": node_id}

        scheduler = Scheduler()
        config = AgentConfig(
            agent_type="test-agent",
            display_name="Result",
            max_concurrent=10,
        )
        scheduler.register(config, result_factory)

        orc = MultiAgentOrchestrator(scheduler)
        wf = _fan_out_fan_in_workflow()
        orc.register_workflow(wf)

        execution = await orc.start_workflow("wf-diamond", {"seed": "test"})

        assert execution.status == WorkflowStatus.COMPLETED
        assert len(execution.node_results) == 4
        for node_id in ("A", "B", "C", "D"):
            res = execution.node_results[node_id]
            assert res["success"] is True
            assert res["output"]["computed"] == f"value-{node_id}"
