"""Tests for OpenClawClient — dispatch, polling, parallel, callbacks, extraction.

Covers 30+ scenarios with mocked HTTP (no real server calls).
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from adapters.openclaw_client import OpenClawClient, OpenClawTask
from config.openclaw_agents import (
    AGENT_OPENCLAW_MAP,
    get_agent_model,
    get_agent_workspace,
    get_all_agent_ids,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client() -> OpenClawClient:
    return OpenClawClient(
        base_url="https://claw.occp.ai",
        auth_user="admin",
        auth_pass="secret",
        webhook_secret="test-secret-key",
        callback_url="https://api.occp.ai/api/v1/agents/callback",
        timeout=10.0,
        max_retries=1,
        retry_delay=0.0,
    )


@pytest.fixture
def client_no_secret() -> OpenClawClient:
    return OpenClawClient(
        base_url="https://claw.occp.ai",
        auth_user="admin",
        auth_pass="secret",
    )


def _sign(payload: dict, secret: str) -> str:
    body = json.dumps(payload, sort_keys=True, default=str).encode()
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _mock_response(status_code: int = 200, json_data: Any = None, text: str = "") -> httpx.Response:
    content = text.encode() if text else b""
    if json_data is not None:
        content = json.dumps(json_data).encode()
    return httpx.Response(
        status_code=status_code,
        content=content,
        headers={"content-type": "application/json"} if json_data is not None else {},
        request=httpx.Request("POST", "https://claw.occp.ai/api/v1/sessions"),
    )


# ---------------------------------------------------------------------------
# 1-5: Task dispatch tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatch_task_success(client: OpenClawClient) -> None:
    """Successful dispatch returns running task with session_key."""
    mock_resp = _mock_response(201, {"sessionKey": "sess-abc123"})

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
        task = await client.dispatch_task("eng-core", "Build the API")

    assert task.status == "running"
    assert task.session_key == "sess-abc123"
    assert task.agent_id == "eng-core"
    assert task.input_text == "Build the API"
    assert task.started_at is not None
    assert task.task_id in client.tasks


@pytest.mark.asyncio
async def test_dispatch_task_with_custom_id(client: OpenClawClient) -> None:
    """Custom task_id is preserved."""
    mock_resp = _mock_response(200, {"sessionKey": "s1"})

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
        task = await client.dispatch_task("wp-web", "Fix WordPress", task_id="custom-123")

    assert task.task_id == "custom-123"
    assert "custom-123" in client.tasks


@pytest.mark.asyncio
async def test_dispatch_task_http_error(client: OpenClawClient) -> None:
    """HTTP 500 marks task as failed with error message."""
    mock_resp = _mock_response(500, text="Internal Server Error")

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
        task = await client.dispatch_task("eng-core", "Some task")

    assert task.status == "failed"
    assert "HTTP 500" in task.error


@pytest.mark.asyncio
async def test_dispatch_task_connection_error(client: OpenClawClient) -> None:
    """Connection error marks task as failed."""
    with patch(
        "httpx.AsyncClient.post",
        new_callable=AsyncMock,
        side_effect=httpx.ConnectError("Connection refused"),
    ):
        task = await client.dispatch_task("eng-core", "Task")

    assert task.status == "failed"
    assert "Connection failed" in task.error


@pytest.mark.asyncio
async def test_dispatch_task_timeout(client: OpenClawClient) -> None:
    """Timeout marks task as failed."""
    with patch(
        "httpx.AsyncClient.post",
        new_callable=AsyncMock,
        side_effect=httpx.TimeoutException("timed out"),
    ):
        task = await client.dispatch_task("infra-ops", "Deploy server")

    assert task.status == "failed"
    assert "Timeout" in task.error or "timeout" in task.error


# ---------------------------------------------------------------------------
# 6-8: Dispatch with metadata and session_key formats
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatch_task_with_metadata(client: OpenClawClient) -> None:
    """Metadata is passed through in the payload."""
    captured_payload = {}

    async def capture_post(url, **kwargs):
        captured_payload.update(kwargs.get("json", {}))
        return _mock_response(201, {"sessionKey": "s-meta"})

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=capture_post):
        task = await client.dispatch_task(
            "eng-core", "Task", metadata={"priority": "high", "project": "occp"}
        )

    assert captured_payload["metadata"]["priority"] == "high"
    assert task.session_key == "s-meta"


@pytest.mark.asyncio
async def test_dispatch_task_session_key_snake_case(client: OpenClawClient) -> None:
    """Handle session_key in snake_case format."""
    mock_resp = _mock_response(200, {"session_key": "snake-key"})

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
        task = await client.dispatch_task("wp-web", "Task")

    assert task.session_key == "snake-key"


@pytest.mark.asyncio
async def test_dispatch_task_http_401(client: OpenClawClient) -> None:
    """HTTP 401 Unauthorized."""
    mock_resp = _mock_response(401, text="Unauthorized")

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
        task = await client.dispatch_task("eng-core", "Task")

    assert task.status == "failed"
    assert "HTTP 401" in task.error


# ---------------------------------------------------------------------------
# 9-12: Result polling tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_task_result_completed(client: OpenClawClient) -> None:
    """Poll session history and extract assistant text."""
    # First dispatch
    mock_dispatch = _mock_response(201, {"sessionKey": "sess-poll"})
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_dispatch):
        task = await client.dispatch_task("eng-core", "Build API")

    # Then poll
    history = [
        {"role": "user", "content": "Build API"},
        {"role": "assistant", "content": "Here is the API implementation..."},
    ]
    mock_history = _mock_response(200, history)
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_history):
        result = await client.get_task_result(task.task_id)

    assert result.status == "completed"
    assert result.result["text"] == "Here is the API implementation..."
    assert result.completed_at is not None


@pytest.mark.asyncio
async def test_get_task_result_no_session_key(client: OpenClawClient) -> None:
    """Task without session_key returns task as-is."""
    # Manually add a task without session_key
    task = OpenClawTask(task_id="no-sess", agent_id="eng-core", input_text="x")
    client._tasks["no-sess"] = task

    result = await client.get_task_result("no-sess")
    assert result.status == "pending"


@pytest.mark.asyncio
async def test_get_task_result_unknown_id(client: OpenClawClient) -> None:
    """Unknown task_id returns None."""
    result = await client.get_task_result("nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_get_task_result_poll_error(client: OpenClawClient) -> None:
    """Network error during poll sets error but does not crash."""
    mock_dispatch = _mock_response(201, {"sessionKey": "sess-err"})
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_dispatch):
        task = await client.dispatch_task("eng-core", "Task")

    with patch(
        "httpx.AsyncClient.get",
        new_callable=AsyncMock,
        side_effect=httpx.ConnectError("Network down"),
    ):
        result = await client.get_task_result(task.task_id)

    assert result.error is not None
    assert "Network down" in result.error


# ---------------------------------------------------------------------------
# 13-15: Parallel dispatch tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatch_parallel_success(client: OpenClawClient) -> None:
    """Parallel dispatch of 3 tasks all succeed."""
    call_count = 0

    async def mock_post(url, **kwargs):
        nonlocal call_count
        call_count += 1
        return _mock_response(201, {"sessionKey": f"sess-{call_count}"})

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=mock_post):
        results = await client.dispatch_parallel([
            {"agent_id": "eng-core", "input": "Task 1"},
            {"agent_id": "wp-web", "input": "Task 2"},
            {"agent_id": "infra-ops", "input": "Task 3"},
        ])

    assert len(results) == 3
    assert all(isinstance(r, OpenClawTask) for r in results)
    assert all(r.status == "running" for r in results)


@pytest.mark.asyncio
async def test_dispatch_parallel_partial_failure(client: OpenClawClient) -> None:
    """One task fails, others succeed."""
    call_count = 0

    async def mock_post(url, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            return _mock_response(500, text="Server Error")
        return _mock_response(201, {"sessionKey": f"sess-{call_count}"})

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=mock_post):
        results = await client.dispatch_parallel([
            {"agent_id": "eng-core", "input": "Task 1"},
            {"agent_id": "wp-web", "input": "Task 2"},
            {"agent_id": "infra-ops", "input": "Task 3"},
        ])

    statuses = [r.status for r in results]
    assert statuses.count("running") == 2
    assert statuses.count("failed") == 1


@pytest.mark.asyncio
async def test_dispatch_parallel_empty(client: OpenClawClient) -> None:
    """Empty task list returns empty results."""
    results = await client.dispatch_parallel([])
    assert results == []


# ---------------------------------------------------------------------------
# 16-18: Poll until complete tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_poll_until_complete_success(client: OpenClawClient) -> None:
    """Poll returns completed task on second attempt."""
    mock_dispatch = _mock_response(201, {"sessionKey": "sess-poll2"})
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_dispatch):
        task = await client.dispatch_task("eng-core", "Task")

    poll_count = 0

    async def mock_get(url, **kwargs):
        nonlocal poll_count
        poll_count += 1
        if poll_count >= 2:
            return _mock_response(200, [
                {"role": "assistant", "content": "Done!"},
            ])
        return _mock_response(200, [])

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=mock_get):
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await client.poll_until_complete(task.task_id, max_wait=30, interval=1)

    assert result.status == "completed"
    assert result.result["text"] == "Done!"


@pytest.mark.asyncio
async def test_poll_until_complete_timeout(client: OpenClawClient) -> None:
    """Poll times out after max_wait."""
    mock_dispatch = _mock_response(201, {"sessionKey": "sess-timeout"})
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_dispatch):
        task = await client.dispatch_task("eng-core", "Task")

    async def mock_get(url, **kwargs):
        return _mock_response(200, [])

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=mock_get):
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await client.poll_until_complete(task.task_id, max_wait=5, interval=2)

    assert result.status == "timeout"
    assert "Timed out" in result.error


@pytest.mark.asyncio
async def test_poll_until_complete_already_failed(client: OpenClawClient) -> None:
    """Poll returns immediately for already-failed task."""
    task = OpenClawTask(
        task_id="fail-task", agent_id="eng-core", input_text="x", status="failed",
        error="Connection refused", session_key="sess-x",
    )
    client._tasks["fail-task"] = task

    async def mock_get(url, **kwargs):
        return _mock_response(200, [])

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=mock_get):
        result = await client.poll_until_complete("fail-task", max_wait=10, interval=1)

    assert result.status == "failed"


# ---------------------------------------------------------------------------
# 19-23: Callback handling tests
# ---------------------------------------------------------------------------


def test_handle_callback_valid_signature(client: OpenClawClient) -> None:
    """Valid HMAC signature accepts callback."""
    task = OpenClawTask(task_id="cb-task-1", agent_id="eng-core", input_text="x", status="running")
    client._tasks["cb-task-1"] = task

    payload = {"taskId": "cb-task-1", "status": "completed", "result": {"text": "Done"}}
    sig = f"sha256={_sign(payload, 'test-secret-key')}"

    result = client.handle_callback(payload, sig)

    assert result is not None
    assert result.status == "completed"
    assert result.result == {"text": "Done"}
    assert result.completed_at is not None


def test_handle_callback_invalid_signature(client: OpenClawClient) -> None:
    """Invalid HMAC signature raises ValueError."""
    task = OpenClawTask(task_id="cb-task-2", agent_id="eng-core", input_text="x", status="running")
    client._tasks["cb-task-2"] = task

    payload = {"taskId": "cb-task-2", "status": "completed"}

    with pytest.raises(ValueError, match="Invalid callback signature"):
        client.handle_callback(payload, "sha256=0000000000000000")


def test_handle_callback_unknown_task(client: OpenClawClient) -> None:
    """Unknown task_id returns None."""
    payload = {"taskId": "nonexistent", "status": "completed"}
    sig = f"sha256={_sign(payload, 'test-secret-key')}"

    result = client.handle_callback(payload, sig)
    assert result is None


def test_handle_callback_with_error(client: OpenClawClient) -> None:
    """Callback with error field sets task.error."""
    task = OpenClawTask(task_id="cb-err", agent_id="eng-core", input_text="x", status="running")
    client._tasks["cb-err"] = task

    payload = {"taskId": "cb-err", "status": "failed", "error": "Agent crashed"}
    sig = f"sha256={_sign(payload, 'test-secret-key')}"

    result = client.handle_callback(payload, sig)
    assert result.status == "failed"
    assert result.error == "Agent crashed"


def test_handle_callback_no_secret(client_no_secret: OpenClawClient) -> None:
    """Without webhook_secret, signature verification is skipped."""
    task = OpenClawTask(task_id="cb-nosec", agent_id="eng-core", input_text="x", status="running")
    client_no_secret._tasks["cb-nosec"] = task

    payload = {"taskId": "cb-nosec", "status": "completed", "result": {"text": "OK"}}

    result = client_no_secret.handle_callback(payload, "anything")
    assert result is not None
    assert result.status == "completed"


def test_handle_callback_task_id_snake_case(client: OpenClawClient) -> None:
    """Callback with task_id in snake_case."""
    task = OpenClawTask(task_id="cb-snake", agent_id="eng-core", input_text="x", status="running")
    client._tasks["cb-snake"] = task

    payload = {"task_id": "cb-snake", "status": "completed"}
    sig = f"sha256={_sign(payload, 'test-secret-key')}"

    result = client.handle_callback(payload, sig)
    assert result is not None
    assert result.status == "completed"


# ---------------------------------------------------------------------------
# 24-28: Text extraction from various history formats
# ---------------------------------------------------------------------------


def test_extract_assistant_text_list_format() -> None:
    """Extract from simple message list."""
    history = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
    ]
    assert OpenClawClient._extract_assistant_text(history) == "Hi there!"


def test_extract_assistant_text_dict_messages() -> None:
    """Extract from dict with 'messages' key."""
    history = {
        "messages": [
            {"role": "user", "content": "Query"},
            {"role": "assistant", "content": "Response text"},
        ]
    }
    assert OpenClawClient._extract_assistant_text(history) == "Response text"


def test_extract_assistant_text_dict_history_key() -> None:
    """Extract from dict with 'history' key."""
    history = {
        "history": [
            {"role": "agent", "content": "Agent reply"},
        ]
    }
    assert OpenClawClient._extract_assistant_text(history) == "Agent reply"


def test_extract_assistant_text_multipart_content() -> None:
    """Extract from message with list content (multipart)."""
    history = [
        {"role": "assistant", "content": [
            {"type": "text", "text": "Part one."},
            {"type": "text", "text": "Part two."},
        ]},
    ]
    assert OpenClawClient._extract_assistant_text(history) == "Part one. Part two."


def test_extract_assistant_text_empty_history() -> None:
    """Empty history returns None."""
    assert OpenClawClient._extract_assistant_text([]) is None
    assert OpenClawClient._extract_assistant_text({}) is None


def test_extract_assistant_text_no_assistant() -> None:
    """History with only user messages returns None."""
    history = [
        {"role": "user", "content": "Hello"},
        {"role": "user", "content": "Another message"},
    ]
    assert OpenClawClient._extract_assistant_text(history) is None


def test_extract_assistant_text_whitespace_only() -> None:
    """Whitespace-only content is skipped."""
    history = [
        {"role": "assistant", "content": "   "},
        {"role": "assistant", "content": "Real content"},
    ]
    # Returns last non-empty assistant message (iterates in reverse)
    assert OpenClawClient._extract_assistant_text(history) == "Real content"


# ---------------------------------------------------------------------------
# 29-30: Utility / lifecycle tests
# ---------------------------------------------------------------------------


def test_clear_tasks(client: OpenClawClient) -> None:
    """clear_tasks empties the task store."""
    client._tasks["a"] = OpenClawTask(task_id="a", agent_id="x", input_text="y")
    client._tasks["b"] = OpenClawTask(task_id="b", agent_id="x", input_text="y")
    assert len(client.tasks) == 2

    client.clear_tasks()
    assert len(client.tasks) == 0


def test_generate_id() -> None:
    """Generated IDs are 16 hex chars and unique."""
    ids = {OpenClawClient._generate_id() for _ in range(100)}
    assert len(ids) == 100
    assert all(len(i) == 16 for i in ids)


def test_base_url_trailing_slash() -> None:
    """Trailing slash is stripped from base_url."""
    c = OpenClawClient(base_url="https://claw.occp.ai/")
    assert c.base_url == "https://claw.occp.ai"


def test_sign_payload_empty_secret() -> None:
    """Empty secret returns empty signature."""
    c = OpenClawClient(webhook_secret="")
    assert c._sign_payload({"key": "value"}) == ""


def test_sign_payload_deterministic(client: OpenClawClient) -> None:
    """Same payload + secret = same signature."""
    payload = {"agent": "eng-core", "input": "test"}
    sig1 = client._sign_payload(payload)
    sig2 = client._sign_payload(payload)
    assert sig1 == sig2
    assert len(sig1) == 64  # SHA256 hex


# ---------------------------------------------------------------------------
# 35+: Config/mapping tests
# ---------------------------------------------------------------------------


def test_agent_openclaw_map_has_8_agents() -> None:
    """Map contains all 8 OpenClaw agents."""
    assert len(AGENT_OPENCLAW_MAP) == 8


def test_get_agent_workspace_known() -> None:
    assert get_agent_workspace("eng-core") == "eng-core"
    assert get_agent_workspace("intel-research") == "intel-research"
    assert get_agent_workspace("biz-strategy") == "biz-strategy"


def test_get_agent_workspace_unknown() -> None:
    assert get_agent_workspace("nonexistent-agent") is None


def test_get_agent_model_known() -> None:
    assert get_agent_model("eng-core") == "google/gemini-2.5-pro"
    assert get_agent_model("intel-research") == "anthropic/claude-opus-4-6"


def test_get_agent_model_unknown() -> None:
    assert get_agent_model("nonexistent-agent") is None


def test_get_all_agent_ids() -> None:
    ids = get_all_agent_ids()
    assert len(ids) == 8
    assert "eng-core" in ids
    assert "biz-strategy" in ids


def test_all_agents_have_workspace() -> None:
    """Every agent in the map has a workspace key."""
    for agent_id, config in AGENT_OPENCLAW_MAP.items():
        assert "workspace" in config, f"{agent_id} missing workspace"
        assert "model" in config, f"{agent_id} missing model"


# ---------------------------------------------------------------------------
# OpenClawTask dataclass tests
# ---------------------------------------------------------------------------


def test_openclaw_task_defaults() -> None:
    task = OpenClawTask(task_id="t1", agent_id="eng-core", input_text="hello")
    assert task.status == "pending"
    assert task.session_key is None
    assert task.result is None
    assert task.error is None
    assert task.started_at is None
    assert task.completed_at is None
