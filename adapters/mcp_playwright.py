"""Playwright MCP client adapter.

Thin wrapper around the upcoming Playwright MCP sidecar. Real browser
automation requires a headful/headless runtime — until that sidecar is
wired, we expose stubs + a minimal httpx-based text extractor.

All stubbed responses explicitly set {"status": "stub", ...} so callers
can treat them as placeholders.

No env vars required; all browser ops return stub payloads.

FELT: once @playwright/mcp is run as a sidecar service we'll swap the
stubs for ws/http calls into it. Until then extract_text uses httpx +
optional selectolax (if importable) for a usable best-effort path.
"""

from __future__ import annotations

import ipaddress
import logging
import socket
from typing import Any
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 15.0
_MAX_BODY = 4096

# SSRF defense: block all private / link-local / loopback / cloud metadata ranges.
_BLOCKED_NETWORKS = [
    ipaddress.ip_network(n)
    for n in (
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "127.0.0.0/8",
        "169.254.0.0/16",  # link-local + AWS/GCP/Azure IMDS
        "::1/128",
        "fc00::/7",
        "fe80::/10",
        "100.64.0.0/10",  # CGNAT
        "0.0.0.0/8",
    )
]
_BLOCKED_HOSTS = {"localhost", "metadata.google.internal", "metadata.goog"}


def _is_blocked_ip(ip_str: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return True  # refuse malformed
    return any(addr in net for net in _BLOCKED_NETWORKS)


def _validate_url(url: str) -> bool:
    """Validate url: must be http(s), host must resolve to a public IP."""
    if not isinstance(url, str):
        return False
    if not (url.startswith("http://") or url.startswith("https://")):
        return False
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower().strip()
    if not host or host in _BLOCKED_HOSTS:
        return False
    # If host is a literal IP, validate directly.
    try:
        ipaddress.ip_address(host)
        return not _is_blocked_ip(host)
    except ValueError:
        pass
    # Otherwise resolve every A/AAAA and refuse if any is private.
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False
    for family, *_rest, sockaddr in infos:
        ip = sockaddr[0]
        if _is_blocked_ip(ip):
            return False
    return True


async def playwright_goto(params: dict[str, Any]) -> dict[str, Any]:
    url = str(params.get("url", "")).strip()
    if not _validate_url(url):
        return {"status": "error", "error": "valid http(s) url required"}
    return {
        "status": "stub",
        "action": "goto",
        "url": url,
        "note": "No sidecar browser wired; run @playwright/mcp separately and swap this tool for a proxy call.",
    }


async def playwright_screenshot(params: dict[str, Any]) -> dict[str, Any]:
    url = str(params.get("url", "")).strip()
    if not _validate_url(url):
        return {"status": "error", "error": "valid http(s) url required"}
    return {
        "status": "stub",
        "action": "screenshot",
        "url": url,
        "sidecar_hint": "npx @playwright/mcp@latest --port 8931",
        "note": "Stub response: no image captured. Configure sidecar and swap impl.",
    }


async def playwright_extract_text(params: dict[str, Any]) -> dict[str, Any]:
    url = str(params.get("url", "")).strip()
    selector = params.get("selector")
    if not _validate_url(url):
        return {"status": "error", "error": "valid http(s) url required"}

    # follow_redirects=False — each hop could land on a private IP; manual validation only.
    try:
        async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT, follow_redirects=False) as client:
            resp = await client.get(url, headers={"User-Agent": "OCCP-MCP/1.0"})
    except httpx.HTTPError as exc:
        return {"status": "error", "error": f"fetch failed: {exc}"}

    body = resp.text or ""

    # Optional selector-based extraction via selectolax (if installed).
    if selector:
        try:
            from selectolax.parser import HTMLParser  # type: ignore
            tree = HTMLParser(body)
            nodes = tree.css(str(selector))
            texts = [n.text(separator=" ", strip=True) for n in nodes][:50]
            return {
                "status": "ok",
                "url": url,
                "selector": selector,
                "matches": len(texts),
                "texts": texts,
            }
        except ImportError:
            return {
                "status": "stub",
                "url": url,
                "selector": selector,
                "note": "selectolax not installed; returning truncated raw body",
                "body": body[:_MAX_BODY],
            }
        except Exception as exc:  # noqa: BLE001
            return {"status": "error", "error": f"selector parse failed: {exc}"}

    return {
        "status": "ok",
        "url": url,
        "status_code": resp.status_code,
        "body": body[:_MAX_BODY],
    }


def register_playwright_tools(bridge: Any) -> None:
    """Register Playwright MCP tools on the OCCP bridge."""
    bridge.register("playwright.goto", playwright_goto)
    bridge.register("playwright.screenshot", playwright_screenshot)
    bridge.register("playwright.extract_text", playwright_extract_text)
    logger.info("Playwright MCP tools registered (3 tools, goto/screenshot are stubs)")
