"""Cloudflare MCP client adapter.

Exposes Cloudflare API v4 endpoints (zones, DNS, analytics) as MCP-compat
tools on the OCCP MCPBridge. Analytics GraphQL is stubbed until the query
shape is locked down.

Env:
    OCCP_CLOUDFLARE_API_TOKEN — scoped API token

FELT: upstream Cloudflare now ships a "Code Mode MCP"; for now we stay on
the classic REST v4 API for predictability. GraphQL analytics returns
{"status": "stub"} pending query finalisation.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_API_BASE = "https://api.cloudflare.com/client/v4"
_GRAPHQL_URL = "https://api.cloudflare.com/client/v4/graphql"
_DEFAULT_TIMEOUT = 15.0


def _token() -> str | None:
    tok = os.getenv("OCCP_CLOUDFLARE_API_TOKEN", "").strip()
    return tok or None


def _headers(tok: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {tok}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


async def cloudflare_zones_list(params: dict[str, Any]) -> dict[str, Any]:
    tok = _token()
    if tok is None:
        return {"error": "cloudflare-not-configured"}

    async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
        resp = await client.get(
            f"{_API_BASE}/zones",
            headers=_headers(tok),
            params={"per_page": int(params.get("per_page", 50))},
        )
    if resp.status_code >= 400:
        return {"error": f"cloudflare http {resp.status_code}", "body": resp.text[:500]}
    data = resp.json()
    zones = data.get("result", []) or []
    return {
        "success": bool(data.get("success")),
        "count": len(zones),
        "zones": [
            {
                "id": z.get("id"),
                "name": z.get("name"),
                "status": z.get("status"),
                "plan": (z.get("plan") or {}).get("name"),
            }
            for z in zones
        ],
    }


async def cloudflare_dns_list(params: dict[str, Any]) -> dict[str, Any]:
    tok = _token()
    if tok is None:
        return {"error": "cloudflare-not-configured"}

    zone_id = str(params.get("zone_id", "")).strip()
    if not zone_id:
        return {"error": "zone_id required"}

    async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
        resp = await client.get(
            f"{_API_BASE}/zones/{zone_id}/dns_records",
            headers=_headers(tok),
            params={"per_page": int(params.get("per_page", 100))},
        )
    if resp.status_code >= 400:
        return {"error": f"cloudflare http {resp.status_code}", "body": resp.text[:500]}
    data = resp.json()
    records = data.get("result", []) or []
    return {
        "success": bool(data.get("success")),
        "count": len(records),
        "records": [
            {
                "id": r.get("id"),
                "type": r.get("type"),
                "name": r.get("name"),
                "content": r.get("content"),
                "proxied": r.get("proxied"),
                "ttl": r.get("ttl"),
            }
            for r in records
        ],
    }


async def cloudflare_analytics_get(params: dict[str, Any]) -> dict[str, Any]:
    tok = _token()
    if tok is None:
        return {"error": "cloudflare-not-configured"}

    zone_id = str(params.get("zone_id", "")).strip()
    since = str(params.get("since", "")).strip()
    if not zone_id or not since:
        return {"error": "zone_id and since required"}

    return {
        "status": "stub",
        "zone_id": zone_id,
        "since": since,
        "graphql_endpoint": _GRAPHQL_URL,
        "note": "Analytics GraphQL query shape pending; swap for real query once schema locked.",
    }


def register_cloudflare_tools(bridge: Any) -> None:
    """Register Cloudflare MCP tools on the OCCP bridge."""
    bridge.register("cloudflare.zones_list", cloudflare_zones_list)
    bridge.register("cloudflare.dns_list", cloudflare_dns_list)
    bridge.register("cloudflare.analytics_get", cloudflare_analytics_get)
    logger.info("Cloudflare MCP tools registered (3 tools; analytics is stub)")
