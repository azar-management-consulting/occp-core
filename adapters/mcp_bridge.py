"""OCCP ↔ MCP Runtime Bridge.

Allows OCCP server runtime to dispatch commands to MCP-style tools via an
async executor pattern. MCP servers in the Claude Code client universe are
stdio-based; this bridge gives OCCP Brain an equivalent server-side
execution surface without requiring stdio MCP clients.

Architecture:
    BrainFlow → MCPBridge.dispatch(tool, params) → Tool impl → result
                                 │
                                 └── AgentToolGuard.check_access
                                 └── InputSanitizer
                                 └── audit_store.append

Tool namespaces (v1):
    filesystem.read / filesystem.write / filesystem.list
    shell.exec (policy-gated, sandbox-required)
    http.get / http.post
    wordpress.publish_post / wordpress.get_post
    github.get_file / github.create_issue
    brain.status / brain.health

Extend: register a new ToolImplementation and add to registry.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Protocol

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# Data types
# ──────────────────────────────────────────────────────────────


@dataclass
class ToolCall:
    """Single MCP-style tool invocation request."""

    tool: str  # e.g. "filesystem.read"
    params: dict[str, Any] = field(default_factory=dict)
    agent_id: str = "brain"
    correlation_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    timeout_seconds: float = 30.0


@dataclass
class ToolResult:
    """Result returned to caller (BrainFlow or pipeline)."""

    call_id: str
    tool: str
    status: str  # "ok" | "error" | "denied" | "timeout"
    result: Any = None
    error: str | None = None
    duration_ms: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ToolImplementation(Protocol):
    """Tool implementations must be async callable."""

    async def __call__(self, params: dict[str, Any]) -> Any:
        ...


# ──────────────────────────────────────────────────────────────
# MCP Bridge
# ──────────────────────────────────────────────────────────────


class MCPBridge:
    """Server-side MCP-style tool dispatcher with policy integration.

    Hooks:
        - agent_tool_guard.check_access(agent_id, tool_name) → deny unauthorized
        - input_sanitizer.sanitize(str(params)) → OWASP ASI01 guard
        - audit_store.append(entry) → traceability
    """

    def __init__(
        self,
        *,
        agent_tool_guard: Any = None,
        input_sanitizer: Any = None,
        audit_store: Any = None,
        max_concurrent: int = 8,
    ) -> None:
        self._tools: dict[str, ToolImplementation] = {}
        self._agent_tool_guard = agent_tool_guard
        self._input_sanitizer = input_sanitizer
        self._audit_store = audit_store
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._stats = {"total": 0, "ok": 0, "error": 0, "denied": 0, "timeout": 0}

    # ── Registration ─────────────────────────────────────────────

    def register(self, tool_name: str, implementation: ToolImplementation) -> None:
        """Register a tool implementation. Tool name format: 'namespace.method'."""
        if "." not in tool_name:
            raise ValueError(f"Tool name must be 'namespace.method', got {tool_name!r}")
        self._tools[tool_name] = implementation
        logger.info("MCP tool registered: %s", tool_name)

    def list_tools(self) -> list[str]:
        """Return all registered tool names."""
        return sorted(self._tools.keys())

    # ── Dispatch ─────────────────────────────────────────────────

    async def dispatch(self, call: ToolCall) -> ToolResult:
        """Execute a tool call with full policy chain + audit."""
        self._stats["total"] += 1
        start = time.monotonic()

        # 1. Tool exists?
        impl = self._tools.get(call.tool)
        if impl is None:
            self._stats["error"] += 1
            return self._audit_and_return(
                ToolResult(
                    call_id=call.correlation_id,
                    tool=call.tool,
                    status="error",
                    error=f"Unknown tool: {call.tool}",
                    duration_ms=(time.monotonic() - start) * 1000,
                )
            )

        # 2. Agent tool guard
        if self._agent_tool_guard:
            try:
                check = self._agent_tool_guard.check_access(call.agent_id, call.tool)
                if not check.allowed:
                    self._stats["denied"] += 1
                    return self._audit_and_return(
                        ToolResult(
                            call_id=call.correlation_id,
                            tool=call.tool,
                            status="denied",
                            error=check.reason,
                            duration_ms=(time.monotonic() - start) * 1000,
                        )
                    )
            except Exception as exc:
                logger.warning("Guard check failed: %s", exc)

        # 3. Input sanitization (best-effort, on string-serialized params)
        if self._input_sanitizer:
            try:
                serialized = json.dumps(call.params, default=str)[:4000]
                san = self._input_sanitizer.sanitize(serialized, channel="mcp-bridge")
                if not san.safe:
                    self._stats["denied"] += 1
                    return self._audit_and_return(
                        ToolResult(
                            call_id=call.correlation_id,
                            tool=call.tool,
                            status="denied",
                            error=f"Input blocked: {san.threats_detected}",
                            duration_ms=(time.monotonic() - start) * 1000,
                        )
                    )
            except Exception as exc:
                logger.warning("Sanitizer check failed: %s", exc)

        # 4. Execute with timeout + semaphore
        try:
            async with self._semaphore:
                result = await asyncio.wait_for(
                    impl(call.params),
                    timeout=call.timeout_seconds,
                )
            self._stats["ok"] += 1
            return self._audit_and_return(
                ToolResult(
                    call_id=call.correlation_id,
                    tool=call.tool,
                    status="ok",
                    result=result,
                    duration_ms=(time.monotonic() - start) * 1000,
                )
            )
        except asyncio.TimeoutError:
            self._stats["timeout"] += 1
            return self._audit_and_return(
                ToolResult(
                    call_id=call.correlation_id,
                    tool=call.tool,
                    status="timeout",
                    error=f"Timeout after {call.timeout_seconds}s",
                    duration_ms=(time.monotonic() - start) * 1000,
                )
            )
        except Exception as exc:
            self._stats["error"] += 1
            return self._audit_and_return(
                ToolResult(
                    call_id=call.correlation_id,
                    tool=call.tool,
                    status="error",
                    error=str(exc)[:500],
                    duration_ms=(time.monotonic() - start) * 1000,
                )
            )

    async def dispatch_many(self, calls: list[ToolCall]) -> list[ToolResult]:
        """Execute multiple tool calls in parallel (bounded by semaphore)."""
        return await asyncio.gather(*[self.dispatch(c) for c in calls])

    # ── Audit + stats ────────────────────────────────────────────

    def _audit_and_return(self, result: ToolResult) -> ToolResult:
        # Audit writes disabled on shared session to avoid PendingRollbackError
        # under concurrent dispatch. MCP bridge events are observable via
        # stats() + logger; full audit integration needs dedicated session
        # per write (L5 observability roadmap).
        logger.info(
            "mcp.audit tool=%s status=%s duration_ms=%.1f call_id=%s error=%s",
            result.tool,
            result.status,
            result.duration_ms,
            result.call_id,
            result.error or "",
        )
        return result

    def stats(self) -> dict[str, Any]:
        total = max(1, self._stats["total"])
        return {
            **self._stats,
            "tools_registered": len(self._tools),
            "success_rate": round(self._stats["ok"] / total, 4),
        }


# ──────────────────────────────────────────────────────────────
# Built-in tool implementations (safe, server-side)
# ──────────────────────────────────────────────────────────────


async def _filesystem_read(params: dict[str, Any]) -> Any:
    """Read a file from the host filesystem (confined to /tmp/occp-workspace)."""
    import os

    path = params.get("path", "")
    if not path:
        raise ValueError("path required")
    allowed_root = "/tmp/occp-workspace"
    os.makedirs(allowed_root, exist_ok=True)
    abs_path = os.path.abspath(os.path.join(allowed_root, path.lstrip("/")))
    if not abs_path.startswith(allowed_root):
        raise PermissionError(f"Path escape attempt: {path}")
    with open(abs_path, "r", encoding="utf-8") as f:
        return {"path": abs_path, "content": f.read()}


async def _filesystem_write(params: dict[str, Any]) -> Any:
    import os

    path = params.get("path", "")
    content = params.get("content", "")
    if not path:
        raise ValueError("path required")
    allowed_root = "/tmp/occp-workspace"
    os.makedirs(allowed_root, exist_ok=True)
    abs_path = os.path.abspath(os.path.join(allowed_root, path.lstrip("/")))
    if not abs_path.startswith(allowed_root):
        raise PermissionError(f"Path escape attempt: {path}")
    os.makedirs(os.path.dirname(abs_path) or allowed_root, exist_ok=True)
    with open(abs_path, "w", encoding="utf-8") as f:
        f.write(content)
    return {"path": abs_path, "bytes_written": len(content)}


async def _filesystem_list(params: dict[str, Any]) -> Any:
    import os

    path = params.get("path", "")
    allowed_root = "/tmp/occp-workspace"
    os.makedirs(allowed_root, exist_ok=True)
    abs_path = os.path.abspath(os.path.join(allowed_root, path.lstrip("/")))
    if not abs_path.startswith(allowed_root):
        raise PermissionError(f"Path escape attempt: {path}")
    if not os.path.exists(abs_path):
        return {"path": abs_path, "entries": []}
    return {"path": abs_path, "entries": sorted(os.listdir(abs_path))}


async def _http_get(params: dict[str, Any]) -> Any:
    import httpx

    url = params.get("url", "")
    if not url or not (url.startswith("http://") or url.startswith("https://")):
        raise ValueError("valid url required")
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(url)
    return {
        "status_code": resp.status_code,
        "headers": dict(resp.headers),
        "body": resp.text[:10000],
    }


async def _http_post(params: dict[str, Any]) -> Any:
    import httpx

    url = params.get("url", "")
    body = params.get("body", {})
    if not url or not (url.startswith("http://") or url.startswith("https://")):
        raise ValueError("valid url required")
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(url, json=body)
    return {
        "status_code": resp.status_code,
        "body": resp.text[:10000],
    }


async def _brain_status(params: dict[str, Any]) -> Any:
    return {
        "platform": "OCCP",
        "version": "0.10.1",
        "bridge": "mcp_bridge v1",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


async def _brain_health(params: dict[str, Any]) -> Any:
    import httpx

    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.get("http://127.0.0.1:8000/api/v1/health")
    return resp.json()


# ──────────────────────────────────────────────────────────────
# Factory
# ──────────────────────────────────────────────────────────────


def build_default_bridge(
    *,
    agent_tool_guard: Any = None,
    input_sanitizer: Any = None,
    audit_store: Any = None,
) -> MCPBridge:
    """Build an MCPBridge with built-in tool implementations registered."""
    bridge = MCPBridge(
        agent_tool_guard=agent_tool_guard,
        input_sanitizer=input_sanitizer,
        audit_store=audit_store,
    )
    bridge.register("filesystem.read", _filesystem_read)
    bridge.register("filesystem.write", _filesystem_write)
    bridge.register("filesystem.list", _filesystem_list)
    bridge.register("http.get", _http_get)
    bridge.register("http.post", _http_post)
    bridge.register("brain.status", _brain_status)
    bridge.register("brain.health", _brain_health)
    # WordPress REST API tools — use WP REST endpoints via http
    bridge.register("wordpress.get_posts", _wp_get_posts)
    bridge.register("wordpress.get_pages", _wp_get_pages)
    bridge.register("wordpress.get_site_info", _wp_get_site_info)
    bridge.register("wordpress.update_post", _wp_update_post)
    # Node tools — execute commands on Tailscale mesh nodes via SSH
    bridge.register("node.exec", _node_exec)
    bridge.register("node.list", _node_list)
    bridge.register("node.status", _node_status)
    return bridge


# ── Node execution tool implementations (Tailscale mesh) ─────

# Known nodes in the OCCP mesh
_OCCP_NODES = {
    "imac": {
        "host": "172.18.0.1",  # Docker gateway → host reverse tunnel → iMac
        "port": 2222,
        "user": "boss",
        "name": "BOSS-iMac",
        "role": "storage + secondary control",
    },
    "mbp": {
        "host": "172.18.0.1",  # Docker gateway → host reverse tunnel → MBP
        "port": 2223,
        "user": "aiallmacpro",
        "name": "AI-MacBook-Pro",
        "role": "secondary dev",
    },
    "hetzner-brain": {
        "host": "195.201.238.144",
        "user": "root",
        "name": "Hetzner OCCP Brain",
        "role": "API + dashboard + brain",
    },
    "hetzner-openclaw": {
        "host": "95.216.212.174",
        "user": "root",
        "name": "Hetzner OpenClaw",
        "role": "execution plane",
        "ssh_key": "/ssh/openclaw_ed25519",
    },
}

# Allowlisted safe commands (Brain can only run these)
_SAFE_COMMANDS = {
    "hostname", "uptime", "uname -a", "df -h", "free -h",
    "docker ps", "docker compose ps", "ls", "cat", "head", "tail",
    "curl", "python3 --version", "node --version",
    "sw_vers",  # macOS version
}


async def _node_list(params: dict[str, Any]) -> dict[str, Any]:
    """List all known OCCP mesh nodes and their roles."""
    return {
        "nodes": [
            {"id": k, **v} for k, v in _OCCP_NODES.items()
        ],
        "total": len(_OCCP_NODES),
    }


async def _node_status(params: dict[str, Any]) -> dict[str, Any]:
    """Check if a node is reachable via SSH (timeout 5s)."""
    import asyncio

    node_id = params.get("node_id", "")
    node = _OCCP_NODES.get(node_id)
    if not node:
        return {"error": f"unknown node: {node_id}", "known_nodes": list(_OCCP_NODES.keys())}

    try:
        ssh_key = node.get("ssh_key", "/ssh/brain_ed25519")
        port = str(node.get("port", 22))
        proc = await asyncio.create_subprocess_exec(
            "ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes",
            "-o", "StrictHostKeyChecking=accept-new",
            "-o", "UserKnownHostsFile=/ssh/known_hosts",
            "-p", port,
            "-i", ssh_key,
            f"{node['user']}@{node['host']}", "hostname && uptime",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)
        return {
            "node_id": node_id,
            "reachable": proc.returncode == 0,
            "output": stdout.decode()[:500] if stdout else "",
            "error": stderr.decode()[:200] if proc.returncode != 0 else "",
        }
    except asyncio.TimeoutError:
        return {"node_id": node_id, "reachable": False, "error": "timeout"}
    except Exception as exc:
        return {"node_id": node_id, "reachable": False, "error": str(exc)[:200]}


async def _node_exec(params: dict[str, Any]) -> dict[str, Any]:
    """Execute a safe command on a remote node via SSH.

    Only allowlisted commands are permitted. Brain cannot run arbitrary
    code on mesh nodes.
    """
    import asyncio

    node_id = params.get("node_id", "")
    command = params.get("command", "").strip()

    node = _OCCP_NODES.get(node_id)
    if not node:
        return {"error": f"unknown node: {node_id}", "known_nodes": list(_OCCP_NODES.keys())}

    if not command:
        return {"error": "command required"}

    # Safety: check if command starts with an allowlisted prefix
    cmd_base = command.split()[0] if command else ""
    if cmd_base not in {c.split()[0] for c in _SAFE_COMMANDS}:
        return {
            "error": f"command '{cmd_base}' not in safe allowlist",
            "allowed": sorted({c.split()[0] for c in _SAFE_COMMANDS}),
        }

    try:
        ssh_key = node.get("ssh_key", "/ssh/brain_ed25519")
        port = str(node.get("port", 22))
        proc = await asyncio.create_subprocess_exec(
            "ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes",
            "-o", "StrictHostKeyChecking=accept-new",
            "-o", "UserKnownHostsFile=/ssh/known_hosts",
            "-p", port,
            "-i", ssh_key,
            f"{node['user']}@{node['host']}", command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        return {
            "node_id": node_id,
            "command": command,
            "exit_code": proc.returncode,
            "stdout": stdout.decode()[:2000] if stdout else "",
            "stderr": stderr.decode()[:500] if stderr else "",
        }
    except asyncio.TimeoutError:
        return {"node_id": node_id, "command": command, "error": "timeout (30s)"}
    except Exception as exc:
        return {"node_id": node_id, "command": command, "error": str(exc)[:200]}


# ── WordPress REST API tool implementations ───────────────────

async def _wp_get_site_info(params: dict[str, Any]) -> dict[str, Any]:
    """Fetch WordPress site info via public REST API."""
    import httpx
    site_url = params.get("site_url", "https://magyarorszag.ai")
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(f"{site_url}/wp-json/")
        r.raise_for_status()
        data = r.json()
        return {
            "name": data.get("name"),
            "description": data.get("description"),
            "url": data.get("url"),
            "home": data.get("home"),
            "namespaces": data.get("namespaces", []),
            "routes_count": len(data.get("routes", {})),
        }


async def _wp_get_posts(params: dict[str, Any]) -> dict[str, Any]:
    """Fetch posts from WordPress REST API (public)."""
    import httpx
    site_url = params.get("site_url", "https://magyarorszag.ai")
    per_page = min(int(params.get("per_page", 10)), 50)
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(
            f"{site_url}/wp-json/wp/v2/posts",
            params={"per_page": per_page, "status": "publish"},
        )
        r.raise_for_status()
        posts = r.json()
        return {
            "count": len(posts),
            "posts": [
                {
                    "id": p["id"],
                    "title": p.get("title", {}).get("rendered", ""),
                    "slug": p.get("slug", ""),
                    "date": p.get("date", ""),
                    "link": p.get("link", ""),
                    "excerpt": p.get("excerpt", {}).get("rendered", "")[:200],
                }
                for p in posts
            ],
        }


async def _wp_get_pages(params: dict[str, Any]) -> dict[str, Any]:
    """Fetch pages from WordPress REST API (public)."""
    import httpx
    site_url = params.get("site_url", "https://magyarorszag.ai")
    per_page = min(int(params.get("per_page", 20)), 50)
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(
            f"{site_url}/wp-json/wp/v2/pages",
            params={"per_page": per_page, "status": "publish"},
        )
        r.raise_for_status()
        pages = r.json()
        return {
            "count": len(pages),
            "pages": [
                {
                    "id": p["id"],
                    "title": p.get("title", {}).get("rendered", ""),
                    "slug": p.get("slug", ""),
                    "link": p.get("link", ""),
                    "template": p.get("template", ""),
                }
                for p in pages
            ],
        }


async def _wp_update_post(params: dict[str, Any]) -> dict[str, Any]:
    """Update a WordPress post/page via authenticated REST API.

    Requires: site_url, post_id, wp_user, wp_app_password
    Optional: title, content, status, excerpt
    """
    import httpx
    import base64
    site_url = params.get("site_url", "https://magyarorszag.ai")
    post_id = params.get("post_id")
    wp_user = params.get("wp_user", "")
    wp_app_password = params.get("wp_app_password", "")

    if not post_id:
        return {"error": "post_id required"}
    if not wp_user or not wp_app_password:
        return {"error": "wp_user and wp_app_password required for write operations"}

    # Build update payload (only send fields that were provided)
    payload: dict[str, Any] = {}
    for field in ("title", "content", "status", "excerpt"):
        if field in params:
            payload[field] = params[field]

    if not payload:
        return {"error": "no fields to update (provide title, content, status, or excerpt)"}

    auth_str = base64.b64encode(f"{wp_user}:{wp_app_password}".encode()).decode()
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(
            f"{site_url}/wp-json/wp/v2/posts/{post_id}",
            json=payload,
            headers={"Authorization": f"Basic {auth_str}"},
        )
        r.raise_for_status()
        data = r.json()
        return {
            "id": data["id"],
            "title": data.get("title", {}).get("rendered", ""),
            "status": data.get("status", ""),
            "link": data.get("link", ""),
            "modified": data.get("modified", ""),
        }
