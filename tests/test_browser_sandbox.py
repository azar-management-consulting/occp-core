"""Tests for BrowserSandbox — Policy-governed browser automation layer.

Covers:
- BrowserSandboxConfig: defaults, custom, frozen
- BrowserAction: enum values, all 8 actions
- BrowserCommand: creation, defaults, frozen
- BrowserResult: creation, auto audit_id, success/failure
- BrowserSandbox: navigate, domain policy, execute, sequence, stats, gate, audit
- BrowserDomainPolicy: deny precedence, wildcard, empty lists, case insensitive
- BrowserGating: gate called, gate denied, no gate, audit events
- BrowserErrors: hierarchy, messages
- Acceptance tests: ACC-BROWSER-01 through ACC-BROWSER-05
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from adapters.browser_sandbox import (
    BrowserAction,
    BrowserCommand,
    BrowserDomainDeniedError,
    BrowserGateDeniedError,
    BrowserResult,
    BrowserSandbox,
    BrowserSandboxConfig,
    BrowserSandboxError,
    BrowserTimeoutError,
    _domain_matches,
    _extract_domain,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_gate(allowed: bool = True, reason: str = "") -> MagicMock:
    """Create a mock PolicyGate that returns allowed/denied."""
    gate = MagicMock()
    decision = MagicMock()
    decision.allowed = allowed
    decision.reason = reason
    gate.gate_action = AsyncMock(return_value=decision)
    return gate


def _audit_recorder() -> tuple[list[dict], Any]:
    """Return (log, callback) pair for audit testing."""
    log: list[dict] = []

    def callback(event: dict) -> None:
        log.append(event)

    return log, callback


# ---------------------------------------------------------------------------
# TestBrowserSandboxConfig
# ---------------------------------------------------------------------------


class TestBrowserSandboxConfig:
    def test_defaults(self):
        cfg = BrowserSandboxConfig()
        assert cfg.allowed_domains == []
        assert cfg.denied_domains == []
        assert cfg.max_pages == 5
        assert cfg.timeout_seconds == 30
        assert cfg.screenshot_enabled is True
        assert cfg.javascript_enabled is True
        assert cfg.cookie_policy == "session_only"
        assert cfg.viewport == (1280, 800)
        assert cfg.user_data_dir == ""

    def test_custom_values(self):
        cfg = BrowserSandboxConfig(
            allowed_domains=["example.com", "test.org"],
            denied_domains=["bad.com"],
            max_pages=10,
            timeout_seconds=60,
            screenshot_enabled=False,
            javascript_enabled=False,
            cookie_policy="none",
            viewport=(1920, 1080),
            user_data_dir="/tmp/profile",
        )
        assert cfg.allowed_domains == ["example.com", "test.org"]
        assert cfg.denied_domains == ["bad.com"]
        assert cfg.max_pages == 10
        assert cfg.timeout_seconds == 60
        assert cfg.screenshot_enabled is False
        assert cfg.javascript_enabled is False
        assert cfg.cookie_policy == "none"
        assert cfg.viewport == (1920, 1080)
        assert cfg.user_data_dir == "/tmp/profile"

    def test_frozen(self):
        cfg = BrowserSandboxConfig()
        with pytest.raises(Exception):
            cfg.max_pages = 99  # type: ignore[misc]

    def test_immutable_viewport(self):
        cfg = BrowserSandboxConfig(viewport=(800, 600))
        assert cfg.viewport == (800, 600)
        with pytest.raises(Exception):
            cfg.viewport = (1024, 768)  # type: ignore[misc]


# ---------------------------------------------------------------------------
# TestBrowserAction
# ---------------------------------------------------------------------------


class TestBrowserAction:
    def test_all_eight_actions_exist(self):
        actions = {a.value for a in BrowserAction}
        assert actions == {
            "navigate", "click", "type", "screenshot",
            "evaluate", "wait", "scroll", "select",
        }

    def test_enum_count(self):
        assert len(BrowserAction) == 8

    def test_values_are_strings(self):
        for action in BrowserAction:
            assert isinstance(action.value, str)

    def test_access_by_name(self):
        assert BrowserAction.NAVIGATE == BrowserAction("navigate")
        assert BrowserAction.CLICK == BrowserAction("click")
        assert BrowserAction.SCREENSHOT == BrowserAction("screenshot")


# ---------------------------------------------------------------------------
# TestBrowserCommand
# ---------------------------------------------------------------------------


class TestBrowserCommand:
    def test_required_action(self):
        cmd = BrowserCommand(action=BrowserAction.CLICK)
        assert cmd.action == BrowserAction.CLICK

    def test_defaults(self):
        cmd = BrowserCommand(action=BrowserAction.NAVIGATE)
        assert cmd.target == ""
        assert cmd.value == ""
        assert cmd.timeout == 5.0
        assert cmd.metadata == {}

    def test_custom_values(self):
        cmd = BrowserCommand(
            action=BrowserAction.TYPE,
            target="#input",
            value="hello world",
            timeout=10.0,
            metadata={"label": "test"},
        )
        assert cmd.target == "#input"
        assert cmd.value == "hello world"
        assert cmd.timeout == 10.0
        assert cmd.metadata == {"label": "test"}

    def test_frozen(self):
        cmd = BrowserCommand(action=BrowserAction.CLICK)
        with pytest.raises(Exception):
            cmd.target = "new"  # type: ignore[misc]

    def test_different_actions(self):
        for action in BrowserAction:
            cmd = BrowserCommand(action=action, target="test")
            assert cmd.action == action


# ---------------------------------------------------------------------------
# TestBrowserResult
# ---------------------------------------------------------------------------


class TestBrowserResult:
    def test_creation_success(self):
        cmd = BrowserCommand(action=BrowserAction.NAVIGATE, target="https://example.com")
        result = BrowserResult(command=cmd, success=True, output={"status": 200})
        assert result.success is True
        assert result.output == {"status": 200}
        assert result.error == ""

    def test_creation_failure(self):
        cmd = BrowserCommand(action=BrowserAction.CLICK, target="#btn")
        result = BrowserResult(command=cmd, success=False, error="Element not found")
        assert result.success is False
        assert result.error == "Element not found"

    def test_auto_audit_id(self):
        cmd = BrowserCommand(action=BrowserAction.NAVIGATE)
        r1 = BrowserResult(command=cmd, success=True)
        r2 = BrowserResult(command=cmd, success=True)
        assert r1.audit_id != r2.audit_id
        assert len(r1.audit_id) == 16

    def test_screenshot_data_default_none(self):
        cmd = BrowserCommand(action=BrowserAction.SCREENSHOT)
        result = BrowserResult(command=cmd, success=True)
        assert result.screenshot_data is None

    def test_duration_default_zero(self):
        cmd = BrowserCommand(action=BrowserAction.WAIT)
        result = BrowserResult(command=cmd, success=True)
        assert result.duration_ms == 0.0


# ---------------------------------------------------------------------------
# TestBrowserSandbox
# ---------------------------------------------------------------------------


class TestBrowserSandbox:
    @pytest.mark.asyncio
    async def test_navigate_allowed_domain(self):
        cfg = BrowserSandboxConfig(allowed_domains=["example.com"])
        sandbox = BrowserSandbox(config=cfg)
        result = await sandbox.navigate("https://example.com/page")
        assert result.success is True
        assert result.command.action == BrowserAction.NAVIGATE

    @pytest.mark.asyncio
    async def test_navigate_denied_domain_raises(self):
        cfg = BrowserSandboxConfig(denied_domains=["malicious.com"])
        sandbox = BrowserSandbox(config=cfg)
        with pytest.raises(BrowserDomainDeniedError) as exc_info:
            await sandbox.navigate("https://malicious.com/path")
        assert "malicious.com" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_execute_command(self):
        sandbox = BrowserSandbox()
        cmd = BrowserCommand(action=BrowserAction.CLICK, target="#button")
        result = await sandbox.execute(cmd)
        assert result.success is True
        assert result.command == cmd

    @pytest.mark.asyncio
    async def test_execute_sequence_all_succeed(self):
        sandbox = BrowserSandbox()
        commands = [
            BrowserCommand(action=BrowserAction.NAVIGATE, target="https://example.com"),
            BrowserCommand(action=BrowserAction.CLICK, target="#link"),
            BrowserCommand(action=BrowserAction.SCREENSHOT),
        ]
        results = await sandbox.execute_sequence(commands)
        assert len(results) == 3
        assert all(r.success for r in results)

    @pytest.mark.asyncio
    async def test_execute_sequence_stops_on_error(self):
        cfg = BrowserSandboxConfig(denied_domains=["blocked.com"])
        sandbox = BrowserSandbox(config=cfg)
        commands = [
            BrowserCommand(action=BrowserAction.CLICK, target="#btn"),
            BrowserCommand(action=BrowserAction.NAVIGATE, target="https://blocked.com"),
            BrowserCommand(action=BrowserAction.SCREENSHOT),
        ]
        results = await sandbox.execute_sequence(commands)
        assert len(results) == 2  # stopped after second command raised error
        assert results[0].success is True
        assert results[1].success is False

    def test_stats_initial(self):
        sandbox = BrowserSandbox()
        stats = sandbox.get_stats()
        assert stats["active_pages"] == 0
        assert stats["commands_executed"] == 0
        assert stats["domains_visited"] == []
        assert stats["denied_count"] == 0

    @pytest.mark.asyncio
    async def test_stats_after_navigation(self):
        sandbox = BrowserSandbox()
        await sandbox.navigate("https://example.com")
        stats = sandbox.get_stats()
        assert stats["commands_executed"] == 1
        assert "example.com" in stats["domains_visited"]

    @pytest.mark.asyncio
    async def test_gate_integration_allowed(self):
        gate = _make_gate(allowed=True)
        sandbox = BrowserSandbox(gate=gate)
        result = await sandbox.navigate("https://example.com")
        assert result.success is True
        gate.gate_action.assert_called_once()

    @pytest.mark.asyncio
    async def test_audit_callback_called(self):
        log, callback = _audit_recorder()
        sandbox = BrowserSandbox(audit_callback=callback)
        await sandbox.navigate("https://example.com")
        assert len(log) >= 1
        events = [e["event"] for e in log]
        assert "action_executed" in events


# ---------------------------------------------------------------------------
# TestBrowserDomainPolicy
# ---------------------------------------------------------------------------


class TestBrowserDomainPolicy:
    def test_deny_takes_precedence_over_allow(self):
        cfg = BrowserSandboxConfig(
            allowed_domains=["example.com"],
            denied_domains=["example.com"],
        )
        sandbox = BrowserSandbox(config=cfg)
        assert sandbox.is_domain_allowed("example.com") is False

    def test_empty_allow_list_permits_all(self):
        cfg = BrowserSandboxConfig(denied_domains=[])
        sandbox = BrowserSandbox(config=cfg)
        assert sandbox.is_domain_allowed("anything.com") is True

    def test_allow_list_restricts_unknown(self):
        cfg = BrowserSandboxConfig(allowed_domains=["example.com"])
        sandbox = BrowserSandbox(config=cfg)
        assert sandbox.is_domain_allowed("example.com") is True
        assert sandbox.is_domain_allowed("other.com") is False

    def test_wildcard_deny(self):
        cfg = BrowserSandboxConfig(denied_domains=["*.bad.com"])
        sandbox = BrowserSandbox(config=cfg)
        assert sandbox.is_domain_allowed("sub.bad.com") is False
        assert sandbox.is_domain_allowed("bad.com") is False
        assert sandbox.is_domain_allowed("notbad.com") is True

    def test_wildcard_allow(self):
        cfg = BrowserSandboxConfig(allowed_domains=["*.example.com"])
        sandbox = BrowserSandbox(config=cfg)
        assert sandbox.is_domain_allowed("api.example.com") is True
        assert sandbox.is_domain_allowed("example.com") is True
        assert sandbox.is_domain_allowed("other.com") is False

    def test_case_insensitive(self):
        cfg = BrowserSandboxConfig(allowed_domains=["Example.COM"])
        sandbox = BrowserSandbox(config=cfg)
        assert sandbox.is_domain_allowed("example.com") is True
        assert sandbox.is_domain_allowed("EXAMPLE.COM") is True

    @pytest.mark.asyncio
    async def test_denied_count_increments(self):
        cfg = BrowserSandboxConfig(denied_domains=["blocked.com"])
        sandbox = BrowserSandbox(config=cfg)
        with pytest.raises(BrowserDomainDeniedError):
            await sandbox.navigate("https://blocked.com")
        assert sandbox.get_stats()["denied_count"] == 1

    @pytest.mark.asyncio
    async def test_wildcard_match_subdomain(self):
        cfg = BrowserSandboxConfig(allowed_domains=["*.trusted.com"])
        sandbox = BrowserSandbox(config=cfg)
        assert sandbox.is_domain_allowed("api.trusted.com") is True
        assert sandbox.is_domain_allowed("evil.com") is False


# ---------------------------------------------------------------------------
# TestBrowserGating
# ---------------------------------------------------------------------------


class TestBrowserGating:
    @pytest.mark.asyncio
    async def test_gate_called_for_navigate(self):
        gate = _make_gate(allowed=True)
        sandbox = BrowserSandbox(gate=gate)
        await sandbox.navigate("https://example.com")
        gate.gate_action.assert_called_once()
        call_kwargs = gate.gate_action.call_args
        assert call_kwargs.kwargs["action"] == "browser.navigate"

    @pytest.mark.asyncio
    async def test_gate_denied_raises_browser_gate_denied(self):
        gate = _make_gate(allowed=False, reason="Network access denied")
        sandbox = BrowserSandbox(gate=gate)
        with pytest.raises(BrowserGateDeniedError) as exc_info:
            await sandbox.navigate("https://example.com")
        assert "navigate" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_no_gate_skips_gate_check(self):
        sandbox = BrowserSandbox()  # no gate
        result = await sandbox.navigate("https://example.com")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_audit_callback_on_every_action(self):
        log, callback = _audit_recorder()
        sandbox = BrowserSandbox(audit_callback=callback)

        actions = [
            BrowserCommand(action=BrowserAction.CLICK, target="#btn"),
            BrowserCommand(action=BrowserAction.TYPE, target="#input", value="text"),
            BrowserCommand(action=BrowserAction.SCROLL, target="body"),
        ]
        for cmd in actions:
            await sandbox.execute(cmd)

        # One audit event per action executed
        executed_events = [e for e in log if e["event"] == "action_executed"]
        assert len(executed_events) == 3

    @pytest.mark.asyncio
    async def test_gate_called_for_all_execute_actions(self):
        gate = _make_gate(allowed=True)
        sandbox = BrowserSandbox(gate=gate)
        for action in BrowserAction:
            if action == BrowserAction.NAVIGATE:
                continue  # skip to avoid domain check interference
            cmd = BrowserCommand(action=action, target="test")
            await sandbox.execute(cmd)
        # Gate should have been called for each action
        assert gate.gate_action.call_count == len(BrowserAction) - 1


# ---------------------------------------------------------------------------
# TestBrowserErrors
# ---------------------------------------------------------------------------


class TestBrowserErrors:
    def test_error_hierarchy(self):
        assert issubclass(BrowserDomainDeniedError, BrowserSandboxError)
        assert issubclass(BrowserTimeoutError, BrowserSandboxError)
        assert issubclass(BrowserGateDeniedError, BrowserSandboxError)

    def test_domain_denied_error_message(self):
        err = BrowserDomainDeniedError("evil.com")
        assert "evil.com" in str(err)
        assert err.domain == "evil.com"

    def test_timeout_error_message(self):
        err = BrowserTimeoutError("navigate", 5.0)
        assert "navigate" in str(err)
        assert err.action == "navigate"
        assert err.timeout == 5.0

    def test_gate_denied_error_message(self):
        err = BrowserGateDeniedError("click", "Policy denied")
        assert "click" in str(err)
        assert "Policy denied" in str(err)
        assert err.action == "click"
        assert err.reason == "Policy denied"

    def test_domain_matches_helper(self):
        assert _domain_matches("example.com", "example.com") is True
        assert _domain_matches("sub.example.com", "*.example.com") is True
        assert _domain_matches("example.com", "*.example.com") is True
        assert _domain_matches("other.com", "example.com") is False

    def test_extract_domain_helper(self):
        assert _extract_domain("https://example.com/path") == "example.com"
        assert _extract_domain("http://sub.example.com:8080/") == "sub.example.com"
        assert _extract_domain("https://EXAMPLE.COM") == "example.com"


# ---------------------------------------------------------------------------
# Acceptance Tests
# ---------------------------------------------------------------------------


class TestAcceptanceBrowser:
    @pytest.mark.asyncio
    async def test_acc_browser_01_navigate_allowed_with_audit(self):
        """ACC-BROWSER-01: Navigate to allowed domain succeeds with audit trail."""
        log, callback = _audit_recorder()
        cfg = BrowserSandboxConfig(allowed_domains=["example.com"])
        sandbox = BrowserSandbox(config=cfg, audit_callback=callback)

        result = await sandbox.navigate("https://example.com/page")

        assert result.success is True
        assert result.audit_id
        assert len(result.audit_id) == 16
        # Audit trail captured
        assert len(log) >= 1
        audit_event = next((e for e in log if e.get("event") == "action_executed"), None)
        assert audit_event is not None
        assert audit_event["action"] == "navigate"

    @pytest.mark.asyncio
    async def test_acc_browser_02_navigate_denied_before_request(self):
        """ACC-BROWSER-02: Navigate to denied domain blocked before request sent."""
        log, callback = _audit_recorder()
        cfg = BrowserSandboxConfig(denied_domains=["malicious.com"])
        sandbox = BrowserSandbox(config=cfg, audit_callback=callback)

        with pytest.raises(BrowserDomainDeniedError):
            await sandbox.navigate("https://malicious.com/harvest")

        # Denied event in audit log
        denied_events = [e for e in log if e.get("event") == "domain_denied"]
        assert len(denied_events) == 1
        assert denied_events[0]["domain"] == "malicious.com"
        # Stats show denial
        assert sandbox.get_stats()["denied_count"] == 1
        assert sandbox.get_stats()["commands_executed"] == 0

    @pytest.mark.asyncio
    async def test_acc_browser_03_gate_denies_raises(self):
        """ACC-BROWSER-03: Gate denies action — BrowserGateDeniedError raised."""
        gate = _make_gate(allowed=False, reason="REQ-GOV-03: action blocked")
        sandbox = BrowserSandbox(gate=gate)

        with pytest.raises(BrowserGateDeniedError) as exc_info:
            await sandbox.navigate("https://example.com")

        err = exc_info.value
        assert isinstance(err, BrowserGateDeniedError)
        assert "navigate" in err.action
        # Command was NOT executed (gate denied before stub)
        assert sandbox.get_stats()["commands_executed"] == 0

    @pytest.mark.asyncio
    async def test_acc_browser_04_sequence_stops_on_error(self):
        """ACC-BROWSER-04: Sequence execution stops on first error."""
        cfg = BrowserSandboxConfig(denied_domains=["blocked.com"])
        sandbox = BrowserSandbox(config=cfg)

        commands = [
            BrowserCommand(action=BrowserAction.CLICK, target="#a"),
            BrowserCommand(action=BrowserAction.NAVIGATE, target="https://blocked.com"),
            BrowserCommand(action=BrowserAction.SCREENSHOT),
            BrowserCommand(action=BrowserAction.SCROLL, target="body"),
        ]
        results = await sandbox.execute_sequence(commands)

        # First command succeeds, second fails, third and fourth not executed
        assert len(results) == 2
        assert results[0].success is True
        assert results[1].success is False
        assert "blocked.com" in results[1].error

    @pytest.mark.asyncio
    async def test_acc_browser_05_all_actions_produce_audit_events(self):
        """ACC-BROWSER-05: All actions produce audit callback events."""
        log, callback = _audit_recorder()
        sandbox = BrowserSandbox(audit_callback=callback)

        actions = [
            BrowserCommand(action=BrowserAction.NAVIGATE, target="https://example.com"),
            BrowserCommand(action=BrowserAction.CLICK, target="#btn"),
            BrowserCommand(action=BrowserAction.TYPE, target="#input", value="test"),
            BrowserCommand(action=BrowserAction.SCREENSHOT),
            BrowserCommand(action=BrowserAction.EVALUATE, value="document.title"),
            BrowserCommand(action=BrowserAction.WAIT, target="2000"),
            BrowserCommand(action=BrowserAction.SCROLL, target="body"),
            BrowserCommand(action=BrowserAction.SELECT, target="#select", value="opt1"),
        ]

        for cmd in actions:
            await sandbox.execute(cmd)

        executed_events = [e for e in log if e["event"] == "action_executed"]
        assert len(executed_events) == len(actions)

        executed_action_names = {e["action"] for e in executed_events}
        for action in BrowserAction:
            assert action.value in executed_action_names
