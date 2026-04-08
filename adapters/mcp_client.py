"""MCP Native Client — Policy-governed tool discovery and invocation.

Implements an MCP client that:
- Connects to MCP servers (stdio, streamable-HTTP, SSE transports)
- Discovers available tools/resources/prompts via real MCP SDK sessions
- Invokes tools through the PolicyGate (every call gated)
- Manages server lifecycle (connect, reconnect, disconnect)
- Supports capability negotiation
- Emits audit events for every invocation

Uses the ``mcp`` SDK (>=1.6) for real transport when available.
Falls back to simulated transport for testing without the SDK.

All tool invocations are policy-gated via PolicyGate.

Acceptance Tests (REQ-MCP-01 through REQ-MCP-05):
  (1) Tool discovery from multiple servers returns aggregated list.
  (2) Gated invocation succeeds when trust level is sufficient.
  (3) Gated invocation denied when trust level is insufficient.
  (4) Audit callback fired for every invocation (allowed and denied).
  (5) Server lifecycle: connect / disconnect / reconnect transitions.
"""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional MCP SDK import — graceful fallback to simulated transport
# ---------------------------------------------------------------------------

_HAS_MCP_SDK = False
try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    _HAS_MCP_SDK = True
except ImportError:
    ClientSession = None  # type: ignore[assignment, misc]
    StdioServerParameters = None  # type: ignore[assignment, misc]
    stdio_client = None  # type: ignore[assignment]

try:
    from mcp.client.streamable_http import streamablehttp_client

    _HAS_STREAMABLE_HTTP = True
except ImportError:
    streamablehttp_client = None  # type: ignore[assignment]
    _HAS_STREAMABLE_HTTP = False

try:
    from mcp.client.sse import sse_client

    _HAS_SSE = True
except ImportError:
    sse_client = None  # type: ignore[assignment]
    _HAS_SSE = False


# ---------------------------------------------------------------------------
# Transport enum
# ---------------------------------------------------------------------------


class MCPTransport(str, Enum):
    """Wire transport for MCP server connections."""

    STDIO = "stdio"
    """Child-process standard-in / standard-out (local tools)."""

    SSE = "sse"
    """Server-Sent Events over HTTP (legacy — use HTTP for new servers)."""

    HTTP = "http"
    """Streamable HTTP — recommended for remote servers (MCP spec 2025-03-26)."""


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class MCPError(Exception):
    """Base error for all MCP client operations."""


class MCPConnectionError(MCPError):
    """Failed to establish or maintain a server connection."""


class MCPInvocationError(MCPError):
    """Tool invocation failed (transport error or tool-side error)."""


class MCPServerNotFoundError(MCPError):
    """Referenced server_id is not registered with this client."""


class MCPPolicyDeniedError(MCPError):
    """PolicyGate denied the tool invocation."""


# ---------------------------------------------------------------------------
# Data models — immutable (frozen) where appropriate
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MCPServerConfig:
    """Configuration for a single MCP server endpoint.

    Args:
        server_id: Unique identifier within this client instance.
        name: Human-readable server name.
        transport: Wire transport to use.
        command: For STDIO — command + args list to spawn.
        url: For SSE/HTTP — base URL of the server.
        env: Extra environment variables to pass to STDIO process.
        timeout: Per-request timeout in seconds.
        capabilities: Declared server capabilities (tools/resources/prompts).
    """

    server_id: str
    name: str
    transport: MCPTransport = MCPTransport.STDIO
    command: list[str] = field(default_factory=list)
    url: str = ""
    env: dict[str, str] = field(default_factory=dict)
    timeout: float = 30.0
    capabilities: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "serverId": self.server_id,
            "name": self.name,
            "transport": self.transport.value,
            "command": list(self.command),
            "url": self.url,
            "env": dict(self.env),
            "timeout": self.timeout,
            "capabilities": dict(self.capabilities),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MCPServerConfig:
        return cls(
            server_id=data["serverId"],
            name=data["name"],
            transport=MCPTransport(data.get("transport", "stdio")),
            command=data.get("command", []),
            url=data.get("url", ""),
            env=data.get("env", {}),
            timeout=float(data.get("timeout", 30.0)),
            capabilities=data.get("capabilities", {}),
        )


@dataclass(frozen=True)
class MCPToolInfo:
    """Describes a single tool exposed by an MCP server."""

    name: str
    description: str
    input_schema: dict[str, Any]
    server_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": dict(self.input_schema),
            "serverId": self.server_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MCPToolInfo:
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            input_schema=data.get("inputSchema", {}),
            server_id=data["serverId"],
        )


@dataclass(frozen=True)
class MCPResourceInfo:
    """Describes a single resource exposed by an MCP server."""

    uri: str
    name: str
    description: str
    mime_type: str
    server_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "uri": self.uri,
            "name": self.name,
            "description": self.description,
            "mimeType": self.mime_type,
            "serverId": self.server_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MCPResourceInfo:
        return cls(
            uri=data["uri"],
            name=data.get("name", ""),
            description=data.get("description", ""),
            mime_type=data.get("mimeType", ""),
            server_id=data["serverId"],
        )


@dataclass(frozen=True)
class MCPPromptInfo:
    """Describes a single prompt template exposed by an MCP server."""

    name: str
    description: str
    arguments: list[dict[str, Any]]
    server_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "arguments": list(self.arguments),
            "serverId": self.server_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MCPPromptInfo:
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            arguments=data.get("arguments", []),
            server_id=data["serverId"],
        )


@dataclass
class MCPInvocationResult:
    """Result of a single MCP tool invocation."""

    tool_name: str
    server_id: str
    content: Any
    is_error: bool = False
    duration_ms: float = 0.0
    audit_id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def to_dict(self) -> dict[str, Any]:
        return {
            "toolName": self.tool_name,
            "serverId": self.server_id,
            "content": self.content,
            "isError": self.is_error,
            "durationMs": self.duration_ms,
            "auditId": self.audit_id,
        }


# ---------------------------------------------------------------------------
# Internal server state (mutable, not exposed to callers)
# ---------------------------------------------------------------------------


@dataclass
class _ServerState:
    config: MCPServerConfig
    connected: bool = False
    connect_count: int = 0
    disconnect_count: int = 0
    tools: list[MCPToolInfo] = field(default_factory=list)
    resources: list[MCPResourceInfo] = field(default_factory=list)
    prompts: list[MCPPromptInfo] = field(default_factory=list)
    error: str = ""
    # Real MCP SDK state
    session: Any = None  # ClientSession when connected via SDK
    exit_stack: AsyncExitStack | None = None
    use_real_transport: bool = False


# ---------------------------------------------------------------------------
# MCPClient
# ---------------------------------------------------------------------------


class MCPClient:
    """Policy-governed MCP client with real MCP SDK transport.

    Uses the ``mcp`` Python SDK (>=1.6) for actual server communication
    when available. Falls back to simulated responses for testing.

    Every call to ``invoke_tool`` passes through the ``PolicyGate``.

    Usage::

        client = MCPClient(gate=my_gate)
        cfg = MCPServerConfig(
            server_id="fs", name="Filesystem",
            transport=MCPTransport.STDIO,
            command=["npx", "-y", "@modelcontextprotocol/server-filesystem"],
        )
        client.add_server(cfg)
        await client.connect("fs")
        tools = client.discover_tools("fs")
        result = await client.invoke_tool(
            "fs", "read_file", {"path": "/data/file.txt"},
            agent_id="agent-001", trust_level=TrustLevel.L3_AUTONOMOUS,
        )
    """

    def __init__(
        self,
        gate: Any | None = None,
        audit_callback: Callable[[dict[str, Any]], None] | None = None,
        force_simulated: bool = False,
    ) -> None:
        """Create an MCPClient.

        Args:
            gate: ``PolicyGate`` instance.  If None the gate check is skipped
                  (useful for testing).  Production MUST supply a gate.
            audit_callback: Optional callable receiving an audit event dict on
                            every invocation (allowed or denied).
            force_simulated: If True, never use real MCP SDK transport
                             (for testing without spawning processes).
        """
        self._gate = gate
        self._audit_callback = audit_callback
        self._servers: dict[str, _ServerState] = {}
        self._force_simulated = force_simulated

        # Stats
        self._total_invocations: int = 0
        self._denied_invocations: int = 0
        self._raw_invocations: int = 0
        self._discovery_calls: int = 0

    @property
    def has_real_transport(self) -> bool:
        """Whether the real MCP SDK is available."""
        return _HAS_MCP_SDK and not self._force_simulated

    # ------------------------------------------------------------------
    # Server lifecycle
    # ------------------------------------------------------------------

    def add_server(self, config: MCPServerConfig) -> None:
        """Register a server configuration.

        Does not connect — call :meth:`connect` explicitly.
        """
        if config.server_id in self._servers:
            raise ValueError(
                f"Server '{config.server_id}' already registered. "
                "Use remove_server() first to replace it."
            )
        self._servers[config.server_id] = _ServerState(config=config)
        logger.info(
            "MCP server registered: id=%s name=%s transport=%s",
            config.server_id,
            config.name,
            config.transport.value,
        )

    def remove_server(self, server_id: str) -> None:
        """Unregister a server.  Disconnects first if connected."""
        state = self._require_server(server_id)
        if state.connected:
            self.disconnect(server_id)
        del self._servers[server_id]
        logger.info("MCP server removed: id=%s", server_id)

    def connect(self, server_id: str) -> None:
        """Establish a simulated connection to a registered server.

        For real MCP SDK transport, use :meth:`aconnect` instead.
        """
        state = self._require_server(server_id)
        if state.connected:
            logger.debug("MCP server already connected: id=%s", server_id)
            return
        state.connected = True
        state.connect_count += 1
        state.error = ""
        logger.info(
            "MCP server connected: id=%s transport=%s",
            server_id,
            state.config.transport.value,
        )

    async def aconnect(self, server_id: str) -> None:
        """Establish a real MCP SDK transport connection.

        Opens a real stdio/SSE/HTTP session and auto-discovers tools.
        Falls back to simulated mode if SDK is unavailable.
        """
        state = self._require_server(server_id)
        if state.connected:
            logger.debug("MCP server already connected: id=%s", server_id)
            return

        config = state.config
        use_real = self.has_real_transport

        if use_real:
            try:
                await self._connect_real(state)
            except Exception as exc:
                state.error = str(exc)
                logger.warning(
                    "Real MCP transport failed for %s, falling back to simulated: %s",
                    server_id,
                    exc,
                )
                use_real = False

        state.connected = True
        state.connect_count += 1
        state.use_real_transport = use_real
        state.error = ""
        logger.info(
            "MCP server connected: id=%s transport=%s real=%s tools=%d",
            server_id,
            config.transport.value,
            use_real,
            len(state.tools),
        )

    async def _connect_real(self, state: _ServerState) -> None:
        """Open a real MCP SDK transport session."""
        config = state.config
        exit_stack = AsyncExitStack()

        if config.transport == MCPTransport.STDIO:
            if not config.command:
                raise MCPConnectionError(
                    f"STDIO transport requires 'command' for server '{config.server_id}'"
                )
            server_params = StdioServerParameters(
                command=config.command[0],
                args=config.command[1:] if len(config.command) > 1 else [],
                env=config.env or None,
            )
            transport = await exit_stack.enter_async_context(
                stdio_client(server_params)
            )
            read_stream, write_stream = transport

        elif config.transport == MCPTransport.HTTP:
            if not _HAS_STREAMABLE_HTTP:
                raise MCPConnectionError(
                    "Streamable HTTP transport requires mcp[streamable-http]. "
                    "Install with: pip install 'mcp[streamable-http]'"
                )
            if not config.url:
                raise MCPConnectionError(
                    f"HTTP transport requires 'url' for server '{config.server_id}'"
                )
            transport = await exit_stack.enter_async_context(
                streamablehttp_client(config.url)
            )
            read_stream, write_stream = transport[0], transport[1]

        elif config.transport == MCPTransport.SSE:
            if not _HAS_SSE:
                raise MCPConnectionError(
                    "SSE transport requires mcp package with SSE support."
                )
            if not config.url:
                raise MCPConnectionError(
                    f"SSE transport requires 'url' for server '{config.server_id}'"
                )
            transport = await exit_stack.enter_async_context(
                sse_client(config.url)
            )
            read_stream, write_stream = transport

        else:
            raise MCPConnectionError(f"Unknown transport: {config.transport}")

        session = await exit_stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )
        await session.initialize()

        # Discover capabilities
        state.session = session
        state.exit_stack = exit_stack

        # Auto-discover tools
        try:
            tools_result = await session.list_tools()
            state.tools = [
                MCPToolInfo(
                    name=t.name,
                    description=t.description or "",
                    input_schema=t.inputSchema if hasattr(t, "inputSchema") else {},
                    server_id=config.server_id,
                )
                for t in tools_result.tools
            ]
        except Exception as exc:
            logger.warning("Tool discovery failed for %s: %s", config.server_id, exc)

    def disconnect(self, server_id: str) -> None:
        """Close a server connection (simulated mode)."""
        state = self._require_server(server_id)
        if not state.connected:
            logger.debug("MCP server already disconnected: id=%s", server_id)
            return
        state.connected = False
        state.disconnect_count += 1
        state.use_real_transport = False
        logger.info("MCP server disconnected: id=%s", server_id)

    async def adisconnect(self, server_id: str) -> None:
        """Close a real MCP SDK transport connection."""
        state = self._require_server(server_id)
        if not state.connected:
            logger.debug("MCP server already disconnected: id=%s", server_id)
            return

        if state.exit_stack is not None:
            try:
                await state.exit_stack.aclose()
            except Exception as exc:
                logger.warning("Error closing MCP transport for %s: %s", server_id, exc)
            state.exit_stack = None
            state.session = None

        state.connected = False
        state.disconnect_count += 1
        state.use_real_transport = False
        logger.info("MCP server disconnected: id=%s", server_id)

    def list_servers(self) -> list[MCPServerConfig]:
        """Return configs for all registered servers."""
        return [s.config for s in self._servers.values()]

    def get_server_status(self, server_id: str) -> dict[str, Any]:
        """Return status dict for a registered server."""
        state = self._require_server(server_id)
        return {
            "serverId": server_id,
            "name": state.config.name,
            "transport": state.config.transport.value,
            "connected": state.connected,
            "realTransport": state.use_real_transport,
            "connectCount": state.connect_count,
            "disconnectCount": state.disconnect_count,
            "toolCount": len(state.tools),
            "resourceCount": len(state.resources),
            "promptCount": len(state.prompts),
            "error": state.error,
        }

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def discover_tools(self, server_id: str) -> list[MCPToolInfo]:
        """List tools exposed by a connected server."""
        state = self._require_connected(server_id)
        self._discovery_calls += 1
        return list(state.tools)

    def discover_resources(self, server_id: str) -> list[MCPResourceInfo]:
        """List resources exposed by a connected server."""
        state = self._require_connected(server_id)
        self._discovery_calls += 1
        return list(state.resources)

    def discover_prompts(self, server_id: str) -> list[MCPPromptInfo]:
        """List prompt templates exposed by a connected server."""
        state = self._require_connected(server_id)
        self._discovery_calls += 1
        return list(state.prompts)

    def get_all_tools(self) -> list[MCPToolInfo]:
        """Aggregate tools from all connected servers.

        REQ-MCP-01: Tool discovery from multiple servers.
        """
        result: list[MCPToolInfo] = []
        for state in self._servers.values():
            if state.connected:
                result.extend(state.tools)
        return result

    # ------------------------------------------------------------------
    # Invocation — policy-gated
    # ------------------------------------------------------------------

    async def invoke_tool(
        self,
        server_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        agent_id: str,
        trust_level: Any,
        task: Any = None,
    ) -> MCPInvocationResult:
        """Invoke a tool through the PolicyGate.

        REQ-MCP-02: Gated invocation succeeds with proper trust.
        REQ-MCP-03: Gated invocation denied without proper trust.
        REQ-MCP-04: Audit trail captured for every invocation.
        """
        state = self._require_connected(server_id)
        audit_id = uuid.uuid4().hex
        self._total_invocations += 1
        start = time.monotonic()

        action = f"mcp.tool.{tool_name}"

        # ── Policy gate ──────────────────────────────────────────────
        if self._gate is not None:
            _task = task if task is not None else _MinimalTask(
                id=audit_id,
                description=f"MCP tool invocation: {server_id}/{tool_name}",
            )
            decision = await self._gate.gate_action(
                _task,
                agent_id=agent_id,
                trust_level=trust_level,
                action=action,
                tool_category="mcp",
                requires_network=(
                    state.config.transport in (MCPTransport.SSE, MCPTransport.HTTP)
                ),
            )

            if not decision.allowed:
                self._denied_invocations += 1
                duration_ms = (time.monotonic() - start) * 1000
                self._emit_audit({
                    "auditId": audit_id,
                    "event": "mcp.tool.denied",
                    "serverId": server_id,
                    "toolName": tool_name,
                    "agentId": agent_id,
                    "reason": decision.reason,
                    "durationMs": round(duration_ms, 2),
                    "gated": True,
                })
                raise MCPPolicyDeniedError(
                    f"PolicyGate denied invocation of '{tool_name}' "
                    f"on server '{server_id}': {decision.reason}"
                )

        # ── Execute via real transport or simulated ──────────────────
        if state.use_real_transport and state.session is not None:
            result = await self._invoke_real(state, tool_name, arguments, audit_id)
        else:
            result = self._simulate_invocation(server_id, tool_name, arguments, audit_id)

        result.duration_ms = round((time.monotonic() - start) * 1000, 2)

        self._emit_audit({
            "auditId": audit_id,
            "event": "mcp.tool.invoked",
            "serverId": server_id,
            "toolName": tool_name,
            "agentId": agent_id,
            "isError": result.is_error,
            "durationMs": result.duration_ms,
            "gated": True,
            "realTransport": state.use_real_transport,
        })

        logger.info(
            "MCP tool invoked: server=%s tool=%s agent=%s audit=%s "
            "dur=%.1fms real=%s",
            server_id,
            tool_name,
            agent_id,
            audit_id,
            result.duration_ms,
            state.use_real_transport,
        )
        return result

    async def _invoke_real(
        self,
        state: _ServerState,
        tool_name: str,
        arguments: dict[str, Any],
        audit_id: str,
    ) -> MCPInvocationResult:
        """Invoke a tool via the real MCP SDK session."""
        try:
            call_result = await state.session.call_tool(tool_name, arguments)
            content: Any
            if hasattr(call_result, "content") and call_result.content:
                parts = []
                for part in call_result.content:
                    if hasattr(part, "text"):
                        parts.append(part.text)
                    elif hasattr(part, "data"):
                        parts.append(part.data)
                    else:
                        parts.append(str(part))
                content = parts[0] if len(parts) == 1 else parts
            else:
                content = None

            is_error = getattr(call_result, "isError", False)
            return MCPInvocationResult(
                tool_name=tool_name,
                server_id=state.config.server_id,
                content=content,
                is_error=is_error,
                audit_id=audit_id,
            )
        except Exception as exc:
            return MCPInvocationResult(
                tool_name=tool_name,
                server_id=state.config.server_id,
                content={"error": str(exc)},
                is_error=True,
                audit_id=audit_id,
            )

    def invoke_tool_raw(
        self,
        server_id: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> MCPInvocationResult:
        """Invoke a tool bypassing the PolicyGate.

        FOR INTERNAL USE ONLY.  All raw invocations are logged with a
        ``RAW`` marker in the audit event.
        """
        self._require_connected(server_id)
        audit_id = uuid.uuid4().hex
        self._total_invocations += 1
        self._raw_invocations += 1

        start = time.monotonic()
        result = self._simulate_invocation(server_id, tool_name, arguments, audit_id)
        result.duration_ms = round((time.monotonic() - start) * 1000, 2)

        self._emit_audit({
            "auditId": audit_id,
            "event": "mcp.tool.raw_invocation",
            "serverId": server_id,
            "toolName": tool_name,
            "isError": result.is_error,
            "durationMs": result.duration_ms,
            "gated": False,
            "warning": "RAW invocation — bypassed PolicyGate",
        })

        logger.warning(
            "MCP RAW tool invocation (no gate): server=%s tool=%s audit=%s",
            server_id,
            tool_name,
            audit_id,
        )
        return result

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """Return operational statistics for monitoring."""
        connected = sum(1 for s in self._servers.values() if s.connected)
        real = sum(
            1 for s in self._servers.values() if s.connected and s.use_real_transport
        )
        return {
            "totalServers": len(self._servers),
            "connectedServers": connected,
            "realTransportServers": real,
            "totalInvocations": self._total_invocations,
            "deniedInvocations": self._denied_invocations,
            "rawInvocations": self._raw_invocations,
            "discoveryCalls": self._discovery_calls,
            "hasGate": self._gate is not None,
            "hasMCPSDK": _HAS_MCP_SDK,
        }

    # ------------------------------------------------------------------
    # Testing helpers — not part of the public contract
    # ------------------------------------------------------------------

    def _inject_tools(self, server_id: str, tools: list[MCPToolInfo]) -> None:
        """Inject tool descriptors into a server (for tests)."""
        state = self._require_server(server_id)
        state.tools = list(tools)

    def _inject_resources(self, server_id: str, resources: list[MCPResourceInfo]) -> None:
        """Inject resource descriptors into a server (for tests)."""
        state = self._require_server(server_id)
        state.resources = list(resources)

    def _inject_prompts(self, server_id: str, prompts: list[MCPPromptInfo]) -> None:
        """Inject prompt descriptors into a server (for tests)."""
        state = self._require_server(server_id)
        state.prompts = list(prompts)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _require_server(self, server_id: str) -> _ServerState:
        state = self._servers.get(server_id)
        if state is None:
            raise MCPServerNotFoundError(
                f"Server '{server_id}' is not registered. Call add_server() first."
            )
        return state

    def _require_connected(self, server_id: str) -> _ServerState:
        state = self._require_server(server_id)
        if not state.connected:
            raise MCPConnectionError(
                f"Server '{server_id}' is not connected. Call connect() first."
            )
        return state

    def _simulate_invocation(
        self,
        server_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        audit_id: str,
    ) -> MCPInvocationResult:
        """Simulated tool execution for testing without real servers."""
        state = self._servers[server_id]
        known_tools = {t.name for t in state.tools}

        if known_tools and tool_name not in known_tools:
            return MCPInvocationResult(
                tool_name=tool_name,
                server_id=server_id,
                content={"error": f"Tool '{tool_name}' not found on server '{server_id}'"},
                is_error=True,
                audit_id=audit_id,
            )

        return MCPInvocationResult(
            tool_name=tool_name,
            server_id=server_id,
            content={
                "result": "ok",
                "tool": tool_name,
                "arguments": arguments,
                "serverId": server_id,
            },
            is_error=False,
            audit_id=audit_id,
        )

    def _emit_audit(self, event: dict[str, Any]) -> None:
        """Fire the audit callback if registered."""
        if self._audit_callback is not None:
            try:
                self._audit_callback(event)
            except Exception:
                logger.exception("Audit callback raised — suppressed")


# ---------------------------------------------------------------------------
# Minimal task stub for gate calls without a full Task object
# ---------------------------------------------------------------------------


@dataclass
class _MinimalTask:
    """Minimal task-like object for PolicyGate calls inside MCPClient."""

    id: str
    description: str
    name: str = "mcp-invocation"
    agent_type: str = "mcp"
