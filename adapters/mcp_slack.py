"""Slack MCP client adapter.

Exposes core Slack Web API methods (chat.postMessage, conversations.*,
search) as MCP-compat tools on the OCCP MCPBridge.

Env:
    OCCP_SLACK_BOT_TOKEN — xoxb-... bot token

FELT: Slack does not yet ship a first-party MCP server; this is a
pragmatic REST-over-httpx shim. Error-shape mirrors Slack's
{"ok": false, "error": "..."}.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_API_BASE = "https://slack.com/api"
_DEFAULT_TIMEOUT = 15.0


def _token() -> str | None:
    tok = os.getenv("OCCP_SLACK_BOT_TOKEN", "").strip()
    return tok or None


def _headers(tok: str, *, form: bool = False) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {tok}",
        "Content-Type": "application/x-www-form-urlencoded" if form else "application/json; charset=utf-8",
    }


async def slack_post_message(params: dict[str, Any]) -> dict[str, Any]:
    tok = _token()
    if tok is None:
        return {"error": "slack-not-configured"}

    channel = str(params.get("channel", "")).strip()
    text = str(params.get("text", ""))
    if not channel:
        return {"error": "channel required"}
    if not text:
        return {"error": "text required"}

    async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
        resp = await client.post(
            f"{_API_BASE}/chat.postMessage",
            headers=_headers(tok),
            json={"channel": channel, "text": text},
        )
    data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
    return {
        "ok": bool(data.get("ok")),
        "ts": data.get("ts"),
        "channel": data.get("channel"),
        "error": data.get("error"),
    }


async def slack_search(params: dict[str, Any]) -> dict[str, Any]:
    tok = _token()
    if tok is None:
        return {"error": "slack-not-configured"}

    query = str(params.get("query", "")).strip()
    channel = str(params.get("channel", "")).strip()
    if not query:
        return {"error": "query required"}
    if not channel:
        return {"error": "channel required (conversations.history is channel-scoped)"}

    async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
        resp = await client.get(
            f"{_API_BASE}/conversations.history",
            headers={"Authorization": f"Bearer {tok}"},
            params={"channel": channel, "limit": int(params.get("limit", 100))},
        )
    data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
    if not data.get("ok"):
        return {"ok": False, "error": data.get("error", "unknown")}
    q = query.lower()
    messages = [
        {"ts": m.get("ts"), "user": m.get("user"), "text": m.get("text", "")}
        for m in data.get("messages", [])
        if q in str(m.get("text", "")).lower()
    ]
    return {"ok": True, "channel": channel, "query": query, "matches": len(messages), "messages": messages[:50]}


async def slack_list_channels(params: dict[str, Any]) -> dict[str, Any]:
    tok = _token()
    if tok is None:
        return {"error": "slack-not-configured"}

    async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
        resp = await client.get(
            f"{_API_BASE}/conversations.list",
            headers={"Authorization": f"Bearer {tok}"},
            params={
                "limit": int(params.get("limit", 200)),
                "types": str(params.get("types", "public_channel,private_channel")),
                "exclude_archived": "true",
            },
        )
    data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
    if not data.get("ok"):
        return {"ok": False, "error": data.get("error", "unknown")}
    channels = data.get("channels", []) or []
    return {
        "ok": True,
        "count": len(channels),
        "channels": [
            {
                "id": c.get("id"),
                "name": c.get("name"),
                "is_private": c.get("is_private"),
                "num_members": c.get("num_members"),
            }
            for c in channels
        ],
    }


def register_slack_tools(bridge: Any) -> None:
    """Register Slack MCP tools on the OCCP bridge."""
    bridge.register("slack.post_message", slack_post_message)
    bridge.register("slack.search", slack_search)
    bridge.register("slack.list_channels", slack_list_channels)
    logger.info("Slack MCP tools registered (3 tools)")
