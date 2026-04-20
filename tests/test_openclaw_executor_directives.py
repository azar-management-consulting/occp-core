"""Tests for OpenClaw executor's execution_directives parsing + routing.

Covers the architectural upgrade from "text-only scaffold" to MCP
``tools/call``-style structured directive emission (OCCP #3 blocker).

Tested behaviour (see adapters/openclaw_executor.py):
  * ``_extract_output`` now returns a dict with ``output`` + ``execution_directives``.
  * JSON directive blocks inside ```` ```json ... ``` ```` fences are extracted.
  * Invalid / oversized / unknown-tool directives are skipped (no crash).
  * ``execute()`` propagates directives in its return dict for Brain dispatch.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from adapters.openclaw_executor import (
    ALLOWED_DIRECTIVE_TOOLS,
    MAX_DIRECTIVE_ARGS_BYTES,
    MAX_DIRECTIVES_PER_RESPONSE,
    OpenClawConfig,
    OpenClawExecutor,
)
from orchestrator.models import RiskLevel, Task

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_task(**overrides: Any) -> Task:
    defaults: dict[str, Any] = {
        "name": "test-task",
        "description": "Directive parsing test",
        "agent_type": "openclaw-general",
        "risk_level": RiskLevel.LOW,
    }
    defaults.update(overrides)
    return Task(**defaults)


def _chat_final(text: str) -> dict[str, Any]:
    """Build a fake chat.final payload like OpenClaw Gateway emits."""
    return {
        "state": "final",
        "runId": "run-abc123",
        "sessionKey": "general/test-task",
        "message": {"text": text},
    }


def _make_executor() -> OpenClawExecutor:
    cfg = OpenClawConfig(gateway_url="ws://127.0.0.1:0", gateway_token="")
    return OpenClawExecutor(config=cfg)


# ---------------------------------------------------------------------------
# Unit tests for _extract_output
# ---------------------------------------------------------------------------

class TestExtractOutput:

    def test_extract_output_no_json_block(self) -> None:
        """Plain prose → directives=[], output preserved."""
        result = _chat_final("Hello world, just prose, no directives here.")
        extracted = OpenClawExecutor._extract_output(result)
        assert extracted["output"] == "Hello world, just prose, no directives here."
        assert extracted["execution_directives"] == []

    def test_extract_output_valid_json_block(self) -> None:
        """Fenced json block with directives → parsed into list."""
        text = (
            "Analysis complete.\n\n"
            "```json\n"
            '{"directives": [\n'
            '  {"tool": "wordpress.get_site_info", '
            '"args": {"site": "magyarorszag.ai"}, "risk": "low"},\n'
            '  {"tool": "filesystem.read", '
            '"args": {"path": "/tmp/occp-workspace/notes.md"}, "risk": "low"}\n'
            "]}\n"
            "```\n"
        )
        extracted = OpenClawExecutor._extract_output(_chat_final(text))
        directives = extracted["execution_directives"]
        assert len(directives) == 2
        assert directives[0]["tool"] == "wordpress.get_site_info"
        assert directives[0]["args"] == {"site": "magyarorszag.ai"}
        assert directives[0]["risk"] == "low"
        assert directives[1]["tool"] == "filesystem.read"
        assert "Analysis complete" in extracted["output"]

    def test_extract_output_invalid_json(self, caplog: pytest.LogCaptureFixture) -> None:
        """Corrupt JSON → warn log + empty directives, no crash."""
        text = (
            "Here's a broken block:\n"
            "```json\n"
            '{"directives": [ {"tool": "brain.status", "args": {  ,,, INVALID }\n'
            "```\n"
        )
        with caplog.at_level("WARNING"):
            extracted = OpenClawExecutor._extract_output(_chat_final(text))
        assert extracted["execution_directives"] == []
        # At least one warning about invalid JSON should have fired
        assert any("invalid JSON" in r.message for r in caplog.records)

    def test_extract_output_max_directives(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """>10 directives → truncated to cap + warning."""
        many = [
            {"tool": "brain.status", "args": {}, "risk": "low"}
            for _ in range(MAX_DIRECTIVES_PER_RESPONSE + 5)
        ]
        text = "```json\n" + json.dumps({"directives": many}) + "\n```"
        with caplog.at_level("WARNING"):
            extracted = OpenClawExecutor._extract_output(_chat_final(text))
        assert len(extracted["execution_directives"]) == MAX_DIRECTIVES_PER_RESPONSE
        assert any("exceeds max" in r.message for r in caplog.records)

    def test_extract_output_oversized_args(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Directive with args >50KB → skipped with warning."""
        big_blob = "x" * (MAX_DIRECTIVE_ARGS_BYTES + 128)
        oversized = {
            "tool": "filesystem.write",
            "args": {"path": "/tmp/occp-workspace/a.txt", "content": big_blob},
            "risk": "medium",
        }
        small_ok = {
            "tool": "brain.status",
            "args": {},
            "risk": "low",
        }
        text = (
            "```json\n"
            + json.dumps({"directives": [oversized, small_ok]})
            + "\n```"
        )
        with caplog.at_level("WARNING"):
            extracted = OpenClawExecutor._extract_output(_chat_final(text))
        tools = [d["tool"] for d in extracted["execution_directives"]]
        assert "filesystem.write" not in tools
        assert "brain.status" in tools
        assert any("exceeds cap" in r.message for r in caplog.records)

    def test_extract_output_unknown_tool(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Unknown tool name → skipped + audit log."""
        text = (
            "```json\n"
            '{"directives": [\n'
            '  {"tool": "rm_rf_everything", "args": {"path": "/"}, "risk": "high"},\n'
            '  {"tool": "brain.status", "args": {}, "risk": "low"}\n'
            "]}\n"
            "```"
        )
        with caplog.at_level("WARNING"):
            extracted = OpenClawExecutor._extract_output(_chat_final(text))
        tools = [d["tool"] for d in extracted["execution_directives"]]
        assert tools == ["brain.status"]
        assert any(
            "NOT in whitelist" in r.message and "rm_rf_everything" in r.message
            for r in caplog.records
        )

    def test_extract_output_whitelisted_tools_all_pass(self) -> None:
        """Smoke: every one of the 14 whitelisted tools is accepted."""
        directives = [
            {"tool": t, "args": {}, "risk": "low"}
            for t in sorted(ALLOWED_DIRECTIVE_TOOLS)
        ]
        # Batch into multiple blocks so we stay within MAX_DIRECTIVES_PER_RESPONSE
        # per extraction call (14 > 10 cap). Test each batch of ≤10.
        batch_a = directives[:10]
        batch_b = directives[10:]
        text_a = "```json\n" + json.dumps({"directives": batch_a}) + "\n```"
        text_b = "```json\n" + json.dumps({"directives": batch_b}) + "\n```"
        ea = OpenClawExecutor._extract_output(_chat_final(text_a))
        eb = OpenClawExecutor._extract_output(_chat_final(text_b))
        got_tools = {d["tool"] for d in ea["execution_directives"]} | {
            d["tool"] for d in eb["execution_directives"]
        }
        assert got_tools == set(ALLOWED_DIRECTIVE_TOOLS)
        assert len(ALLOWED_DIRECTIVE_TOOLS) == 14

    def test_extract_output_bare_json_no_fence(self) -> None:
        """Bare JSON (no code fence) with directives key is also accepted."""
        text = (
            "Plan:\n"
            '{"directives": [{"tool": "brain.health", "args": {}, "risk": "low"}]}'
        )
        extracted = OpenClawExecutor._extract_output(_chat_final(text))
        assert len(extracted["execution_directives"]) == 1
        assert extracted["execution_directives"][0]["tool"] == "brain.health"


# ---------------------------------------------------------------------------
# End-to-end: execute() routes directives through its return dict
# ---------------------------------------------------------------------------

class TestExecuteReturnsDirectives:

    @pytest.mark.asyncio
    async def test_execute_returns_directives_in_dict(self) -> None:
        """Full execute() path: mock agent response → directives surfaced."""
        executor = _make_executor()

        # Fake gateway response containing a fenced directive block
        agent_text = (
            "I will check brain status.\n"
            "```json\n"
            '{"directives": [\n'
            '  {"tool": "brain.status", "args": {}, "risk": "low"}\n'
            "]}\n"
            "```"
        )
        fake_result = _chat_final(agent_text)

        # Stub connection so execute() runs without a real WebSocket.
        # `is_connected` is a read-only property driven by these flags.
        executor._conn._connected = True  # type: ignore[attr-defined]
        executor._conn._authenticated = True  # type: ignore[attr-defined]
        with patch.object(
            executor, "_ensure_connected", new=AsyncMock(return_value=None)
        ), patch.object(
            executor._conn,
            "send_chat",
            new=AsyncMock(return_value=fake_result),
        ):
            task = _make_task()
            result = await executor.execute(task)

        assert result["exit_code"] == 0
        assert "execution_directives" in result
        assert len(result["execution_directives"]) == 1
        assert result["execution_directives"][0] == {
            "tool": "brain.status",
            "args": {},
            "risk": "low",
        }
        # Narrative text is still preserved
        assert "brain status" in result["output"]

    @pytest.mark.asyncio
    async def test_execute_no_directives_empty_list(self) -> None:
        """Plain-prose agent response → execute() returns [] directives."""
        executor = _make_executor()
        fake_result = _chat_final("All good. Nothing to execute.")

        executor._conn._connected = True  # type: ignore[attr-defined]
        executor._conn._authenticated = True  # type: ignore[attr-defined]
        with patch.object(
            executor, "_ensure_connected", new=AsyncMock(return_value=None)
        ), patch.object(
            executor._conn,
            "send_chat",
            new=AsyncMock(return_value=fake_result),
        ):
            task = _make_task()
            result = await executor.execute(task)

        assert result["execution_directives"] == []
        assert result["output"].startswith("All good")
