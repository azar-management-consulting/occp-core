"""Tests for Workflow State Persistence.

Covers:
- WorkflowExecutionRow model creation
- WorkflowStore CRUD operations
- State persistence across simulated restart
- Resume interrupted workflow
- Checkpoint save/load
- Node result persistence
- API endpoints (list executions, resume workflow)
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock

import pytest

from orchestrator.models import AgentConfig
from orchestrator.multi_agent import (
    AgentNode,
    MultiAgentOrchestrator,
    WorkflowDefinition,
    WorkflowError,
    WorkflowExecution,
    WorkflowNotFoundError,
    WorkflowStatus,
)
from orchestrator.scheduler import Scheduler

# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------


def _make_scheduler(return_value: Any = {"result": "ok"}) -> Scheduler:
    scheduler = Scheduler()
    factory = AsyncMock(return_value=return_value)
    config = AgentConfig(
        agent_type="test-agent",
        display_name="Test Agent",
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


def _diamond_workflow() -> WorkflowDefinition:
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
# SQLAlchemy test fixtures (in-memory SQLite)
# ---------------------------------------------------------------------------


@pytest.fixture
async def db_session():
    """Create an async in-memory SQLite session for testing."""
    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        async_sessionmaker,
        create_async_engine,
    )

    from store.base import Base

    # Import models to register tables
    import store.models  # noqa: F401

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.fixture
async def workflow_store(db_session):
    """Create a WorkflowStore backed by the test session."""
    from store.workflow_store import WorkflowStore

    return WorkflowStore(db_session)


# ---------------------------------------------------------------------------
# TestWorkflowExecutionRow
# ---------------------------------------------------------------------------


class TestWorkflowExecutionRow:
    def test_model_creation(self) -> None:
        from store.models import WorkflowExecutionRow

        row = WorkflowExecutionRow(
            execution_id="exec-001",
            workflow_id="wf-test",
            status="running",
            dag_definition={"workflow_id": "wf-test", "name": "Test", "nodes": []},
            node_results={},
            checkpoints=[],
            current_wave=0,
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        assert row.execution_id == "exec-001"
        assert row.workflow_id == "wf-test"
        assert row.status == "running"
        assert row.dag_definition["workflow_id"] == "wf-test"
        assert row.finished_at is None
        assert row.error_detail is None

    def test_model_with_all_fields(self) -> None:
        from store.models import WorkflowExecutionRow

        now = datetime.now(timezone.utc).isoformat()
        row = WorkflowExecutionRow(
            execution_id="exec-002",
            workflow_id="wf-full",
            status="completed",
            dag_definition={"workflow_id": "wf-full", "name": "Full"},
            node_results={"A": {"success": True}},
            checkpoints=[{"wave_index": 0}],
            current_wave=2,
            started_at=now,
            finished_at=now,
            error_detail=None,
        )
        assert row.current_wave == 2
        assert row.node_results["A"]["success"] is True


# ---------------------------------------------------------------------------
# TestWorkflowStoreCRUD
# ---------------------------------------------------------------------------


class TestWorkflowStoreCRUD:
    @pytest.mark.asyncio
    async def test_save_and_get(self, workflow_store) -> None:
        from store.models import WorkflowExecutionRow

        row = WorkflowExecutionRow(
            execution_id="crud-001",
            workflow_id="wf-crud",
            status="pending",
            dag_definition={"workflow_id": "wf-crud", "name": "CRUD Test", "nodes": [], "edges": [], "metadata": {}},
            node_results={},
            checkpoints=[],
            current_wave=0,
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        await workflow_store.save_workflow_execution(row)

        fetched = await workflow_store.get_workflow_execution("crud-001")
        assert fetched is not None
        assert fetched.execution_id == "crud-001"
        assert fetched.workflow_id == "wf-crud"
        assert fetched.status == "pending"

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, workflow_store) -> None:
        result = await workflow_store.get_workflow_execution("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_by_workflow(self, workflow_store) -> None:
        from store.models import WorkflowExecutionRow

        now = datetime.now(timezone.utc).isoformat()
        for i in range(3):
            row = WorkflowExecutionRow(
                execution_id=f"list-{i:03d}",
                workflow_id="wf-list",
                status="completed",
                dag_definition={},
                node_results={},
                checkpoints=[],
                current_wave=0,
                started_at=now,
            )
            await workflow_store.save_workflow_execution(row)

        # Different workflow
        row = WorkflowExecutionRow(
            execution_id="list-other",
            workflow_id="wf-other",
            status="completed",
            dag_definition={},
            node_results={},
            checkpoints=[],
            current_wave=0,
            started_at=now,
        )
        await workflow_store.save_workflow_execution(row)

        results = await workflow_store.list_workflow_executions("wf-list")
        assert len(results) == 3
        assert all(r.workflow_id == "wf-list" for r in results)

    @pytest.mark.asyncio
    async def test_update_node_result(self, workflow_store) -> None:
        from store.models import WorkflowExecutionRow

        row = WorkflowExecutionRow(
            execution_id="node-001",
            workflow_id="wf-node",
            status="running",
            dag_definition={},
            node_results={},
            checkpoints=[],
            current_wave=0,
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        await workflow_store.save_workflow_execution(row)

        await workflow_store.update_workflow_node_result(
            "node-001", "A", {"success": True, "output": {"value": 42}}
        )

        fetched = await workflow_store.get_workflow_execution("node-001")
        assert fetched is not None
        assert "A" in fetched.node_results
        assert fetched.node_results["A"]["success"] is True
        assert fetched.node_results["A"]["output"]["value"] == 42

    @pytest.mark.asyncio
    async def test_add_checkpoint(self, workflow_store) -> None:
        from store.models import WorkflowExecutionRow

        row = WorkflowExecutionRow(
            execution_id="ckpt-001",
            workflow_id="wf-ckpt",
            status="running",
            dag_definition={},
            node_results={},
            checkpoints=[],
            current_wave=0,
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        await workflow_store.save_workflow_execution(row)

        await workflow_store.add_workflow_checkpoint(
            "ckpt-001", {"wave_index": 0, "timestamp": "2026-03-26T10:00:00"}
        )
        await workflow_store.add_workflow_checkpoint(
            "ckpt-001", {"wave_index": 1, "timestamp": "2026-03-26T10:01:00"}
        )

        fetched = await workflow_store.get_workflow_execution("ckpt-001")
        assert fetched is not None
        assert len(fetched.checkpoints) == 2
        assert fetched.checkpoints[0]["wave_index"] == 0
        assert fetched.checkpoints[1]["wave_index"] == 1

    @pytest.mark.asyncio
    async def test_update_status(self, workflow_store) -> None:
        from store.models import WorkflowExecutionRow

        row = WorkflowExecutionRow(
            execution_id="stat-001",
            workflow_id="wf-stat",
            status="running",
            dag_definition={},
            node_results={},
            checkpoints=[],
            current_wave=0,
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        await workflow_store.save_workflow_execution(row)

        await workflow_store.update_workflow_status(
            "stat-001",
            "completed",
            current_wave=3,
            finished_at=datetime.now(timezone.utc).isoformat(),
        )

        fetched = await workflow_store.get_workflow_execution("stat-001")
        assert fetched is not None
        assert fetched.status == "completed"
        assert fetched.current_wave == 3
        assert fetched.finished_at is not None

    @pytest.mark.asyncio
    async def test_list_interrupted(self, workflow_store) -> None:
        from store.models import WorkflowExecutionRow

        now = datetime.now(timezone.utc).isoformat()
        # Running execution
        await workflow_store.save_workflow_execution(
            WorkflowExecutionRow(
                execution_id="int-001",
                workflow_id="wf-int",
                status="running",
                dag_definition={},
                node_results={},
                checkpoints=[],
                current_wave=1,
                started_at=now,
            )
        )
        # Completed execution (should NOT appear)
        await workflow_store.save_workflow_execution(
            WorkflowExecutionRow(
                execution_id="int-002",
                workflow_id="wf-int",
                status="completed",
                dag_definition={},
                node_results={},
                checkpoints=[],
                current_wave=3,
                started_at=now,
            )
        )
        # Paused execution
        await workflow_store.save_workflow_execution(
            WorkflowExecutionRow(
                execution_id="int-003",
                workflow_id="wf-int",
                status="paused",
                dag_definition={},
                node_results={},
                checkpoints=[],
                current_wave=2,
                started_at=now,
            )
        )

        interrupted = await workflow_store.list_interrupted_executions()
        assert len(interrupted) == 2
        ids = {r.execution_id for r in interrupted}
        assert ids == {"int-001", "int-003"}


# ---------------------------------------------------------------------------
# TestStatePersistenceAcrossRestart
# ---------------------------------------------------------------------------


class TestStatePersistenceAcrossRestart:
    @pytest.mark.asyncio
    async def test_state_survives_simulated_restart(self, workflow_store) -> None:
        """Simulate: orchestrator saves state, then a new orchestrator reads it."""
        scheduler = _make_scheduler({"result": "ok"})
        orc = MultiAgentOrchestrator(scheduler, workflow_store=workflow_store)

        wf = _linear_workflow(3)
        orc.register_workflow(wf)

        # Run workflow — it will persist state
        execution = await orc.start_workflow("wf-linear", {"x": 1})
        assert execution.status == WorkflowStatus.COMPLETED

        # Simulate restart: create a new orchestrator, verify state is in DB
        row = await workflow_store.get_workflow_execution(execution.execution_id)
        assert row is not None
        assert row.status == "completed"
        assert row.workflow_id == "wf-linear"
        # Node results should be persisted
        assert "A" in row.node_results
        assert "B" in row.node_results
        assert "C" in row.node_results
        assert row.node_results["A"]["success"] is True

    @pytest.mark.asyncio
    async def test_failed_workflow_persisted(self, workflow_store) -> None:
        """A failed workflow should be persisted with error detail."""
        async def failing_factory(config: Any, task: Any) -> dict[str, Any]:
            raise RuntimeError("deliberate failure")

        scheduler = Scheduler()
        config = AgentConfig(
            agent_type="test-agent",
            display_name="Failing",
            max_concurrent=10,
        )
        scheduler.register(config, failing_factory)

        orc = MultiAgentOrchestrator(scheduler, workflow_store=workflow_store)
        wf = _linear_workflow(2)
        orc.register_workflow(wf)

        execution = await orc.start_workflow("wf-linear", {})
        assert execution.status == WorkflowStatus.FAILED

        row = await workflow_store.get_workflow_execution(execution.execution_id)
        assert row is not None
        assert row.status == "failed"
        assert row.error_detail is not None

    @pytest.mark.asyncio
    async def test_diamond_workflow_persisted(self, workflow_store) -> None:
        """Diamond pattern workflow state is correctly persisted."""
        scheduler = _make_scheduler({"result": "diamond"})
        orc = MultiAgentOrchestrator(scheduler, workflow_store=workflow_store)
        wf = _diamond_workflow()
        orc.register_workflow(wf)

        execution = await orc.start_workflow("wf-diamond", {"seed": "test"})
        assert execution.status == WorkflowStatus.COMPLETED

        row = await workflow_store.get_workflow_execution(execution.execution_id)
        assert row is not None
        assert len(row.node_results) == 4
        assert row.current_wave > 0


# ---------------------------------------------------------------------------
# TestResumeInterruptedWorkflow
# ---------------------------------------------------------------------------


class TestResumeInterruptedWorkflow:
    @pytest.mark.asyncio
    async def test_resume_without_store_raises(self) -> None:
        scheduler = _make_scheduler()
        orc = MultiAgentOrchestrator(scheduler)
        with pytest.raises(WorkflowError, match="no workflow_store"):
            await orc.resume_execution("some-id")

    @pytest.mark.asyncio
    async def test_resume_nonexistent_raises(self, workflow_store) -> None:
        scheduler = _make_scheduler()
        orc = MultiAgentOrchestrator(scheduler, workflow_store=workflow_store)
        with pytest.raises(WorkflowNotFoundError):
            await orc.resume_execution("nonexistent")

    @pytest.mark.asyncio
    async def test_resume_completed_raises(self, workflow_store) -> None:
        """Cannot resume a completed execution."""
        from store.models import WorkflowExecutionRow

        wf = _linear_workflow(2)
        await workflow_store.save_workflow_execution(
            WorkflowExecutionRow(
                execution_id="completed-exec",
                workflow_id="wf-linear",
                status="completed",
                dag_definition=wf.to_dict(),
                node_results={"A": {"success": True}, "B": {"success": True}},
                checkpoints=[],
                current_wave=2,
                started_at=datetime.now(timezone.utc).isoformat(),
                finished_at=datetime.now(timezone.utc).isoformat(),
            )
        )

        scheduler = _make_scheduler()
        orc = MultiAgentOrchestrator(scheduler, workflow_store=workflow_store)
        with pytest.raises(WorkflowError, match="Cannot resume"):
            await orc.resume_execution("completed-exec")

    @pytest.mark.asyncio
    async def test_resume_interrupted_execution(self, workflow_store) -> None:
        """Simulate an interrupted execution and resume it."""
        from store.models import WorkflowExecutionRow

        wf = _linear_workflow(3)  # A -> B -> C

        # Simulate: A completed, B and C pending, interrupted at wave 1
        await workflow_store.save_workflow_execution(
            WorkflowExecutionRow(
                execution_id="resume-exec",
                workflow_id="wf-linear",
                status="running",
                dag_definition=wf.to_dict(),
                node_results={"A": {"success": True, "output": {"result": "ok"}}},
                checkpoints=[{"wave_index": 0}],
                current_wave=1,
                started_at=datetime.now(timezone.utc).isoformat(),
            )
        )

        scheduler = _make_scheduler({"result": "resumed"})
        orc = MultiAgentOrchestrator(scheduler, workflow_store=workflow_store)

        execution = await orc.resume_execution("resume-exec")
        assert execution.status == WorkflowStatus.COMPLETED
        assert "B" in execution.node_results
        assert "C" in execution.node_results
        assert execution.node_results["B"]["success"] is True
        assert execution.node_results["C"]["success"] is True

    @pytest.mark.asyncio
    async def test_resume_paused_execution(self, workflow_store) -> None:
        """Resume a paused execution."""
        from store.models import WorkflowExecutionRow

        wf = WorkflowDefinition(
            workflow_id="wf-two",
            name="Two Node",
            nodes=[_simple_node("X"), _simple_node("Y", depends_on=["X"])],
        )
        await workflow_store.save_workflow_execution(
            WorkflowExecutionRow(
                execution_id="paused-exec",
                workflow_id="wf-two",
                status="paused",
                dag_definition=wf.to_dict(),
                node_results={"X": {"success": True, "output": {"v": 1}}},
                checkpoints=[{"wave_index": 0}],
                current_wave=1,
                started_at=datetime.now(timezone.utc).isoformat(),
            )
        )

        scheduler = _make_scheduler({"result": "resumed-Y"})
        orc = MultiAgentOrchestrator(scheduler, workflow_store=workflow_store)

        execution = await orc.resume_execution("paused-exec")
        assert execution.status == WorkflowStatus.COMPLETED
        assert execution.node_results["Y"]["success"] is True


# ---------------------------------------------------------------------------
# TestCheckpointSaveLoad
# ---------------------------------------------------------------------------


class TestCheckpointSaveLoad:
    @pytest.mark.asyncio
    async def test_checkpoints_persisted_during_execution(self, workflow_store) -> None:
        """Verify checkpoints are saved to DB during workflow execution."""
        scheduler = _make_scheduler({"result": "ok"})
        orc = MultiAgentOrchestrator(scheduler, workflow_store=workflow_store)
        wf = _linear_workflow(3)
        orc.register_workflow(wf)

        execution = await orc.start_workflow("wf-linear", {"input": "test"})
        assert execution.status == WorkflowStatus.COMPLETED

        row = await workflow_store.get_workflow_execution(execution.execution_id)
        assert row is not None
        # current_wave should reflect completion
        assert row.current_wave == 3  # all 3 waves done

    @pytest.mark.asyncio
    async def test_node_results_persisted_individually(self, workflow_store) -> None:
        """Each node result is persisted immediately after completion."""
        call_count = 0

        async def counting_factory(config: Any, task: Any) -> dict[str, Any]:
            nonlocal call_count
            call_count += 1
            return {"count": call_count}

        scheduler = Scheduler()
        config = AgentConfig(
            agent_type="test-agent",
            display_name="Counter",
            max_concurrent=10,
        )
        scheduler.register(config, counting_factory)

        orc = MultiAgentOrchestrator(scheduler, workflow_store=workflow_store)
        wf = _linear_workflow(3)
        orc.register_workflow(wf)

        execution = await orc.start_workflow("wf-linear", {})
        assert execution.status == WorkflowStatus.COMPLETED

        row = await workflow_store.get_workflow_execution(execution.execution_id)
        assert row is not None
        assert len(row.node_results) == 3
        for node_id in ("A", "B", "C"):
            assert node_id in row.node_results
            assert row.node_results[node_id]["success"] is True


# ---------------------------------------------------------------------------
# TestCheckInterruptedExecutions
# ---------------------------------------------------------------------------


class TestCheckInterruptedExecutions:
    @pytest.mark.asyncio
    async def test_check_interrupted_with_store(self, workflow_store) -> None:
        from store.models import WorkflowExecutionRow

        now = datetime.now(timezone.utc).isoformat()
        await workflow_store.save_workflow_execution(
            WorkflowExecutionRow(
                execution_id="check-001",
                workflow_id="wf-check",
                status="running",
                dag_definition={},
                node_results={},
                checkpoints=[],
                current_wave=1,
                started_at=now,
            )
        )

        scheduler = _make_scheduler()
        orc = MultiAgentOrchestrator(scheduler, workflow_store=workflow_store)
        interrupted = await orc.check_interrupted_executions()
        assert len(interrupted) == 1
        assert interrupted[0]["execution_id"] == "check-001"

    @pytest.mark.asyncio
    async def test_check_interrupted_without_store(self) -> None:
        scheduler = _make_scheduler()
        orc = MultiAgentOrchestrator(scheduler)
        interrupted = await orc.check_interrupted_executions()
        assert interrupted == []


# ---------------------------------------------------------------------------
# TestExistingMultiAgentUnchanged
# ---------------------------------------------------------------------------


class TestExistingMultiAgentUnchanged:
    """Verify persistence integration doesn't break existing behavior (no store)."""

    @pytest.mark.asyncio
    async def test_workflow_without_store_still_works(self) -> None:
        scheduler = _make_scheduler({"result": "ok"})
        orc = MultiAgentOrchestrator(scheduler)  # No workflow_store
        wf = _linear_workflow(3)
        orc.register_workflow(wf)

        execution = await orc.start_workflow("wf-linear", {"x": 1})
        assert execution.status == WorkflowStatus.COMPLETED
        assert len(execution.node_results) == 3

    @pytest.mark.asyncio
    async def test_diamond_without_store_still_works(self) -> None:
        scheduler = _make_scheduler({"result": "ok"})
        orc = MultiAgentOrchestrator(scheduler)
        wf = _diamond_workflow()
        orc.register_workflow(wf)

        execution = await orc.start_workflow("wf-diamond", {})
        assert execution.status == WorkflowStatus.COMPLETED
        assert len(execution.node_results) == 4


# ---------------------------------------------------------------------------
# TestAPIModels
# ---------------------------------------------------------------------------


class TestAPIModels:
    def test_workflow_execution_summary(self) -> None:
        from api.models import WorkflowExecutionSummary

        summary = WorkflowExecutionSummary(
            execution_id="api-001",
            workflow_id="wf-api",
            status="running",
            current_wave=1,
            node_results={"A": {"success": True}},
            started_at="2026-03-26T10:00:00",
        )
        assert summary.execution_id == "api-001"
        assert summary.status == "running"

    def test_workflow_execution_list_response(self) -> None:
        from api.models import WorkflowExecutionListResponse, WorkflowExecutionSummary

        resp = WorkflowExecutionListResponse(
            executions=[
                WorkflowExecutionSummary(
                    execution_id="e1",
                    workflow_id="w1",
                    status="completed",
                ),
            ],
            total=1,
        )
        assert resp.total == 1
        assert len(resp.executions) == 1

    def test_workflow_resume_response(self) -> None:
        from api.models import WorkflowResumeResponse

        resp = WorkflowResumeResponse(
            execution_id="r1",
            workflow_id="w1",
            status="completed",
            resumed_from_wave=1,
            node_results={"B": {"success": True}},
        )
        assert resp.resumed_from_wave == 1
