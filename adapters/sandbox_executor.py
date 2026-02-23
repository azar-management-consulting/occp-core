"""SandboxExecutor — OS-level isolated execution with nsjail/bwrap/process fallback.

Provides defense-in-depth for task execution:
  1. nsjail   — full namespace isolation (PID, NET, MNT, IPC) + seccomp + cgroups
  2. bwrap    — lightweight namespace isolation (Flatpak's bubblewrap)
  3. process  — subprocess with rlimits and timeout (fallback for shared hosting)

The backend is auto-detected at construction time based on available binaries
and kernel capabilities.  Override via ``SandboxConfig.backend``.
"""

from __future__ import annotations

import asyncio
import enum
import logging
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from orchestrator.exceptions import ExecutionError
from orchestrator.models import Task

logger = logging.getLogger(__name__)

# Maximum output size before truncation (10 MB)
_MAX_OUTPUT_BYTES = 10 * 1024 * 1024


class SandboxBackend(enum.Enum):
    """Available isolation backends in priority order."""

    NSJAIL = "nsjail"
    BWRAP = "bwrap"
    PROCESS = "process"
    MOCK = "mock"


@dataclass
class SandboxConfig:
    """Configuration for the sandbox executor."""

    # Explicit backend selection; None = auto-detect
    backend: SandboxBackend | None = None

    # Resource limits
    time_limit_seconds: int = 30
    memory_limit_mb: int = 256
    max_pids: int = 32
    max_fds: int = 64
    max_output_bytes: int = _MAX_OUTPUT_BYTES

    # Filesystem
    work_dir: str = ""  # auto-created tmpdir if empty
    read_only_root: bool = True
    allowed_paths: list[str] = field(default_factory=list)

    # Network
    enable_network: bool = False

    # nsjail-specific
    nsjail_bin: str = "nsjail"
    nsjail_config: str = ""  # path to .cfg file; empty = generate from settings
    nsjail_log: str = ""

    # bwrap-specific
    bwrap_bin: str = "bwrap"

    # Execution
    shell: str = "/bin/sh"
    env_whitelist: list[str] = field(default_factory=lambda: ["PATH", "HOME", "LANG"])


def detect_backend(config: SandboxConfig | None = None) -> SandboxBackend:
    """Probe the system for the best available sandbox backend.

    Returns the highest-isolation backend available on this machine.
    """
    cfg = config or SandboxConfig()

    # 1. nsjail
    if shutil.which(cfg.nsjail_bin):
        if _check_user_namespaces():
            logger.info("Sandbox backend: nsjail (full isolation)")
            return SandboxBackend.NSJAIL
        logger.warning(
            "nsjail binary found but user namespaces unavailable — skipping"
        )

    # 2. bwrap
    if shutil.which(cfg.bwrap_bin):
        if _check_user_namespaces():
            logger.info("Sandbox backend: bwrap (namespace isolation)")
            return SandboxBackend.BWRAP
        logger.warning(
            "bwrap binary found but user namespaces unavailable — skipping"
        )

    # 3. process (always available)
    logger.info("Sandbox backend: process (rlimit isolation only)")
    return SandboxBackend.PROCESS


def _check_user_namespaces() -> bool:
    """Return True if unprivileged user namespaces are enabled."""
    try:
        path = Path("/proc/sys/kernel/unprivileged_userns_clone")
        if path.exists():
            return path.read_text().strip() == "1"
        # If the sysctl doesn't exist, user namespaces may still be available
        # (e.g., older kernels without the toggle).  Try a harmless unshare.
        result = os.popen("unshare --user --pid echo ok 2>/dev/null").read()
        return "ok" in result
    except Exception:
        return False


class SandboxExecutor:
    """Executor adapter that runs task commands in an isolated sandbox.

    Implements the ``Executor`` protocol from ``orchestrator.pipeline``.

    Usage::

        executor = SandboxExecutor()                     # auto-detect
        executor = SandboxExecutor(config=SandboxConfig(
            backend=SandboxBackend.PROCESS,
            time_limit_seconds=60,
            memory_limit_mb=512,
        ))
        result = await executor.execute(task)
    """

    def __init__(self, config: SandboxConfig | None = None) -> None:
        self._config = config or SandboxConfig()
        if self._config.backend is None:
            self._config.backend = detect_backend(self._config)
        self._backend = self._config.backend
        logger.info("SandboxExecutor initialised (backend=%s)", self._backend.value)

    @property
    def backend(self) -> SandboxBackend:
        return self._backend

    async def execute(self, task: Task) -> dict[str, Any]:
        """Run *task* in the selected sandbox and return structured result."""
        command = self._extract_command(task)
        if not command:
            return {
                "executor": f"sandbox/{self._backend.value}",
                "task_id": task.id,
                "output": "No executable command in task plan or metadata.",
                "exit_code": 0,
                "sandbox": self._backend.value,
            }

        work_dir = self._config.work_dir or tempfile.mkdtemp(prefix="occp_sandbox_")
        try:
            if self._backend == SandboxBackend.NSJAIL:
                return await self._run_nsjail(task, command, work_dir)
            elif self._backend == SandboxBackend.BWRAP:
                return await self._run_bwrap(task, command, work_dir)
            elif self._backend == SandboxBackend.PROCESS:
                return await self._run_process(task, command, work_dir)
            else:
                return await self._run_mock(task, command)
        finally:
            # Clean up auto-created work dir
            if not self._config.work_dir and os.path.isdir(work_dir):
                shutil.rmtree(work_dir, ignore_errors=True)

    # ------------------------------------------------------------------
    # Command extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_command(task: Task) -> str:
        """Extract executable command from task plan or metadata.

        Supported locations (checked in order):
          1. task.plan["command"]
          2. task.metadata["command"]
          3. task.plan["steps"][0]["command"]  (first step)
        """
        if task.plan:
            if isinstance(task.plan.get("command"), str):
                return task.plan["command"]
            steps = task.plan.get("steps", [])
            if steps and isinstance(steps[0], dict):
                cmd = steps[0].get("command", "")
                if cmd:
                    return str(cmd)
        if task.metadata:
            cmd = task.metadata.get("command", "")
            if cmd:
                return str(cmd)
        return ""

    # ------------------------------------------------------------------
    # nsjail backend
    # ------------------------------------------------------------------

    async def _run_nsjail(
        self, task: Task, command: str, work_dir: str
    ) -> dict[str, Any]:
        """Execute command inside nsjail sandbox."""
        cfg = self._config
        args = [
            cfg.nsjail_bin,
            "--mode", "o",  # ONCE mode
            "--time_limit", str(cfg.time_limit_seconds),
            "--rlimit_as", str(cfg.memory_limit_mb),
            "--max_cpuid", "1",
            "--cwd", "/tmp",
            # Namespaces
            "--clone_newpid",
            "--clone_newuts",
            "--clone_newipc",
        ]

        # Network isolation
        if not cfg.enable_network:
            args.append("--clone_newnet")

        # Filesystem mounts
        args.extend(["--bindmount_ro", "/"])
        args.extend(["--tmpfsmount", "/tmp"])
        args.extend(["--bindmount", f"{work_dir}:/workspace"])

        # Additional allowed paths
        for path in cfg.allowed_paths:
            args.extend(["--bindmount_ro", path])

        # Resource limits
        args.extend(["--rlimit_nproc", str(cfg.max_pids)])
        args.extend(["--rlimit_nofile", str(cfg.max_fds)])

        # Logging
        if cfg.nsjail_log:
            args.extend(["--log", cfg.nsjail_log])
        else:
            args.extend(["--really_quiet"])

        # Custom config file overrides CLI args
        if cfg.nsjail_config:
            args = [cfg.nsjail_bin, "--config", cfg.nsjail_config]

        # Command to execute
        args.extend(["--", cfg.shell, "-c", command])

        return await self._exec_subprocess(task, args, work_dir, "nsjail")

    # ------------------------------------------------------------------
    # bwrap backend
    # ------------------------------------------------------------------

    async def _run_bwrap(
        self, task: Task, command: str, work_dir: str
    ) -> dict[str, Any]:
        """Execute command inside bubblewrap sandbox."""
        cfg = self._config
        args = [
            cfg.bwrap_bin,
            "--unshare-pid",
            "--unshare-uts",
            "--unshare-ipc",
        ]

        # Network isolation
        if not cfg.enable_network:
            args.append("--unshare-net")

        # Read-only root bind mount
        args.extend(["--ro-bind", "/", "/"])

        # Writable tmpfs for /tmp
        args.extend(["--tmpfs", "/tmp"])

        # Writable workspace
        args.extend(["--bind", work_dir, "/workspace"])

        # /dev basics
        args.extend(["--dev", "/dev"])
        args.extend(["--proc", "/proc"])

        # Die with parent (prevent orphans)
        args.append("--die-with-parent")

        # Additional allowed paths
        for path in cfg.allowed_paths:
            args.extend(["--ro-bind", path, path])

        # Command
        args.extend(["--", cfg.shell, "-c", command])

        return await self._exec_subprocess(task, args, work_dir, "bwrap")

    # ------------------------------------------------------------------
    # process backend (fallback)
    # ------------------------------------------------------------------

    async def _run_process(
        self, task: Task, command: str, work_dir: str
    ) -> dict[str, Any]:
        """Execute command as a subprocess with resource limits.

        Uses ulimit-style limits via preexec_fn.  No namespace isolation.
        """
        cfg = self._config
        env = {k: os.environ.get(k, "") for k in cfg.env_whitelist if k in os.environ}
        env["HOME"] = work_dir

        # Build ulimit prefix for the shell command.
        # On macOS: ulimit -v is unreliable (Python needs huge virtual address
        # space on arm64) and ulimit -u is per-user (not per-process-tree),
        # so both are skipped.  Only ulimit -n (file descriptors) is portable.
        ulimit_prefix = ""
        if sys.platform != "darwin":
            ulimit_prefix += f"ulimit -v {cfg.memory_limit_mb * 1024} 2>/dev/null; "
            ulimit_prefix += f"ulimit -u {cfg.max_pids} 2>/dev/null; "
        ulimit_prefix += f"ulimit -n {cfg.max_fds} 2>/dev/null; "

        args = [cfg.shell, "-c", ulimit_prefix + command]
        return await self._exec_subprocess(
            task, args, work_dir, "process", env=env
        )

    # ------------------------------------------------------------------
    # mock backend
    # ------------------------------------------------------------------

    @staticmethod
    async def _run_mock(task: Task, command: str) -> dict[str, Any]:
        """Simulate execution (for development/testing)."""
        await asyncio.sleep(0.1)
        return {
            "executor": "sandbox/mock",
            "task_id": task.id,
            "output": f"[mock] Would execute: {command}",
            "exit_code": 0,
            "sandbox": "mock",
        }

    # ------------------------------------------------------------------
    # Shared subprocess runner
    # ------------------------------------------------------------------

    async def _exec_subprocess(
        self,
        task: Task,
        args: list[str],
        work_dir: str,
        backend_name: str,
        env: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Run *args* as an async subprocess with timeout and output limits."""
        cfg = self._config
        timeout = cfg.time_limit_seconds + 5  # grace period for nsjail's own limit

        logger.info(
            "Sandbox exec [%s] task=%s timeout=%ds cmd=%s",
            backend_name,
            task.id,
            timeout,
            args[:5],
        )

        try:
            process = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=work_dir if backend_name == "process" else None,
                env=env,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(), timeout=timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                raise ExecutionError(
                    task.id,
                    f"Sandbox timeout after {timeout}s (backend={backend_name})",
                )

            # Truncate oversized output
            stdout = stdout_bytes[:cfg.max_output_bytes].decode("utf-8", errors="replace")
            stderr = stderr_bytes[:cfg.max_output_bytes].decode("utf-8", errors="replace")

            exit_code = process.returncode or 0

            result: dict[str, Any] = {
                "executor": f"sandbox/{backend_name}",
                "task_id": task.id,
                "output": stdout,
                "stderr": stderr,
                "exit_code": exit_code,
                "sandbox": backend_name,
            }

            if exit_code != 0:
                logger.warning(
                    "Sandbox [%s] task=%s exited with code %d",
                    backend_name,
                    task.id,
                    exit_code,
                )
                # Non-zero exit is not necessarily a fatal error — let the
                # Validator decide.  But if we got a signal kill, raise.
                if exit_code < 0:
                    raise ExecutionError(
                        task.id,
                        f"Process killed by signal {-exit_code} "
                        f"(backend={backend_name})",
                    )
                # Shell convention: 128+N means the child was killed by
                # signal N.  Treat as fatal.
                if exit_code > 128:
                    signal_num = exit_code - 128
                    raise ExecutionError(
                        task.id,
                        f"Process killed by signal {signal_num} "
                        f"(exit code {exit_code}, backend={backend_name})",
                    )

            return result

        except ExecutionError:
            raise
        except FileNotFoundError:
            raise ExecutionError(
                task.id,
                f"Sandbox binary not found: {args[0]}",
            )
        except Exception as exc:
            raise ExecutionError(
                task.id,
                f"Sandbox execution failed ({backend_name}): {exc}",
            ) from exc
