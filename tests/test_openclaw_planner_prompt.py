"""Tests for the OpenClaw planner's strict JSON directive prompt.

Guards the invariant that ``OpenClawPlanner``'s system prompt produces
output the ``OpenClawExecutor`` JSON parser actually understands.

Covers:
  * The system prompt contains the exact keys the executor parser reads
    (``directives``, ``tool``, ``args``, ``risk``, plus the ``exec_type``
    alias).
  * The prompt version constant is strictly greater than the previous
    released version (lexicographic — date-prefixed scheme).
  * At least one positive one-shot example, when rendered in the wire
    format the prompt teaches the model to emit, roundtrips through
    :meth:`OpenClawExecutor._parse_execution_directives` and yields a
    normalized directive dict.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from adapters.openclaw_executor import (
    ALLOWED_DIRECTIVE_TOOLS,
    OpenClawExecutor,
)
from adapters.openclaw_planner import (
    OPENCLAW_PROMPT_VERSION,
    POSITIVE_EXAMPLE_1,
    POSITIVE_EXAMPLE_2,
    RESPONSE_SCHEMA,
    _render_tools_schema_block,
)


# Previous released prompt version — empty string because no explicit
# version constant existed before this commit. Any non-empty date-prefixed
# string sorts strictly greater.
_PREVIOUS_PROMPT_VERSION: str = ""


# ---------------------------------------------------------------------------
# Prompt contract: key presence
# ---------------------------------------------------------------------------

class TestPromptContainsExecutorKeys:
    """The system prompt must name every key the executor parser reads."""

    @pytest.fixture(scope="class")
    def prompt(self) -> str:
        return _render_tools_schema_block()

    def test_contains_directives_top_level_key(self, prompt: str) -> None:
        assert '"directives"' in prompt, (
            "System prompt must literally mention the top-level "
            "'directives' key — the executor's _FENCED_JSON_RE requires "
            "that string to match the fenced block."
        )

    def test_contains_tool_key(self, prompt: str) -> None:
        assert '"tool"' in prompt

    def test_contains_args_key(self, prompt: str) -> None:
        assert '"args"' in prompt

    def test_contains_risk_key(self, prompt: str) -> None:
        assert '"risk"' in prompt

    def test_mentions_exec_type_alias(self, prompt: str) -> None:
        # exec_type is the alt directive key the executor also accepts;
        # the prompt documents it so models that prefer that naming still
        # produce matchable output.
        assert "exec_type" in prompt

    def test_fenced_json_enforced(self, prompt: str) -> None:
        # Must instruct the model to wrap the payload in ```json``` fences.
        assert "```json" in prompt

    def test_includes_prompt_version(self, prompt: str) -> None:
        assert OPENCLAW_PROMPT_VERSION in prompt

    def test_includes_all_whitelisted_tools(self, prompt: str) -> None:
        # Every tool the executor allows must appear in the tools schema
        # block — otherwise the planner would teach the model to emit
        # tools that the executor drops.
        for tool in ALLOWED_DIRECTIVE_TOOLS:
            assert tool in prompt, f"tool {tool!r} missing from prompt"

    def test_has_positive_and_negative_examples(self, prompt: str) -> None:
        assert "POSITIVE EXAMPLE 1" in prompt
        assert "POSITIVE EXAMPLE 2" in prompt
        assert "NEGATIVE EXAMPLE" in prompt


# ---------------------------------------------------------------------------
# Prompt version monotonicity
# ---------------------------------------------------------------------------

class TestPromptVersion:
    def test_is_string(self) -> None:
        assert isinstance(OPENCLAW_PROMPT_VERSION, str)
        assert OPENCLAW_PROMPT_VERSION, "version must be non-empty"

    def test_is_greater_than_previous(self) -> None:
        assert OPENCLAW_PROMPT_VERSION > _PREVIOUS_PROMPT_VERSION, (
            f"OPENCLAW_PROMPT_VERSION={OPENCLAW_PROMPT_VERSION!r} must "
            f"be lexicographically greater than previous "
            f"{_PREVIOUS_PROMPT_VERSION!r}"
        )

    def test_date_prefixed_schema(self) -> None:
        # Enforce YYYY-MM-DD-… so lexicographic compare = chronological.
        assert len(OPENCLAW_PROMPT_VERSION) >= 10
        assert OPENCLAW_PROMPT_VERSION[4] == "-"
        assert OPENCLAW_PROMPT_VERSION[7] == "-"
        year = OPENCLAW_PROMPT_VERSION[:4]
        month = OPENCLAW_PROMPT_VERSION[5:7]
        day = OPENCLAW_PROMPT_VERSION[8:10]
        assert year.isdigit() and month.isdigit() and day.isdigit()


# ---------------------------------------------------------------------------
# Response schema contract
# ---------------------------------------------------------------------------

class TestResponseSchema:
    def test_required_top_level_fields(self) -> None:
        assert "required" in RESPONSE_SCHEMA
        required = set(RESPONSE_SCHEMA["required"])
        assert {"strategy", "description", "steps"}.issubset(required)

    def test_directive_item_schema_matches_executor(self) -> None:
        directive_schema = (
            RESPONSE_SCHEMA["properties"]["directives"]["items"]
        )
        props = directive_schema["properties"]
        assert "tool" in props
        assert "args" in props
        assert "risk" in props
        assert set(props["risk"]["enum"]) == {"low", "medium", "high"}


# ---------------------------------------------------------------------------
# Roundtrip: prompt example → executor parser → normalized directives
# ---------------------------------------------------------------------------

def _render_as_wire(example: dict[str, Any]) -> str:
    """Render a one-shot example the way the prompt teaches the model to
    emit it: a single fenced ```json``` block with the JSON object.
    """
    return "```json\n" + json.dumps(example, indent=2) + "\n```"


class TestRoundtripExamplesParse:
    """Positive examples from the prompt MUST parse via the executor's
    JSON parser — this is the load-bearing invariant."""

    def test_example1_directives_extracted(self) -> None:
        wire = _render_as_wire(POSITIVE_EXAMPLE_1)
        directives = OpenClawExecutor._parse_execution_directives(wire)
        assert directives, (
            "Positive example 1 MUST produce at least one directive; "
            "got empty — executor's _FENCED_JSON_RE no longer matches the "
            "example format. Fix the prompt or the regex."
        )
        assert directives[0]["tool"] == "wordpress.get_site_info"
        assert directives[0]["args"] == {"site": "magyarorszag.ai"}
        assert directives[0]["risk"] == "low"

    def test_example2_empty_directives_are_accepted(self) -> None:
        # Analytical task: empty directives is legal. The executor parser
        # returns [] (not an error).
        wire = _render_as_wire(POSITIVE_EXAMPLE_2)
        directives = OpenClawExecutor._parse_execution_directives(wire)
        assert directives == []

    def test_example1_tool_is_whitelisted(self) -> None:
        tool = POSITIVE_EXAMPLE_1["directives"][0]["tool"]
        assert tool in ALLOWED_DIRECTIVE_TOOLS, (
            f"Example 1 uses tool {tool!r} which is NOT in "
            f"ALLOWED_DIRECTIVE_TOOLS — the executor would drop it."
        )
