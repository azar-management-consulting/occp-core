"""Tests for the Click-based CLI module."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from cli.main import cli, main


class TestCLI:
    def test_no_command_shows_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, [])
        assert result.exit_code == 0
        assert "OpenCloud Control Plane" in result.output

    def test_version(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "0.7.0" in result.output

    def test_status(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["status"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["platform"] == "OCCP"

    def test_run_missing_file(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["run", "/nonexistent/workflow.json"])
        assert result.exit_code != 0

    def test_run_dry_run(self, tmp_path: Path) -> None:
        wf = tmp_path / "test.json"
        wf.write_text(json.dumps({"name": "test_wf", "tasks": []}))
        runner = CliRunner()
        result = runner.invoke(cli, ["run", str(wf), "--dry-run"])
        assert result.exit_code == 0
        assert "validated OK" in result.output

    def test_export_json(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["export", "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)

    def test_demo(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["demo"])
        assert result.exit_code == 0
        assert "Pipeline completed" in result.output

    def test_demo_inject(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["demo", "--inject"])
        assert result.exit_code == 0
        assert "blocked" in result.output.lower()

    def test_agents_command_offline(self) -> None:
        """agents command handles offline API gracefully."""
        runner = CliRunner()
        result = runner.invoke(cli, ["agents"])
        # Should fail gracefully when no API is running
        assert result.exit_code != 0 or "Error" in result.output or "No agents" in result.output

    def test_main_compat(self) -> None:
        """Backward compat wrapper returns int."""
        ret = main(["status"])
        assert ret == 0
