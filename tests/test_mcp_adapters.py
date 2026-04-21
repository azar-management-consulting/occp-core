"""Tests for the 5 external MCP client adapters.

We use ``httpx.MockTransport`` instead of ``respx`` to avoid adding a new
test dependency; it delivers the same assertion surface (method, URL
path, headers) in a few lines.
"""

from __future__ import annotations

import json
from typing import Any, Callable
from unittest.mock import patch

import httpx
import pytest

from adapters.mcp_bridge import build_default_bridge


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────


class _Captured:
    """Collects the last request that hit the mock transport."""

    def __init__(self) -> None:
        self.request: httpx.Request | None = None


def _patch_async_client(
    monkeypatch: pytest.MonkeyPatch,
    handler: Callable[[httpx.Request], httpx.Response],
    captured: _Captured,
) -> None:
    """Monkey-patch ``httpx.AsyncClient`` so every instance uses a MockTransport."""

    original = httpx.AsyncClient

    def factory(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        def _wrap(req: httpx.Request) -> httpx.Response:
            captured.request = req
            return handler(req)

        kwargs["transport"] = httpx.MockTransport(_wrap)
        return original(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", factory)


def _json_response(payload: Any, status: int = 200) -> httpx.Response:
    return httpx.Response(
        status,
        headers={"content-type": "application/json"},
        content=json.dumps(payload).encode(),
    )


# ──────────────────────────────────────────────────────────────
# 1. Supabase
# ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_supabase_list_tables_dispatches_correctly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OCCP_SUPABASE_URL", "https://proj.supabase.co")
    monkeypatch.setenv("OCCP_SUPABASE_SERVICE_ROLE_KEY", "svc-key-xyz")

    captured = _Captured()
    _patch_async_client(
        monkeypatch,
        lambda req: _json_response([{"table_name": "users"}, {"table_name": "posts"}]),
        captured,
    )

    from adapters.mcp_supabase import supabase_list_tables

    result = await supabase_list_tables({"schema": "public"})

    assert captured.request is not None
    assert captured.request.method == "GET"
    assert captured.request.url.path == "/rest/v1/information_schema.tables"
    assert captured.request.headers["Authorization"] == "Bearer svc-key-xyz"
    assert captured.request.headers["apikey"] == "svc-key-xyz"
    assert result == {"schema": "public", "tables": ["users", "posts"], "count": 2}


@pytest.mark.asyncio
async def test_supabase_query_blocks_writes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OCCP_SUPABASE_URL", "https://proj.supabase.co")
    monkeypatch.setenv("OCCP_SUPABASE_SERVICE_ROLE_KEY", "svc")
    from adapters.mcp_supabase import supabase_query

    # Plain write
    result = await supabase_query({"sql": "DELETE FROM users"})
    assert result == {"error": "write SQL blocked (read-only tool)"}

    # CTE-bypass attempt — strict guard must catch this too
    result = await supabase_query(
        {"sql": "WITH x AS (SELECT 1) DELETE FROM users WHERE id IN x"}
    )
    assert result == {"error": "write SQL blocked (read-only tool)"}

    # Multi-statement stack — must be blocked
    result = await supabase_query({"sql": "SELECT 1; DROP TABLE audit_log"})
    assert result == {"error": "write SQL blocked (read-only tool)"}

    # Comment-bypass — write keyword hidden after /* ... */ block
    result = await supabase_query(
        {"sql": "/* safe */ UPDATE users SET admin = true WHERE id = 1"}
    )
    assert result == {"error": "write SQL blocked (read-only tool)"}


@pytest.mark.asyncio
async def test_playwright_extract_text_blocks_ssrf(monkeypatch: pytest.MonkeyPatch) -> None:
    """SSRF defense: private IPs, localhost, and metadata hosts must be rejected."""
    from adapters.mcp_playwright import playwright_extract_text

    blocked = [
        "http://127.0.0.1/admin",
        "http://localhost/",
        "http://169.254.169.254/latest/meta-data/",  # AWS IMDS
        "http://metadata.google.internal/",
        "http://10.0.0.5/",
        "http://192.168.1.1/router",
        "http://[::1]/",
    ]
    for url in blocked:
        result = await playwright_extract_text({"url": url})
        assert result.get("status") == "error", f"SSRF NOT blocked for {url}: {result}"


@pytest.mark.asyncio
async def test_supabase_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OCCP_SUPABASE_URL", raising=False)
    monkeypatch.delenv("OCCP_SUPABASE_SERVICE_ROLE_KEY", raising=False)
    from adapters.mcp_supabase import supabase_query

    assert await supabase_query({"sql": "SELECT 1"}) == {"error": "supabase-not-configured"}


# ──────────────────────────────────────────────────────────────
# 2. GitHub
# ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_github_search_issues_dispatches_correctly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OCCP_GITHUB_TOKEN", "ghp_abc")

    captured = _Captured()
    _patch_async_client(
        monkeypatch,
        lambda req: _json_response(
            {
                "total_count": 1,
                "items": [
                    {
                        "number": 42,
                        "title": "bug",
                        "state": "open",
                        "html_url": "https://github.com/o/r/issues/42",
                        "user": {"login": "alice"},
                    }
                ],
            }
        ),
        captured,
    )

    from adapters.mcp_github import github_search_issues

    result = await github_search_issues({"repo": "o/r", "query": "crash", "state": "open"})

    assert captured.request is not None
    assert captured.request.method == "GET"
    assert captured.request.url.path == "/search/issues"
    assert captured.request.headers["Authorization"] == "Bearer ghp_abc"
    assert captured.request.headers["X-GitHub-Api-Version"] == "2022-11-28"
    assert result["total_count"] == 1
    assert result["items"][0]["number"] == 42
    assert result["items"][0]["user"] == "alice"


# ──────────────────────────────────────────────────────────────
# 3. Playwright
# ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_playwright_extract_text_fetches_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _Captured()
    _patch_async_client(
        monkeypatch,
        lambda req: httpx.Response(200, text="<html><body>hello</body></html>"),
        captured,
    )

    from adapters.mcp_playwright import playwright_extract_text

    result = await playwright_extract_text({"url": "https://example.com"})

    assert captured.request is not None
    assert captured.request.method == "GET"
    assert str(captured.request.url) == "https://example.com"
    assert result["status"] == "ok"
    assert "hello" in result["body"]


@pytest.mark.asyncio
async def test_playwright_goto_returns_stub() -> None:
    from adapters.mcp_playwright import playwright_goto

    result = await playwright_goto({"url": "https://example.com"})
    assert result["status"] == "stub"
    assert result["action"] == "goto"


# ──────────────────────────────────────────────────────────────
# 4. Cloudflare
# ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cloudflare_zones_list_dispatches_correctly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OCCP_CLOUDFLARE_API_TOKEN", "cf-token-xyz")

    captured = _Captured()
    _patch_async_client(
        monkeypatch,
        lambda req: _json_response(
            {
                "success": True,
                "result": [
                    {"id": "z1", "name": "azar.hu", "status": "active", "plan": {"name": "Free"}},
                ],
            }
        ),
        captured,
    )

    from adapters.mcp_cloudflare import cloudflare_zones_list

    result = await cloudflare_zones_list({})

    assert captured.request is not None
    assert captured.request.method == "GET"
    assert captured.request.url.path == "/client/v4/zones"
    assert captured.request.headers["Authorization"] == "Bearer cf-token-xyz"
    assert result["success"] is True
    assert result["count"] == 1
    assert result["zones"][0]["name"] == "azar.hu"


# ──────────────────────────────────────────────────────────────
# 5. Slack
# ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_slack_post_message_dispatches_correctly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OCCP_SLACK_BOT_TOKEN", "xoxb-abc")

    captured = _Captured()
    _patch_async_client(
        monkeypatch,
        lambda req: _json_response({"ok": True, "ts": "1700.0", "channel": "C01"}),
        captured,
    )

    from adapters.mcp_slack import slack_post_message

    result = await slack_post_message({"channel": "C01", "text": "hi"})

    assert captured.request is not None
    assert captured.request.method == "POST"
    assert str(captured.request.url) == "https://slack.com/api/chat.postMessage"
    assert captured.request.headers["Authorization"] == "Bearer xoxb-abc"
    body = json.loads(captured.request.content.decode())
    assert body == {"channel": "C01", "text": "hi"}
    assert result == {"ok": True, "ts": "1700.0", "channel": "C01", "error": None}


# ──────────────────────────────────────────────────────────────
# 6. Env-var-gated registration
# ──────────────────────────────────────────────────────────────


def test_registration_gated_by_env(monkeypatch: pytest.MonkeyPatch) -> None:
    # Unset every adapter env var — nothing external registered.
    for k in (
        "OCCP_SUPABASE_URL",
        "OCCP_SUPABASE_SERVICE_ROLE_KEY",
        "OCCP_GITHUB_TOKEN",
        "OCCP_CLOUDFLARE_API_TOKEN",
        "OCCP_SLACK_BOT_TOKEN",
    ):
        monkeypatch.delenv(k, raising=False)

    bridge = build_default_bridge()
    tools = bridge.list_tools()
    assert "supabase.query" not in tools
    assert "github.search_issues" not in tools
    assert "cloudflare.zones_list" not in tools
    assert "slack.post_message" not in tools
    # Playwright is unconditional.
    assert "playwright.extract_text" in tools

    # Now set all → all registered.
    monkeypatch.setenv("OCCP_SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("OCCP_SUPABASE_SERVICE_ROLE_KEY", "k")
    monkeypatch.setenv("OCCP_GITHUB_TOKEN", "ghp")
    monkeypatch.setenv("OCCP_CLOUDFLARE_API_TOKEN", "cf")
    monkeypatch.setenv("OCCP_SLACK_BOT_TOKEN", "xoxb")

    bridge2 = build_default_bridge()
    tools2 = bridge2.list_tools()
    assert "supabase.query" in tools2
    assert "supabase.list_tables" in tools2
    assert "supabase.describe_table" in tools2
    assert "github.search_issues" in tools2
    assert "github.get_pr" in tools2
    assert "github.list_commits" in tools2
    assert "cloudflare.zones_list" in tools2
    assert "cloudflare.dns_list" in tools2
    assert "cloudflare.analytics_get" in tools2
    assert "slack.post_message" in tools2
    assert "slack.search" in tools2
    assert "slack.list_channels" in tools2
