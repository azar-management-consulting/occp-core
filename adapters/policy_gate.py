"""PolicyGate — REQ-GOV-03: Non-Bypassable Universal Gate.

Wraps the PolicyEngine so that ALL adapter calls (MCP tools, plugin calls,
browser actions) are gated.  No code path from adapter to execution may
skip ``evaluate()``.

Also integrates REQ-GOV-06 trust level enforcement and REQ-GOV-04 break-glass
override checking.

Usage::

    gate = PolicyGate(engine=my_engine, trust_enforcer=my_enforcer)

    # Every adapter action goes through gate_action first
    decision = await gate.gate_action(
        task=task,
        agent_id="agent-001",
        trust_level=TrustLevel.L3_AUTONOMOUS,
        action="shell.exec",
        tool_category="execute",
    )
    if not decision.allowed:
        raise PermissionError(decision.reason)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from policy_engine.engine import GateResult, PolicyEngine
from policy_engine.trust_levels import (
    TrustCheckResult,
    TrustEnforcer,
    TrustLevel,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Gate Decision model
# ---------------------------------------------------------------------------


@dataclass
class GateDecision:
    """Combined decision from policy engine + trust enforcer."""

    allowed: bool
    reason: str = ""
    gate_result: GateResult | None = None
    trust_check: TrustCheckResult | None = None
    break_glass_token_id: str = ""
    bypassed_via_break_glass: bool = False
    checks_performed: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "bypassed_via_break_glass": self.bypassed_via_break_glass,
            "break_glass_token_id": self.break_glass_token_id,
            "checks_performed": self.checks_performed,
            "gate_result": self.gate_result.__dict__ if self.gate_result else None,
            "trust_check": self.trust_check.to_dict() if self.trust_check else None,
        }


# ---------------------------------------------------------------------------
# Policy Gate
# ---------------------------------------------------------------------------


class PolicyGateError(Exception):
    """Gate evaluation failure."""


class PolicyGate:
    """Universal non-bypassable gate — REQ-GOV-03.

    ALL adapter actions route through ``gate_action()``.  The gate performs:

    1. Trust level enforcement (REQ-GOV-06)
    2. Policy engine evaluation (REQ-POL-01/02)
    3. Optional break-glass override check (REQ-GOV-04)

    If any check fails, the action is denied unless an active break-glass
    token covers the required scope.
    """

    def __init__(
        self,
        *,
        engine: PolicyEngine | None = None,
        trust_enforcer: TrustEnforcer | None = None,
    ) -> None:
        self._engine = engine or PolicyEngine()
        self._trust_enforcer = trust_enforcer or TrustEnforcer()
        self._evaluation_count: int = 0
        self._bypass_attempts: int = 0

    @property
    def engine(self) -> PolicyEngine:
        return self._engine

    @property
    def trust_enforcer(self) -> TrustEnforcer:
        return self._trust_enforcer

    @property
    def evaluation_count(self) -> int:
        """Total number of gate_action calls processed."""
        return self._evaluation_count

    @property
    def bypass_attempts(self) -> int:
        """Number of denied actions (audit metric)."""
        return self._bypass_attempts

    async def gate_action(
        self,
        task: Any,
        *,
        agent_id: str,
        trust_level: TrustLevel,
        action: str,
        tool_category: str = "",
        requires_llm: bool = False,
        requires_network: bool = False,
        requires_spawn: bool = False,
        break_glass_token_id: str = "",
        break_glass_protocol: Any | None = None,
    ) -> GateDecision:
        """Universal gate check — MUST be called for every adapter action.

        Returns a :class:`GateDecision` indicating whether the action is
        allowed.  This is the ONLY entry point for action authorization.
        """
        self._evaluation_count += 1
        checks: list[str] = []

        # ── 1. Trust level enforcement ──────────────────────────────
        trust_result = self._trust_enforcer.check_action(
            agent_id,
            trust_level,
            action,
            tool_category=tool_category,
            requires_llm=requires_llm,
            requires_network=requires_network,
            requires_spawn=requires_spawn,
        )
        checks.append("trust_level")

        if not trust_result.allowed:
            # Check break-glass override before denying
            if break_glass_token_id and break_glass_protocol:
                if break_glass_protocol.check_scope(break_glass_token_id, action):
                    logger.warning(
                        "Break-glass override: agent=%s action=%s token=%s",
                        agent_id, action, break_glass_token_id,
                    )
                    checks.append("break_glass_override")
                    return GateDecision(
                        allowed=True,
                        trust_check=trust_result,
                        break_glass_token_id=break_glass_token_id,
                        bypassed_via_break_glass=True,
                        checks_performed=checks,
                    )

            self._bypass_attempts += 1
            return GateDecision(
                allowed=False,
                reason=trust_result.reason,
                trust_check=trust_result,
                checks_performed=checks,
            )

        # ── 2. Policy engine evaluation ─────────────────────────────
        try:
            gate_result = await self._engine.evaluate(task)
            checks.append("policy_engine")
        except Exception as exc:
            # Fail-secure: deny on engine errors
            self._bypass_attempts += 1
            return GateDecision(
                allowed=False,
                reason=f"Policy engine error: {exc}",
                trust_check=trust_result,
                checks_performed=checks,
            )

        if not gate_result.approved:
            # Check break-glass before denying
            if break_glass_token_id and break_glass_protocol:
                if break_glass_protocol.check_scope(break_glass_token_id, action):
                    logger.warning(
                        "Break-glass policy override: agent=%s action=%s",
                        agent_id, action,
                    )
                    checks.append("break_glass_override")
                    return GateDecision(
                        allowed=True,
                        gate_result=gate_result,
                        trust_check=trust_result,
                        break_glass_token_id=break_glass_token_id,
                        bypassed_via_break_glass=True,
                        checks_performed=checks,
                    )

            self._bypass_attempts += 1
            return GateDecision(
                allowed=False,
                reason=gate_result.reason,
                gate_result=gate_result,
                trust_check=trust_result,
                checks_performed=checks,
            )

        # ── All checks passed ───────────────────────────────────────
        return GateDecision(
            allowed=True,
            gate_result=gate_result,
            trust_check=trust_result,
            checks_performed=checks,
        )

    def check_content(self, text: str) -> list[dict[str, Any]]:
        """Synchronously check *text* through all guards.

        Returns a list of dicts, one per guard, with keys
        ``guard``, ``passed``, ``detail``.
        """
        payload = {"description": text}
        results = []
        for guard in self._engine._guards:
            gr = guard.check(payload)
            results.append({
                "guard": gr.guard_name,
                "passed": gr.passed,
                "detail": gr.detail,
            })
        return results

    async def evaluate(self, task: Any) -> GateResult:
        """Async evaluation passthrough to the engine.

        .. deprecated::
            Use :meth:`gate_action` instead for full trust+policy enforcement.
        """
        self._evaluation_count += 1
        return await self._engine.evaluate(task)
