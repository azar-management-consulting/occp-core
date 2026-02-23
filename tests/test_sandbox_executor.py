"""Tests for SandboxExecutor — backend detection, execution, resource limits."""

from __future__ import annotations

import asyncio
import os
import shutil
from unittest.mock import patch

import pytest

from adapters.sandbox_executor import (
    SandboxBackend,
    SandboxConfig,
    SandboxExecutor,
    detect_backend,
    _check_user_namespaces,
)
from orchestrator.exceptions import ExecutionError
from orchestrator.models import Task


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_task(
    command: str = "echo hello",
    *,
    name: str = "test-task",
    via_plan: bool = True,
    via_metadata: bool = False,
) -> Task:
    """Create a task with a command in plan or metadata."""
    plan = {"command": command} if via_plan else None
    metadata = {"command": command} if via_metadata else {}
    return Task(
        name=name,
        description="sandbox test",
        agent_type="general",
        plan=plan,
        metadata=metadata,
    )


# ---------------------------------------------------------------------------
# Backend detection
# ---------------------------------------------------------------------------

class TestBackendDetection:
    def test_process_fallback_when_no_binaries(self) -> None:
        """When nsjail and bwrap are not on PATH, fall back to process."""
        with patch.object(shutil, "which", return_value=None):
            backend = detect_backend()
        assert backend == SandboxBackend.PROCESS

    def test_nsjail_selected_when_available(self) -> None:
        """nsjail is preferred when binary exists and user namespaces work."""
        def _which(name: str) -> str | None:
            return "/usr/bin/nsjail" if name == "nsjail" else None

        with (
            patch.object(shutil, "which", side_effect=_which),
            patch(
                "adapters.sandbox_executor._check_user_namespaces",
                return_value=True,
            ),
        ):
            backend = detect_backend()
        assert backend == SandboxBackend.NSJAIL

    def test_bwrap_fallback_when_nsjail_missing(self) -> None:
        """bwrap is used when nsjail is missing but bwrap is available."""
        def _which(name: str) -> str | None:
            return "/usr/bin/bwrap" if name == "bwrap" else None

        with (
            patch.object(shutil, "which", side_effect=_which),
            patch(
                "adapters.sandbox_executor._check_user_namespaces",
                return_value=True,
            ),
        ):
            backend = detect_backend()
        assert backend == SandboxBackend.BWRAP

    def test_process_when_no_user_namespaces(self) -> None:
        """Even with nsjail on PATH, fall back to process without userns."""
        with (
            patch.object(shutil, "which", return_value="/usr/bin/nsjail"),
            patch(
                "adapters.sandbox_executor._check_user_namespaces",
                return_value=False,
            ),
        ):
            backend = detect_backend()
        assert backend == SandboxBackend.PROCESS

    def test_explicit_backend_skips_detection(self) -> None:
        """When backend is explicitly set, detection is skipped."""
        cfg = SandboxConfig(backend=SandboxBackend.MOCK)
        executor = SandboxExecutor(config=cfg)
        assert executor.backend == SandboxBackend.MOCK


# ---------------------------------------------------------------------------
# Command extraction
# ---------------------------------------------------------------------------

class TestCommandExtraction:
    def test_from_plan_command(self) -> None:
        task = _make_task("ls -la", via_plan=True)
        assert SandboxExecutor._extract_command(task) == "ls -la"

    def test_from_metadata_command(self) -> None:
        task = _make_task("pwd", via_plan=False, via_metadata=True)
        assert SandboxExecutor._extract_command(task) == "pwd"

    def test_from_plan_steps(self) -> None:
        task = Task(
            name="steps-task",
            description="test",
            agent_type="general",
            plan={"steps": [{"command": "whoami"}, {"command": "date"}]},
        )
        assert SandboxExecutor._extract_command(task) == "whoami"

    def test_empty_plan_returns_empty(self) -> None:
        task = Task(
            name="no-cmd",
            description="test",
            agent_type="general",
        )
        assert SandboxExecutor._extract_command(task) == ""

    async def test_no_command_returns_noop_result(self) -> None:
        """When no command is found, executor returns a benign result."""
        cfg = SandboxConfig(backend=SandboxBackend.MOCK)
        executor = SandboxExecutor(config=cfg)
        task = Task(name="empty", description="test", agent_type="general")
        result = await executor.execute(task)
        assert result["exit_code"] == 0
        assert "No executable command" in result["output"]


# ---------------------------------------------------------------------------
# Mock backend execution
# ---------------------------------------------------------------------------

class TestMockBackend:
    @pytest.fixture
    def executor(self) -> SandboxExecutor:
        return SandboxExecutor(config=SandboxConfig(backend=SandboxBackend.MOCK))

    async def test_mock_returns_command(self, executor: SandboxExecutor) -> None:
        task = _make_task("echo sandbox-test")
        result = await executor.execute(task)
        assert result["sandbox"] == "mock"
        assert "echo sandbox-test" in result["output"]
        assert result["exit_code"] == 0

    async def test_mock_executor_type(self, executor: SandboxExecutor) -> None:
        task = _make_task("date")
        result = await executor.execute(task)
        assert result["executor"] == "sandbox/mock"


# ---------------------------------------------------------------------------
# Process backend execution
# ---------------------------------------------------------------------------

class TestProcessBackend:
    @pytest.fixture
    def executor(self) -> SandboxExecutor:
        return SandboxExecutor(
            config=SandboxConfig(
                backend=SandboxBackend.PROCESS,
                time_limit_seconds=10,
                memory_limit_mb=128,
            )
        )

    async def test_echo_command(self, executor: SandboxExecutor) -> None:
        task = _make_task("echo hello-sandbox")
        result = await executor.execute(task)
        assert result["exit_code"] == 0
        assert "hello-sandbox" in result["output"]
        assert result["sandbox"] == "process"

    async def test_exit_code_nonzero(self, executor: SandboxExecutor) -> None:
        task = _make_task("exit 42")
        result = await executor.execute(task)
        assert result["exit_code"] == 42

    async def test_stderr_captured(self, executor: SandboxExecutor) -> None:
        task = _make_task("echo err >&2")
        result = await executor.execute(task)
        assert "err" in result["stderr"]

    async def test_timeout_kills_process(self) -> None:
        executor = SandboxExecutor(
            config=SandboxConfig(
                backend=SandboxBackend.PROCESS,
                time_limit_seconds=2,
                max_pids=256,
                max_fds=256,
                memory_limit_mb=2048,
            )
        )
        # sleep(1) is the most portable way to trigger a timeout
        task = _make_task("sleep 120")
        with pytest.raises(ExecutionError, match="[Tt]imeout|signal"):
            await executor.execute(task)

    async def test_multiline_output(self, executor: SandboxExecutor) -> None:
        task = _make_task("echo line1; echo line2; echo line3")
        result = await executor.execute(task)
        lines = result["output"].strip().split("\n")
        assert len(lines) == 3
        assert lines[0] == "line1"

    async def test_env_whitelist(self) -> None:
        """Only whitelisted env vars are passed to subprocess."""
        executor = SandboxExecutor(
            config=SandboxConfig(
                backend=SandboxBackend.PROCESS,
                env_whitelist=["PATH"],
            )
        )
        os.environ["OCCP_SECRET_TEST"] = "leaked"
        try:
            task = _make_task("env")
            result = await executor.execute(task)
            assert "OCCP_SECRET_TEST" not in result["output"]
        finally:
            os.environ.pop("OCCP_SECRET_TEST", None)

    async def test_work_dir_cleanup(self) -> None:
        """Auto-created work dir is cleaned up after execution."""
        executor = SandboxExecutor(
            config=SandboxConfig(
                backend=SandboxBackend.PROCESS,
                work_dir="",  # auto-create
            )
        )
        task = _make_task("pwd")
        result = await executor.execute(task)
        # The work_dir was cleaned up; we can't inspect it directly,
        # but we can verify the executor didn't crash.
        assert result["exit_code"] == 0

    async def test_output_truncation(self) -> None:
        """Output exceeding max_output_bytes is truncated."""
        executor = SandboxExecutor(
            config=SandboxConfig(
                backend=SandboxBackend.PROCESS,
                max_output_bytes=50,
            )
        )
        # Generate more than 50 bytes of output
        task = _make_task("python3 -c 'print(\"A\" * 200)'")
        result = await executor.execute(task)
        assert len(result["output"]) <= 60  # some tolerance for decode


# ---------------------------------------------------------------------------
# SandboxConfig defaults
# ---------------------------------------------------------------------------

class TestSandboxConfig:
    def test_defaults(self) -> None:
        cfg = SandboxConfig()
        assert cfg.time_limit_seconds == 30
        assert cfg.memory_limit_mb == 256
        assert cfg.max_pids == 32
        assert cfg.max_fds == 64
        assert cfg.enable_network is False
        assert cfg.read_only_root is True
        assert cfg.backend is None

    def test_custom_config(self) -> None:
        cfg = SandboxConfig(
            backend=SandboxBackend.NSJAIL,
            time_limit_seconds=60,
            memory_limit_mb=512,
            enable_network=True,
        )
        assert cfg.backend == SandboxBackend.NSJAIL
        assert cfg.time_limit_seconds == 60
        assert cfg.enable_network is True


# ---------------------------------------------------------------------------
# Integration with Pipeline
# ---------------------------------------------------------------------------

class TestPipelineIntegration:
    """Verify SandboxExecutor conforms to the Executor protocol."""

    async def test_conforms_to_executor_protocol(self) -> None:
        """SandboxExecutor satisfies the Executor structural type."""
        from orchestrator.pipeline import Executor

        executor = SandboxExecutor(
            config=SandboxConfig(backend=SandboxBackend.MOCK)
        )
        # Protocol check — must have execute(task) -> dict
        assert hasattr(executor, "execute")
        assert callable(executor.execute)

    async def test_adapter_registry_accepts_sandbox(self) -> None:
        """AdapterRegistry works with SandboxExecutor."""
        from adapters.echo_planner import EchoPlanner
        from adapters.basic_validator import BasicValidator
        from adapters.log_shipper import LogShipper
        from orchestrator.adapter_registry import AdapterRegistry

        sandbox = SandboxExecutor(
            config=SandboxConfig(backend=SandboxBackend.MOCK)
        )
        registry = AdapterRegistry(
            default_planner=EchoPlanner(),
            default_executor=sandbox,
            default_validator=BasicValidator(),
            default_shipper=LogShipper(),
        )
        resolved = registry.get_executor("general")
        assert resolved is sandbox


# ---------------------------------------------------------------------------
# nsjail / bwrap CLI argument generation
# ---------------------------------------------------------------------------

class TestNsjailArgs:
    """Verify nsjail CLI arg construction (doesn't actually run nsjail)."""

    async def test_nsjail_args_include_time_limit(self) -> None:
        """nsjail args contain --time_limit."""
        cfg = SandboxConfig(
            backend=SandboxBackend.NSJAIL,
            time_limit_seconds=45,
            nsjail_bin="/fake/nsjail",
        )
        executor = SandboxExecutor(config=cfg)
        task = _make_task("echo test")

        # We'll patch _exec_subprocess to capture the args
        captured_args: list[str] = []

        async def _fake_exec(
            self_ref: Any, task: Any, args: list[str], work_dir: str, name: str, **kw: Any
        ) -> dict[str, Any]:
            captured_args.extend(args)
            return {"executor": "test", "task_id": "x", "output": "", "exit_code": 0, "sandbox": "nsjail"}

        with patch.object(SandboxExecutor, "_exec_subprocess", _fake_exec):
            await executor.execute(task)

        assert "--time_limit" in captured_args
        idx = captured_args.index("--time_limit")
        assert captured_args[idx + 1] == "45"

    async def test_nsjail_no_network_by_default(self) -> None:
        """nsjail args include --clone_newnet when network disabled."""
        cfg = SandboxConfig(
            backend=SandboxBackend.NSJAIL,
            enable_network=False,
            nsjail_bin="/fake/nsjail",
        )
        executor = SandboxExecutor(config=cfg)
        task = _make_task("echo test")

        captured_args: list[str] = []

        async def _fake_exec(
            self_ref: Any, task: Any, args: list[str], work_dir: str, name: str, **kw: Any
        ) -> dict[str, Any]:
            captured_args.extend(args)
            return {"executor": "test", "task_id": "x", "output": "", "exit_code": 0, "sandbox": "nsjail"}

        with patch.object(SandboxExecutor, "_exec_subprocess", _fake_exec):
            await executor.execute(task)

        assert "--clone_newnet" in captured_args


class TestBwrapArgs:
    """Verify bwrap CLI arg construction."""

    async def test_bwrap_unshare_flags(self) -> None:
        """bwrap args include namespace unshare flags."""
        cfg = SandboxConfig(
            backend=SandboxBackend.BWRAP,
            bwrap_bin="/fake/bwrap",
        )
        executor = SandboxExecutor(config=cfg)
        task = _make_task("echo test")

        captured_args: list[str] = []

        async def _fake_exec(
            self_ref: Any, task: Any, args: list[str], work_dir: str, name: str, **kw: Any
        ) -> dict[str, Any]:
            captured_args.extend(args)
            return {"executor": "test", "task_id": "x", "output": "", "exit_code": 0, "sandbox": "bwrap"}

        with patch.object(SandboxExecutor, "_exec_subprocess", _fake_exec):
            await executor.execute(task)

        assert "--unshare-pid" in captured_args
        assert "--unshare-net" in captured_args
        assert "--die-with-parent" in captured_args

    async def test_bwrap_network_enabled(self) -> None:
        """When network is enabled, --unshare-net is NOT included."""
        cfg = SandboxConfig(
            backend=SandboxBackend.BWRAP,
            enable_network=True,
            bwrap_bin="/fake/bwrap",
        )
        executor = SandboxExecutor(config=cfg)
        task = _make_task("curl example.com")

        captured_args: list[str] = []

        async def _fake_exec(
            self_ref: Any, task: Any, args: list[str], work_dir: str, name: str, **kw: Any
        ) -> dict[str, Any]:
            captured_args.extend(args)
            return {"executor": "test", "task_id": "x", "output": "", "exit_code": 0, "sandbox": "bwrap"}

        with patch.object(SandboxExecutor, "_exec_subprocess", _fake_exec):
            await executor.execute(task)

        assert "--unshare-net" not in captured_args


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    async def test_binary_not_found_raises_execution_error(self) -> None:
        """Missing sandbox binary raises ExecutionError, not FileNotFoundError."""
        cfg = SandboxConfig(
            backend=SandboxBackend.NSJAIL,
            nsjail_bin="/nonexistent/nsjail",
        )
        executor = SandboxExecutor(config=cfg)
        task = _make_task("echo test")

        with pytest.raises(ExecutionError, match="not found"):
            await executor.execute(task)

    async def test_process_signal_kill_raises(self) -> None:
        """Process killed by signal raises ExecutionError."""
        cfg = SandboxConfig(
            backend=SandboxBackend.PROCESS,
            time_limit_seconds=5,
        )
        executor = SandboxExecutor(config=cfg)
        # kill -9 self
        task = _make_task("kill -9 $$")

        with pytest.raises(ExecutionError, match="signal"):
            await executor.execute(task)
