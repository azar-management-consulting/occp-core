"""Tests for autodev.sandbox_worktree.

These tests verify the git worktree lifecycle without actually calling git
against the real repo — we use tmp_path + mock subprocess where needed.
"""

from __future__ import annotations

import pathlib
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from autodev.sandbox_worktree import (
    SandboxError,
    SandboxWorktree,
    WorktreeHandle,
    get_sandbox_worktree,
)


@pytest.fixture
def sandbox(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    worktree_root = tmp_path / "worktrees"
    return SandboxWorktree(repo_root=repo, worktree_root=worktree_root)


class TestDiffParsing:

    def test_parse_modified_files_simple(self):
        diff = """diff --git a/foo.py b/foo.py
index 1234..5678 100644
--- a/foo.py
+++ b/foo.py
@@ -1 +1 @@
-old
+new
"""
        files = SandboxWorktree._parse_modified_files(diff)
        assert files == ["foo.py"]

    def test_parse_modified_files_multiple(self):
        diff = """diff --git a/a.py b/a.py
--- a/a.py
+++ b/a.py
diff --git a/b.py b/b.py
--- a/b.py
+++ b/b.py
"""
        files = SandboxWorktree._parse_modified_files(diff)
        assert sorted(files) == ["a.py", "b.py"]

    def test_parse_ignores_devnull(self):
        diff = """--- a/deleted.py
+++ /dev/null
"""
        files = SandboxWorktree._parse_modified_files(diff)
        assert "/dev/null" not in files


class TestLifecycle:

    @patch("autodev.sandbox_worktree.subprocess.run")
    def test_create_worktree(self, mock_run, sandbox):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        handle = sandbox.create(run_id="abc123")
        assert handle.run_id == "abc123"
        assert handle.branch_name == "autodev/abc123"
        assert "abc123" in str(handle.worktree_path)

    @patch("autodev.sandbox_worktree.subprocess.run")
    def test_duplicate_run_id_raises(self, mock_run, sandbox):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        sandbox.create(run_id="dup")
        with pytest.raises(SandboxError, match="already active"):
            sandbox.create(run_id="dup")

    @patch("autodev.sandbox_worktree.subprocess.run")
    def test_get_unknown_returns_none(self, mock_run, sandbox):
        assert sandbox.get("nonexistent") is None

    @patch("autodev.sandbox_worktree.subprocess.run")
    def test_list_active(self, mock_run, sandbox):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        sandbox.create(run_id="r1")
        sandbox.create(run_id="r2")
        active = sandbox.list_active()
        assert len(active) == 2


class TestCleanup:

    @patch("autodev.sandbox_worktree.subprocess.run")
    def test_cleanup_marks_handle(self, mock_run, sandbox):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        sandbox.create(run_id="c1")
        sandbox.cleanup("c1")
        handle = sandbox.get("c1")
        assert handle.cleaned_up is True

    @patch("autodev.sandbox_worktree.subprocess.run")
    def test_cleanup_noop_on_unknown(self, mock_run, sandbox):
        sandbox.cleanup("nonexistent")  # should not raise


class TestGitErrorHandling:

    @patch("autodev.sandbox_worktree.subprocess.run")
    def test_git_failure_raises_sandbox_error(self, mock_run, sandbox):
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=128,
            cmd=["git", "worktree", "add"],
            output="",
            stderr="fatal: bad reference",
        )
        with pytest.raises(SandboxError, match=r"git worktree add"):
            sandbox.create(run_id="fail1")


class TestStats:

    @patch("autodev.sandbox_worktree.subprocess.run")
    def test_stats_structure(self, mock_run, sandbox):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        sandbox.create(run_id="s1")
        stats = sandbox.stats
        assert "total_tracked" in stats
        assert "active" in stats
        assert stats["active"] == 1


class TestWorktreeHandleSerialization:

    def test_to_dict(self):
        handle = WorktreeHandle(
            run_id="x",
            worktree_path=pathlib.Path("/tmp/x"),
            branch_name="autodev/x",
            base_branch="HEAD",
        )
        d = handle.to_dict()
        assert d["run_id"] == "x"
        assert d["branch_name"] == "autodev/x"
        assert d["cleaned_up"] is False


class TestSingleton:

    def test_singleton(self):
        s1 = get_sandbox_worktree()
        s2 = get_sandbox_worktree()
        assert s1 is s2
