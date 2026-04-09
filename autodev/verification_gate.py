"""Verification gate — lint + targeted test + regression runner.

Runs inside a sandbox worktree to validate a proposed change BEFORE merge.

Three-stage verification:
1. LINT — ruff (or flake8 fallback) on modified files only
2. TARGETED TEST — pytest on tests that import modified modules
3. REGRESSION — fast subset of full suite (tests/architecture + smoke tests)

Design principles:
- Never runs in the live repo (always a worktree path)
- Capped execution time per stage (default 180s each)
- Captures all output for audit
- Returns structured verdict: PASS | FAIL | ERROR

Preservation: pure subprocess runner, no code execution in-process.
"""

from __future__ import annotations

import logging
import pathlib
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class StageResult:
    """Result of one verification stage."""

    stage: str  # "lint" | "targeted_test" | "regression"
    verdict: str  # "pass" | "fail" | "error" | "skipped"
    duration_seconds: float
    exit_code: int | None = None
    stdout_tail: str = ""
    stderr_tail: str = ""
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "verdict": self.verdict,
            "duration_seconds": self.duration_seconds,
            "exit_code": self.exit_code,
            "stdout_tail": self.stdout_tail,
            "stderr_tail": self.stderr_tail,
            "detail": self.detail,
        }


@dataclass
class VerificationReport:
    """Aggregate verification outcome for a worktree."""

    run_id: str
    worktree_path: pathlib.Path
    stages: list[StageResult] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None

    @property
    def passed(self) -> bool:
        return all(s.verdict == "pass" or s.verdict == "skipped" for s in self.stages)

    @property
    def total_duration(self) -> float:
        return sum(s.duration_seconds for s in self.stages)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "worktree_path": str(self.worktree_path),
            "passed": self.passed,
            "total_duration_seconds": self.total_duration,
            "stages": [s.to_dict() for s in self.stages],
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
        }


class VerificationGate:
    """Runs lint + targeted + regression tests in a sandbox worktree."""

    def __init__(
        self,
        *,
        lint_timeout: int = 60,
        test_timeout: int = 180,
        regression_timeout: int = 180,
        python_executable: str | None = None,
    ) -> None:
        self._lint_timeout = lint_timeout
        self._test_timeout = test_timeout
        self._regression_timeout = regression_timeout
        self._python = python_executable or ".venv/bin/python"

    # ── Main entry ─────────────────────────────────────────
    def verify(
        self,
        run_id: str,
        worktree_path: pathlib.Path,
        modified_files: list[str],
    ) -> VerificationReport:
        """Run all 3 stages sequentially, stopping on first hard failure."""
        report = VerificationReport(run_id=run_id, worktree_path=worktree_path)

        # Stage 1: lint (only Python files)
        py_files = [f for f in modified_files if f.endswith(".py")]
        if py_files:
            lint_result = self._run_lint(worktree_path, py_files)
            report.stages.append(lint_result)
            if lint_result.verdict == "fail":
                logger.warning("verification: lint FAILED run_id=%s", run_id)
                report.finished_at = datetime.now(timezone.utc)
                return report
        else:
            report.stages.append(
                StageResult(
                    stage="lint",
                    verdict="skipped",
                    duration_seconds=0.0,
                    detail="no python files modified",
                )
            )

        # Stage 2: targeted tests
        target_tests = self._discover_targeted_tests(worktree_path, modified_files)
        if target_tests:
            test_result = self._run_pytest(
                worktree_path, target_tests, self._test_timeout, "targeted_test"
            )
            report.stages.append(test_result)
            if test_result.verdict == "fail":
                logger.warning(
                    "verification: targeted tests FAILED run_id=%s", run_id
                )
                report.finished_at = datetime.now(timezone.utc)
                return report
        else:
            report.stages.append(
                StageResult(
                    stage="targeted_test",
                    verdict="skipped",
                    duration_seconds=0.0,
                    detail="no targeted tests discovered",
                )
            )

        # Stage 3: regression (fast subset — architecture + smoke)
        regression = self._run_regression(worktree_path)
        report.stages.append(regression)

        report.finished_at = datetime.now(timezone.utc)
        logger.info(
            "verification: run_id=%s passed=%s duration=%.1fs",
            run_id,
            report.passed,
            report.total_duration,
        )
        return report

    # ── Stage 1: lint ──────────────────────────────────────
    def _run_lint(
        self, worktree_path: pathlib.Path, py_files: list[str]
    ) -> StageResult:
        """Run ruff check on modified Python files."""
        # Try ruff first
        try:
            return self._run_subprocess(
                ["ruff", "check", *py_files],
                cwd=worktree_path,
                timeout=self._lint_timeout,
                stage="lint",
            )
        except FileNotFoundError:
            pass
        # Fallback to flake8
        try:
            return self._run_subprocess(
                ["flake8", *py_files],
                cwd=worktree_path,
                timeout=self._lint_timeout,
                stage="lint",
            )
        except FileNotFoundError:
            pass
        # Fallback to python -m py_compile
        return self._run_subprocess(
            [self._python, "-m", "py_compile", *py_files],
            cwd=worktree_path,
            timeout=self._lint_timeout,
            stage="lint",
        )

    # ── Stage 2: targeted tests ────────────────────────────
    def _discover_targeted_tests(
        self, worktree_path: pathlib.Path, modified_files: list[str]
    ) -> list[str]:
        """Find tests that correspond to modified source files.

        Heuristic: for each modified module `foo/bar.py` look for
        `tests/test_bar.py`.
        """
        targets: set[str] = set()
        for mod in modified_files:
            if not mod.endswith(".py"):
                continue
            # tests/test_<name>.py
            name = pathlib.Path(mod).stem
            candidate = worktree_path / "tests" / f"test_{name}.py"
            if candidate.exists():
                targets.add(f"tests/test_{name}.py")
            # tests/<subdir>/test_<name>.py
            parent = pathlib.Path(mod).parent.name
            if parent:
                candidate2 = worktree_path / "tests" / parent / f"test_{name}.py"
                if candidate2.exists():
                    targets.add(f"tests/{parent}/test_{name}.py")
        return sorted(targets)

    def _run_pytest(
        self,
        worktree_path: pathlib.Path,
        test_paths: list[str],
        timeout: int,
        stage: str,
    ) -> StageResult:
        """Run pytest on the given test paths."""
        return self._run_subprocess(
            [self._python, "-m", "pytest", "-q", "--tb=line", *test_paths],
            cwd=worktree_path,
            timeout=timeout,
            stage=stage,
        )

    # ── Stage 3: regression ────────────────────────────────
    def _run_regression(self, worktree_path: pathlib.Path) -> StageResult:
        """Run a fast regression suite: architecture + smoke tests."""
        return self._run_subprocess(
            [
                self._python,
                "-m",
                "pytest",
                "-q",
                "--tb=line",
                "tests/architecture/",
                "tests/test_feature_flags.py",
                "tests/test_self_modifier.py",
                "tests/test_kill_switch.py",
                "tests/test_drift_detector.py",
            ],
            cwd=worktree_path,
            timeout=self._regression_timeout,
            stage="regression",
        )

    # ── Subprocess runner ──────────────────────────────────
    def _run_subprocess(
        self,
        cmd: list[str],
        cwd: pathlib.Path,
        timeout: int,
        stage: str,
    ) -> StageResult:
        """Wrap subprocess.run with standard capture + timeout + verdict."""
        start = datetime.now(timezone.utc)
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
                env={"PATH": "/usr/bin:/bin:/usr/local/bin:.venv/bin"},
            )
            duration = (datetime.now(timezone.utc) - start).total_seconds()
            return StageResult(
                stage=stage,
                verdict="pass" if result.returncode == 0 else "fail",
                duration_seconds=duration,
                exit_code=result.returncode,
                stdout_tail=result.stdout[-2000:] if result.stdout else "",
                stderr_tail=result.stderr[-2000:] if result.stderr else "",
            )
        except subprocess.TimeoutExpired as exc:
            duration = (datetime.now(timezone.utc) - start).total_seconds()
            return StageResult(
                stage=stage,
                verdict="fail",
                duration_seconds=duration,
                detail=f"timeout after {timeout}s",
                stdout_tail=(exc.stdout or "")[-2000:] if isinstance(exc.stdout, str) else "",
                stderr_tail=(exc.stderr or "")[-2000:] if isinstance(exc.stderr, str) else "",
            )
        except FileNotFoundError as exc:
            raise
        except Exception as exc:  # noqa: BLE001
            duration = (datetime.now(timezone.utc) - start).total_seconds()
            return StageResult(
                stage=stage,
                verdict="error",
                duration_seconds=duration,
                detail=f"{type(exc).__name__}: {exc}",
            )


# ── Singleton accessor ────────────────────────────────────────
_global_gate: VerificationGate | None = None


def get_verification_gate() -> VerificationGate:
    """Return the process-global verification gate."""
    global _global_gate
    if _global_gate is None:
        _global_gate = VerificationGate()
    return _global_gate
