"""Multi-Agent Orchestration — coordinated agent workflows.

Enables:
- Agent graph execution (DAG-based task dependencies)
- Fan-out/fan-in patterns (parallel subtasks, aggregated results)
- Agent-to-agent delegation with trust level inheritance
- Workflow state machine with checkpoints
- Kill-switch: any agent can be halted mid-workflow
- Result aggregation and conflict resolution
- Parallel task dispatch with concurrency control and partial failure handling
"""

from __future__ import annotations

import asyncio
import enum
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Callable

from orchestrator.exceptions import OccpError
from orchestrator.models import AgentConfig, Task
from orchestrator.scheduler import Scheduler

if TYPE_CHECKING:
    from store.workflow_store import WorkflowStore

logger = logging.getLogger(__name__)

# Configurable max concurrent agents (env override or default 12)
MAX_CONCURRENT_AGENTS: int = int(
    os.environ.get("OCCP_MAX_CONCURRENT_AGENTS", "12")
)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class WorkflowError(OccpError):
    """Base workflow error."""


class WorkflowValidationError(WorkflowError):
    """Raised when a workflow definition fails validation."""

    def __init__(self, workflow_id: str, issues: list[str]) -> None:
        self.workflow_id = workflow_id
        self.issues = issues
        super().__init__(
            f"Workflow {workflow_id} validation failed: {'; '.join(issues)}"
        )


class WorkflowNotFoundError(WorkflowError):
    """Raised when a workflow or execution is not found."""

    def __init__(self, workflow_id: str) -> None:
        self.workflow_id = workflow_id
        super().__init__(f"Workflow not found: {workflow_id}")


class WorkflowKilledError(WorkflowError):
    """Raised when a workflow is forcibly killed."""

    def __init__(self, execution_id: str) -> None:
        self.execution_id = execution_id
        super().__init__(f"Workflow execution killed: {execution_id}")


class CyclicDependencyError(WorkflowValidationError):
    """Raised when a workflow graph contains a cycle."""

    def __init__(self, workflow_id: str, cycle_nodes: list[str]) -> None:
        self.cycle_nodes = cycle_nodes
        super().__init__(
            workflow_id,
            [f"Cycle detected involving nodes: {cycle_nodes}"],
        )


# ---------------------------------------------------------------------------
# Status enum
# ---------------------------------------------------------------------------


class WorkflowStatus(str, enum.Enum):
    """Lifecycle states of a workflow execution."""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    KILLED = "killed"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AgentNode:
    """A single node in a workflow DAG.

    Attributes:
        node_id: Unique identifier within the workflow.
        agent_type: Registered agent type that executes this node.
        task_template: Template dict for constructing the Task.
        depends_on: List of node_ids that must complete before this node.
        timeout_seconds: Per-node execution timeout (0 = no override).
        retry_count: Number of retries on transient failure.
    """

    node_id: str
    agent_type: str
    task_template: dict[str, Any]
    depends_on: list[str] = field(default_factory=list)
    timeout_seconds: int = 0
    retry_count: int = 0


@dataclass(frozen=True)
class WorkflowEdge:
    """A directed edge between two workflow nodes.

    Attributes:
        from_node: Source node_id.
        to_node: Target node_id.
        condition: Optional callable name or expression string for conditional edges.
    """

    from_node: str
    to_node: str
    condition: str | None = None


@dataclass
class WorkflowDefinition:
    """Complete definition of a multi-agent workflow (DAG).

    Attributes:
        workflow_id: Unique workflow identifier.
        name: Human-readable name.
        nodes: List of AgentNode objects.
        edges: List of WorkflowEdge objects (supplemental to depends_on).
        metadata: Arbitrary metadata.
    """

    workflow_id: str
    name: str
    nodes: list[AgentNode]
    edges: list[WorkflowEdge] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> list[str]:
        """Validate the workflow definition.

        Returns a list of issue strings (empty means valid).
        """
        issues: list[str] = []
        node_ids = {n.node_id for n in self.nodes}

        if not self.nodes:
            issues.append("Workflow has no nodes")
            return issues

        # Check for duplicate node IDs
        seen: set[str] = set()
        for node in self.nodes:
            if node.node_id in seen:
                issues.append(f"Duplicate node_id: {node.node_id}")
            seen.add(node.node_id)

        # Check depends_on references exist
        for node in self.nodes:
            for dep in node.depends_on:
                if dep not in node_ids:
                    issues.append(
                        f"Node {node.node_id} depends on unknown node: {dep}"
                    )

        # Check edge references exist
        for edge in self.edges:
            if edge.from_node not in node_ids:
                issues.append(f"Edge references unknown from_node: {edge.from_node}")
            if edge.to_node not in node_ids:
                issues.append(f"Edge references unknown to_node: {edge.to_node}")

        # Check for cycles
        if not issues:
            cycle_nodes = self._detect_cycle(node_ids)
            if cycle_nodes:
                issues.append(f"Cycle detected involving nodes: {cycle_nodes}")

        return issues

    def _detect_cycle(self, node_ids: set[str]) -> list[str]:
        """Detect cycles using DFS. Returns list of cycle nodes (empty = no cycle)."""
        # Build adjacency from depends_on
        adj: dict[str, list[str]] = {n.node_id: list(n.depends_on) for n in self.nodes}

        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[str, int] = {nid: WHITE for nid in node_ids}
        cycle_found: list[str] = []

        def dfs(node: str, path: list[str]) -> bool:
            color[node] = GRAY
            path.append(node)
            for dep in adj.get(node, []):
                if color[dep] == GRAY:
                    # Found cycle — capture the cycle portion
                    idx = path.index(dep)
                    cycle_found.extend(path[idx:])
                    return True
                if color[dep] == WHITE:
                    if dfs(dep, path):
                        return True
            path.pop()
            color[node] = BLACK
            return False

        for nid in node_ids:
            if color[nid] == WHITE:
                if dfs(nid, []):
                    break

        return cycle_found

    def topological_sort(self) -> list[list[str]]:
        """Return execution waves — groups of nodes that can run in parallel.

        Each wave contains nodes whose dependencies are all satisfied by
        previous waves.

        Returns:
            List of lists of node_ids, in execution order.

        Raises:
            CyclicDependencyError: If the graph contains a cycle.
        """
        issues = self.validate()
        cycle_issues = [i for i in issues if "Cycle" in i]
        if cycle_issues:
            raise CyclicDependencyError(self.workflow_id, self._detect_cycle(
                {n.node_id for n in self.nodes}
            ))

        # Kahn's algorithm
        adj: dict[str, set[str]] = {n.node_id: set(n.depends_on) for n in self.nodes}
        waves: list[list[str]] = []

        remaining = set(adj.keys())
        while remaining:
            # Nodes with no unresolved dependencies
            ready = [
                nid for nid in remaining
                if not (adj[nid] & remaining)
            ]
            if not ready:
                # Shouldn't happen after validate() but guard anyway
                raise CyclicDependencyError(
                    self.workflow_id, list(remaining)
                )
            waves.append(sorted(ready))
            remaining -= set(ready)

        return waves

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "name": self.name,
            "nodes": [
                {
                    "node_id": n.node_id,
                    "agent_type": n.agent_type,
                    "task_template": n.task_template,
                    "depends_on": n.depends_on,
                    "timeout_seconds": n.timeout_seconds,
                    "retry_count": n.retry_count,
                }
                for n in self.nodes
            ],
            "edges": [
                {
                    "from_node": e.from_node,
                    "to_node": e.to_node,
                    "condition": e.condition,
                }
                for e in self.edges
            ],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkflowDefinition:
        nodes = [
            AgentNode(
                node_id=n["node_id"],
                agent_type=n["agent_type"],
                task_template=n["task_template"],
                depends_on=n.get("depends_on", []),
                timeout_seconds=n.get("timeout_seconds", 0),
                retry_count=n.get("retry_count", 0),
            )
            for n in data.get("nodes", [])
        ]
        edges = [
            WorkflowEdge(
                from_node=e["from_node"],
                to_node=e["to_node"],
                condition=e.get("condition"),
            )
            for e in data.get("edges", [])
        ]
        return cls(
            workflow_id=data["workflow_id"],
            name=data["name"],
            nodes=nodes,
            edges=edges,
            metadata=data.get("metadata", {}),
        )


@dataclass
class WorkflowExecution:
    """Mutable state of a running or completed workflow execution.

    Attributes:
        execution_id: Unique ID for this execution run.
        workflow_id: Reference to the WorkflowDefinition.
        status: Current WorkflowStatus.
        node_results: Dict mapping node_id → result dict.
        started_at: When execution started.
        finished_at: When execution ended (None if still running).
        checkpoints: List of checkpoint dicts for pause/resume.
        error: Error message if execution failed.
    """

    execution_id: str
    workflow_id: str
    status: WorkflowStatus
    node_results: dict[str, Any] = field(default_factory=dict)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None
    checkpoints: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "workflow_id": self.workflow_id,
            "status": self.status.value,
            "node_results": self.node_results,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "checkpoints": self.checkpoints,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Multi-Agent Orchestrator
# ---------------------------------------------------------------------------


class MultiAgentOrchestrator:
    """Coordinates multiple agents working on related tasks via a DAG workflow.

    Features:
    - Register workflow definitions
    - Execute workflows with wave-based parallelism (topological sort)
    - Pass upstream results to downstream nodes via task metadata
    - Kill-switch: immediate halt at any point
    - Pause/resume at wave boundaries (checkpoints)
    - Stats collection
    """

    def __init__(
        self,
        scheduler: Scheduler,
        gate: Any | None = None,
        *,
        max_concurrent: int = MAX_CONCURRENT_AGENTS,
        workflow_store: WorkflowStore | None = None,
    ) -> None:
        self._scheduler = scheduler
        self._gate = gate
        self._max_concurrent = max_concurrent
        self._workflow_store = workflow_store
        self._workflows: dict[str, WorkflowDefinition] = {}
        self._executions: dict[str, WorkflowExecution] = {}
        self._kill_flags: dict[str, asyncio.Event] = {}
        self._pause_flags: dict[str, asyncio.Event] = {}
        self._total_started: int = 0
        self._total_completed: int = 0
        self._total_failed: int = 0
        self._total_killed: int = 0

    # ------------------------------------------------------------------
    # Workflow registration
    # ------------------------------------------------------------------

    def register_workflow(self, definition: WorkflowDefinition) -> None:
        """Register a workflow definition.

        Raises:
            WorkflowValidationError: If the definition is invalid.
        """
        issues = definition.validate()
        if issues:
            raise WorkflowValidationError(definition.workflow_id, issues)
        self._workflows[definition.workflow_id] = definition
        logger.info(
            "Registered workflow id=%s name=%s nodes=%d",
            definition.workflow_id,
            definition.name,
            len(definition.nodes),
        )

    def get_workflow(self, workflow_id: str) -> WorkflowDefinition:
        """Return a registered workflow definition."""
        wf = self._workflows.get(workflow_id)
        if wf is None:
            raise WorkflowNotFoundError(workflow_id)
        return wf

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    async def _persist_execution(
        self,
        execution: WorkflowExecution,
        definition: WorkflowDefinition,
        current_wave: int = 0,
    ) -> None:
        """Persist execution state to DB if workflow_store is configured."""
        if self._workflow_store is None:
            return
        try:
            from store.models import WorkflowExecutionRow

            row = WorkflowExecutionRow(
                execution_id=execution.execution_id,
                workflow_id=execution.workflow_id,
                status=execution.status.value,
                dag_definition=definition.to_dict(),
                node_results=execution.node_results,
                checkpoints=execution.checkpoints,
                current_wave=current_wave,
                started_at=execution.started_at.isoformat(),
                finished_at=(
                    execution.finished_at.isoformat()
                    if execution.finished_at
                    else None
                ),
                error_detail=execution.error,
            )
            await self._workflow_store.save_workflow_execution(row)
        except Exception:
            logger.exception(
                "Failed to persist execution state: %s", execution.execution_id
            )

    async def _persist_node_result(
        self,
        execution_id: str,
        node_id: str,
        result: dict[str, Any],
    ) -> None:
        """Persist a single node result to DB if workflow_store is configured."""
        if self._workflow_store is None:
            return
        try:
            await self._workflow_store.update_workflow_node_result(
                execution_id, node_id, result
            )
        except Exception:
            logger.exception(
                "Failed to persist node result: exec=%s node=%s",
                execution_id,
                node_id,
            )

    async def check_interrupted_executions(self) -> list[dict[str, Any]]:
        """Check for executions interrupted by restart. Returns list of resumable dicts."""
        if self._workflow_store is None:
            return []
        try:
            rows = await self._workflow_store.list_interrupted_executions()
            return [
                {
                    "execution_id": r.execution_id,
                    "workflow_id": r.workflow_id,
                    "status": r.status,
                    "current_wave": r.current_wave,
                    "node_results": r.node_results,
                    "started_at": r.started_at,
                }
                for r in rows
            ]
        except Exception:
            logger.exception("Failed to check interrupted executions")
            return []

    async def resume_execution(
        self,
        execution_id: str,
        input_data: dict[str, Any] | None = None,
    ) -> WorkflowExecution:
        """Resume an interrupted workflow execution from its last checkpoint.

        Loads persisted state from DB and continues from the next unfinished wave.

        Args:
            execution_id: ID of the interrupted execution.
            input_data: Optional override for input data (uses persisted if None).

        Returns:
            The resumed WorkflowExecution (completed or failed).

        Raises:
            WorkflowError: If no workflow_store or execution not found/resumable.
        """
        if self._workflow_store is None:
            raise WorkflowError("Cannot resume: no workflow_store configured")

        row = await self._workflow_store.get_workflow_execution(execution_id)
        if row is None:
            raise WorkflowNotFoundError(execution_id)

        if row.status not in ("running", "paused"):
            raise WorkflowError(
                f"Cannot resume execution in status '{row.status}'"
            )

        # Reconstruct definition from persisted DAG
        definition = WorkflowDefinition.from_dict(row.dag_definition)

        # Register workflow if not already known
        if definition.workflow_id not in self._workflows:
            self._workflows[definition.workflow_id] = definition

        # Build execution object from persisted state
        execution = WorkflowExecution(
            execution_id=execution_id,
            workflow_id=row.workflow_id,
            status=WorkflowStatus.RUNNING,
            node_results=row.node_results or {},
            started_at=datetime.fromisoformat(row.started_at),
            checkpoints=row.checkpoints or [],
        )
        self._executions[execution_id] = execution
        self._kill_flags[execution_id] = asyncio.Event()
        self._pause_flags[execution_id] = asyncio.Event()

        # Determine resume point
        resume_wave = row.current_wave
        waves = definition.topological_sort()
        node_map: dict[str, AgentNode] = {
            n.node_id: n for n in definition.nodes
        }

        # Rebuild accumulated context from completed node results
        accumulated: dict[str, Any] = {
            "input": input_data or row.dag_definition.get("metadata", {}).get("input", {}),
        }
        for node_id, nr in execution.node_results.items():
            if nr.get("success"):
                accumulated[node_id] = nr.get("output")

        logger.info(
            "Resuming execution=%s from wave=%d/%d",
            execution_id,
            resume_wave,
            len(waves),
        )

        try:
            for wave_index in range(resume_wave, len(waves)):
                wave = waves[wave_index]

                if self._kill_flags[execution_id].is_set():
                    raise WorkflowKilledError(execution_id)

                # Skip nodes already completed
                pending_nodes = [
                    nid for nid in wave
                    if nid not in execution.node_results
                    or not execution.node_results[nid].get("success")
                ]

                if not pending_nodes:
                    continue

                execution.status = WorkflowStatus.RUNNING

                sem = asyncio.Semaphore(self._max_concurrent)

                async def _bounded_execute(n: AgentNode) -> Any:
                    async with sem:
                        return await self._execute_node(n, accumulated, execution_id)

                wave_tasks = []
                for node_id in pending_nodes:
                    node = node_map[node_id]
                    wave_tasks.append(_bounded_execute(node))

                wave_results = await asyncio.gather(
                    *wave_tasks, return_exceptions=True
                )

                wave_failed = False
                for node_id, result in zip(pending_nodes, wave_results):
                    if isinstance(result, WorkflowKilledError):
                        raise result
                    if isinstance(result, Exception):
                        node_result = {"success": False, "error": str(result)}
                        execution.node_results[node_id] = node_result
                        await self._persist_node_result(execution_id, node_id, node_result)
                        wave_failed = True
                    else:
                        node_result = {"success": True, "output": result}
                        execution.node_results[node_id] = node_result
                        accumulated[node_id] = result
                        await self._persist_node_result(execution_id, node_id, node_result)

                # Persist wave checkpoint
                await self._persist_execution(execution, definition, wave_index + 1)

                if wave_failed:
                    execution.status = WorkflowStatus.FAILED
                    execution.finished_at = datetime.now(timezone.utc)
                    execution.error = f"Nodes failed in wave {wave_index}: {pending_nodes}"
                    self._total_failed += 1
                    await self._persist_execution(execution, definition, wave_index + 1)
                    return execution

            execution.status = WorkflowStatus.COMPLETED
            execution.finished_at = datetime.now(timezone.utc)
            self._total_completed += 1
            await self._persist_execution(execution, definition, len(waves))
            return execution

        except WorkflowKilledError:
            execution.status = WorkflowStatus.KILLED
            execution.finished_at = datetime.now(timezone.utc)
            execution.error = f"Workflow execution {execution_id} was killed"
            self._total_killed += 1
            await self._persist_execution(execution, definition, 0)
            raise

        except Exception as exc:
            execution.status = WorkflowStatus.FAILED
            execution.finished_at = datetime.now(timezone.utc)
            execution.error = str(exc)
            self._total_failed += 1
            await self._persist_execution(execution, definition, 0)
            return execution

        finally:
            self._kill_flags.pop(execution_id, None)
            self._pause_flags.pop(execution_id, None)

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def start_workflow(
        self,
        workflow_id: str,
        input_data: dict[str, Any],
        agent_id: str = "orchestrator",
        trust_level: Any = None,
    ) -> WorkflowExecution:
        """Start a workflow execution.

        Args:
            workflow_id: ID of the registered workflow.
            input_data: Initial input data passed to the first wave of nodes.
            agent_id: Identity of the orchestrating agent.
            trust_level: Trust level for gate checks (passed through).

        Returns:
            A WorkflowExecution (completed or failed).

        Raises:
            WorkflowNotFoundError: If workflow_id is not registered.
            WorkflowValidationError: If definition is invalid at runtime.
            WorkflowKilledError: If the workflow is killed mid-execution.
        """
        definition = self.get_workflow(workflow_id)
        issues = definition.validate()
        if issues:
            raise WorkflowValidationError(workflow_id, issues)

        execution_id = uuid.uuid4().hex[:16]
        execution = WorkflowExecution(
            execution_id=execution_id,
            workflow_id=workflow_id,
            status=WorkflowStatus.RUNNING,
        )
        self._executions[execution_id] = execution
        self._kill_flags[execution_id] = asyncio.Event()
        self._pause_flags[execution_id] = asyncio.Event()
        self._total_started += 1

        logger.info(
            "Starting workflow execution id=%s workflow=%s",
            execution_id,
            workflow_id,
        )

        # Persist initial execution state
        await self._persist_execution(execution, definition, 0)

        try:
            waves = definition.topological_sort()
            # Build node lookup
            node_map: dict[str, AgentNode] = {
                n.node_id: n for n in definition.nodes
            }

            # Accumulated context passed downstream
            accumulated: dict[str, Any] = {"input": input_data}

            for wave_index, wave in enumerate(waves):
                # Check kill flag
                if self._kill_flags[execution_id].is_set():
                    raise WorkflowKilledError(execution_id)

                # Check pause flag — wait until resumed
                while self._pause_flags[execution_id].is_set():
                    execution.status = WorkflowStatus.PAUSED
                    execution.checkpoints.append({
                        "wave_index": wave_index,
                        "wave": wave,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                    logger.info(
                        "Workflow paused at wave %d: execution=%s",
                        wave_index,
                        execution_id,
                    )
                    await asyncio.sleep(0.05)
                    if self._kill_flags[execution_id].is_set():
                        raise WorkflowKilledError(execution_id)

                execution.status = WorkflowStatus.RUNNING

                logger.info(
                    "Executing wave %d/%d nodes=%s execution=%s",
                    wave_index + 1,
                    len(waves),
                    wave,
                    execution_id,
                )

                # Execute all nodes in this wave in parallel (bounded by max_concurrent)
                sem = asyncio.Semaphore(self._max_concurrent)

                async def _bounded_execute(n: AgentNode) -> Any:
                    async with sem:
                        return await self._execute_node(n, accumulated, execution_id)

                wave_tasks = []
                for node_id in wave:
                    node = node_map[node_id]
                    wave_tasks.append(_bounded_execute(node))

                wave_results = await asyncio.gather(
                    *wave_tasks, return_exceptions=True
                )

                # Process results
                wave_failed = False
                for node_id, result in zip(wave, wave_results):
                    if isinstance(result, WorkflowKilledError):
                        raise result
                    if isinstance(result, Exception):
                        node_result = {
                            "success": False,
                            "error": str(result),
                        }
                        execution.node_results[node_id] = node_result
                        await self._persist_node_result(execution_id, node_id, node_result)
                        wave_failed = True
                        logger.error(
                            "Node %s failed: %s execution=%s",
                            node_id,
                            result,
                            execution_id,
                        )
                    else:
                        node_result = {
                            "success": True,
                            "output": result,
                        }
                        execution.node_results[node_id] = node_result
                        await self._persist_node_result(execution_id, node_id, node_result)
                        # Feed results forward
                        accumulated[node_id] = result

                # Persist wave checkpoint
                await self._persist_execution(execution, definition, wave_index + 1)

                if wave_failed:
                    execution.status = WorkflowStatus.FAILED
                    execution.finished_at = datetime.now(timezone.utc)
                    execution.error = (
                        f"One or more nodes failed in wave {wave_index}: {wave}"
                    )
                    self._total_failed += 1
                    await self._persist_execution(execution, definition, wave_index + 1)
                    return execution

            # All waves completed
            execution.status = WorkflowStatus.COMPLETED
            execution.finished_at = datetime.now(timezone.utc)
            self._total_completed += 1
            await self._persist_execution(execution, definition, len(waves))
            logger.info(
                "Workflow completed execution=%s workflow=%s",
                execution_id,
                workflow_id,
            )
            return execution

        except WorkflowKilledError:
            execution.status = WorkflowStatus.KILLED
            execution.finished_at = datetime.now(timezone.utc)
            execution.error = f"Workflow execution {execution_id} was killed"
            self._total_killed += 1
            await self._persist_execution(execution, definition, 0)
            logger.warning("Workflow killed: execution=%s", execution_id)
            raise

        except Exception as exc:
            execution.status = WorkflowStatus.FAILED
            execution.finished_at = datetime.now(timezone.utc)
            execution.error = str(exc)
            self._total_failed += 1
            await self._persist_execution(execution, definition, 0)
            logger.exception(
                "Workflow execution failed: execution=%s error=%s", execution_id, exc
            )
            return execution

        finally:
            # Clean up event flags
            self._kill_flags.pop(execution_id, None)
            self._pause_flags.pop(execution_id, None)

    async def _execute_node(
        self,
        node: AgentNode,
        context: dict[str, Any],
        execution_id: str,
    ) -> Any:
        """Execute a single workflow node via the Scheduler.

        Builds a Task from node.task_template + upstream context, then
        dispatches through the registered agent factory.

        Args:
            node: The AgentNode to execute.
            context: Accumulated results from upstream nodes.
            execution_id: Parent execution ID for logging.

        Returns:
            The raw result from the agent factory.
        """
        # Check kill flag before dispatching
        if self._kill_flags.get(execution_id, asyncio.Event()).is_set():
            raise WorkflowKilledError(execution_id)

        template = node.task_template
        task = Task(
            name=template.get("name", f"workflow-node-{node.node_id}"),
            description=template.get("description", ""),
            agent_type=node.agent_type,
            metadata={
                **template.get("metadata", {}),
                "_workflow_execution_id": execution_id,
                "_node_id": node.node_id,
                "_upstream_results": {
                    dep: context.get(dep) for dep in node.depends_on
                },
                "_workflow_input": context.get("input", {}),
            },
        )

        retries = node.retry_count
        last_exc: Exception | None = None
        for attempt in range(1 + retries):
            try:
                # Check kill between retries
                if self._kill_flags.get(execution_id, asyncio.Event()).is_set():
                    raise WorkflowKilledError(execution_id)

                result = await self._scheduler.dispatch(task)
                logger.debug(
                    "Node %s succeeded (attempt %d) execution=%s",
                    node.node_id,
                    attempt + 1,
                    execution_id,
                )
                return result

            except WorkflowKilledError:
                raise
            except Exception as exc:
                last_exc = exc
                if attempt < retries:
                    logger.warning(
                        "Node %s attempt %d/%d failed: %s — retrying",
                        node.node_id,
                        attempt + 1,
                        1 + retries,
                        exc,
                    )

        raise WorkflowError(
            f"Node {node.node_id} failed after {1 + retries} attempt(s): {last_exc}"
        )

    # ------------------------------------------------------------------
    # Control
    # ------------------------------------------------------------------

    def pause_workflow(self, execution_id: str) -> None:
        """Signal a running workflow to pause at the next wave boundary.

        The workflow will check the pause flag before starting each wave and
        wait until resume_workflow() is called.
        """
        execution = self.get_execution(execution_id)
        if execution.status not in (WorkflowStatus.RUNNING, WorkflowStatus.PENDING):
            raise WorkflowError(
                f"Cannot pause execution in status {execution.status.value}"
            )
        flag = self._pause_flags.get(execution_id)
        if flag is None:
            raise WorkflowError(
                f"No active execution found for id={execution_id}"
            )
        flag.set()
        logger.info("Pause requested for execution=%s", execution_id)

    def resume_workflow(self, execution_id: str) -> None:
        """Resume a paused workflow.

        Clears the pause flag so the execution loop can continue.
        """
        execution = self.get_execution(execution_id)
        if execution.status not in (WorkflowStatus.PAUSED, WorkflowStatus.RUNNING):
            raise WorkflowError(
                f"Cannot resume execution in status {execution.status.value}"
            )
        flag = self._pause_flags.get(execution_id)
        if flag is None:
            raise WorkflowError(
                f"No active execution found for id={execution_id}"
            )
        flag.clear()
        execution.status = WorkflowStatus.RUNNING
        logger.info("Resumed execution=%s", execution_id)

    def kill_workflow(self, execution_id: str) -> None:
        """Immediately halt a workflow execution (kill-switch).

        Sets the kill flag — the execution loop will check this before
        dispatching each node and raise WorkflowKilledError.
        """
        execution = self.get_execution(execution_id)
        if execution.status in (WorkflowStatus.COMPLETED, WorkflowStatus.KILLED):
            raise WorkflowError(
                f"Cannot kill execution in terminal status {execution.status.value}"
            )
        flag = self._kill_flags.get(execution_id)
        if flag is None:
            raise WorkflowError(
                f"No active execution found for id={execution_id}"
            )
        flag.set()
        logger.warning("Kill signal sent to execution=%s", execution_id)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_execution(self, execution_id: str) -> WorkflowExecution:
        """Return a workflow execution by ID.

        Raises:
            WorkflowNotFoundError: If not found.
        """
        execution = self._executions.get(execution_id)
        if execution is None:
            raise WorkflowNotFoundError(execution_id)
        return execution

    def list_executions(
        self,
        status_filter: WorkflowStatus | None = None,
    ) -> list[WorkflowExecution]:
        """Return all executions, optionally filtered by status."""
        if status_filter is None:
            return list(self._executions.values())
        return [
            e for e in self._executions.values()
            if e.status == status_filter
        ]

    def get_stats(self) -> dict[str, Any]:
        """Return orchestrator statistics."""
        by_status: dict[str, int] = {}
        for e in self._executions.values():
            by_status[e.status.value] = by_status.get(e.status.value, 0) + 1
        return {
            "total_started": self._total_started,
            "total_completed": self._total_completed,
            "total_failed": self._total_failed,
            "total_killed": self._total_killed,
            "active_executions": len(self._executions),
            "registered_workflows": len(self._workflows),
            "by_status": by_status,
        }


# ---------------------------------------------------------------------------
# Parallel Task Dispatch
# ---------------------------------------------------------------------------


class DispatchTaskStatus(str, enum.Enum):
    """Status of a single dispatched task in a parallel batch."""

    DISPATCHED = "dispatched"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class DispatchTaskResult:
    """Result of a single task within a parallel dispatch."""

    agent_id: str
    task_input: str
    status: DispatchTaskStatus = DispatchTaskStatus.DISPATCHED
    result: Any = None
    error: str | None = None
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "task_input": self.task_input,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
        }


@dataclass
class ParallelDispatchState:
    """Aggregate state of a parallel dispatch batch."""

    dispatch_id: str
    tasks: list[DispatchTaskResult] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def total(self) -> int:
        return len(self.tasks)

    @property
    def completed(self) -> int:
        return sum(
            1 for t in self.tasks if t.status == DispatchTaskStatus.COMPLETED
        )

    @property
    def failed(self) -> int:
        return sum(
            1
            for t in self.tasks
            if t.status in (DispatchTaskStatus.FAILED, DispatchTaskStatus.TIMEOUT)
        )

    @property
    def pending(self) -> int:
        return sum(
            1
            for t in self.tasks
            if t.status
            in (DispatchTaskStatus.DISPATCHED, DispatchTaskStatus.RUNNING)
        )

    @property
    def is_done(self) -> bool:
        return self.pending == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "dispatch_id": self.dispatch_id,
            "total": self.total,
            "completed": self.completed,
            "failed": self.failed,
            "pending": self.pending,
            "results": [t.to_dict() for t in self.tasks],
            "created_at": self.created_at.isoformat(),
        }


class ParallelDispatcher:
    """Manages concurrent dispatch of tasks to multiple agents.

    Features:
    - Concurrency control via asyncio.Semaphore
    - Per-task timeout handling
    - Partial failure tolerance (some agents fail, others continue)
    - Progress tracking (X/N completed)
    - In-memory dispatch state storage
    """

    def __init__(
        self,
        max_concurrent: int = 12,
        default_timeout: int = 120,
    ) -> None:
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._default_timeout = default_timeout
        self._max_concurrent = max_concurrent
        self._dispatches: dict[str, ParallelDispatchState] = {}

    @property
    def max_concurrent(self) -> int:
        return self._max_concurrent

    @property
    def default_timeout(self) -> int:
        return self._default_timeout

    async def dispatch(
        self,
        tasks: list[dict[str, Any]],
        executor_fn: Callable[..., Any] | None = None,
    ) -> ParallelDispatchState:
        """Dispatch multiple tasks in parallel with concurrency control.

        Args:
            tasks: List of dicts with ``agent_id`` and ``input`` keys.
                   Optional ``timeout`` key overrides the default.
            executor_fn: Async callable ``(agent_id, input) -> result``.
                         If None, a mock executor is used.

        Returns:
            A ``ParallelDispatchState`` with all task results.
        """
        dispatch_id = uuid.uuid4().hex[:16]
        state = ParallelDispatchState(dispatch_id=dispatch_id)

        task_results: list[DispatchTaskResult] = []
        for task_def in tasks:
            agent_id = task_def.get("agent_id", "unknown")
            task_input = task_def.get("input", "")
            task_results.append(
                DispatchTaskResult(agent_id=agent_id, task_input=task_input)
            )
        state.tasks = task_results
        self._dispatches[dispatch_id] = state

        actual_executor = executor_fn
        if actual_executor is None:

            async def _mock_exec(
                aid: str, tinput: str
            ) -> dict[str, Any]:
                return {"agent_id": aid, "output": f"Mock result for: {tinput}"}

            actual_executor = _mock_exec

        async_tasks = []
        for idx, task_def in enumerate(tasks):
            timeout = task_def.get("timeout", self._default_timeout)
            async_tasks.append(
                self._run_single(
                    task_result=task_results[idx],
                    executor_fn=actual_executor,
                    timeout=timeout,
                )
            )

        await asyncio.gather(*async_tasks, return_exceptions=True)

        logger.info(
            "Parallel dispatch completed: id=%s total=%d completed=%d failed=%d",
            dispatch_id,
            state.total,
            state.completed,
            state.failed,
        )

        return state

    async def _run_single(
        self,
        task_result: DispatchTaskResult,
        executor_fn: Callable[..., Any],
        timeout: int,
    ) -> None:
        """Execute a single task with semaphore and timeout."""
        async with self._semaphore:
            task_result.status = DispatchTaskStatus.RUNNING
            try:
                result = await asyncio.wait_for(
                    executor_fn(task_result.agent_id, task_result.task_input),
                    timeout=timeout,
                )
                task_result.status = DispatchTaskStatus.COMPLETED
                task_result.result = result
            except asyncio.TimeoutError:
                task_result.status = DispatchTaskStatus.TIMEOUT
                task_result.error = f"Timeout after {timeout}s"
                logger.warning(
                    "Parallel dispatch task timeout: agent=%s timeout=%ds",
                    task_result.agent_id,
                    timeout,
                )
            except Exception as exc:
                task_result.status = DispatchTaskStatus.FAILED
                task_result.error = str(exc)
                logger.error(
                    "Parallel dispatch task failed: agent=%s error=%s",
                    task_result.agent_id,
                    exc,
                )
            finally:
                task_result.finished_at = datetime.now(timezone.utc)

    def get_dispatch(self, dispatch_id: str) -> ParallelDispatchState | None:
        """Return dispatch state by ID, or None if not found."""
        return self._dispatches.get(dispatch_id)

    def list_dispatches(self) -> list[ParallelDispatchState]:
        """Return all tracked dispatch states."""
        return list(self._dispatches.values())
