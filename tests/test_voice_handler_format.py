"""Tests for VoiceCommandHandler._format_result() — OpenClaw gateway response handling.

Verifies that:
1. Direct executor output text is extracted correctly
2. OpenClaw gateway metadata (runId/sessionKey/state) is NOT shown as raw JSON
3. Nested text fields (messages, result, response, gateway_response) are extracted
4. Session history fetch is attempted for gateway-only responses
5. Fallback to user-friendly message when no text is extractable
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Minimal stubs
# ---------------------------------------------------------------------------

@dataclass
class FakePipelineResult:
    success: bool = True
    evidence: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    output: Any = None
    result: Any = None


def _make_handler():
    """Create a VoiceCommandHandler with minimal stubs."""
    from adapters.voice_handler import VoiceCommandHandler

    handler = VoiceCommandHandler(
        whisper=MagicMock(),
        intent_router=MagicMock(),
        pipeline=MagicMock(),
        task_store=MagicMock(),
        audit_store=MagicMock(),
    )
    return handler


# ---------------------------------------------------------------------------
# _is_openclaw_gateway_response
# ---------------------------------------------------------------------------

class TestIsOpenClawGatewayResponse:
    def test_detects_gateway_response(self):
        from adapters.voice_handler import VoiceCommandHandler
        data = {
            "runId": "637e670f-82d1-46ff-adc8-814fcd1fd8be",
            "sessionKey": "agent:main:general/e52b3f4f0a76",
            "seq": 2,
            "state": "final",
        }
        assert VoiceCommandHandler._is_openclaw_gateway_response(data) is True

    def test_rejects_normal_execution(self):
        from adapters.voice_handler import VoiceCommandHandler
        data = {
            "executor": "sandbox/mock",
            "task_id": "abc123",
            "output": "Hello from Brian",
            "exit_code": 0,
        }
        assert VoiceCommandHandler._is_openclaw_gateway_response(data) is False

    def test_rejects_partial_gateway(self):
        from adapters.voice_handler import VoiceCommandHandler
        # Missing sessionKey
        data = {"runId": "abc", "state": "final"}
        assert VoiceCommandHandler._is_openclaw_gateway_response(data) is False


# ---------------------------------------------------------------------------
# _extract_text_from_execution
# ---------------------------------------------------------------------------

class TestExtractTextFromExecution:
    def test_direct_output_string(self):
        from adapters.voice_handler import VoiceCommandHandler
        execution = {"output": "Ez a valasz", "exit_code": 0}
        assert VoiceCommandHandler._extract_text_from_execution(execution) == "Ez a valasz"

    def test_output_dict_with_text(self):
        from adapters.voice_handler import VoiceCommandHandler
        execution = {"output": {"text": "Szoveges valasz", "meta": "ignored"}}
        assert VoiceCommandHandler._extract_text_from_execution(execution) == "Szoveges valasz"

    def test_output_dict_with_content(self):
        from adapters.voice_handler import VoiceCommandHandler
        execution = {"output": {"content": "Content valasz"}}
        assert VoiceCommandHandler._extract_text_from_execution(execution) == "Content valasz"

    def test_gateway_response_text(self):
        from adapters.voice_handler import VoiceCommandHandler
        execution = {
            "output": "",
            "gateway_response": {"text": "GW text", "runId": "abc"},
        }
        assert VoiceCommandHandler._extract_text_from_execution(execution) == "GW text"

    def test_messages_array_last_assistant(self):
        from adapters.voice_handler import VoiceCommandHandler
        execution = {
            "output": "",
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Brian valaszol"},
            ],
        }
        assert VoiceCommandHandler._extract_text_from_execution(execution) == "Brian valaszol"

    def test_messages_array_agent_role(self):
        from adapters.voice_handler import VoiceCommandHandler
        execution = {
            "output": "",
            "messages": [
                {"role": "user", "content": "Kerdes"},
                {"role": "agent", "content": "Agent valasz"},
            ],
        }
        assert VoiceCommandHandler._extract_text_from_execution(execution) == "Agent valasz"

    def test_result_subdict(self):
        from adapters.voice_handler import VoiceCommandHandler
        execution = {"output": "", "result": {"text": "Result text"}}
        assert VoiceCommandHandler._extract_text_from_execution(execution) == "Result text"

    def test_response_subdict(self):
        from adapters.voice_handler import VoiceCommandHandler
        execution = {"output": "", "response": {"content": "Response content"}}
        assert VoiceCommandHandler._extract_text_from_execution(execution) == "Response content"

    def test_gateway_metadata_only_returns_empty(self):
        from adapters.voice_handler import VoiceCommandHandler
        execution = {
            "runId": "637e670f-82d1-46ff-adc8-814fcd1fd8be",
            "sessionKey": "agent:main:general/e52b3f4f0a76",
            "seq": 2,
            "state": "final",
        }
        assert VoiceCommandHandler._extract_text_from_execution(execution) == ""

    def test_empty_execution(self):
        from adapters.voice_handler import VoiceCommandHandler
        assert VoiceCommandHandler._extract_text_from_execution({}) == ""


# ---------------------------------------------------------------------------
# _format_result (async)
# ---------------------------------------------------------------------------

class TestFormatResult:
    """Tests for the async _format_result method."""

    @pytest.mark.asyncio
    async def test_normal_executor_output(self):
        handler = _make_handler()
        result = FakePipelineResult(
            evidence={
                "execution": {
                    "executor": "sandbox/mock",
                    "task_id": "abc",
                    "output": "Hello, Henry! Ez a valasz.",
                    "exit_code": 0,
                },
            }
        )
        text = await handler._format_result(result)
        assert "Hello" in text
        assert "Henry" in text
        # Should NOT contain raw JSON keys
        assert "runId" not in text
        assert "sessionKey" not in text

    @pytest.mark.asyncio
    async def test_openclaw_gateway_response_triggers_fetch(self):
        """When execution is gateway metadata, should attempt session history fetch."""
        handler = _make_handler()
        result = FakePipelineResult(
            evidence={
                "execution": {
                    "runId": "637e670f-82d1-46ff-adc8-814fcd1fd8be",
                    "sessionKey": "agent:main:general/e52b3f4f0a76",
                    "seq": 2,
                    "state": "final",
                },
            }
        )

        with patch.object(
            handler,
            "_fetch_openclaw_session_text",
            new_callable=AsyncMock,
            return_value="Brian azt valaszolta, hogy minden rendben.",
        ) as mock_fetch:
            text = await handler._format_result(result)

        mock_fetch.assert_called_once_with("agent:main:general/e52b3f4f0a76")
        assert "Brian azt valaszolta" in text
        assert "runId" not in text

    @pytest.mark.asyncio
    async def test_openclaw_gateway_fetch_fails_gracefully(self):
        """When session history fetch returns empty, show user-friendly fallback."""
        handler = _make_handler()
        result = FakePipelineResult(
            evidence={
                "execution": {
                    "runId": "abc",
                    "sessionKey": "agent:main:test/xyz",
                    "seq": 1,
                    "state": "final",
                },
            }
        )

        with patch.object(
            handler,
            "_fetch_openclaw_session_text",
            new_callable=AsyncMock,
            return_value="",
        ):
            text = await handler._format_result(result)

        # Should NOT show raw JSON
        assert "runId" not in text
        assert "sessionKey" not in text
        # Should show user-friendly message (Hungarian)
        assert "Feldolgoztam" in text or "Nincs" in text

    @pytest.mark.asyncio
    async def test_gateway_with_embedded_output(self):
        """Gateway response that also has an output field should use it directly."""
        handler = _make_handler()
        result = FakePipelineResult(
            evidence={
                "execution": {
                    "runId": "abc",
                    "sessionKey": "agent:main:test/xyz",
                    "seq": 1,
                    "state": "final",
                    "output": "Ez kozvetlenul benne van a gateway valaszban.",
                },
            }
        )
        text = await handler._format_result(result)
        assert "kozvetlenul" in text

    @pytest.mark.asyncio
    async def test_legacy_output_attribute_not_gateway(self):
        """Legacy fallback: result.output dict that is NOT gateway metadata."""
        handler = _make_handler()
        result = FakePipelineResult(
            evidence={},
            output={"summary": "Q4 revenue was strong"},
        )
        text = await handler._format_result(result)
        assert "Q4 revenue" in text

    @pytest.mark.asyncio
    async def test_legacy_output_gateway_triggers_fetch(self):
        """Legacy fallback: result.output is gateway metadata."""
        handler = _make_handler()
        result = FakePipelineResult(
            evidence={},
            output={
                "runId": "abc",
                "sessionKey": "agent:main:test/xyz",
                "seq": 1,
                "state": "final",
            },
        )

        with patch.object(
            handler,
            "_fetch_openclaw_session_text",
            new_callable=AsyncMock,
            return_value="Legacy fetch result",
        ):
            text = await handler._format_result(result)

        assert "Legacy fetch result" in text
        assert "runId" not in text

    @pytest.mark.asyncio
    async def test_no_output_at_all(self):
        handler = _make_handler()
        result = FakePipelineResult(evidence={})
        text = await handler._format_result(result)
        assert "Nincs" in text

    @pytest.mark.asyncio
    async def test_truncation_at_3500(self):
        handler = _make_handler()
        long_text = "A" * 5000
        result = FakePipelineResult(
            evidence={"execution": {"output": long_text}}
        )
        text = await handler._format_result(result)
        assert len(text) < 4000
        assert "csonkolva" in text

    @pytest.mark.asyncio
    async def test_evidence_plan_validation_fallback(self):
        handler = _make_handler()
        result = FakePipelineResult(
            evidence={
                "execution": {},
                "plan": {"steps": ["step1", "step2"]},
            }
        )
        text = await handler._format_result(result)
        assert "plan" in text.lower()


# ---------------------------------------------------------------------------
# _fetch_openclaw_session_text
# ---------------------------------------------------------------------------

class TestFetchOpenClawSessionText:
    @pytest.mark.asyncio
    async def test_empty_session_key(self):
        handler = _make_handler()
        result = await handler._fetch_openclaw_session_text("")
        assert result == ""

    @pytest.mark.asyncio
    async def test_successful_fetch_messages_format(self):
        """Mock httpx to return session history with messages array."""
        import httpx

        handler = _make_handler()
        mock_response = httpx.Response(
            status_code=200,
            json={
                "messages": [
                    {"role": "user", "content": "Mi az OCCP?"},
                    {"role": "assistant", "content": "Az OCCP egy Agent Control Plane."},
                ]
            },
        )

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client), \
             patch.dict("os.environ", {"OCCP_OPENCLAW_BASE_URL": "https://claw.occp.ai"}):
            result = await handler._fetch_openclaw_session_text("agent:main:general/abc123")

        assert "Agent Control Plane" in result

    @pytest.mark.asyncio
    async def test_fetch_non_200_returns_empty(self):
        import httpx

        handler = _make_handler()
        mock_response = httpx.Response(status_code=404)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client), \
             patch.dict("os.environ", {"OCCP_OPENCLAW_BASE_URL": "https://claw.occp.ai"}):
            result = await handler._fetch_openclaw_session_text("agent:main:test/xyz")

        assert result == ""

    @pytest.mark.asyncio
    async def test_fetch_network_error_returns_empty(self):
        handler = _make_handler()

        with patch("httpx.AsyncClient", side_effect=Exception("Connection refused")):
            result = await handler._fetch_openclaw_session_text("agent:main:test/xyz")

        assert result == ""
