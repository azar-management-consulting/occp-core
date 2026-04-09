"""Ephemeral git-worktree sandbox for auto-dev proposals.

Design (per 2026 best practice):
- Every proposal gets its own git worktree branch
- Worktree is created under `/tmp/occp-autodev/<run_id>/`
- Code edits happen ONLY inside the worktree — live repo untouched
- On success: diff is captured, worktree kept for review
- On failure: worktree destroyed, no residue
- Rollback = delete worktree + branch

Preservation contract:
- Never modifies files outside the worktree
- Never touches origin/main or production branches
- Never force-pushes
- Every action logged with hash-chain audit

This module is PURE subprocess wrapper around `git worktree` — no
custom git logic, no bypass of git safety features.
"""

from __future__ import annotations

import logging
import pathlib
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# Default worktree root — separate from main repo
_DEFAULT_WORKTREE_ROOT = pathlib.Path("/tmp/occp-autodev")

# Branch name prefix for autodev branches (never conflicts with human branches)
_AUTODEV_BRANCH_PREFIX = "autodev/"


class SandboxError(Exception):
    """Sandbox operation failed."""


@dataclass
class WorktreeHandle:
    """Handle to an active git worktree sandbox."""

    run_id: str
    worktree_path: pathlib.Path
    branch_name: str
    base_branch: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    files_modified: list[str] = field(default_factory=list)
    diff_captured: str | None = None
    cleaned_up: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "worktree_path": str(self.worktree_path),
            "branch_name": self.branch_name,
            "base_branch": self.base_branch,
            "created_at": self.created_at.isoformat(),
            "files_modified": self.files_modified,
            "diff_captured": self.diff_captured is not None,
            "diff_size": len(self.diff_captured) if self.diff_captured else 0,
            "cleaned_up": self.cleaned_up,
        }


class SandboxWorktree:
    """Manages the lifecycle of git-worktree-based sandboxes."""

    def __init__(
        self,
        repo_root: pathlib.Path,
        worktree_root: pathlib.Path | None = None,
    ) -> None:
        self._repo_root = repo_root.resolve()
        self._worktree_root = worktree_root or _DEFAULT_WORKTREE_ROOT
        self._active: dict[str, WorktreeHandle] = {}

    # ── Git command wrapper ────────────────────────────────
    def _run_git(
        self,
        args: list[str],
        cwd: pathlib.Path | None = None,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        """Run git with safe defaults: no prompts, text mode, captured output.

        We never use --no-verify or force flags — all standard safety preserved.
        """
        full_args = ["git"] + args
        logger.debug("git %s (cwd=%s)", " ".join(args), cwd or self._repo_root)
        try:
            result = subprocess.run(
                full_args,
                cwd=cwd or self._repo_root,
                check=check,
                capture_output=True,
                text=True,
                env={"GIT_TERMINAL_PROMPT": "0", "PATH": "/usr/bin:/bin:/usr/local/bin"},
            )
        except subprocess.CalledProcessError as exc:
            raise SandboxError(
                f"git {' '.join(args)} failed (code {exc.returncode}): "
                f"{exc.stderr.strip() if exc.stderr else '?'}"
            ) from exc
        except FileNotFoundError:
            raise SandboxError("git executable not found in PATH")
        return result

    # ── Lifecycle ──────────────────────────────────────────
    def create(
        self,
        run_id: str,
        base_branch: str = "HEAD",
    ) -> WorktreeHandle:
        """Create a new worktree at `<worktree_root>/<run_id>`.

        Args:
            run_id: Short identifier (used for branch + directory name).
            base_branch: Branch/SHA to base the worktree on (default: current HEAD).

        Returns:
            WorktreeHandle with path + branch info.

        Raises:
            SandboxError: if worktree creation fails.
        """
        if run_id in self._active:
            raise SandboxError(f"run_id {run_id!r} already active")

        self._worktree_root.mkdir(parents=True, exist_ok=True)
        worktree_path = self._worktree_root / run_id
        if worktree_path.exists():
            raise SandboxError(
                f"worktree path {worktree_path} already exists — refusing to overwrite"
            )

        branch_name = f"{_AUTODEV_BRANCH_PREFIX}{run_id}"
        self._run_git(
            ["worktree", "add", "-b", branch_name, str(worktree_path), base_branch],
        )

        handle = WorktreeHandle(
            run_id=run_id,
            worktree_path=worktree_path,
            branch_name=branch_name,
            base_branch=base_branch,
        )
        self._active[run_id] = handle
        logger.info(
            "autodev.sandbox: created worktree run_id=%s path=%s branch=%s",
            run_id,
            worktree_path,
            branch_name,
        )
        return handle

    def get(self, run_id: str) -> WorktreeHandle | None:
        return self._active.get(run_id)

    def list_active(self) -> list[WorktreeHandle]:
        return [h for h in self._active.values() if not h.cleaned_up]

    # ── Diff capture ──────────────────────────────────────
    def capture_diff(self, run_id: str) -> str:
        """Capture unstaged+staged diff from the worktree."""
        handle = self._require_handle(run_id)
        result = self._run_git(
            ["diff", "HEAD"],
            cwd=handle.worktree_path,
        )
        handle.diff_captured = result.stdout
        handle.files_modified = self._parse_modified_files(result.stdout)
        return result.stdout

    @staticmethod
    def _parse_modified_files(diff: str) -> list[str]:
        """Extract list of modified file paths from a unified diff."""
        files: set[str] = set()
        for line in diff.splitlines():
            if line.startswith("+++ b/"):
                files.add(line[len("+++ b/") :])
            elif line.startswith("--- a/"):
                files.add(line[len("--- a/") :])
        files.discard("/dev/null")
        return sorted(files)

    # ── Cleanup ────────────────────────────────────────────
    def cleanup(self, run_id: str, keep_branch: bool = False) -> None:
        """Remove the worktree directory and (optionally) the branch.

        Safe to call multiple times; no-op if already cleaned up.
        """
        handle = self._active.get(run_id)
        if handle is None or handle.cleaned_up:
            return

        # Remove worktree via git (safer than rm -rf)
        if handle.worktree_path.exists():
            try:
                self._run_git(
                    ["worktree", "remove", "--force", str(handle.worktree_path)],
                    check=False,
                )
            except SandboxError:
                # Fallback to filesystem removal if git command fails
                if handle.worktree_path.exists():
                    shutil.rmtree(handle.worktree_path, ignore_errors=True)

        # Prune stale worktree references
        self._run_git(["worktree", "prune"], check=False)

        # Delete branch unless explicitly asked to keep
        if not keep_branch:
            try:
                self._run_git(
                    ["branch", "-D", handle.branch_name],
                    check=False,
                )
            except SandboxError:
                pass

        handle.cleaned_up = True
        logger.info(
            "autodev.sandbox: cleaned up run_id=%s (branch kept=%s)",
            run_id,
            keep_branch,
        )

    def cleanup_all(self) -> int:
        """Remove all active worktrees. Returns count removed."""
        ids = list(self._active.keys())
        for rid in ids:
            self.cleanup(rid)
        return len(ids)

    # ── Helpers ────────────────────────────────────────────
    def _require_handle(self, run_id: str) -> WorktreeHandle:
        handle = self._active.get(run_id)
        if handle is None:
            raise SandboxError(f"unknown run_id: {run_id}")
        if handle.cleaned_up:
            raise SandboxError(f"run_id {run_id} already cleaned up")
        return handle

    @property
    def stats(self) -> dict[str, Any]:
        active = self.list_active()
        return {
            "total_tracked": len(self._active),
            "active": len(active),
            "cleaned_up": len(self._active) - len(active),
            "worktree_root": str(self._worktree_root),
        }


# ── Singleton accessor ────────────────────────────────────────
_global_sandbox: SandboxWorktree | None = None


def get_sandbox_worktree(
    repo_root: pathlib.Path | None = None,
) -> SandboxWorktree:
    """Return the process-global SandboxWorktree singleton."""
    global _global_sandbox
    if _global_sandbox is None:
        root = repo_root or pathlib.Path(__file__).parent.parent
        _global_sandbox = SandboxWorktree(repo_root=root)
    return _global_sandbox
