"""Tests for per-agent sandbox policy and parallel task dispatch.

Covers:
- AgentSandboxPolicy dataclass creation and serialization
- get_sandbox_policy() for all 8 agent types
- get_sandbox_policy() with overrides
- get_sandbox_policy() for unknown agent (fallback)
- to_sandbox_config() conversion
- list_all_agent_policies()
- ParallelDispatcher with mock executor
- ParallelDispatcher with 10+ concurrent tasks
- Partial failure handling (some agents fail, others succeed)
- Timeout handling
- Progress tracking (completed/failed/pending)
- ParallelDispatchState serialization
- DispatchTaskResult serialization
- Concurrency semaphore enforcement
- Settings: parallel_dispatch_max_concurrent, parallel_dispatch_default_timeout
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock

import pytest

from adapters.sandbox_executor import (
    AgentSandboxPolicy,
    SandboxBackend,
    SandboxConfig,
    get_sandbox_policy,
    list_all_agent_policies,
    _DEFAULT_AGENT_POLICIES,
)
from orchestrator.multi_agent import (
    DispatchTaskResult,
    DispatchTaskStatus,
    ParallelDispatcher,
    ParallelDispatchState,
)
from config.settings import Settings


# ---------------------------------------------------------------------------
# Per-Agent Sandbox Policy
# ---------------------------------------------------------------------------


class TestAgentSandboxPolicy:
    """Tests for AgentSandboxPolicy dataclass."""

    def test_default_values(self) -> None:
        policy = AgentSandboxPolicy(agent_id="test")
        assert policy.agent_id == "test"
        assert policy.backend == "bwrap"
        assert policy.time_limit == 30
        assert policy.memory_mb == 256
        assert policy.network is False
        assert policy.writable_paths == []

    def test_custom_values(self) -> None:
        policy = AgentSandboxPolicy(
            agent_id="custom",
            backend="nsjail",
            time_limit=120,
            memory_mb=512,
            network=True,
            writable_paths=["/tmp/work"],
        )
        assert policy.backend == "nsjail"
        assert policy.time_limit == 120
        assert policy.memory_mb == 512
        assert policy.network is True
        assert policy.writable_paths == ["/tmp/work"]

    def test_to_dict(self) -> None:
        policy = AgentSandboxPolicy(
            agent_id="eng-core",
            backend="bwrap",
            time_limit=120,
            memory_mb=512,
        )
        d = policy.to_dict()
        assert d["agent_id"] == "eng-core"
        assert d["backend"] == "bwrap"
        assert d["time_limit"] == 120
        assert d["memory_mb"] == 512
        assert d["network"] is False
        assert d["writable_paths"] == []

    def test_to_sandbox_config_bwrap(self) -> None:
        policy = AgentSandboxPolicy(
            agent_id="eng-core",
            backend="bwrap",
            time_limit=120,
            memory_mb=512,
            network=False,
        )
        cfg = policy.to_sandbox_config()
        assert isinstance(cfg, SandboxConfig)
        assert cfg.backend == SandboxBackend.BWRAP
        assert cfg.time_limit_seconds == 120
        assert cfg.memory_limit_mb == 512
        assert cfg.enable_network is False

    def test_to_sandbox_config_nsjail(self) -> None:
        policy = AgentSandboxPolicy(agent_id="infra-ops", backend="nsjail")
        cfg = policy.to_sandbox_config()
        assert cfg.backend == SandboxBackend.NSJAIL

    def test_to_sandbox_config_process(self) -> None:
        policy = AgentSandboxPolicy(agent_id="intel-research", backend="process")
        cfg = policy.to_sandbox_config()
        assert cfg.backend == SandboxBackend.PROCESS

    def test_to_sandbox_config_mock(self) -> None:
        policy = AgentSandboxPolicy(agent_id="design-lab", backend="mock")
        cfg = policy.to_sandbox_config()
        assert cfg.backend == SandboxBackend.MOCK

    def test_to_sandbox_config_unknown_backend_falls_back_to_process(self) -> None:
        policy = AgentSandboxPolicy(agent_id="x", backend="unknown_backend")
        cfg = policy.to_sandbox_config()
        assert cfg.backend == SandboxBackend.PROCESS


class TestGetSandboxPolicy:
    """Tests for get_sandbox_policy() function."""

    def test_eng_core(self) -> None:
        p = get_sandbox_policy("eng-core")
        assert p.agent_id == "eng-core"
        assert p.backend == "bwrap"
        assert p.time_limit == 120
        assert p.memory_mb == 512
        assert p.network is False

    def test_wp_web(self) -> None:
        p = get_sandbox_policy("wp-web")
        assert p.agent_id == "wp-web"
        assert p.backend == "bwrap"
        assert p.time_limit == 60
        assert p.memory_mb == 256
        assert p.network is True

    def test_infra_ops(self) -> None:
        p = get_sandbox_policy("infra-ops")
        assert p.agent_id == "infra-ops"
        assert p.backend == "nsjail"
        assert p.time_limit == 30
        assert p.memory_mb == 128
        assert p.network is True

    def test_design_lab(self) -> None:
        p = get_sandbox_policy("design-lab")
        assert p.agent_id == "design-lab"
        assert p.backend == "mock"
        assert p.time_limit == 60
        assert p.memory_mb == 256
        assert p.network is False

    def test_content_forge(self) -> None:
        p = get_sandbox_policy("content-forge")
        assert p.agent_id == "content-forge"
        assert p.backend == "mock"
        assert p.time_limit == 30
        assert p.memory_mb == 128
        assert p.network is False

    def test_social_growth(self) -> None:
        p = get_sandbox_policy("social-growth")
        assert p.agent_id == "social-growth"
        assert p.backend == "mock"
        assert p.time_limit == 30
        assert p.memory_mb == 128
        assert p.network is False

    def test_intel_research(self) -> None:
        p = get_sandbox_policy("intel-research")
        assert p.agent_id == "intel-research"
        assert p.backend == "process"
        assert p.time_limit == 120
        assert p.memory_mb == 512
        assert p.network is True

    def test_biz_strategy(self) -> None:
        p = get_sandbox_policy("biz-strategy")
        assert p.agent_id == "biz-strategy"
        assert p.backend == "mock"
        assert p.time_limit == 60
        assert p.memory_mb == 128
        assert p.network is False

    def test_unknown_agent_returns_restrictive_fallback(self) -> None:
        p = get_sandbox_policy("nonexistent-agent")
        assert p.agent_id == "nonexistent-agent"
        assert p.backend == "process"
        assert p.time_limit == 30
        assert p.memory_mb == 128
        assert p.network is False

    def test_overrides_applied(self) -> None:
        p = get_sandbox_policy("eng-core", overrides={
            "time_limit": 300,
            "network": True,
        })
        assert p.agent_id == "eng-core"
        assert p.time_limit == 300
        assert p.network is True
        # Non-overridden fields keep defaults
        assert p.backend == "bwrap"
        assert p.memory_mb == 512

    def test_overrides_on_unknown_agent(self) -> None:
        p = get_sandbox_policy("custom-agent", overrides={
            "backend": "nsjail",
            "memory_mb": 1024,
        })
        assert p.backend == "nsjail"
        assert p.memory_mb == 1024

    def test_all_8_agents_have_policies(self) -> None:
        expected_agents = {
            "eng-core", "wp-web", "infra-ops", "design-lab",
            "content-forge", "social-growth", "intel-research", "biz-strategy",
        }
        assert set(_DEFAULT_AGENT_POLICIES.keys()) == expected_agents


class TestListAllAgentPolicies:
    """Tests for list_all_agent_policies()."""

    def test_returns_8_policies(self) -> None:
        policies = list_all_agent_policies()
        assert len(policies) == 8

    def test_all_are_agent_sandbox_policy(self) -> None:
        for p in list_all_agent_policies():
            assert isinstance(p, AgentSandboxPolicy)

    def test_agent_ids_match(self) -> None:
        ids = {p.agent_id for p in list_all_agent_policies()}
        expected = set(_DEFAULT_AGENT_POLICIES.keys())
        assert ids == expected


# ---------------------------------------------------------------------------
# Parallel Dispatcher
# ---------------------------------------------------------------------------


class TestDispatchTaskResult:
    """Tests for DispatchTaskResult dataclass."""

    def test_defaults(self) -> None:
        r = DispatchTaskResult(agent_id="eng-core", task_input="hello")
        assert r.status == DispatchTaskStatus.DISPATCHED
        assert r.result is None
        assert r.error is None
        assert r.finished_at is None

    def test_to_dict(self) -> None:
        r = DispatchTaskResult(agent_id="eng-core", task_input="hello")
        d = r.to_dict()
        assert d["agent_id"] == "eng-core"
        assert d["task_input"] == "hello"
        assert d["status"] == "dispatched"
        assert d["result"] is None
        assert "started_at" in d


class TestParallelDispatchState:
    """Tests for ParallelDispatchState dataclass."""

    def test_empty_state(self) -> None:
        s = ParallelDispatchState(dispatch_id="test123")
        assert s.total == 0
        assert s.completed == 0
        assert s.failed == 0
        assert s.pending == 0
        assert s.is_done is True

    def test_with_tasks(self) -> None:
        tasks = [
            DispatchTaskResult(agent_id="a", task_input="1", status=DispatchTaskStatus.COMPLETED),
            DispatchTaskResult(agent_id="b", task_input="2", status=DispatchTaskStatus.FAILED),
            DispatchTaskResult(agent_id="c", task_input="3", status=DispatchTaskStatus.RUNNING),
        ]
        s = ParallelDispatchState(dispatch_id="test", tasks=tasks)
        assert s.total == 3
        assert s.completed == 1
        assert s.failed == 1
        assert s.pending == 1
        assert s.is_done is False

    def test_timeout_counts_as_failed(self) -> None:
        tasks = [
            DispatchTaskResult(agent_id="a", task_input="1", status=DispatchTaskStatus.TIMEOUT),
        ]
        s = ParallelDispatchState(dispatch_id="test", tasks=tasks)
        assert s.failed == 1

    def test_to_dict(self) -> None:
        s = ParallelDispatchState(dispatch_id="abc123")
        d = s.to_dict()
        assert d["dispatch_id"] == "abc123"
        assert d["total"] == 0
        assert d["completed"] == 0
        assert d["failed"] == 0
        assert d["pending"] == 0
        assert d["results"] == []
        assert "created_at" in d


class TestParallelDispatcher:
    """Tests for ParallelDispatcher class."""

    def test_init_defaults(self) -> None:
        d = ParallelDispatcher()
        assert d.max_concurrent == 12
        assert d.default_timeout == 120

    def test_init_custom(self) -> None:
        d = ParallelDispatcher(max_concurrent=5, default_timeout=30)
        assert d.max_concurrent == 5
        assert d.default_timeout == 30

    @pytest.mark.asyncio
    async def test_dispatch_with_mock_executor(self) -> None:
        """Dispatch 3 tasks with default mock executor."""
        d = ParallelDispatcher()
        tasks = [
            {"agent_id": "eng-core", "input": "task 1"},
            {"agent_id": "wp-web", "input": "task 2"},
            {"agent_id": "design-lab", "input": "task 3"},
        ]
        state = await d.dispatch(tasks)
        assert state.total == 3
        assert state.completed == 3
        assert state.failed == 0
        assert state.pending == 0
        assert state.is_done is True

    @pytest.mark.asyncio
    async def test_dispatch_10_plus_concurrent(self) -> None:
        """Dispatch 15 tasks concurrently with custom executor."""
        call_count = 0

        async def executor(agent_id: str, task_input: str) -> dict[str, Any]:
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)
            return {"agent_id": agent_id, "result": f"done-{task_input}"}

        d = ParallelDispatcher(max_concurrent=15, default_timeout=10)
        tasks = [
            {"agent_id": f"agent-{i}", "input": f"task-{i}"}
            for i in range(15)
        ]
        state = await d.dispatch(tasks, executor_fn=executor)
        assert state.total == 15
        assert state.completed == 15
        assert state.failed == 0
        assert call_count == 15

    @pytest.mark.asyncio
    async def test_partial_failure(self) -> None:
        """Some tasks fail, others succeed."""
        async def executor(agent_id: str, task_input: str) -> dict[str, Any]:
            if agent_id == "fail-agent":
                raise RuntimeError("Agent crashed")
            return {"ok": True}

        d = ParallelDispatcher(max_concurrent=10, default_timeout=10)
        tasks = [
            {"agent_id": "good-agent", "input": "a"},
            {"agent_id": "fail-agent", "input": "b"},
            {"agent_id": "good-agent", "input": "c"},
            {"agent_id": "fail-agent", "input": "d"},
            {"agent_id": "good-agent", "input": "e"},
        ]
        state = await d.dispatch(tasks, executor_fn=executor)
        assert state.total == 5
        assert state.completed == 3
        assert state.failed == 2
        assert state.is_done is True

        # Check individual statuses
        statuses = {t.agent_id: t.status for t in state.tasks}
        for t in state.tasks:
            if t.agent_id == "fail-agent":
                assert t.status == DispatchTaskStatus.FAILED
                assert t.error is not None
                assert "crashed" in t.error
            else:
                assert t.status == DispatchTaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_timeout_handling(self) -> None:
        """Tasks that exceed timeout get TIMEOUT status."""
        async def slow_executor(agent_id: str, task_input: str) -> dict[str, Any]:
            if agent_id == "slow":
                await asyncio.sleep(10)  # Will be cancelled by timeout
            return {"ok": True}

        d = ParallelDispatcher(max_concurrent=10, default_timeout=60)
        tasks = [
            {"agent_id": "fast", "input": "quick"},
            {"agent_id": "slow", "input": "slow", "timeout": 1},  # 1s timeout
        ]
        state = await d.dispatch(tasks, executor_fn=slow_executor)
        assert state.total == 2
        assert state.completed == 1
        assert state.failed == 1  # timeout counts as failed

        fast_task = state.tasks[0]
        slow_task = state.tasks[1]
        assert fast_task.status == DispatchTaskStatus.COMPLETED
        assert slow_task.status == DispatchTaskStatus.TIMEOUT
        assert slow_task.error is not None
        assert "Timeout" in slow_task.error

    @pytest.mark.asyncio
    async def test_progress_tracking(self) -> None:
        """State properties track progress correctly."""
        d = ParallelDispatcher(max_concurrent=10, default_timeout=10)
        tasks = [
            {"agent_id": f"agent-{i}", "input": f"t-{i}"}
            for i in range(10)
        ]
        state = await d.dispatch(tasks)
        assert state.total == 10
        assert state.completed == 10
        assert state.pending == 0
        assert state.is_done is True

    @pytest.mark.asyncio
    async def test_get_dispatch_returns_state(self) -> None:
        d = ParallelDispatcher()
        tasks = [{"agent_id": "a", "input": "x"}]
        state = await d.dispatch(tasks)

        retrieved = d.get_dispatch(state.dispatch_id)
        assert retrieved is not None
        assert retrieved.dispatch_id == state.dispatch_id
        assert retrieved.total == 1

    @pytest.mark.asyncio
    async def test_get_dispatch_unknown_returns_none(self) -> None:
        d = ParallelDispatcher()
        assert d.get_dispatch("nonexistent") is None

    @pytest.mark.asyncio
    async def test_list_dispatches(self) -> None:
        d = ParallelDispatcher()
        await d.dispatch([{"agent_id": "a", "input": "1"}])
        await d.dispatch([{"agent_id": "b", "input": "2"}])
        dispatches = d.list_dispatches()
        assert len(dispatches) == 2

    @pytest.mark.asyncio
    async def test_semaphore_limits_concurrency(self) -> None:
        """Verify semaphore actually limits concurrent executions."""
        max_concurrent_seen = 0
        current_concurrent = 0

        async def counting_executor(agent_id: str, task_input: str) -> dict[str, Any]:
            nonlocal max_concurrent_seen, current_concurrent
            current_concurrent += 1
            if current_concurrent > max_concurrent_seen:
                max_concurrent_seen = current_concurrent
            await asyncio.sleep(0.05)
            current_concurrent -= 1
            return {"ok": True}

        d = ParallelDispatcher(max_concurrent=3, default_timeout=10)
        tasks = [
            {"agent_id": f"a-{i}", "input": f"t-{i}"}
            for i in range(10)
        ]
        state = await d.dispatch(tasks, executor_fn=counting_executor)
        assert state.completed == 10
        assert max_concurrent_seen <= 3

    @pytest.mark.asyncio
    async def test_finished_at_set_on_completion(self) -> None:
        d = ParallelDispatcher()
        tasks = [{"agent_id": "a", "input": "x"}]
        state = await d.dispatch(tasks)
        for t in state.tasks:
            assert t.finished_at is not None

    @pytest.mark.asyncio
    async def test_finished_at_set_on_failure(self) -> None:
        async def failing(agent_id: str, task_input: str) -> dict[str, Any]:
            raise ValueError("boom")

        d = ParallelDispatcher()
        tasks = [{"agent_id": "a", "input": "x"}]
        state = await d.dispatch(tasks, executor_fn=failing)
        for t in state.tasks:
            assert t.finished_at is not None
            assert t.status == DispatchTaskStatus.FAILED


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


class TestParallelDispatchSettings:
    """Tests for parallel dispatch settings in config/settings.py."""

    def test_default_settings(self) -> None:
        s = Settings()
        assert s.parallel_dispatch_max_concurrent == 12
        assert s.parallel_dispatch_default_timeout == 120

    def test_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OCCP_PARALLEL_DISPATCH_MAX_CONCURRENT", "20")
        monkeypatch.setenv("OCCP_PARALLEL_DISPATCH_DEFAULT_TIMEOUT", "300")
        s = Settings()
        assert s.parallel_dispatch_max_concurrent == 20
        assert s.parallel_dispatch_default_timeout == 300
