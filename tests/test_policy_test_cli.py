"""Tests for Policy Test CLI — REQ-POL-03.

Covers:
- Fixture loading (YAML + JSON, edge cases)
- Test runner (pass/fail/error scenarios)
- Output formatting (text + JSON)
- CLI integration (exit codes, options)
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Any

import pytest

from cli.policy_test import (
    FixtureCase,
    FixtureResult,
    _FakeTask,
    format_results_json,
    format_results_text,
    load_fixtures,
    run_policy_tests,
)


# ---------------------------------------------------------------------------
# Helpers — create temp policy + fixture files
# ---------------------------------------------------------------------------


def _write_yaml_policy(tmp_path: Path, name: str = "test_policy") -> Path:
    """Create a minimal ABAC YAML policy."""
    content = textwrap.dedent(f"""\
        name: {name}
        version: "1.0"
        rules:
          - id: allow-admin
            effect: allow
            conditions:
              user_role: admin
          - id: deny-guest
            effect: deny
            conditions:
              user_role: guest
    """)
    p = tmp_path / "policy.yaml"
    p.write_text(content)
    return p


def _write_yaml_fixtures(tmp_path: Path, fixtures: list[dict]) -> Path:
    """Create a YAML fixtures file."""
    import yaml

    data = {"fixtures": fixtures}
    p = tmp_path / "fixtures.yaml"
    p.write_text(yaml.dump(data, default_flow_style=False))
    return p


def _write_json_fixtures(tmp_path: Path, fixtures: list[dict]) -> Path:
    """Create a JSON fixtures file."""
    data = {"fixtures": fixtures}
    p = tmp_path / "fixtures.json"
    p.write_text(json.dumps(data, indent=2))
    return p


# ---------------------------------------------------------------------------
# load_fixtures
# ---------------------------------------------------------------------------


class TestLoadFixtures:
    def test_load_yaml_fixtures(self, tmp_path: Path) -> None:
        fixtures = [
            {"name": "admin-ok", "input": {"user_role": "admin"}, "expect": {"approved": True}},
            {"name": "guest-blocked", "input": {"user_role": "guest"}, "expect": {"approved": False}},
        ]
        path = _write_yaml_fixtures(tmp_path, fixtures)
        cases = load_fixtures(path)
        assert len(cases) == 2
        assert cases[0].name == "admin-ok"
        assert cases[0].expect_approved is True
        assert cases[1].name == "guest-blocked"
        assert cases[1].expect_approved is False

    def test_load_json_fixtures(self, tmp_path: Path) -> None:
        fixtures = [
            {"name": "case1", "input": {"agent_type": "safe"}, "expect": {"approved": True}},
        ]
        path = _write_json_fixtures(tmp_path, fixtures)
        cases = load_fixtures(path)
        assert len(cases) == 1
        assert cases[0].name == "case1"

    def test_load_fixtures_with_violated_rules(self, tmp_path: Path) -> None:
        fixtures = [
            {
                "name": "guest-denied",
                "input": {"user_role": "guest"},
                "expect": {"approved": False, "violated_rules": ["deny-guest"]},
            },
        ]
        path = _write_yaml_fixtures(tmp_path, fixtures)
        cases = load_fixtures(path)
        assert cases[0].expect_violated == ["deny-guest"]

    def test_load_fixtures_with_tests_key(self, tmp_path: Path) -> None:
        """Supports 'tests' key as alternative to 'fixtures'."""
        import yaml

        data = {"tests": [
            {"name": "t1", "input": {}, "expect": {"approved": True}},
        ]}
        p = tmp_path / "alt.yaml"
        p.write_text(yaml.dump(data))
        cases = load_fixtures(p)
        assert len(cases) == 1

    def test_load_fixtures_auto_names(self, tmp_path: Path) -> None:
        """Cases without names get auto-generated names."""
        fixtures = [
            {"input": {"user_role": "admin"}, "expect": {"approved": True}},
        ]
        path = _write_yaml_fixtures(tmp_path, fixtures)
        cases = load_fixtures(path)
        assert cases[0].name == "case_0"

    def test_load_fixtures_missing_file(self) -> None:
        with pytest.raises(FileNotFoundError):
            load_fixtures(Path("/nonexistent/fixtures.yaml"))

    def test_load_fixtures_empty_file(self, tmp_path: Path) -> None:
        p = tmp_path / "empty.yaml"
        p.write_text("")
        with pytest.raises(ValueError, match="Empty fixture"):
            load_fixtures(p)

    def test_load_fixtures_no_cases(self, tmp_path: Path) -> None:
        import yaml

        p = tmp_path / "no_cases.yaml"
        p.write_text(yaml.dump({"other_key": "value"}))
        with pytest.raises(ValueError, match="No fixtures found"):
            load_fixtures(p)

    def test_load_fixtures_unsupported_format(self, tmp_path: Path) -> None:
        p = tmp_path / "policy.toml"
        p.write_text("key = 'value'")
        with pytest.raises(ValueError, match="Unsupported"):
            load_fixtures(p)


# ---------------------------------------------------------------------------
# run_policy_tests — end-to-end
# ---------------------------------------------------------------------------


class TestRunPolicyTests:
    @pytest.mark.asyncio
    async def test_all_pass(self, tmp_path: Path) -> None:
        policy_path = _write_yaml_policy(tmp_path)
        fixtures = [
            {"name": "admin-ok", "input": {"user_role": "admin", "agent_type": "test"}, "expect": {"approved": True}},
        ]
        fixture_path = _write_yaml_fixtures(tmp_path, fixtures)

        results = await run_policy_tests(policy_path, fixture_path)
        assert len(results) == 1
        assert results[0].passed is True
        assert results[0].actual_approved is True

    @pytest.mark.asyncio
    async def test_deny_detected(self, tmp_path: Path) -> None:
        policy_path = _write_yaml_policy(tmp_path)
        fixtures = [
            {
                "name": "guest-denied",
                "input": {"user_role": "guest", "agent_type": "test", "description": "safe"},
                "expect": {"approved": False, "violated_rules": ["deny-guest"]},
            },
        ]
        fixture_path = _write_yaml_fixtures(tmp_path, fixtures)

        results = await run_policy_tests(policy_path, fixture_path)
        assert len(results) == 1
        assert results[0].passed is True
        assert results[0].actual_approved is False
        assert "deny-guest" in results[0].actual_violated

    @pytest.mark.asyncio
    async def test_mismatch_detected(self, tmp_path: Path) -> None:
        """When expectation doesn't match reality → case fails."""
        policy_path = _write_yaml_policy(tmp_path)
        fixtures = [
            {
                "name": "wrong-expectation",
                "input": {"user_role": "admin", "agent_type": "test"},
                "expect": {"approved": False},  # Admin is actually allowed
            },
        ]
        fixture_path = _write_yaml_fixtures(tmp_path, fixtures)

        results = await run_policy_tests(policy_path, fixture_path)
        assert results[0].passed is False

    @pytest.mark.asyncio
    async def test_mixed_results(self, tmp_path: Path) -> None:
        policy_path = _write_yaml_policy(tmp_path)
        fixtures = [
            {"name": "pass", "input": {"user_role": "admin", "agent_type": "test"}, "expect": {"approved": True}},
            {"name": "fail", "input": {"user_role": "admin", "agent_type": "test"}, "expect": {"approved": False}},
        ]
        fixture_path = _write_yaml_fixtures(tmp_path, fixtures)

        results = await run_policy_tests(policy_path, fixture_path)
        assert results[0].passed is True
        assert results[1].passed is False

    @pytest.mark.asyncio
    async def test_violated_rule_mismatch(self, tmp_path: Path) -> None:
        """Expects specific violated rule that doesn't match."""
        policy_path = _write_yaml_policy(tmp_path)
        fixtures = [
            {
                "name": "wrong-violation",
                "input": {"user_role": "guest", "agent_type": "test", "description": "safe"},
                "expect": {"approved": False, "violated_rules": ["nonexistent-rule"]},
            },
        ]
        fixture_path = _write_yaml_fixtures(tmp_path, fixtures)

        results = await run_policy_tests(policy_path, fixture_path)
        assert results[0].passed is False


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


class TestFormatResults:
    def _make_results(self) -> list[FixtureResult]:
        return [
            FixtureResult(
                case=FixtureCase(name="pass-case", input={}, expect_approved=True),
                passed=True,
                actual_approved=True,
            ),
            FixtureResult(
                case=FixtureCase(name="fail-case", input={}, expect_approved=False),
                passed=False,
                actual_approved=True,
            ),
        ]

    def test_text_format(self) -> None:
        results = self._make_results()
        text = format_results_text(results, Path("test.yaml"))
        assert "PASS  pass-case" in text
        assert "FAIL  fail-case" in text
        assert "1 passed, 1 failed" in text

    def test_json_format(self) -> None:
        results = self._make_results()
        raw = format_results_json(results, Path("test.yaml"))
        data = json.loads(raw)
        assert data["total"] == 2
        assert data["passed"] == 1
        assert data["failed"] == 1
        assert data["cases"][0]["name"] == "pass-case"
        assert data["cases"][0]["passed"] is True

    def test_json_format_includes_error(self) -> None:
        results = [
            FixtureResult(
                case=FixtureCase(name="error-case", input={}, expect_approved=True),
                passed=False,
                actual_approved=False,
                error="Something broke",
            ),
        ]
        raw = format_results_json(results, Path("test.yaml"))
        data = json.loads(raw)
        assert data["cases"][0]["error"] == "Something broke"

    def test_text_format_with_error(self) -> None:
        results = [
            FixtureResult(
                case=FixtureCase(name="err", input={}, expect_approved=True),
                passed=False,
                actual_approved=False,
                error="Boom",
            ),
        ]
        text = format_results_text(results, Path("p.yaml"))
        assert "Error: Boom" in text


# ---------------------------------------------------------------------------
# _FakeTask
# ---------------------------------------------------------------------------


class TestFakeTask:
    def test_basic_attrs(self) -> None:
        t = _FakeTask({"name": "t1", "description": "d1", "agent_type": "safe"})
        assert t.name == "t1"
        assert t.description == "d1"
        assert t.agent_type == "safe"

    def test_extra_attrs_in_metadata(self) -> None:
        t = _FakeTask({"name": "t", "user_role": "admin", "tool_category": "shell"})
        assert t.metadata["user_role"] == "admin"
        assert t.metadata["tool_category"] == "shell"


# ---------------------------------------------------------------------------
# CLI integration (Click runner)
# ---------------------------------------------------------------------------


class TestCLIIntegration:
    def test_policy_test_exit_0_on_pass(self, tmp_path: Path) -> None:
        """Exit code 0 when all tests pass."""
        from click.testing import CliRunner

        # Need to import to register the command
        from cli.policy_test import policy  # noqa: F401
        from cli.main import cli

        policy_path = _write_yaml_policy(tmp_path)
        fixtures = [
            {"name": "ok", "input": {"user_role": "admin", "agent_type": "test"}, "expect": {"approved": True}},
        ]
        fixture_path = _write_yaml_fixtures(tmp_path, fixtures)

        runner = CliRunner()
        result = runner.invoke(cli, [
            "policy", "test",
            "--file", str(policy_path),
            "--fixtures", str(fixture_path),
        ])
        assert result.exit_code == 0
        assert "PASS" in result.output

    def test_policy_test_exit_1_on_fail(self, tmp_path: Path) -> None:
        """Exit code 1 when any test fails."""
        from click.testing import CliRunner

        from cli.policy_test import policy  # noqa: F401
        from cli.main import cli

        policy_path = _write_yaml_policy(tmp_path)
        fixtures = [
            {"name": "wrong", "input": {"user_role": "admin", "agent_type": "test"}, "expect": {"approved": False}},
        ]
        fixture_path = _write_yaml_fixtures(tmp_path, fixtures)

        runner = CliRunner()
        result = runner.invoke(cli, [
            "policy", "test",
            "--file", str(policy_path),
            "--fixtures", str(fixture_path),
        ])
        assert result.exit_code == 1
        assert "FAIL" in result.output

    def test_policy_test_json_format(self, tmp_path: Path) -> None:
        from click.testing import CliRunner

        from cli.policy_test import policy  # noqa: F401
        from cli.main import cli

        policy_path = _write_yaml_policy(tmp_path)
        fixtures = [
            {"name": "ok", "input": {"user_role": "admin", "agent_type": "test"}, "expect": {"approved": True}},
        ]
        fixture_path = _write_yaml_fixtures(tmp_path, fixtures)

        runner = CliRunner()
        result = runner.invoke(cli, [
            "policy", "test",
            "--file", str(policy_path),
            "--fixtures", str(fixture_path),
            "--format", "json",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["passed"] == 1

    def test_policy_validate_command(self, tmp_path: Path) -> None:
        from click.testing import CliRunner

        from cli.policy_test import policy  # noqa: F401
        from cli.main import cli

        policy_path = _write_yaml_policy(tmp_path)

        runner = CliRunner()
        result = runner.invoke(cli, [
            "policy", "validate",
            "--file", str(policy_path),
        ])
        assert result.exit_code == 0
        assert "Valid:" in result.output
        assert "test_policy" in result.output
