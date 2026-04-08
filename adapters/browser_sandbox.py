"""BrowserSandbox — Policy-governed browser automation layer.

Provides a clean-room browser automation abstraction with domain allow/deny lists,
policy gate integration (REQ-GOV-03), and full audit trail support.

NO actual Playwright dependency — uses stubs that record actions.
Production implementation will wrap Playwright.

Usage::

    config = BrowserSandboxConfig(
        allowed_domains=["example.com"],
        denied_domains=["malicious.com"],
    )
    sandbox = BrowserSandbox(config=config, gate=my_gate)

    result = await sandbox.navigate("https://example.com/page")
    if result.success:
        print(result.output)
"""

from __future__ import annotations

import enum
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from adapters.policy_gate import PolicyGate


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class BrowserSandboxError(Exception):
    """Base error for BrowserSandbox."""


class BrowserDomainDeniedError(BrowserSandboxError):
    """Raised when navigation to a denied domain is attempted."""

    def __init__(self, domain: str) -> None:
        self.domain = domain
        super().__init__(f"Domain denied by policy: {domain}")


class BrowserTimeoutError(BrowserSandboxError):
    """Raised when a browser action exceeds its timeout."""

    def __init__(self, action: str, timeout: float) -> None:
        self.action = action
        self.timeout = timeout
        super().__init__(f"Browser action '{action}' timed out after {timeout}s")


class BrowserGateDeniedError(BrowserSandboxError):
    """Raised when PolicyGate denies a browser action."""

    def __init__(self, action: str, reason: str = "") -> None:
        self.action = action
        self.reason = reason
        super().__init__(f"Gate denied browser action '{action}': {reason}")


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class BrowserAction(str, enum.Enum):
    """Supported browser automation actions."""

    NAVIGATE = "navigate"
    CLICK = "click"
    TYPE = "type"
    SCREENSHOT = "screenshot"
    EVALUATE = "evaluate"
    WAIT = "wait"
    SCROLL = "scroll"
    SELECT = "select"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BrowserSandboxConfig:
    """Immutable configuration for BrowserSandbox."""

    allowed_domains: list[str] = field(default_factory=list)
    denied_domains: list[str] = field(default_factory=list)
    max_pages: int = 5
    timeout_seconds: int = 30
    screenshot_enabled: bool = True
    javascript_enabled: bool = True
    cookie_policy: str = "session_only"
    viewport: tuple[int, int] = (1280, 800)
    user_data_dir: str = ""


@dataclass(frozen=True)
class BrowserCommand:
    """Immutable browser command descriptor."""

    action: BrowserAction
    target: str = ""
    value: str = ""
    timeout: float = 5.0
    metadata: dict = field(default_factory=dict)


@dataclass
class BrowserResult:
    """Result of a browser action execution."""

    command: BrowserCommand
    success: bool
    output: Any = None
    error: str = ""
    duration_ms: float = 0.0
    screenshot_data: bytes | None = None
    audit_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])


# ---------------------------------------------------------------------------
# Domain policy helpers
# ---------------------------------------------------------------------------


def _extract_domain(url: str) -> str:
    """Extract hostname from a URL string."""
    # Strip scheme
    stripped = url
    for scheme in ("https://", "http://", "ftp://"):
        if stripped.lower().startswith(scheme):
            stripped = stripped[len(scheme):]
            break
    # Strip path
    domain = stripped.split("/")[0]
    # Strip port
    domain = domain.split(":")[0]
    return domain.lower()


def _domain_matches(domain: str, pattern: str) -> bool:
    """Check if domain matches pattern, supporting wildcard prefix (*.)."""
    domain = domain.lower()
    pattern = pattern.lower()
    if pattern.startswith("*."):
        suffix = pattern[2:]
        return domain == suffix or domain.endswith("." + suffix)
    return domain == pattern


# ---------------------------------------------------------------------------
# BrowserSandbox
# ---------------------------------------------------------------------------


class BrowserSandbox:
    """Policy-governed browser automation sandbox.

    All actions are subject to:
    1. Domain allow/deny list enforcement
    2. Optional PolicyGate check (REQ-GOV-03)
    3. Audit callback on every action

    No real browser is launched — stubs record all actions for testing.
    """

    def __init__(
        self,
        config: BrowserSandboxConfig | None = None,
        gate: PolicyGate | None = None,
        audit_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self._config = config or BrowserSandboxConfig()
        self._gate = gate
        self._audit_callback = audit_callback

        # Internal state
        self._active_pages: int = 0
        self._commands_executed: int = 0
        self._domains_visited: set[str] = set()
        self._denied_count: int = 0

        # Action log (stub — records all executed commands)
        self._action_log: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Domain policy
    # ------------------------------------------------------------------

    def is_domain_allowed(self, domain: str) -> bool:
        """Return True if domain is permitted by config.

        Deny-list takes precedence over allow-list.
        If allow-list is empty, all non-denied domains are allowed.
        """
        domain = domain.lower()

        # Deny-list check first (takes precedence)
        for pattern in self._config.denied_domains:
            if _domain_matches(domain, pattern):
                return False

        # Allow-list check (empty = allow all)
        if not self._config.allowed_domains:
            return True

        for pattern in self._config.allowed_domains:
            if _domain_matches(domain, pattern):
                return True

        return False

    # ------------------------------------------------------------------
    # Gate integration
    # ------------------------------------------------------------------

    async def _check_gate(self, action: BrowserAction, target: str) -> None:
        """Run gate check if gate is configured. Raises BrowserGateDeniedError."""
        if self._gate is None:
            return

        from orchestrator.models import RiskLevel, Task
        from policy_engine.trust_levels import TrustLevel

        task = Task(
            name=f"browser:{action.value}",
            description=f"Browser action {action.value} on target: {target}",
            agent_type="browser_sandbox",
            risk_level=RiskLevel.MEDIUM,
        )
        decision = await self._gate.gate_action(
            task,
            agent_id="browser_sandbox",
            trust_level=TrustLevel.L2_SUPERVISED,
            action=f"browser.{action.value}",
            tool_category="browser",
            requires_network=True,
        )
        if not decision.allowed:
            raise BrowserGateDeniedError(action.value, decision.reason)

    # ------------------------------------------------------------------
    # Audit
    # ------------------------------------------------------------------

    def _emit_audit(self, event: dict[str, Any]) -> None:
        """Emit audit event to callback if configured."""
        if self._audit_callback is not None:
            self._audit_callback(event)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def navigate(self, url: str) -> BrowserResult:
        """Navigate to URL after domain policy and gate checks."""
        domain = _extract_domain(url)

        command = BrowserCommand(
            action=BrowserAction.NAVIGATE,
            target=url,
        )

        # Domain check BEFORE any request is sent
        if not self.is_domain_allowed(domain):
            self._denied_count += 1
            self._emit_audit({
                "event": "domain_denied",
                "url": url,
                "domain": domain,
                "audit_id": uuid.uuid4().hex[:16],
            })
            raise BrowserDomainDeniedError(domain)

        # Gate check
        await self._check_gate(BrowserAction.NAVIGATE, url)

        return await self._execute_stub(command, domain=domain)

    async def execute(self, command: BrowserCommand) -> BrowserResult:
        """Dispatch a BrowserCommand through policy gate and stub handler."""
        # Gate check for all actions
        await self._check_gate(command.action, command.target)

        # Domain check for NAVIGATE actions within execute()
        if command.action == BrowserAction.NAVIGATE and command.target:
            domain = _extract_domain(command.target)
            if not self.is_domain_allowed(domain):
                self._denied_count += 1
                self._emit_audit({
                    "event": "domain_denied",
                    "url": command.target,
                    "domain": domain,
                    "audit_id": uuid.uuid4().hex[:16],
                })
                raise BrowserDomainDeniedError(domain)

        return await self._execute_stub(command)

    async def execute_sequence(
        self, commands: list[BrowserCommand]
    ) -> list[BrowserResult]:
        """Execute commands sequentially, stopping on first error."""
        results: list[BrowserResult] = []
        for cmd in commands:
            try:
                result = await self.execute(cmd)
                results.append(result)
                if not result.success:
                    break
            except BrowserSandboxError as exc:
                error_result = BrowserResult(
                    command=cmd,
                    success=False,
                    error=str(exc),
                )
                results.append(error_result)
                break
        return results

    def get_stats(self) -> dict[str, Any]:
        """Return sandbox execution statistics."""
        return {
            "active_pages": self._active_pages,
            "commands_executed": self._commands_executed,
            "domains_visited": list(self._domains_visited),
            "denied_count": self._denied_count,
        }

    # ------------------------------------------------------------------
    # Stub execution (no real browser)
    # ------------------------------------------------------------------

    async def _execute_stub(
        self,
        command: BrowserCommand,
        domain: str | None = None,
    ) -> BrowserResult:
        """Stub implementation — records the action without a real browser."""
        t0 = time.monotonic()
        audit_id = uuid.uuid4().hex[:16]

        try:
            output = self._stub_dispatch(command)
            duration_ms = (time.monotonic() - t0) * 1000

            self._commands_executed += 1
            if domain:
                self._domains_visited.add(domain)
            elif command.action == BrowserAction.NAVIGATE and command.target:
                self._domains_visited.add(_extract_domain(command.target))

            # Record to action log
            self._action_log.append({
                "action": command.action.value,
                "target": command.target,
                "value": command.value,
                "audit_id": audit_id,
                "success": True,
            })

            result = BrowserResult(
                command=command,
                success=True,
                output=output,
                duration_ms=duration_ms,
                audit_id=audit_id,
            )

            # Screenshot stub
            if (
                command.action == BrowserAction.SCREENSHOT
                and self._config.screenshot_enabled
            ):
                result.screenshot_data = b"stub_screenshot_data"

            self._emit_audit({
                "event": "action_executed",
                "action": command.action.value,
                "target": command.target,
                "audit_id": audit_id,
                "success": True,
            })

            return result

        except Exception as exc:
            duration_ms = (time.monotonic() - t0) * 1000
            self._action_log.append({
                "action": command.action.value,
                "target": command.target,
                "audit_id": audit_id,
                "success": False,
                "error": str(exc),
            })
            self._emit_audit({
                "event": "action_failed",
                "action": command.action.value,
                "audit_id": audit_id,
                "error": str(exc),
            })
            return BrowserResult(
                command=command,
                success=False,
                error=str(exc),
                duration_ms=duration_ms,
                audit_id=audit_id,
            )

    def _stub_dispatch(self, command: BrowserCommand) -> Any:
        """Return stub output for each action type."""
        action = command.action
        if action == BrowserAction.NAVIGATE:
            return {"url": command.target, "status": 200, "stub": True}
        elif action == BrowserAction.CLICK:
            return {"clicked": command.target, "stub": True}
        elif action == BrowserAction.TYPE:
            return {"typed": command.value, "into": command.target, "stub": True}
        elif action == BrowserAction.SCREENSHOT:
            return {"screenshot": "stub_data", "stub": True}
        elif action == BrowserAction.EVALUATE:
            return {"result": None, "expression": command.value, "stub": True}
        elif action == BrowserAction.WAIT:
            return {"waited": command.target or command.value, "stub": True}
        elif action == BrowserAction.SCROLL:
            return {"scrolled": command.target, "value": command.value, "stub": True}
        elif action == BrowserAction.SELECT:
            return {"selected": command.value, "in": command.target, "stub": True}
        return {"action": action.value, "stub": True}
