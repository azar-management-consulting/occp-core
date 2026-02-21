"""Tests for the CLI module."""

from __future__ import annotations

import json
from pathlib import Path

from cli.main import main


class TestCLI:
    def test_no_command_returns_zero(self) -> None:
        assert main([]) == 0

    def test_version(self, capsys) -> None:  # type: ignore[no-untyped-def]
        import pytest

        with pytest.raises(SystemExit) as exc_info:
            main(["--version"])
        assert exc_info.value.code == 0

    def test_status(self, capsys) -> None:  # type: ignore[no-untyped-def]
        ret = main(["status"])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["platform"] == "OCCP"
        assert ret == 0

    def test_run_missing_file(self) -> None:
        ret = main(["run", "/nonexistent/workflow.json"])
        assert ret == 1

    def test_run_dry_run(self, tmp_path: Path) -> None:
        wf = tmp_path / "test.json"
        wf.write_text(json.dumps({"name": "test_wf", "tasks": []}))
        ret = main(["run", str(wf), "--dry-run"])
        assert ret == 0

    def test_export_json(self, capsys) -> None:  # type: ignore[no-untyped-def]
        ret = main(["export", "--format", "json"])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert isinstance(data, list)
        assert ret == 0
