"""Tests for the MCP runtime bridge (L4 component)."""

from __future__ import annotations

import asyncio

import pytest

from adapters.mcp_bridge import (
    MCPBridge,
    ToolCall,
    build_default_bridge,
)
from security.agent_allowlist import AgentToolGuard


class _DummyGuard:
    def __init__(self, allow: bool = True, reason: str = "") -> None:
        self._allow = allow
        self._reason = reason

    def check_access(self, agent_id: str, tool: str):  # noqa: D401
        class R:
            allowed = self._allow
            reason = self._reason

        return R()


@pytest.mark.asyncio
async def test_register_and_dispatch_ok() -> None:
    bridge = MCPBridge()

    async def _echo(params):
        return {"echo": params}

    bridge.register("test.echo", _echo)
    result = await bridge.dispatch(
        ToolCall(tool="test.echo", params={"x": 1}, agent_id="brain")
    )
    assert result.status == "ok"
    assert result.result == {"echo": {"x": 1}}
    assert result.duration_ms >= 0


@pytest.mark.asyncio
async def test_unknown_tool_returns_error() -> None:
    bridge = MCPBridge()
    result = await bridge.dispatch(
        ToolCall(tool="missing.tool", params={}, agent_id="brain")
    )
    assert result.status == "error"
    assert "Unknown tool" in (result.error or "")


@pytest.mark.asyncio
async def test_register_rejects_bad_name() -> None:
    bridge = MCPBridge()
    with pytest.raises(ValueError):
        bridge.register("bad_name_no_dot", lambda p: None)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_timeout_path() -> None:
    bridge = MCPBridge()

    async def _slow(params):
        await asyncio.sleep(2)
        return "late"

    bridge.register("test.slow", _slow)
    result = await bridge.dispatch(
        ToolCall(tool="test.slow", params={}, agent_id="brain", timeout_seconds=0.1)
    )
    assert result.status == "timeout"


@pytest.mark.asyncio
async def test_guard_denies() -> None:
    bridge = MCPBridge(agent_tool_guard=_DummyGuard(allow=False, reason="no-access"))

    async def _noop(params):
        return "ok"

    bridge.register("test.noop", _noop)
    result = await bridge.dispatch(
        ToolCall(tool="test.noop", params={}, agent_id="brain")
    )
    assert result.status == "denied"
    assert "no-access" in (result.error or "")


@pytest.mark.asyncio
async def test_guard_allows_brain_with_real_allowlist() -> None:
    """Regression: brain agent must be in the real allowlist."""
    bridge = MCPBridge(agent_tool_guard=AgentToolGuard())

    async def _status(params):
        return {"ok": True}

    bridge.register("brain.status", _status)
    result = await bridge.dispatch(
        ToolCall(tool="brain.status", params={}, agent_id="brain")
    )
    assert result.status == "ok"


@pytest.mark.asyncio
async def test_dispatch_many_parallel() -> None:
    bridge = MCPBridge()

    async def _square(params):
        return params["n"] ** 2

    bridge.register("math.square", _square)
    calls = [
        ToolCall(tool="math.square", params={"n": i}, agent_id="brain") for i in range(5)
    ]
    results = await bridge.dispatch_many(calls)
    assert len(results) == 5
    squares = sorted([r.result for r in results if r.status == "ok"])
    assert squares == [0, 1, 4, 9, 16]


@pytest.mark.asyncio
async def test_stats_tracked() -> None:
    bridge = MCPBridge()

    async def _ok(params):
        return True

    async def _fail(params):
        raise RuntimeError("boom")

    bridge.register("t.ok", _ok)
    bridge.register("t.fail", _fail)

    await bridge.dispatch(ToolCall(tool="t.ok", agent_id="brain"))
    await bridge.dispatch(ToolCall(tool="t.fail", agent_id="brain"))
    stats = bridge.stats()
    assert stats["total"] == 2
    assert stats["ok"] == 1
    assert stats["error"] == 1
    assert stats["tools_registered"] == 2
    assert 0.0 <= stats["success_rate"] <= 1.0


@pytest.mark.asyncio
async def test_default_bridge_has_all_builtin_tools() -> None:
    bridge = build_default_bridge()
    tools = bridge.list_tools()
    assert "filesystem.read" in tools
    assert "filesystem.write" in tools
    assert "filesystem.list" in tools
    assert "http.get" in tools
    assert "http.post" in tools
    assert "brain.status" in tools
    assert "brain.health" in tools


@pytest.mark.asyncio
async def test_filesystem_read_write_roundtrip(tmp_path, monkeypatch) -> None:
    from adapters import mcp_bridge as mb

    monkeypatch.setattr(
        mb, "_filesystem_write",
        mb._filesystem_write,  # re-bind to ensure import works
    )
    bridge = build_default_bridge()
    w = await bridge.dispatch(
        ToolCall(
            tool="filesystem.write",
            params={"path": "rt.txt", "content": "hello-bridge"},
            agent_id="brain",
        )
    )
    assert w.status == "ok"
    r = await bridge.dispatch(
        ToolCall(
            tool="filesystem.read",
            params={"path": "rt.txt"},
            agent_id="brain",
        )
    )
    assert r.status == "ok"
    assert r.result["content"] == "hello-bridge"


@pytest.mark.asyncio
async def test_filesystem_path_escape_blocked() -> None:
    bridge = build_default_bridge()
    r = await bridge.dispatch(
        ToolCall(
            tool="filesystem.read",
            params={"path": "/etc/passwd"},
            agent_id="brain",
        )
    )
    # Path is stripped of leading / and joined into /tmp/occp-workspace;
    # either read succeeds (as /tmp/occp-workspace/etc/passwd, likely missing)
    # or raises FileNotFoundError / PermissionError — both are acceptable safe outcomes.
    assert r.status in ("error",)  # must not expose /etc/passwd
