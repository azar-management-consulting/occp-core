"""Kill switch — hard-stop primitive for autonomous OCCP operations.

Industry pattern (2026):
- Every production AI agent needs a hard-stop with state capture.
- The kill switch itself must not be writeable by the agents it controls.
- Activation + deactivation must be logged with immutable evidence.
- Multiple trigger classes: manual, anomaly-based, canary-failure, error-spike.

Design (OCCP v0.10.0):
- Pure in-process state (process-global, thread-safe)
- Fail-secure: default OFF; any component may QUERY state cheaply
- Activation records: reason, actor, evidence, timestamp
- Never auto-deactivates — human must explicitly clear
- Governed by architecture/governance.yaml immutable paths (itself in boundaries)

This module does NOT enforce throttling — it publishes the state.
Consumers (pipeline, brain_flow, mcp_bridge) check `is_active()` at
entry points and refuse to proceed when active.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


def _emit_gauge(active: bool) -> None:
    """Set the kill-switch gauge metric. Import-safe / never raises."""
    try:
        from observability.metrics_collector import get_collector

        get_collector().set_kill_switch_active(active)
    except Exception as exc:  # noqa: BLE001
        logger.debug("kill_switch gauge emit failed: %s", exc)


def _emit_activation(*, trigger: str, actor: str) -> None:
    """Increment activations counter. Import-safe / never raises."""
    try:
        from observability.metrics_collector import get_collector

        get_collector().record_kill_switch_activation(
            trigger=trigger, actor=actor
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("kill_switch activation emit failed: %s", exc)


class KillSwitchState(str, Enum):
    """Current state of the kill switch."""

    INACTIVE = "inactive"      # Normal operation
    ACTIVE = "active"          # Hard stop — refuse all autonomous actions
    DRILL = "drill"            # Test activation — logs but does not block


class KillSwitchTrigger(str, Enum):
    """Why the kill switch was activated."""

    MANUAL = "manual"                  # Henry flipped it
    ANOMALY = "anomaly"                # AnomalyDetector critical finding
    CANARY_FAILURE = "canary_failure"  # CanaryEngine rollback verdict
    ERROR_SPIKE = "error_spike"        # Error rate threshold exceeded
    SECURITY = "security"              # Input sanitizer / policy critical
    DRILL = "drill"                    # Test (does not block)


@dataclass
class KillSwitchActivation:
    """A single activation record (immutable once recorded)."""

    state: KillSwitchState
    trigger: KillSwitchTrigger
    actor: str                  # "henry" | "anomaly_detector" | "canary_engine"
    reason: str
    evidence: dict[str, Any] = field(default_factory=dict)
    activated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    deactivated_at: datetime | None = None
    deactivated_by: str | None = None
    deactivation_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "trigger": self.trigger.value,
            "actor": self.actor,
            "reason": self.reason,
            "evidence": self.evidence,
            "activated_at": self.activated_at.isoformat(),
            "deactivated_at": (
                self.deactivated_at.isoformat() if self.deactivated_at else None
            ),
            "deactivated_by": self.deactivated_by,
            "deactivation_reason": self.deactivation_reason,
        }


class KillSwitch:
    """Process-global hard-stop state.

    Thread-safe. Exposes:
    - is_active()        — fast read, used by entry points
    - is_drill()         — read drill state
    - activate(...)      — flip to ACTIVE with audit record
    - drill(...)         — flip to DRILL with audit record
    - deactivate(...)    — clear, requires explicit actor+reason
    - status()           — current state + last 10 activations
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._state: KillSwitchState = KillSwitchState.INACTIVE
        self._current: KillSwitchActivation | None = None
        self._history: list[KillSwitchActivation] = []
        self._max_history = 100

    # ── Fast-path reads (called by pipeline on every task) ──
    def is_active(self) -> bool:
        """Return True iff the switch is ACTIVE (hard stop)."""
        return self._state == KillSwitchState.ACTIVE

    def is_drill(self) -> bool:
        """Return True iff the switch is in DRILL mode."""
        return self._state == KillSwitchState.DRILL

    @property
    def state(self) -> KillSwitchState:
        return self._state

    @property
    def current_activation(self) -> KillSwitchActivation | None:
        return self._current

    # ── State transitions ────────────────────────────────
    def activate(
        self,
        *,
        trigger: KillSwitchTrigger,
        actor: str,
        reason: str,
        evidence: dict[str, Any] | None = None,
    ) -> KillSwitchActivation:
        """Flip to ACTIVE. If already active, updates the reason."""
        with self._lock:
            record = KillSwitchActivation(
                state=KillSwitchState.ACTIVE,
                trigger=trigger,
                actor=actor,
                reason=reason,
                evidence=evidence or {},
            )
            self._state = KillSwitchState.ACTIVE
            self._current = record
            self._append_history(record)
            logger.critical(
                "KILL_SWITCH ACTIVATED trigger=%s actor=%s reason=%s",
                trigger.value,
                actor,
                reason,
            )
            _emit_gauge(True)
            _emit_activation(trigger=trigger.value, actor=actor)
            return record

    def drill(
        self,
        *,
        actor: str,
        reason: str,
        evidence: dict[str, Any] | None = None,
    ) -> KillSwitchActivation:
        """Flip to DRILL — logs and simulates but does not block operations.

        Used for verifying the activation path without stopping production.
        """
        with self._lock:
            record = KillSwitchActivation(
                state=KillSwitchState.DRILL,
                trigger=KillSwitchTrigger.DRILL,
                actor=actor,
                reason=reason,
                evidence=evidence or {},
            )
            self._state = KillSwitchState.DRILL
            self._current = record
            self._append_history(record)
            logger.warning(
                "KILL_SWITCH DRILL actor=%s reason=%s", actor, reason
            )
            return record

    def deactivate(
        self,
        *,
        actor: str,
        reason: str,
    ) -> KillSwitchActivation | None:
        """Clear the switch. Requires explicit actor + reason for audit."""
        with self._lock:
            if self._state == KillSwitchState.INACTIVE:
                logger.info("KILL_SWITCH deactivate: already inactive")
                return None
            prev = self._current
            if prev is not None:
                prev.deactivated_at = datetime.now(timezone.utc)
                prev.deactivated_by = actor
                prev.deactivation_reason = reason
            self._state = KillSwitchState.INACTIVE
            self._current = None
            logger.warning(
                "KILL_SWITCH DEACTIVATED actor=%s reason=%s (was %s)",
                actor,
                reason,
                prev.state.value if prev else "?",
            )
            _emit_gauge(False)
            return prev

    # ── Introspection ────────────────────────────────────
    def status(self) -> dict[str, Any]:
        """Return current state + recent history."""
        with self._lock:
            return {
                "state": self._state.value,
                "is_active": self.is_active(),
                "is_drill": self.is_drill(),
                "current": self._current.to_dict() if self._current else None,
                "history_count": len(self._history),
                "recent_history": [r.to_dict() for r in self._history[-10:]],
            }

    def stats(self) -> dict[str, Any]:
        """Aggregate statistics across all activations."""
        with self._lock:
            total = len(self._history)
            by_trigger: dict[str, int] = {}
            for r in self._history:
                by_trigger[r.trigger.value] = by_trigger.get(r.trigger.value, 0) + 1
            return {
                "total_activations": total,
                "by_trigger": by_trigger,
                "current_state": self._state.value,
            }

    def reset(self) -> None:
        """Test-only: reset history + state."""
        with self._lock:
            self._state = KillSwitchState.INACTIVE
            self._current = None
            self._history.clear()

    # ── Internal ────────────────────────────────────────
    def _append_history(self, record: KillSwitchActivation) -> None:
        self._history.append(record)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history :]


# ── Singleton accessor ────────────────────────────────────────
_global_switch: KillSwitch | None = None
_init_lock = threading.Lock()


def get_kill_switch() -> KillSwitch:
    """Return the process-global KillSwitch singleton."""
    global _global_switch
    if _global_switch is None:
        with _init_lock:
            if _global_switch is None:
                _global_switch = KillSwitch()
                logger.info("kill_switch: initialized (state=inactive)")
    return _global_switch


class KillSwitchActive(Exception):
    """Raised by enforcement points when the kill switch is ACTIVE."""

    def __init__(
        self,
        reason: str,
        trigger: KillSwitchTrigger,
        activation: KillSwitchActivation | None = None,
    ) -> None:
        self.reason = reason
        self.trigger = trigger
        self.activation = activation
        super().__init__(f"Kill switch ACTIVE ({trigger.value}): {reason}")


def require_kill_switch_inactive() -> None:
    """Entry-point guard: raise KillSwitchActive if switch is flipped.

    Fast-path: check without lock for common case. Only blocks on ACTIVE,
    not DRILL (drill logs but does not block).
    """
    ks = get_kill_switch()
    if ks.is_active():
        current = ks.current_activation
        raise KillSwitchActive(
            reason=current.reason if current else "unknown",
            trigger=current.trigger if current else KillSwitchTrigger.MANUAL,
            activation=current,
        )
