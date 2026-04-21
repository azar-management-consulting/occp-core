"""Supabase MCP client adapter.

Exposes Supabase REST (PostgREST) + RPC endpoints as MCP-compat tools
over the OCCP MCPBridge. Read-only by policy — write SQL is rejected.

Env:
    OCCP_SUPABASE_URL              — e.g. https://xxx.supabase.co
    OCCP_SUPABASE_SERVICE_ROLE_KEY — service role JWT

FELT: pragmatic MCP-compat shim (raw REST); real stdio MCP server is a
follow-up once the upstream Supabase MCP server stabilises.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_WRITE_KEYWORDS = ("INSERT", "UPDATE", "DELETE", "DROP", "TRUNCATE", "ALTER", "CREATE", "GRANT", "REVOKE")
_DEFAULT_TIMEOUT = 15.0


def _config() -> tuple[str, str] | None:
    url = os.getenv("OCCP_SUPABASE_URL", "").rstrip("/")
    key = os.getenv("OCCP_SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        return None
    return url, key


def _headers(key: str) -> dict[str, str]:
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


_WRITE_TOKEN_RE = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|CREATE|GRANT|"
    r"REVOKE|REPLACE|RENAME|COMMENT|COPY|VACUUM|REINDEX|CLUSTER|"
    r"SECURITY|LOCK|EXECUTE|CALL|DO)\b",
    re.IGNORECASE,
)
_STMT_SEP_RE = re.compile(r";\s*\S")  # multi-statement (semicolon followed by more tokens)


def _strip_sql_comments(sql: str) -> str:
    # Remove /* ... */ block comments and -- line comments before scanning.
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    sql = re.sub(r"--[^\n]*", " ", sql)
    return sql


def _is_read_only(sql: str) -> bool:
    """Reject any SQL containing write/DDL tokens OR multi-statement syntax.

    Stricter than prefix match: catches `WITH x AS (...) DELETE ...`,
    leading whitespace/comment bypasses, and stacked queries `SELECT 1; DROP ...`.
    """
    if not sql or not sql.strip():
        return False
    stripped = _strip_sql_comments(sql).strip()
    if _STMT_SEP_RE.search(stripped):
        return False
    if _WRITE_TOKEN_RE.search(stripped):
        return False
    # Must start with SELECT or WITH (read CTE) after normalization.
    head = stripped.upper().lstrip()
    return head.startswith("SELECT") or head.startswith("WITH") or head.startswith("EXPLAIN") or head.startswith("SHOW")


async def supabase_query(params: dict[str, Any]) -> dict[str, Any]:
    cfg = _config()
    if cfg is None:
        return {"error": "supabase-not-configured"}
    url, key = cfg

    sql = str(params.get("sql", "")).strip()
    if not sql:
        return {"error": "sql required"}
    if not _is_read_only(sql):
        return {"error": "write SQL blocked (read-only tool)"}

    payload: dict[str, Any] = {"query": sql}
    if "params" in params:
        payload["params"] = params["params"]

    async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
        resp = await client.post(
            f"{url}/rest/v1/rpc/execute_sql",
            headers=_headers(key),
            json=payload,
        )
    return {
        "status_code": resp.status_code,
        "rows": resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text[:4000],
    }


async def supabase_list_tables(params: dict[str, Any]) -> dict[str, Any]:
    cfg = _config()
    if cfg is None:
        return {"error": "supabase-not-configured"}
    url, key = cfg

    schema = str(params.get("schema", "public"))
    async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
        resp = await client.get(
            f"{url}/rest/v1/information_schema.tables",
            headers=_headers(key),
            params={"select": "table_name,table_schema", "table_schema": f"eq.{schema}"},
        )
    if resp.status_code >= 400:
        return {"error": f"supabase http {resp.status_code}", "body": resp.text[:500]}
    tables = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else []
    return {
        "schema": schema,
        "tables": [t.get("table_name") for t in tables if isinstance(t, dict)],
        "count": len(tables),
    }


async def supabase_describe_table(params: dict[str, Any]) -> dict[str, Any]:
    cfg = _config()
    if cfg is None:
        return {"error": "supabase-not-configured"}
    url, key = cfg

    name = str(params.get("name", "")).strip()
    if not name:
        return {"error": "name required"}
    schema = str(params.get("schema", "public"))

    async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
        resp = await client.get(
            f"{url}/rest/v1/information_schema.columns",
            headers=_headers(key),
            params={
                "select": "column_name,data_type,is_nullable,column_default",
                "table_schema": f"eq.{schema}",
                "table_name": f"eq.{name}",
            },
        )
    if resp.status_code >= 400:
        return {"error": f"supabase http {resp.status_code}", "body": resp.text[:500]}
    cols = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else []
    return {
        "schema": schema,
        "table": name,
        "columns": cols,
        "count": len(cols),
    }


def register_supabase_tools(bridge: Any) -> None:
    """Register Supabase MCP tools on the OCCP bridge."""
    bridge.register("supabase.query", supabase_query)
    bridge.register("supabase.list_tables", supabase_list_tables)
    bridge.register("supabase.describe_table", supabase_describe_table)
    logger.info("Supabase MCP tools registered (3 tools)")
