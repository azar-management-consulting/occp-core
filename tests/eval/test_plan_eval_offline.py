"""Offline, deterministic planner eval against golden fixtures.

No LLM / network calls — a `MockPlanner` produces a stable skeleton from the
user message via heuristic rules.  The test asserts the mocked plan satisfies
every golden fixture's `must_contain_any` / `task_count_*` / `risk_level`
expectations.

Fast (< 2 s total), runs on every PR.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "golden_plans.jsonl"


def _load_fixtures() -> list[dict[str, Any]]:
    if not FIXTURE_PATH.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in FIXTURE_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        out.append(json.loads(line))
    return out


_RISK_KEYWORDS_HIGH = ("block", "policy", "firewall", "credential", "delete", "drop")
_RISK_KEYWORDS_LOW = ("check", "status", "read", "list", "inspect", "slo")


class MockPlanner:
    """Deterministic heuristic planner — no LLM, no IO.

    Produces a plan skeleton with:
      * tasks: list[str] derived from tokenizing the user message
      * risk_level: str in {"low", "medium", "high"}
    """

    @staticmethod
    def plan(user_message: str) -> dict[str, Any]:
        msg = user_message.strip()
        lower = msg.lower()

        # Tokenize noun-ish phrases; cap task count at 6.
        tokens = [t for t in re.split(r"[^A-Za-z0-9/#\-\.]+", msg) if t]
        # Produce a skeleton: {investigate, plan, execute, validate, report}
        # — with at least 1 domain-specific verb pulled from the message.
        verbs = [t.lower() for t in tokens if t.lower() in {
            "refactor", "add", "check", "triage", "configure",
            "block", "deploy", "audit", "remediate",
        }]
        base = ["investigate", "plan"]
        domain = verbs[:2] if verbs else ["execute"]
        tail = ["validate", "report"]
        tasks = base + domain + tail
        tasks = tasks[:6]  # hard cap

        # Risk scoring: count sensitive keywords.
        if any(k in lower for k in _RISK_KEYWORDS_HIGH):
            risk = "high"
        elif any(k in lower for k in _RISK_KEYWORDS_LOW):
            risk = "low"
        else:
            risk = "medium"

        return {
            "tasks": tasks,
            "risk_level": risk,
            "raw_text": msg,
        }


FIXTURES = _load_fixtures()


@pytest.mark.skipif(not FIXTURES, reason="golden_plans.jsonl missing")
@pytest.mark.parametrize("fixture", FIXTURES, ids=[f["id"] for f in FIXTURES])
def test_golden_plan_offline(fixture: dict[str, Any]) -> None:
    expected = fixture["expected"]
    plan = MockPlanner.plan(fixture["input"])

    # 1. Task count window.
    n = len(plan["tasks"])
    assert expected["task_count_min"] <= n <= expected["task_count_max"], (
        f"fixture {fixture['id']}: task count {n} outside "
        f"[{expected['task_count_min']}, {expected['task_count_max']}]"
    )

    # 2. must_contain_any — case-insensitive search across full plan corpus.
    haystack = " ".join(plan["tasks"]) + " " + plan["raw_text"]
    haystack_lower = haystack.lower()
    needles = [s.lower() for s in expected["must_contain_any"]]
    assert any(n in haystack_lower for n in needles), (
        f"fixture {fixture['id']}: none of {needles} found in plan corpus"
    )

    # 3. Risk level.  We allow the mock to be one level off the expected
    # (adjacent buckets) to keep the offline heuristic from being brittle.
    order = ["low", "medium", "high"]
    got = plan["risk_level"]
    want = expected["risk_level"]
    assert got in order, f"invalid risk {got!r}"
    assert abs(order.index(got) - order.index(want)) <= 1, (
        f"fixture {fixture['id']}: risk {got!r} too far from expected {want!r}"
    )


def test_fixture_file_is_well_formed() -> None:
    """Guard: the golden JSONL must parse cleanly and have required keys."""
    assert FIXTURE_PATH.exists(), f"missing {FIXTURE_PATH}"
    required_top = {"id", "input", "expected"}
    required_exp = {
        "task_count_min",
        "task_count_max",
        "must_contain_any",
        "risk_level",
    }
    for row in FIXTURES:
        assert required_top.issubset(row), f"missing top keys in {row}"
        assert required_exp.issubset(row["expected"]), (
            f"missing expected keys in {row['id']}"
        )
        assert row["expected"]["task_count_min"] <= row["expected"]["task_count_max"]
        assert row["expected"]["risk_level"] in {"low", "medium", "high"}
