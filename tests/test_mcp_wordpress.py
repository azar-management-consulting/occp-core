"""Tests for adapters.mcp_wordpress (httpx.MockTransport pattern)."""

from __future__ import annotations

import base64
import json
from typing import Any, Callable

import httpx
import pytest


# ──────────────────────────────────────────────────────────────
# Helpers (mirrored from test_mcp_adapters.py)
# ──────────────────────────────────────────────────────────────


class _Captured:
    def __init__(self) -> None:
        self.request: httpx.Request | None = None


def _patch_async_client(
    monkeypatch: pytest.MonkeyPatch,
    handler: Callable[[httpx.Request], httpx.Response],
    captured: _Captured,
) -> None:
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


def _set_single_site_env(monkeypatch: pytest.MonkeyPatch, *, url: str = "https://azar.hu") -> None:
    """Install one azar site via OCCP_WP_SITES JSON; clear per-slug fallbacks."""
    monkeypatch.setenv(
        "OCCP_WP_SITES",
        json.dumps(
            [
                {
                    "slug": "azar",
                    "url": url,
                    "user": "admin",
                    "app_password": "abcd efgh ijkl mnop qrst uvwx",
                }
            ]
        ),
    )
    # Make sure no stray per-slug env var leaks in.
    for k in list(__import__("os").environ):
        if k.startswith("OCCP_WP_") and k != "OCCP_WP_SITES":
            monkeypatch.delenv(k, raising=False)


# ──────────────────────────────────────────────────────────────
# 1. HTTPS-only guard
# ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_https_only_guard_rejects_http(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_single_site_env(monkeypatch, url="http://azar.hu")
    from adapters.mcp_wordpress import wordpress_get_site_info

    result = await wordpress_get_site_info({"site_slug": "azar"})
    assert result == {"error": "HTTPS-only: http:// sites are rejected"}


# ──────────────────────────────────────────────────────────────
# 2. get_site_info dispatches correctly with Basic auth
# ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_site_info_dispatches_basic_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_single_site_env(monkeypatch)

    captured = _Captured()
    _patch_async_client(
        monkeypatch,
        lambda req: _json_response(
            {
                "name": "Azar",
                "description": "AMC site",
                "url": "https://azar.hu",
                "home": "https://azar.hu",
                "namespaces": ["wp/v2"],
                "routes": {"/": {}, "/wp/v2/posts": {}},
            }
        ),
        captured,
    )

    from adapters.mcp_wordpress import wordpress_get_site_info

    result = await wordpress_get_site_info({"site_slug": "azar"})

    assert captured.request is not None
    assert captured.request.method == "GET"
    assert str(captured.request.url) == "https://azar.hu/wp-json/"

    expected = base64.b64encode(b"admin:abcd efgh ijkl mnop qrst uvwx").decode()
    assert captured.request.headers["Authorization"] == f"Basic {expected}"
    assert result["name"] == "Azar"
    assert result["routes_count"] == 2


# ──────────────────────────────────────────────────────────────
# 3. get_posts returns parsed list
# ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_posts_returns_parsed_list(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_single_site_env(monkeypatch)

    captured = _Captured()
    _patch_async_client(
        monkeypatch,
        lambda req: _json_response(
            [
                {
                    "id": 1,
                    "title": {"rendered": "Hello"},
                    "slug": "hello",
                    "date": "2026-04-20T10:00:00",
                    "status": "publish",
                    "link": "https://azar.hu/hello",
                },
                {
                    "id": 2,
                    "title": {"rendered": "World"},
                    "slug": "world",
                    "date": "2026-04-21T10:00:00",
                    "status": "publish",
                    "link": "https://azar.hu/world",
                },
            ]
        ),
        captured,
    )

    from adapters.mcp_wordpress import wordpress_get_posts

    result = await wordpress_get_posts({"site_slug": "azar", "per_page": 5})

    assert captured.request is not None
    assert captured.request.method == "GET"
    assert captured.request.url.path == "/wp-json/wp/v2/posts"
    assert captured.request.url.params["per_page"] == "5"
    assert captured.request.url.params["status"] == "publish"
    assert result["count"] == 2
    assert result["posts"][0]["id"] == 1
    assert result["posts"][0]["title"] == "Hello"
    assert result["posts"][1]["slug"] == "world"


# ──────────────────────────────────────────────────────────────
# 4. create_post sends title/content via POST
# ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_post_sends_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_single_site_env(monkeypatch)

    captured = _Captured()
    _patch_async_client(
        monkeypatch,
        lambda req: _json_response(
            {
                "id": 99,
                "title": {"rendered": "New"},
                "status": "draft",
                "link": "https://azar.hu/?p=99",
            }
        ),
        captured,
    )

    from adapters.mcp_wordpress import wordpress_create_post

    result = await wordpress_create_post(
        {
            "site_slug": "azar",
            "title": "New",
            "content": "<p>Body</p>",
            "status": "draft",
        }
    )

    assert captured.request is not None
    assert captured.request.method == "POST"
    assert captured.request.url.path == "/wp-json/wp/v2/posts"
    body = json.loads(captured.request.content.decode())
    assert body == {"title": "New", "content": "<p>Body</p>", "status": "draft"}
    assert result["id"] == 99
    assert result["status"] == "draft"


# ──────────────────────────────────────────────────────────────
# 5. Missing env → wordpress-not-configured
# ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_missing_env_returns_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    for k in list(__import__("os").environ):
        if k.startswith("OCCP_WP_"):
            monkeypatch.delenv(k, raising=False)

    from adapters.mcp_wordpress import wordpress_get_posts

    result = await wordpress_get_posts({"site_slug": "azar"})
    assert result == {"error": "wordpress-not-configured"}


# ──────────────────────────────────────────────────────────────
# 6. Unknown site_slug returns error
# ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_unknown_site_slug_returns_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_single_site_env(monkeypatch)
    from adapters.mcp_wordpress import wordpress_get_posts

    result = await wordpress_get_posts({"site_slug": "nosuch"})
    assert result["error"].startswith("unknown site_slug")
    assert "azar" in result["known"]
