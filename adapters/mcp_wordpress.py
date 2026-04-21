"""WordPress MCP client adapter.

Wraps WordPress REST API v2 with Application Password auth (Basic).
Supports multi-site via OCCP_WP_SITES JSON or per-slug env vars.

Env (either form):
    OCCP_WP_SITES — JSON array:
        '[{"slug":"azar","url":"https://azar.hu",
           "user":"admin","app_password":"xxxx xxxx xxxx xxxx xxxx xxxx"}]'
    OR per-slug triples:
        OCCP_WP_<SLUG>_URL, OCCP_WP_<SLUG>_USER, OCCP_WP_<SLUG>_APP_PASSWORD

Safety:
    - HTTPS-only: http:// URLs are rejected to prevent credential leakage.
    - site_slug is required on every call and routed through the registry.

FELT: single JSON array is the canonical shape for multi-site ops; per-site
triples are a convenience fallback for ops who prefer discrete vars.
"""

from __future__ import annotations

import base64
import json
import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 15.0
_NOT_CONFIGURED = {"error": "wordpress-not-configured"}


# ──────────────────────────────────────────────────────────────
# Site registry
# ──────────────────────────────────────────────────────────────


class WordPressMCP:
    """Multi-site WordPress REST API v2 client (Application Password auth)."""

    def __init__(self, sites: dict[str, dict[str, str]]) -> None:
        self._sites = sites

    @classmethod
    def from_env(cls) -> "WordPressMCP | None":
        """Build from env. Returns None if no config present."""
        sites: dict[str, dict[str, str]] = {}

        raw = os.getenv("OCCP_WP_SITES", "").strip()
        if raw:
            try:
                arr = json.loads(raw)
                if isinstance(arr, list):
                    for entry in arr:
                        if not isinstance(entry, dict):
                            continue
                        slug = str(entry.get("slug", "")).strip().lower()
                        url = str(entry.get("url", "")).strip()
                        user = str(entry.get("user", "")).strip()
                        pw = str(entry.get("app_password", "")).strip()
                        if slug and url and user and pw:
                            sites[slug] = {"url": url, "user": user, "app_password": pw}
            except json.JSONDecodeError as exc:
                logger.warning("OCCP_WP_SITES JSON invalid: %s", exc)

        # Per-slug fallback: OCCP_WP_<SLUG>_URL / _USER / _APP_PASSWORD
        prefix = "OCCP_WP_"
        for key in os.environ:
            if not key.startswith(prefix) or not key.endswith("_URL"):
                continue
            slug = key[len(prefix):-len("_URL")].lower()
            if not slug or slug in sites:
                continue
            url = os.environ.get(key, "").strip()
            user = os.environ.get(f"{prefix}{slug.upper()}_USER", "").strip()
            pw = os.environ.get(f"{prefix}{slug.upper()}_APP_PASSWORD", "").strip()
            if url and user and pw:
                sites[slug] = {"url": url, "user": user, "app_password": pw}

        if not sites:
            return None
        return cls(sites)

    # ── Helpers ──────────────────────────────────────────────

    def _site(self, site_slug: str) -> dict[str, str] | dict[str, str]:
        slug = (site_slug or "").strip().lower()
        if not slug:
            return {"error": "site_slug required"}
        site = self._sites.get(slug)
        if site is None:
            return {
                "error": f"unknown site_slug: {slug}",
                "known": sorted(self._sites.keys()),
            }
        url = site["url"]
        if not url.startswith("https://"):
            return {"error": "HTTPS-only: http:// sites are rejected"}
        return site

    @staticmethod
    def _auth_header(user: str, app_password: str) -> dict[str, str]:
        token = base64.b64encode(f"{user}:{app_password}".encode()).decode()
        return {
            "Authorization": f"Basic {token}",
            "Accept": "application/json",
            "User-Agent": "OCCP-MCP-Bridge/1.0",
        }

    async def _get(self, site_slug: str, path: str, query: dict[str, Any] | None = None) -> Any:
        site = self._site(site_slug)
        if "error" in site:
            return site
        async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
            resp = await client.get(
                f"{site['url']}{path}",
                headers=self._auth_header(site["user"], site["app_password"]),
                params=query or {},
            )
        if resp.status_code >= 400:
            return {"error": f"wp http {resp.status_code}", "body": resp.text[:500]}
        return resp.json()

    async def _post(self, site_slug: str, path: str, payload: dict[str, Any]) -> Any:
        site = self._site(site_slug)
        if "error" in site:
            return site
        async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
            resp = await client.post(
                f"{site['url']}{path}",
                headers=self._auth_header(site["user"], site["app_password"]),
                json=payload,
            )
        if resp.status_code >= 400:
            return {"error": f"wp http {resp.status_code}", "body": resp.text[:500]}
        return resp.json()

    # ── Tools ────────────────────────────────────────────────

    async def get_site_info(self, params: dict[str, Any]) -> dict[str, Any]:
        data = await self._get(str(params.get("site_slug", "")), "/wp-json/")
        if isinstance(data, dict) and "error" in data:
            return data
        return {
            "name": data.get("name"),
            "description": data.get("description"),
            "url": data.get("url"),
            "home": data.get("home"),
            "namespaces": data.get("namespaces", []),
            "routes_count": len(data.get("routes", {})),
        }

    async def get_posts(self, params: dict[str, Any]) -> dict[str, Any]:
        per_page = min(int(params.get("per_page", 10)), 100)
        status = str(params.get("status", "publish"))
        data = await self._get(
            str(params.get("site_slug", "")),
            "/wp-json/wp/v2/posts",
            {"per_page": per_page, "status": status},
        )
        if isinstance(data, dict) and "error" in data:
            return data
        posts = data if isinstance(data, list) else []
        return {
            "count": len(posts),
            "posts": [
                {
                    "id": p.get("id"),
                    "title": (p.get("title") or {}).get("rendered", ""),
                    "slug": p.get("slug", ""),
                    "date": p.get("date", ""),
                    "status": p.get("status", ""),
                    "link": p.get("link", ""),
                }
                for p in posts
            ],
        }

    async def get_pages(self, params: dict[str, Any]) -> dict[str, Any]:
        per_page = min(int(params.get("per_page", 10)), 100)
        data = await self._get(
            str(params.get("site_slug", "")),
            "/wp-json/wp/v2/pages",
            {"per_page": per_page},
        )
        if isinstance(data, dict) and "error" in data:
            return data
        pages = data if isinstance(data, list) else []
        return {
            "count": len(pages),
            "pages": [
                {
                    "id": p.get("id"),
                    "title": (p.get("title") or {}).get("rendered", ""),
                    "slug": p.get("slug", ""),
                    "link": p.get("link", ""),
                }
                for p in pages
            ],
        }

    async def update_post(self, params: dict[str, Any]) -> dict[str, Any]:
        post_id = params.get("post_id")
        if post_id is None:
            return {"error": "post_id required"}
        payload: dict[str, Any] = {}
        for field in ("title", "content", "status", "excerpt"):
            if field in params and params[field] is not None:
                payload[field] = params[field]
        if not payload:
            return {"error": "no fields to update"}
        data = await self._post(
            str(params.get("site_slug", "")),
            f"/wp-json/wp/v2/posts/{int(post_id)}",
            payload,
        )
        if isinstance(data, dict) and "error" in data:
            return data
        return {
            "id": data.get("id"),
            "title": (data.get("title") or {}).get("rendered", ""),
            "status": data.get("status", ""),
            "link": data.get("link", ""),
            "modified": data.get("modified", ""),
        }

    async def create_post(self, params: dict[str, Any]) -> dict[str, Any]:
        title = params.get("title")
        content = params.get("content")
        if not title or content is None:
            return {"error": "title and content required"}
        payload = {
            "title": title,
            "content": content,
            "status": str(params.get("status", "draft")),
        }
        data = await self._post(
            str(params.get("site_slug", "")),
            "/wp-json/wp/v2/posts",
            payload,
        )
        if isinstance(data, dict) and "error" in data:
            return data
        return {
            "id": data.get("id"),
            "title": (data.get("title") or {}).get("rendered", ""),
            "status": data.get("status", ""),
            "link": data.get("link", ""),
        }

    async def search(self, params: dict[str, Any]) -> dict[str, Any]:
        query = str(params.get("query", "")).strip()
        if not query:
            return {"error": "query required"}
        data = await self._get(
            str(params.get("site_slug", "")),
            "/wp-json/wp/v2/search",
            {"search": query, "per_page": min(int(params.get("per_page", 10)), 50)},
        )
        if isinstance(data, dict) and "error" in data:
            return data
        items = data if isinstance(data, list) else []
        return {
            "count": len(items),
            "results": [
                {
                    "id": it.get("id"),
                    "title": it.get("title", ""),
                    "url": it.get("url", ""),
                    "type": it.get("type", ""),
                    "subtype": it.get("subtype", ""),
                }
                for it in items
            ],
        }


# ──────────────────────────────────────────────────────────────
# Module-level tool wrappers (bridge.register targets)
# ──────────────────────────────────────────────────────────────


def _unconfigured(_: dict[str, Any]) -> dict[str, Any]:
    return _NOT_CONFIGURED


async def _tool(method: str, params: dict[str, Any]) -> dict[str, Any]:
    client = WordPressMCP.from_env()
    if client is None:
        return _NOT_CONFIGURED
    return await getattr(client, method)(params)


async def wordpress_get_site_info(params: dict[str, Any]) -> dict[str, Any]:
    return await _tool("get_site_info", params)


async def wordpress_get_posts(params: dict[str, Any]) -> dict[str, Any]:
    return await _tool("get_posts", params)


async def wordpress_get_pages(params: dict[str, Any]) -> dict[str, Any]:
    return await _tool("get_pages", params)


async def wordpress_update_post(params: dict[str, Any]) -> dict[str, Any]:
    return await _tool("update_post", params)


async def wordpress_create_post(params: dict[str, Any]) -> dict[str, Any]:
    return await _tool("create_post", params)


async def wordpress_search(params: dict[str, Any]) -> dict[str, Any]:
    return await _tool("search", params)


def register_wordpress_tools(bridge: Any) -> None:
    """Register WordPress MCP tools on the OCCP bridge (overrides legacy)."""
    bridge.register("wordpress.get_site_info", wordpress_get_site_info)
    bridge.register("wordpress.get_posts", wordpress_get_posts)
    bridge.register("wordpress.get_pages", wordpress_get_pages)
    bridge.register("wordpress.update_post", wordpress_update_post)
    bridge.register("wordpress.create_post", wordpress_create_post)
    bridge.register("wordpress.search", wordpress_search)
    logger.info("WordPress MCP tools registered (6 tools)")
