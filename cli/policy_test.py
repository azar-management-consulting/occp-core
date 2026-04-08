"""Policy test CLI — REQ-POL-03: Testable Policies.

``occp policy test`` validates policies against fixture files containing
input → expected-decision pairs.  Exit code 0 means all assertions passed,
exit code 1 means at least one failed — ready for CI integration.

Usage::

    occp policy test --file=policy.yaml --fixtures=tests.yaml
    occp policy test --file=policy.yaml --fixtures=tests.yaml --format=json
"""

from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import click

from cli.main import cli


# ---------------------------------------------------------------------------
# Fixture models
# ---------------------------------------------------------------------------


@dataclass
class FixtureCase:
    """Single test case: input attributes → expected decision."""

    name: str
    input: dict[str, Any]
    expect_approved: bool
    expect_violated: list[str] = field(default_factory=list)
    description: str = ""


@dataclass
class FixtureResult:
    """Result of running a single fixture case."""

    case: FixtureCase
    passed: bool
    actual_approved: bool
    actual_violated: list[str] = field(default_factory=list)
    error: str = ""


# ---------------------------------------------------------------------------
# Fixture loading
# ---------------------------------------------------------------------------


def load_fixtures(path: Path) -> list[FixtureCase]:
    """Load test fixtures from a YAML or JSON file.

    Expected format::

        fixtures:
          - name: admin-allowed
            input:
              user_role: admin
              agent_type: code_gen
            expect:
              approved: true
          - name: guest-denied
            input:
              user_role: guest
            expect:
              approved: false
              violated_rules:
                - deny-guest
    """
    if not path.exists():
        raise FileNotFoundError(f"Fixture file not found: {path}")

    suffix = path.suffix.lower()
    text = path.read_text(encoding="utf-8")

    if suffix in (".yaml", ".yml"):
        import yaml

        data = yaml.safe_load(text)
    elif suffix == ".json":
        data = json.loads(text)
    else:
        raise ValueError(f"Unsupported fixture format: {suffix}")

    if not data:
        raise ValueError(f"Empty fixture file: {path}")

    raw_fixtures = data.get("fixtures", data.get("tests", []))
    if not raw_fixtures:
        raise ValueError(f"No fixtures found in {path} (expected 'fixtures' or 'tests' key)")

    cases: list[FixtureCase] = []
    for i, item in enumerate(raw_fixtures):
        name = item.get("name", f"case_{i}")
        inp = item.get("input", {})
        expect = item.get("expect", {})
        cases.append(FixtureCase(
            name=name,
            input=inp,
            expect_approved=expect.get("approved", True),
            expect_violated=expect.get("violated_rules", []),
            description=item.get("description", ""),
        ))

    return cases


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------


class _FakeTask:
    """Minimal task object for policy engine evaluation."""

    def __init__(self, attrs: dict[str, Any]) -> None:
        self.id = attrs.get("id", "fixture_test")
        self.name = attrs.get("name", "fixture_test")
        self.description = attrs.get("description", "fixture test input")
        self.agent_type = attrs.get("agent_type", "test")
        self.plan = None
        self.metadata: dict[str, Any] = {
            k: v for k, v in attrs.items()
            if k not in ("id", "name", "description", "agent_type", "plan")
        }


async def _run_case(
    engine: Any,
    case: FixtureCase,
) -> FixtureResult:
    """Evaluate a single fixture case against the policy engine."""
    try:
        task = _FakeTask(case.input)
        result = await engine.evaluate(task)

        # Check approval match
        approval_match = result.approved == case.expect_approved

        # Check violated rules (if specified)
        violation_match = True
        if case.expect_violated:
            for expected_rule in case.expect_violated:
                if expected_rule not in result.violated_rules:
                    violation_match = False
                    break

        passed = approval_match and violation_match

        return FixtureResult(
            case=case,
            passed=passed,
            actual_approved=result.approved,
            actual_violated=result.violated_rules,
        )

    except Exception as exc:
        return FixtureResult(
            case=case,
            passed=False,
            actual_approved=False,
            error=str(exc),
        )


async def run_policy_tests(
    policy_path: Path,
    fixture_path: Path,
) -> list[FixtureResult]:
    """Load policy, load fixtures, run all test cases."""
    from policy_engine.engine import PolicyEngine

    engine = PolicyEngine()
    engine.load_policy_file(policy_path)

    cases = load_fixtures(fixture_path)
    results: list[FixtureResult] = []

    for case in cases:
        result = await _run_case(engine, case)
        results.append(result)

    return results


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def format_results_text(results: list[FixtureResult], policy_path: Path) -> str:
    """Human-readable test output."""
    lines: list[str] = []
    lines.append(f"Policy: {policy_path}")
    lines.append(f"Cases:  {len(results)}")
    lines.append("")

    passed = 0
    failed = 0

    for r in results:
        if r.passed:
            lines.append(f"  PASS  {r.case.name}")
            passed += 1
        else:
            lines.append(f"  FAIL  {r.case.name}")
            if r.error:
                lines.append(f"        Error: {r.error}")
            else:
                lines.append(
                    f"        Expected approved={r.case.expect_approved}, "
                    f"got approved={r.actual_approved}"
                )
                if r.case.expect_violated:
                    lines.append(
                        f"        Expected violated={r.case.expect_violated}, "
                        f"got violated={r.actual_violated}"
                    )
            failed += 1

    lines.append("")
    lines.append(f"Result: {passed} passed, {failed} failed")
    return "\n".join(lines)


def format_results_json(results: list[FixtureResult], policy_path: Path) -> str:
    """JSON output for CI integration."""
    output = {
        "policy": str(policy_path),
        "total": len(results),
        "passed": sum(1 for r in results if r.passed),
        "failed": sum(1 for r in results if not r.passed),
        "cases": [
            {
                "name": r.case.name,
                "passed": r.passed,
                "expected_approved": r.case.expect_approved,
                "actual_approved": r.actual_approved,
                "expected_violated": r.case.expect_violated,
                "actual_violated": r.actual_violated,
                **({"error": r.error} if r.error else {}),
            }
            for r in results
        ],
    }
    return json.dumps(output, indent=2)


# ---------------------------------------------------------------------------
# Click commands
# ---------------------------------------------------------------------------


@cli.group()
def policy() -> None:
    """Policy management commands."""


@policy.command("test")
@click.option(
    "--file", "policy_file",
    required=True,
    type=click.Path(exists=True),
    help="Path to policy file (YAML or JSON).",
)
@click.option(
    "--fixtures", "fixture_file",
    required=True,
    type=click.Path(exists=True),
    help="Path to test fixtures file (YAML or JSON).",
)
@click.option(
    "--format", "fmt",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
def policy_test(policy_file: str, fixture_file: str, fmt: str) -> None:
    """Test a policy against fixture cases (REQ-POL-03).

    Evaluates each fixture input against the loaded policy and compares
    the actual decision with the expected decision.

    Exit code 0 = all passed, exit code 1 = at least one failed.
    """
    p_path = Path(policy_file)
    f_path = Path(fixture_file)

    try:
        results = asyncio.run(run_policy_tests(p_path, f_path))
    except Exception as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(2)

    if fmt == "json":
        click.echo(format_results_json(results, p_path))
    else:
        click.echo(format_results_text(results, p_path))

    # Exit code for CI
    if any(not r.passed for r in results):
        sys.exit(1)


@policy.command("validate")
@click.option(
    "--file", "policy_file",
    required=True,
    type=click.Path(exists=True),
    help="Path to policy file to validate.",
)
def policy_validate(policy_file: str) -> None:
    """Validate a policy file syntax and structure."""
    from policy_engine.engine import PolicyEngine

    p_path = Path(policy_file)
    try:
        engine = PolicyEngine()
        policy = engine.load_policy_file(p_path)
        click.echo(f"Valid: {policy.name} v{policy.version}")
        click.echo(f"  Hash: {engine.policy_hash[:16]}...")
        if engine.abac_evaluator:
            click.echo(f"  ABAC rules: {engine.abac_evaluator.rule_count}")
    except Exception as exc:
        click.echo(f"Invalid: {exc}", err=True)
        sys.exit(1)
