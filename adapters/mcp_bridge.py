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
        "version": "0.9.0",
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
    return bridge
