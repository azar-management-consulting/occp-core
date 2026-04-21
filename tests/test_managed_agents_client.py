"""Unit tests for adapters/managed_agents_client.py.

We mock httpx via ``httpx.MockTransport`` rather than ``respx`` so no
additional dev dep is required. The tests verify:

* ``create_session`` posts to the correct URL with the beta header
* ``send_message`` parses SSE ``data: {...}`` chunks into token strings
* ``ManagedAgentsAPIError`` raised on 400 (no retry)
* 500 → retried, succeeds on the 2nd attempt
* ``NotConfigured`` raised when no env var is set
"""

from __future__ import annotations

import json
from collections.abc import Iterable

import httpx
import pytest

import adapters.managed_agents_client as mac_module
from adapters.managed_agents_client import (
    DEFAULT_BETA_HEADER,
    AnthropicManagedAgentsClient,
    ManagedAgentsAPIError,
    NotConfigured,
)


# ── Fixtures / helpers ───────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    """Collapse the retry backoff so 5xx tests run instantly."""
    monkeypatch.setattr(mac_module, "_BACKOFF_SCHEDULE_S", (0.0, 0.0, 0.0))


def _build_client(
    handler,
    *,
    api_key: str = "sk-test-abcd",
) -> AnthropicManagedAgentsClient:
    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport)
    return AnthropicManagedAgentsClient(
        api_key=api_key,
        http_client=http_client,
    )


def _sse_body(events: Iterable[dict]) -> bytes:
    lines: list[str] = []
    for evt in events:
        lines.append(f"data: {json.dumps(evt)}")
        lines.append("")
    lines.append("data: [DONE]")
    lines.append("")
    return ("\n".join(lines)).encode("utf-8")


# ── Beta header is a module constant ─────────────────────────────


def test_beta_header_is_module_string_constant() -> None:
    assert isinstance(DEFAULT_BETA_HEADER, str)
    assert DEFAULT_BETA_HEADER == "managed-agents-2026-04-01"


# ── NotConfigured ────────────────────────────────────────────────


def test_not_configured_when_env_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OCCP_ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(NotConfigured):
        AnthropicManagedAgentsClient()


# ── create_session ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_session_hits_correct_url_and_sends_beta_header() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["beta"] = request.headers.get("anthropic-beta")
        captured["api_key"] = request.headers.get("x-api-key")
        captured["method"] = request.method
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json={
                "id": "sess_01HZ",
                "created_at": "2026-04-21T00:00:00Z",
            },
        )

    client = _build_client(handler)
    try:
        handle = await client.create_session({"name": "deep-web-research"})
    finally:
        await client.aclose()

    assert captured["method"] == "POST"
    assert captured["url"] == (
        "https://api.anthropic.com/v1/managed_agents/sessions"
    )
    assert captured["beta"] == DEFAULT_BETA_HEADER
    assert captured["api_key"] == "sk-test-abcd"
    assert captured["body"] == {"agent": {"name": "deep-web-research"}}
    assert handle.session_id == "sess_01HZ"
    assert handle.agent_name == "deep-web-research"


# ── send_message streaming ───────────────────────────────────────


@pytest.mark.asyncio
async def test_send_message_streams_text_deltas() -> None:
    events = [
        {"type": "text_delta", "delta": {"text": "Hello "}},
        {"type": "text_delta", "delta": {"text": "world"}},
        {"type": "text_delta", "delta": {"text": "!"}},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path.endswith("/sessions/sess_1/messages")
        assert request.headers.get("accept") == "text/event-stream"
        return httpx.Response(
            200,
            content=_sse_body(events),
            headers={"content-type": "text/event-stream"},
        )

    client = _build_client(handler)
    try:
        chunks: list[str] = []
        async for token in client.send_message("sess_1", "hi", max_tokens=64):
            chunks.append(token)
    finally:
        await client.aclose()

    assert chunks == ["Hello ", "world", "!"]


# ── 4xx → ManagedAgentsAPIError, no retry ────────────────────────


@pytest.mark.asyncio
async def test_400_raises_managed_agents_api_error_no_retry() -> None:
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        return httpx.Response(400, json={"error": "bad request"})

    client = _build_client(handler)
    try:
        with pytest.raises(ManagedAgentsAPIError) as excinfo:
            await client.create_session({"name": "x"})
    finally:
        await client.aclose()

    assert excinfo.value.status_code == 400
    assert "bad request" in excinfo.value.body
    assert call_count["n"] == 1  # no retry on 4xx


# ── 5xx → retried with backoff ───────────────────────────────────


@pytest.mark.asyncio
async def test_500_is_retried_and_eventually_succeeds() -> None:
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        if call_count["n"] < 2:
            return httpx.Response(500, text="boom")
        return httpx.Response(
            200,
            json={"id": "sess_ok", "created_at": "2026-04-21T00:00:00Z"},
        )

    client = _build_client(handler)
    try:
        handle = await client.create_session({"name": "x"})
    finally:
        await client.aclose()

    assert call_count["n"] == 2
    assert handle.session_id == "sess_ok"


@pytest.mark.asyncio
async def test_500_exhausts_retries_then_raises() -> None:
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        return httpx.Response(500, text="still broken")

    client = _build_client(handler)
    try:
        with pytest.raises(ManagedAgentsAPIError) as excinfo:
            await client.create_session({"name": "x"})
    finally:
        await client.aclose()

    assert excinfo.value.status_code == 500
    # 1 initial + 3 retries = 4 total
    assert call_count["n"] == 4


# ── end_session ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_end_session_tolerates_404() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "DELETE"
        return httpx.Response(404, json={"error": "already gone"})

    client = _build_client(handler)
    try:
        await client.end_session("sess_missing")  # must NOT raise
    finally:
        await client.aclose()


# ── api_key never appears in logs ────────────────────────────────


@pytest.mark.asyncio
async def test_api_key_not_logged_in_full(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level("INFO", logger="adapters.managed_agents_client")
    client = AnthropicManagedAgentsClient(api_key="sk-ant-verysecretkey12345")
    try:
        combined = " ".join(r.getMessage() for r in caplog.records)
        assert "sk-ant-verysecretkey12345" not in combined
        assert "2345" not in combined  # not even the last 4
        assert "REDACTED" in combined
    finally:
        await client.aclose()
