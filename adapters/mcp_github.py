"""GitHub MCP client adapter.

Exposes a read-oriented subset of the GitHub REST API as MCP-compat tools
on the OCCP MCPBridge.

Env:
    OCCP_GITHUB_TOKEN — PAT or fine-grained token (Bearer)

FELT: pragmatic MCP-compat shim (REST); eventual migration to upstream
github-mcp-server stdio transport is a follow-up.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_API_BASE = "https://api.github.com"
_DEFAULT_TIMEOUT = 15.0


def _token() -> str | None:
    tok = os.getenv("OCCP_GITHUB_TOKEN", "").strip()
    return tok or None


def _headers(tok: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {tok}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "OCCP-MCP-Bridge/1.0",
    }


async def github_search_issues(params: dict[str, Any]) -> dict[str, Any]:
    tok = _token()
    if tok is None:
        return {"error": "github-not-configured"}

    repo = str(params.get("repo", "")).strip()
    query = str(params.get("query", "")).strip()
    state = str(params.get("state", "open")).strip()
    if not repo or "/" not in repo:
        return {"error": "repo required as 'owner/name'"}

    q = f"repo:{repo} state:{state} {query}".strip()
    async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
        resp = await client.get(
            f"{_API_BASE}/search/issues",
            headers=_headers(tok),
            params={"q": q, "per_page": 30},
        )
    if resp.status_code >= 400:
        return {"error": f"github http {resp.status_code}", "body": resp.text[:500]}
    data = resp.json()
    items = data.get("items", [])
    return {
        "total_count": data.get("total_count", 0),
        "items": [
            {
                "number": it.get("number"),
                "title": it.get("title"),
                "state": it.get("state"),
                "url": it.get("html_url"),
                "user": (it.get("user") or {}).get("login"),
            }
            for it in items
        ],
    }


async def github_get_pr(params: dict[str, Any]) -> dict[str, Any]:
    tok = _token()
    if tok is None:
        return {"error": "github-not-configured"}

    repo = str(params.get("repo", "")).strip()
    number = params.get("number")
    if not repo or "/" not in repo:
        return {"error": "repo required as 'owner/name'"}
    if number is None:
        return {"error": "number required"}

    async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
        resp = await client.get(
            f"{_API_BASE}/repos/{repo}/pulls/{int(number)}",
            headers=_headers(tok),
        )
    if resp.status_code >= 400:
        return {"error": f"github http {resp.status_code}", "body": resp.text[:500]}
    pr = resp.json()
    return {
        "number": pr.get("number"),
        "title": pr.get("title"),
        "state": pr.get("state"),
        "merged": pr.get("merged"),
        "draft": pr.get("draft"),
        "head": (pr.get("head") or {}).get("ref"),
        "base": (pr.get("base") or {}).get("ref"),
        "url": pr.get("html_url"),
        "user": (pr.get("user") or {}).get("login"),
        "additions": pr.get("additions"),
        "deletions": pr.get("deletions"),
    }


async def github_list_commits(params: dict[str, Any]) -> dict[str, Any]:
    tok = _token()
    if tok is None:
        return {"error": "github-not-configured"}

    repo = str(params.get("repo", "")).strip()
    if not repo or "/" not in repo:
        return {"error": "repo required as 'owner/name'"}

    q: dict[str, Any] = {"per_page": int(params.get("per_page", 20))}
    if "since" in params and params["since"]:
        q["since"] = params["since"]

    async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
        resp = await client.get(
            f"{_API_BASE}/repos/{repo}/commits",
            headers=_headers(tok),
            params=q,
        )
    if resp.status_code >= 400:
        return {"error": f"github http {resp.status_code}", "body": resp.text[:500]}
    commits = resp.json() or []
    return {
        "count": len(commits),
        "commits": [
            {
                "sha": c.get("sha", "")[:12],
                "message": ((c.get("commit") or {}).get("message") or "").splitlines()[0][:200],
                "author": ((c.get("commit") or {}).get("author") or {}).get("name"),
                "date": ((c.get("commit") or {}).get("author") or {}).get("date"),
                "url": c.get("html_url"),
            }
            for c in commits
        ],
    }


def register_github_tools(bridge: Any) -> None:
    """Register GitHub MCP tools on the OCCP bridge."""
    bridge.register("github.search_issues", github_search_issues)
    bridge.register("github.get_pr", github_get_pr)
    bridge.register("github.list_commits", github_list_commits)
    logger.info("GitHub MCP tools registered (3 tools)")
