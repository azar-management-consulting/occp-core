"""Tests for adapters.mcp_client — MCP Native Client (REQ-MCP-01 through REQ-MCP-05).

Covers:
- MCPTransport: enum values
- MCPServerConfig: creation, to_dict/from_dict
- MCPToolInfo: creation, fields, to_dict/from_dict
- MCPResourceInfo: creation, to_dict/from_dict
- MCPPromptInfo: creation, to_dict/from_dict
- MCPInvocationResult: creation, to_dict
- MCPClient: add/remove/connect/disconnect/list servers
- Discovery: discover_tools/resources/prompts from connected servers
- Invocation: invoke_tool with gate, invoke_tool_raw without gate, error handling
- Gating: PolicyGate called for every tool invocation, denied invocations
- Audit: audit callbacks fired on invocation (allowed and denied)
- Errors: all error types raised correctly
- Stats: statistics tracking across operations
- Acceptance tests (REQ-MCP-01 through REQ-MCP-05)
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, call

import pytest

from adapters.mcp_client import (
    MCPClient,
    MCPConnectionError,
    MCPError,
    MCPInvocationError,
    MCPInvocationResult,
    MCPPolicyDeniedError,
    MCPPromptInfo,
    MCPResourceInfo,
    MCPServerConfig,
    MCPServerNotFoundError,
    MCPToolInfo,
    MCPTransport,
    _MinimalTask,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(
    server_id: str = "srv-1",
    name: str = "Test Server",
    transport: MCPTransport = MCPTransport.STDIO,
    command: list[str] | None = None,
    url: str = "",
) -> MCPServerConfig:
    return MCPServerConfig(
        server_id=server_id,
        name=name,
        transport=transport,
        command=command or ["npx", "test-server"],
        url=url,
    )


def _make_tool(
    name: str = "test_tool",
    description: str = "A test tool",
    server_id: str = "srv-1",
    schema: dict[str, Any] | None = None,
) -> MCPToolInfo:
    return MCPToolInfo(
        name=name,
        description=description,
        input_schema=schema or {"type": "object", "properties": {"param": {"type": "string"}}},
        server_id=server_id,
    )


def _make_resource(
    uri: str = "file:///data/file.txt",
    name: str = "Test File",
    server_id: str = "srv-1",
) -> MCPResourceInfo:
    return MCPResourceInfo(
        uri=uri,
        name=name,
        description="A test resource",
        mime_type="text/plain",
        server_id=server_id,
    )


def _make_prompt(
    name: str = "test_prompt",
    server_id: str = "srv-1",
) -> MCPPromptInfo:
    return MCPPromptInfo(
        name=name,
        description="A test prompt",
        arguments=[{"name": "query", "description": "Input query", "required": True}],
        server_id=server_id,
    )


def _allowed_gate() -> MagicMock:
    """Mock gate that always allows."""
    gate = MagicMock()
    decision = MagicMock()
    decision.allowed = True
    decision.reason = ""
    gate.gate_action = AsyncMock(return_value=decision)
    return gate


def _denied_gate(reason: str = "trust denied") -> MagicMock:
    """Mock gate that always denies."""
    gate = MagicMock()
    decision = MagicMock()
    decision.allowed = False
    decision.reason = reason
    gate.gate_action = AsyncMock(return_value=decision)
    return gate


# ---------------------------------------------------------------------------
# TestMCPTransport
# ---------------------------------------------------------------------------


class TestMCPTransport:
    def test_stdio_value(self) -> None:
        assert MCPTransport.STDIO.value == "stdio"

    def test_sse_value(self) -> None:
        assert MCPTransport.SSE.value == "sse"

    def test_http_value(self) -> None:
        assert MCPTransport.HTTP.value == "http"

    def test_is_str_enum(self) -> None:
        assert isinstance(MCPTransport.STDIO, str)

    def test_all_three_variants(self) -> None:
        variants = {t.value for t in MCPTransport}
        assert variants == {"stdio", "sse", "http"}


# ---------------------------------------------------------------------------
# TestMCPServerConfig
# ---------------------------------------------------------------------------


class TestMCPServerConfig:
    def test_create_minimal(self) -> None:
        cfg = MCPServerConfig(server_id="s1", name="Server One")
        assert cfg.server_id == "s1"
        assert cfg.name == "Server One"
        assert cfg.transport == MCPTransport.STDIO
        assert cfg.command == []
        assert cfg.url == ""
        assert cfg.timeout == 30.0

    def test_create_full(self) -> None:
        cfg = MCPServerConfig(
            server_id="s2",
            name="Remote",
            transport=MCPTransport.SSE,
            url="http://localhost:8080/sse",
            env={"TOKEN": "abc"},
            timeout=60.0,
            capabilities={"tools": True},
        )
        assert cfg.transport == MCPTransport.SSE
        assert cfg.url == "http://localhost:8080/sse"
        assert cfg.env == {"TOKEN": "abc"}

    def test_frozen(self) -> None:
        cfg = MCPServerConfig(server_id="s1", name="N")
        with pytest.raises(AttributeError):
            cfg.server_id = "other"  # type: ignore[misc]

    def test_to_dict(self) -> None:
        cfg = _make_config()
        d = cfg.to_dict()
        assert d["serverId"] == "srv-1"
        assert d["name"] == "Test Server"
        assert d["transport"] == "stdio"

    def test_from_dict_roundtrip(self) -> None:
        cfg = _make_config(server_id="fs", name="Filesystem", transport=MCPTransport.HTTP)
        restored = MCPServerConfig.from_dict(cfg.to_dict())
        assert restored.server_id == "fs"
        assert restored.transport == MCPTransport.HTTP

    def test_from_dict_defaults(self) -> None:
        cfg = MCPServerConfig.from_dict({"serverId": "x", "name": "X"})
        assert cfg.transport == MCPTransport.STDIO
        assert cfg.timeout == 30.0


# ---------------------------------------------------------------------------
# TestMCPToolInfo
# ---------------------------------------------------------------------------


class TestMCPToolInfo:
    def test_create(self) -> None:
        tool = _make_tool()
        assert tool.name == "test_tool"
        assert tool.server_id == "srv-1"
        assert "properties" in tool.input_schema

    def test_frozen(self) -> None:
        tool = _make_tool()
        with pytest.raises(AttributeError):
            tool.name = "other"  # type: ignore[misc]

    def test_to_dict(self) -> None:
        tool = _make_tool(name="read_file", server_id="fs")
        d = tool.to_dict()
        assert d["name"] == "read_file"
        assert d["serverId"] == "fs"
        assert "inputSchema" in d

    def test_from_dict_roundtrip(self) -> None:
        tool = _make_tool(name="write_file", description="Write a file")
        restored = MCPToolInfo.from_dict(tool.to_dict())
        assert restored.name == "write_file"
        assert restored.description == "Write a file"


# ---------------------------------------------------------------------------
# TestMCPResourceInfo
# ---------------------------------------------------------------------------


class TestMCPResourceInfo:
    def test_create(self) -> None:
        res = _make_resource()
        assert res.uri == "file:///data/file.txt"
        assert res.mime_type == "text/plain"

    def test_frozen(self) -> None:
        res = _make_resource()
        with pytest.raises(AttributeError):
            res.uri = "other"  # type: ignore[misc]

    def test_to_dict(self) -> None:
        res = _make_resource(uri="file:///log.txt", name="Log")
        d = res.to_dict()
        assert d["uri"] == "file:///log.txt"
        assert d["name"] == "Log"

    def test_from_dict_roundtrip(self) -> None:
        res = _make_resource()
        restored = MCPResourceInfo.from_dict(res.to_dict())
        assert restored.uri == res.uri
        assert restored.server_id == res.server_id


# ---------------------------------------------------------------------------
# TestMCPPromptInfo
# ---------------------------------------------------------------------------


class TestMCPPromptInfo:
    def test_create(self) -> None:
        p = _make_prompt()
        assert p.name == "test_prompt"
        assert len(p.arguments) == 1

    def test_frozen(self) -> None:
        p = _make_prompt()
        with pytest.raises(AttributeError):
            p.name = "other"  # type: ignore[misc]

    def test_to_dict(self) -> None:
        p = _make_prompt(name="summarize")
        d = p.to_dict()
        assert d["name"] == "summarize"
        assert isinstance(d["arguments"], list)

    def test_from_dict_roundtrip(self) -> None:
        p = _make_prompt()
        restored = MCPPromptInfo.from_dict(p.to_dict())
        assert restored.name == p.name


# ---------------------------------------------------------------------------
# TestMCPInvocationResult
# ---------------------------------------------------------------------------


class TestMCPInvocationResult:
    def test_create_success(self) -> None:
        r = MCPInvocationResult(
            tool_name="read_file",
            server_id="fs",
            content={"text": "hello"},
        )
        assert r.is_error is False
        assert r.audit_id != ""

    def test_create_error(self) -> None:
        r = MCPInvocationResult(
            tool_name="bad_tool",
            server_id="fs",
            content={"error": "not found"},
            is_error=True,
        )
        assert r.is_error is True

    def test_to_dict(self) -> None:
        r = MCPInvocationResult(
            tool_name="tool",
            server_id="srv",
            content="output",
            duration_ms=12.5,
        )
        d = r.to_dict()
        assert d["toolName"] == "tool"
        assert d["durationMs"] == 12.5
        assert "auditId" in d

    def test_unique_audit_ids(self) -> None:
        r1 = MCPInvocationResult(tool_name="t", server_id="s", content=None)
        r2 = MCPInvocationResult(tool_name="t", server_id="s", content=None)
        assert r1.audit_id != r2.audit_id


# ---------------------------------------------------------------------------
# TestMCPClient — server management
# ---------------------------------------------------------------------------


class TestMCPClient:
    def test_initial_empty(self) -> None:
        client = MCPClient()
        assert client.list_servers() == []

    def test_add_server(self) -> None:
        client = MCPClient()
        cfg = _make_config()
        client.add_server(cfg)
        servers = client.list_servers()
        assert len(servers) == 1
        assert servers[0].server_id == "srv-1"

    def test_add_duplicate_raises(self) -> None:
        client = MCPClient()
        cfg = _make_config()
        client.add_server(cfg)
        with pytest.raises(ValueError, match="already registered"):
            client.add_server(cfg)

    def test_remove_server(self) -> None:
        client = MCPClient()
        client.add_server(_make_config())
        client.remove_server("srv-1")
        assert client.list_servers() == []

    def test_remove_nonexistent_raises(self) -> None:
        client = MCPClient()
        with pytest.raises(MCPServerNotFoundError):
            client.remove_server("nope")

    def test_connect(self) -> None:
        client = MCPClient()
        client.add_server(_make_config())
        client.connect("srv-1")
        status = client.get_server_status("srv-1")
        assert status["connected"] is True
        assert status["connectCount"] == 1

    def test_connect_idempotent(self) -> None:
        client = MCPClient()
        client.add_server(_make_config())
        client.connect("srv-1")
        client.connect("srv-1")  # second call is no-op
        status = client.get_server_status("srv-1")
        assert status["connectCount"] == 1

    def test_disconnect(self) -> None:
        client = MCPClient()
        client.add_server(_make_config())
        client.connect("srv-1")
        client.disconnect("srv-1")
        status = client.get_server_status("srv-1")
        assert status["connected"] is False
        assert status["disconnectCount"] == 1

    def test_disconnect_idempotent(self) -> None:
        client = MCPClient()
        client.add_server(_make_config())
        client.connect("srv-1")
        client.disconnect("srv-1")
        client.disconnect("srv-1")  # second call is no-op
        assert client.get_server_status("srv-1")["disconnectCount"] == 1

    def test_connect_unknown_raises(self) -> None:
        client = MCPClient()
        with pytest.raises(MCPServerNotFoundError):
            client.connect("unknown")

    def test_get_server_status(self) -> None:
        client = MCPClient()
        client.add_server(_make_config(server_id="x", name="X Server"))
        client.connect("x")
        st = client.get_server_status("x")
        assert st["serverId"] == "x"
        assert st["name"] == "X Server"
        assert st["connected"] is True

    def test_get_status_nonexistent_raises(self) -> None:
        client = MCPClient()
        with pytest.raises(MCPServerNotFoundError):
            client.get_server_status("nope")

    def test_remove_connected_server_disconnects_first(self) -> None:
        client = MCPClient()
        client.add_server(_make_config())
        client.connect("srv-1")
        client.remove_server("srv-1")
        assert len(client.list_servers()) == 0

    def test_multiple_servers(self) -> None:
        client = MCPClient()
        client.add_server(_make_config(server_id="a", name="A"))
        client.add_server(_make_config(server_id="b", name="B"))
        assert len(client.list_servers()) == 2


# ---------------------------------------------------------------------------
# TestMCPDiscovery
# ---------------------------------------------------------------------------


class TestMCPDiscovery:
    def _client_with_server(self, server_id: str = "srv-1") -> MCPClient:
        client = MCPClient()
        client.add_server(_make_config(server_id=server_id))
        client.connect(server_id)
        return client

    def test_discover_tools_empty(self) -> None:
        client = self._client_with_server()
        tools = client.discover_tools("srv-1")
        assert tools == []

    def test_discover_tools_injected(self) -> None:
        client = self._client_with_server()
        client._inject_tools("srv-1", [_make_tool("read"), _make_tool("write")])
        tools = client.discover_tools("srv-1")
        assert len(tools) == 2
        assert {t.name for t in tools} == {"read", "write"}

    def test_discover_tools_not_connected_raises(self) -> None:
        client = MCPClient()
        client.add_server(_make_config())
        with pytest.raises(MCPConnectionError):
            client.discover_tools("srv-1")

    def test_discover_resources(self) -> None:
        client = self._client_with_server()
        client._inject_resources("srv-1", [_make_resource()])
        resources = client.discover_resources("srv-1")
        assert len(resources) == 1

    def test_discover_resources_not_connected_raises(self) -> None:
        client = MCPClient()
        client.add_server(_make_config())
        with pytest.raises(MCPConnectionError):
            client.discover_resources("srv-1")

    def test_discover_prompts(self) -> None:
        client = self._client_with_server()
        client._inject_prompts("srv-1", [_make_prompt("p1"), _make_prompt("p2")])
        prompts = client.discover_prompts("srv-1")
        assert len(prompts) == 2

    def test_discover_prompts_not_connected_raises(self) -> None:
        client = MCPClient()
        client.add_server(_make_config())
        with pytest.raises(MCPConnectionError):
            client.discover_prompts("srv-1")

    def test_get_all_tools_from_multiple_servers(self) -> None:
        client = MCPClient()
        for sid in ("a", "b"):
            client.add_server(_make_config(server_id=sid))
            client.connect(sid)
            client._inject_tools(sid, [_make_tool(f"tool_{sid}", server_id=sid)])
        all_tools = client.get_all_tools()
        assert len(all_tools) == 2
        server_ids = {t.server_id for t in all_tools}
        assert server_ids == {"a", "b"}

    def test_get_all_tools_skips_disconnected(self) -> None:
        client = MCPClient()
        client.add_server(_make_config(server_id="a"))
        client.add_server(_make_config(server_id="b"))
        client.connect("a")
        client.connect("b")
        client._inject_tools("a", [_make_tool(server_id="a")])
        client._inject_tools("b", [_make_tool(server_id="b")])
        client.disconnect("b")
        all_tools = client.get_all_tools()
        assert len(all_tools) == 1
        assert all_tools[0].server_id == "a"

    def test_discover_tools_unknown_server_raises(self) -> None:
        client = MCPClient()
        with pytest.raises(MCPServerNotFoundError):
            client.discover_tools("nope")

    def test_discover_increments_discovery_calls(self) -> None:
        client = self._client_with_server()
        client.discover_tools("srv-1")
        client.discover_resources("srv-1")
        assert client.get_stats()["discoveryCalls"] == 2


# ---------------------------------------------------------------------------
# TestMCPInvocation
# ---------------------------------------------------------------------------


class TestMCPInvocation:
    def _client_with_tool(
        self,
        tool_name: str = "my_tool",
        gate: Any = None,
    ) -> MCPClient:
        client = MCPClient(gate=gate)
        client.add_server(_make_config())
        client.connect("srv-1")
        client._inject_tools("srv-1", [_make_tool(tool_name)])
        return client

    @pytest.mark.asyncio
    async def test_invoke_tool_with_allowed_gate(self) -> None:
        client = self._client_with_tool(gate=_allowed_gate())
        result = await client.invoke_tool(
            "srv-1", "my_tool", {"param": "value"},
            agent_id="agent-1",
            trust_level=3,
        )
        assert result.is_error is False
        assert result.tool_name == "my_tool"
        assert result.server_id == "srv-1"

    @pytest.mark.asyncio
    async def test_invoke_tool_no_gate(self) -> None:
        """When gate is None, invocation proceeds without policy check."""
        client = self._client_with_tool(gate=None)
        result = await client.invoke_tool(
            "srv-1", "my_tool", {},
            agent_id="agent-1",
            trust_level=3,
        )
        assert result.is_error is False

    @pytest.mark.asyncio
    async def test_invoke_tool_denied_gate_raises(self) -> None:
        client = self._client_with_tool(gate=_denied_gate("trust violation"))
        with pytest.raises(MCPPolicyDeniedError, match="trust violation"):
            await client.invoke_tool(
                "srv-1", "my_tool", {},
                agent_id="agent-low",
                trust_level=0,
            )

    @pytest.mark.asyncio
    async def test_invoke_tool_not_connected_raises(self) -> None:
        client = MCPClient(gate=_allowed_gate())
        client.add_server(_make_config())
        with pytest.raises(MCPConnectionError):
            await client.invoke_tool(
                "srv-1", "my_tool", {},
                agent_id="a",
                trust_level=3,
            )

    @pytest.mark.asyncio
    async def test_invoke_tool_unknown_server_raises(self) -> None:
        client = MCPClient(gate=_allowed_gate())
        with pytest.raises(MCPServerNotFoundError):
            await client.invoke_tool(
                "nope", "tool", {},
                agent_id="a",
                trust_level=3,
            )

    @pytest.mark.asyncio
    async def test_invoke_tool_returns_error_result_for_unknown_tool(self) -> None:
        """Tool not in server's list → is_error=True result (not exception)."""
        client = self._client_with_tool(gate=_allowed_gate())
        result = await client.invoke_tool(
            "srv-1", "nonexistent_tool", {},
            agent_id="a",
            trust_level=3,
        )
        assert result.is_error is True

    def test_invoke_tool_raw_succeeds(self) -> None:
        client = self._client_with_tool()
        result = client.invoke_tool_raw("srv-1", "my_tool", {"x": 1})
        assert result.is_error is False
        assert result.tool_name == "my_tool"

    def test_invoke_tool_raw_not_connected_raises(self) -> None:
        client = MCPClient()
        client.add_server(_make_config())
        with pytest.raises(MCPConnectionError):
            client.invoke_tool_raw("srv-1", "tool", {})

    def test_invoke_tool_raw_unknown_server_raises(self) -> None:
        client = MCPClient()
        with pytest.raises(MCPServerNotFoundError):
            client.invoke_tool_raw("nope", "tool", {})

    @pytest.mark.asyncio
    async def test_invoke_tool_result_has_audit_id(self) -> None:
        client = self._client_with_tool(gate=_allowed_gate())
        result = await client.invoke_tool(
            "srv-1", "my_tool", {},
            agent_id="a",
            trust_level=3,
        )
        assert result.audit_id != ""
        assert len(result.audit_id) == 32  # uuid4().hex

    @pytest.mark.asyncio
    async def test_invoke_tool_duration_populated(self) -> None:
        client = self._client_with_tool(gate=_allowed_gate())
        result = await client.invoke_tool(
            "srv-1", "my_tool", {},
            agent_id="a",
            trust_level=3,
        )
        assert result.duration_ms >= 0.0


# ---------------------------------------------------------------------------
# TestMCPGating
# ---------------------------------------------------------------------------


class TestMCPGating:
    @pytest.mark.asyncio
    async def test_gate_called_for_every_invocation(self) -> None:
        gate = _allowed_gate()
        client = MCPClient(gate=gate)
        client.add_server(_make_config())
        client.connect("srv-1")
        client._inject_tools("srv-1", [_make_tool("t")])

        for _ in range(3):
            await client.invoke_tool(
                "srv-1", "t", {},
                agent_id="a",
                trust_level=3,
            )

        assert gate.gate_action.call_count == 3

    @pytest.mark.asyncio
    async def test_gate_called_with_correct_action(self) -> None:
        gate = _allowed_gate()
        client = MCPClient(gate=gate)
        client.add_server(_make_config())
        client.connect("srv-1")
        client._inject_tools("srv-1", [_make_tool("special_tool")])

        await client.invoke_tool(
            "srv-1", "special_tool", {},
            agent_id="a",
            trust_level=3,
        )

        _call_kwargs = gate.gate_action.call_args.kwargs
        assert _call_kwargs["action"] == "mcp.tool.special_tool"

    @pytest.mark.asyncio
    async def test_gate_called_with_agent_id(self) -> None:
        gate = _allowed_gate()
        client = MCPClient(gate=gate)
        client.add_server(_make_config())
        client.connect("srv-1")
        client._inject_tools("srv-1", [_make_tool("t")])

        await client.invoke_tool(
            "srv-1", "t", {},
            agent_id="my-agent-007",
            trust_level=3,
        )

        _call_kwargs = gate.gate_action.call_args.kwargs
        assert _call_kwargs["agent_id"] == "my-agent-007"

    @pytest.mark.asyncio
    async def test_denied_increments_counter(self) -> None:
        client = MCPClient(gate=_denied_gate())
        client.add_server(_make_config())
        client.connect("srv-1")
        client._inject_tools("srv-1", [_make_tool("t")])

        for _ in range(2):
            with pytest.raises(MCPPolicyDeniedError):
                await client.invoke_tool(
                    "srv-1", "t", {},
                    agent_id="a",
                    trust_level=0,
                )

        stats = client.get_stats()
        assert stats["deniedInvocations"] == 2
        assert stats["totalInvocations"] == 2

    @pytest.mark.asyncio
    async def test_raw_invocation_skips_gate(self) -> None:
        gate = _allowed_gate()
        client = MCPClient(gate=gate)
        client.add_server(_make_config())
        client.connect("srv-1")
        client._inject_tools("srv-1", [_make_tool("t")])

        client.invoke_tool_raw("srv-1", "t", {})

        assert gate.gate_action.call_count == 0

    @pytest.mark.asyncio
    async def test_requires_network_true_for_sse_server(self) -> None:
        gate = _allowed_gate()
        client = MCPClient(gate=gate)
        cfg = MCPServerConfig(
            server_id="remote", name="Remote", transport=MCPTransport.SSE,
            url="http://example.com/sse",
        )
        client.add_server(cfg)
        client.connect("remote")
        client._inject_tools("remote", [_make_tool(server_id="remote")])

        await client.invoke_tool(
            "remote", "test_tool", {},
            agent_id="a",
            trust_level=3,
        )

        _call_kwargs = gate.gate_action.call_args.kwargs
        assert _call_kwargs["requires_network"] is True

    @pytest.mark.asyncio
    async def test_requires_network_false_for_stdio_server(self) -> None:
        gate = _allowed_gate()
        client = MCPClient(gate=gate)
        client.add_server(_make_config(transport=MCPTransport.STDIO))
        client.connect("srv-1")
        client._inject_tools("srv-1", [_make_tool("t")])

        await client.invoke_tool(
            "srv-1", "t", {},
            agent_id="a",
            trust_level=3,
        )

        _call_kwargs = gate.gate_action.call_args.kwargs
        assert _call_kwargs["requires_network"] is False


# ---------------------------------------------------------------------------
# TestMCPAudit
# ---------------------------------------------------------------------------


class TestMCPAudit:
    @pytest.mark.asyncio
    async def test_audit_callback_fires_on_allowed_invocation(self) -> None:
        events: list[dict] = []
        client = MCPClient(gate=_allowed_gate(), audit_callback=events.append)
        client.add_server(_make_config())
        client.connect("srv-1")
        client._inject_tools("srv-1", [_make_tool("t")])

        await client.invoke_tool(
            "srv-1", "t", {},
            agent_id="a",
            trust_level=3,
        )

        assert len(events) == 1
        assert events[0]["event"] == "mcp.tool.invoked"

    @pytest.mark.asyncio
    async def test_audit_callback_fires_on_denied_invocation(self) -> None:
        events: list[dict] = []
        client = MCPClient(gate=_denied_gate(), audit_callback=events.append)
        client.add_server(_make_config())
        client.connect("srv-1")
        client._inject_tools("srv-1", [_make_tool("t")])

        with pytest.raises(MCPPolicyDeniedError):
            await client.invoke_tool(
                "srv-1", "t", {},
                agent_id="a",
                trust_level=0,
            )

        assert len(events) == 1
        assert events[0]["event"] == "mcp.tool.denied"

    def test_audit_callback_fires_on_raw_invocation(self) -> None:
        events: list[dict] = []
        client = MCPClient(audit_callback=events.append)
        client.add_server(_make_config())
        client.connect("srv-1")
        client._inject_tools("srv-1", [_make_tool("t")])

        client.invoke_tool_raw("srv-1", "t", {})

        assert len(events) == 1
        assert events[0]["event"] == "mcp.tool.raw_invocation"
        assert events[0]["gated"] is False
        assert "RAW" in events[0]["warning"]

    @pytest.mark.asyncio
    async def test_audit_event_contains_server_and_tool(self) -> None:
        events: list[dict] = []
        client = MCPClient(gate=_allowed_gate(), audit_callback=events.append)
        client.add_server(_make_config(server_id="my-server"))
        client.connect("my-server")
        client._inject_tools("my-server", [_make_tool("my_func", server_id="my-server")])

        await client.invoke_tool(
            "my-server", "my_func", {"k": "v"},
            agent_id="agt",
            trust_level=3,
        )

        ev = events[0]
        assert ev["serverId"] == "my-server"
        assert ev["toolName"] == "my_func"
        assert "auditId" in ev

    @pytest.mark.asyncio
    async def test_multiple_invocations_separate_audit_ids(self) -> None:
        events: list[dict] = []
        client = MCPClient(gate=_allowed_gate(), audit_callback=events.append)
        client.add_server(_make_config())
        client.connect("srv-1")
        client._inject_tools("srv-1", [_make_tool("t")])

        for _ in range(3):
            await client.invoke_tool("srv-1", "t", {}, agent_id="a", trust_level=3)

        audit_ids = [e["auditId"] for e in events]
        assert len(set(audit_ids)) == 3  # all unique

    @pytest.mark.asyncio
    async def test_audit_callback_exception_does_not_break_invocation(self) -> None:
        def bad_callback(event: dict) -> None:
            raise RuntimeError("callback error")

        client = MCPClient(gate=_allowed_gate(), audit_callback=bad_callback)
        client.add_server(_make_config())
        client.connect("srv-1")
        client._inject_tools("srv-1", [_make_tool("t")])

        # Should not raise despite bad callback
        result = await client.invoke_tool("srv-1", "t", {}, agent_id="a", trust_level=3)
        assert result.is_error is False


# ---------------------------------------------------------------------------
# TestMCPErrors
# ---------------------------------------------------------------------------


class TestMCPErrors:
    def test_mcp_error_hierarchy(self) -> None:
        assert issubclass(MCPConnectionError, MCPError)
        assert issubclass(MCPInvocationError, MCPError)
        assert issubclass(MCPServerNotFoundError, MCPError)
        assert issubclass(MCPPolicyDeniedError, MCPError)

    def test_server_not_found_error(self) -> None:
        client = MCPClient()
        with pytest.raises(MCPServerNotFoundError) as exc_info:
            client.remove_server("ghost")
        assert "ghost" in str(exc_info.value)

    def test_connection_error_on_discover_disconnected(self) -> None:
        client = MCPClient()
        client.add_server(_make_config())
        with pytest.raises(MCPConnectionError) as exc_info:
            client.discover_tools("srv-1")
        assert "srv-1" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_policy_denied_error_message(self) -> None:
        client = MCPClient(gate=_denied_gate("low trust"))
        client.add_server(_make_config())
        client.connect("srv-1")
        client._inject_tools("srv-1", [_make_tool("t")])

        with pytest.raises(MCPPolicyDeniedError) as exc_info:
            await client.invoke_tool("srv-1", "t", {}, agent_id="a", trust_level=0)

        assert "low trust" in str(exc_info.value)
        assert "t" in str(exc_info.value)


# ---------------------------------------------------------------------------
# TestMCPStats
# ---------------------------------------------------------------------------


class TestMCPStats:
    def test_initial_stats(self) -> None:
        client = MCPClient()
        stats = client.get_stats()
        assert stats["totalServers"] == 0
        assert stats["connectedServers"] == 0
        assert stats["totalInvocations"] == 0
        assert stats["deniedInvocations"] == 0
        assert stats["rawInvocations"] == 0

    def test_stats_after_add_and_connect(self) -> None:
        client = MCPClient()
        client.add_server(_make_config(server_id="a"))
        client.add_server(_make_config(server_id="b"))
        client.connect("a")
        stats = client.get_stats()
        assert stats["totalServers"] == 2
        assert stats["connectedServers"] == 1

    @pytest.mark.asyncio
    async def test_stats_after_invocation(self) -> None:
        client = MCPClient(gate=_allowed_gate())
        client.add_server(_make_config())
        client.connect("srv-1")
        client._inject_tools("srv-1", [_make_tool("t")])

        await client.invoke_tool("srv-1", "t", {}, agent_id="a", trust_level=3)
        stats = client.get_stats()
        assert stats["totalInvocations"] == 1
        assert stats["deniedInvocations"] == 0

    def test_stats_raw_invocation_counted(self) -> None:
        client = MCPClient()
        client.add_server(_make_config())
        client.connect("srv-1")
        client._inject_tools("srv-1", [_make_tool("t")])

        client.invoke_tool_raw("srv-1", "t", {})
        stats = client.get_stats()
        assert stats["rawInvocations"] == 1
        assert stats["totalInvocations"] == 1

    def test_has_gate_reported_in_stats(self) -> None:
        c1 = MCPClient(gate=None)
        c2 = MCPClient(gate=_allowed_gate())
        assert c1.get_stats()["hasGate"] is False
        assert c2.get_stats()["hasGate"] is True


# ---------------------------------------------------------------------------
# TestAcceptanceMCP01 — Acceptance tests REQ-MCP-01 through REQ-MCP-05
# ---------------------------------------------------------------------------


class TestAcceptanceMCP01:
    """Acceptance tests for the MCP Native Client."""

    @pytest.mark.asyncio
    async def test_acc_mcp01_tool_discovery_from_multiple_servers(self) -> None:
        """REQ-MCP-01: Tool discovery from multiple servers returns aggregate."""
        client = MCPClient()

        for srv in ("filesystem", "database", "browser"):
            client.add_server(MCPServerConfig(server_id=srv, name=srv.title()))
            client.connect(srv)
            client._inject_tools(srv, [
                MCPToolInfo(name=f"{srv}_read", description="", input_schema={}, server_id=srv),
                MCPToolInfo(name=f"{srv}_write", description="", input_schema={}, server_id=srv),
            ])

        all_tools = client.get_all_tools()
        assert len(all_tools) == 6
        server_ids = {t.server_id for t in all_tools}
        assert server_ids == {"filesystem", "database", "browser"}

    @pytest.mark.asyncio
    async def test_acc_mcp02_gated_invocation_succeeds_with_proper_trust(self) -> None:
        """REQ-MCP-02: Gated invocation succeeds when trust level is sufficient."""
        gate = _allowed_gate()
        client = MCPClient(gate=gate)
        client.add_server(_make_config(server_id="prod"))
        client.connect("prod")
        client._inject_tools("prod", [_make_tool("deploy", server_id="prod")])

        result = await client.invoke_tool(
            "prod", "deploy", {"env": "staging"},
            agent_id="ops-agent",
            trust_level=4,
        )

        assert result.is_error is False
        assert result.tool_name == "deploy"
        assert gate.gate_action.call_count == 1

    @pytest.mark.asyncio
    async def test_acc_mcp03_gated_invocation_denied_without_proper_trust(self) -> None:
        """REQ-MCP-03: Gated invocation denied when trust level is insufficient."""
        gate = _denied_gate("insufficient trust level for destructive operation")
        client = MCPClient(gate=gate)
        client.add_server(_make_config(server_id="prod"))
        client.connect("prod")
        client._inject_tools("prod", [_make_tool("delete_all", server_id="prod")])

        with pytest.raises(MCPPolicyDeniedError) as exc_info:
            await client.invoke_tool(
                "prod", "delete_all", {},
                agent_id="low-trust-agent",
                trust_level=0,
            )

        assert "insufficient trust" in str(exc_info.value).lower()
        stats = client.get_stats()
        assert stats["deniedInvocations"] == 1

    @pytest.mark.asyncio
    async def test_acc_mcp04_audit_trail_for_every_invocation(self) -> None:
        """REQ-MCP-04: Audit trail captured for every invocation (allowed and denied)."""
        events: list[dict] = []
        gate = _allowed_gate()
        client = MCPClient(gate=gate, audit_callback=events.append)
        client.add_server(_make_config())
        client.connect("srv-1")
        client._inject_tools("srv-1", [_make_tool("tool_a"), _make_tool("tool_b")])

        # Two gated invocations
        await client.invoke_tool("srv-1", "tool_a", {}, agent_id="agent-x", trust_level=3)
        await client.invoke_tool("srv-1", "tool_b", {}, agent_id="agent-x", trust_level=3)

        # One denied invocation
        denied_client = MCPClient(gate=_denied_gate(), audit_callback=events.append)
        denied_client.add_server(_make_config(server_id="d"))
        denied_client.connect("d")
        denied_client._inject_tools("d", [_make_tool("x", server_id="d")])
        with pytest.raises(MCPPolicyDeniedError):
            await denied_client.invoke_tool("d", "x", {}, agent_id="bad", trust_level=0)

        # One raw invocation
        raw_client = MCPClient(audit_callback=events.append)
        raw_client.add_server(_make_config(server_id="r"))
        raw_client.connect("r")
        raw_client._inject_tools("r", [_make_tool("y", server_id="r")])
        raw_client.invoke_tool_raw("r", "y", {})

        assert len(events) == 4
        event_types = {e["event"] for e in events}
        assert "mcp.tool.invoked" in event_types
        assert "mcp.tool.denied" in event_types
        assert "mcp.tool.raw_invocation" in event_types

        # Every event has an auditId
        for ev in events:
            assert "auditId" in ev
            assert ev["auditId"] != ""

    @pytest.mark.asyncio
    async def test_acc_mcp05_server_lifecycle_connect_disconnect_reconnect(self) -> None:
        """REQ-MCP-05: Server lifecycle transitions correctly."""
        client = MCPClient(gate=_allowed_gate())
        cfg = _make_config(server_id="lifecycle")
        client.add_server(cfg)

        # Initial: not connected
        st = client.get_server_status("lifecycle")
        assert st["connected"] is False
        assert st["connectCount"] == 0

        # Connect
        client.connect("lifecycle")
        st = client.get_server_status("lifecycle")
        assert st["connected"] is True
        assert st["connectCount"] == 1

        # Disconnect
        client.disconnect("lifecycle")
        st = client.get_server_status("lifecycle")
        assert st["connected"] is False
        assert st["disconnectCount"] == 1

        # Reconnect
        client.connect("lifecycle")
        st = client.get_server_status("lifecycle")
        assert st["connected"] is True
        assert st["connectCount"] == 2

        # Verify tools accessible after reconnect
        client._inject_tools("lifecycle", [_make_tool("ping", server_id="lifecycle")])
        tools = client.discover_tools("lifecycle")
        assert len(tools) == 1
        assert tools[0].name == "ping"
