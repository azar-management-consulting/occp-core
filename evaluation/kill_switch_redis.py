"""Redis-backed persistent kill switch — L6 hardening (OCCP v0.10.0+).

Why Redis?
- The in-memory :class:`evaluation.kill_switch.KillSwitch` loses state on
  container restart. In production this is unsafe: an operator flips the
  switch to stop a runaway agent, the pod restarts (OOMKill, rolling
  upgrade, evicted), and the agent resumes burning tokens/cash.
- A Redis-backed switch survives restarts, is atomic across multiple
  worker processes, and can be flipped from any admin surface.

Design:
- Persistent state key:  ``occp:agent:halt``  (single JSON blob)
- Fail-secure: if Redis is unavailable AND backend is ``redis``, we
  transparently fall through to the in-memory :class:`KillSwitch`
  singleton so the pipeline never "opens" due to infrastructure failure.
- Writes are audited: every ``activate()`` / ``deactivate()`` also
  updates a capped history list at ``occp:agent:halt:history`` (LPUSH +
  LTRIM 0 99).
- Backend selected by env ``OCCP_KILL_SWITCH_BACKEND`` (``redis`` |
  ``memory``, default ``memory`` for backwards compatibility).
- Connection from ``OCCP_REDIS_URL`` (default
  ``redis://localhost:6379/0``).

This module is import-safe: if the ``redis`` package is not installed
we silently expose the in-memory implementation so that existing call
sites continue to work.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone
from typing import Any

from evaluation.kill_switch import (
    KillSwitch,
    KillSwitchActivation,
    KillSwitchState,
    KillSwitchTrigger,
    get_kill_switch,
)

logger = logging.getLogger(__name__)

# ── Redis import is optional — degrade gracefully ─────────────
try:  # pragma: no cover — exercised in test_fallback_to_memory_when_redis_down
    import redis as _redis  # type: ignore[import-not-found]
    from redis.exceptions import RedisError as _RedisError  # type: ignore[import-not-found]
    _REDIS_AVAILABLE = True
except ImportError:  # pragma: no cover
    _redis = None  # type: ignore[assignment]
    _RedisError = Exception  # type: ignore[assignment,misc]
    _REDIS_AVAILABLE = False


# ── Constants ────────────────────────────────────────────────

HALT_KEY: str = "occp:agent:halt"
HISTORY_KEY: str = "occp:agent:halt:history"
HISTORY_CAP: int = 100

DEFAULT_REDIS_URL: str = "redis://localhost:6379/0"
ENV_REDIS_URL: str = "OCCP_REDIS_URL"
ENV_BACKEND: str = "OCCP_KILL_SWITCH_BACKEND"


# ── Redis kill switch ────────────────────────────────────────


class RedisKillSwitch:
    """Persistent hard-stop state backed by Redis.

    Drop-in companion to :class:`KillSwitch` with identical semantics
    plus cross-process persistence.

    Fallback rules:
    - If ``redis`` is not installed → delegate every call to the
      in-memory singleton.
    - If Redis is installed but a command raises ``RedisError`` →
      log + delegate to the in-memory singleton (fail-secure).
    """

    def __init__(
        self,
        *,
        redis_url: str | None = None,
        redis_client: Any | None = None,
        halt_key: str = HALT_KEY,
        history_key: str = HISTORY_KEY,
    ) -> None:
        self._halt_key = halt_key
        self._history_key = history_key
        self._lock = threading.RLock()
        self._memory_fallback: KillSwitch = get_kill_switch()

        if redis_client is not None:
            self._client = redis_client
            self._available = True
            return

        if not _REDIS_AVAILABLE:
            logger.warning(
                "redis package not installed — RedisKillSwitch will "
                "delegate to in-memory KillSwitch"
            )
            self._client = None
            self._available = False
            return

        url = redis_url or os.environ.get(ENV_REDIS_URL, DEFAULT_REDIS_URL)
        try:
            self._client = _redis.Redis.from_url(  # type: ignore[union-attr]
                url,
                decode_responses=True,
                socket_connect_timeout=2.0,
                socket_timeout=2.0,
            )
            # Ping to verify connectivity at construction time.
            self._client.ping()
            self._available = True
            logger.info("RedisKillSwitch: connected to %s", url)
        except Exception as exc:  # noqa: BLE001 — fail-secure
            logger.warning(
                "RedisKillSwitch: cannot connect to %s (%s) — "
                "falling back to in-memory KillSwitch",
                url,
                exc,
            )
            self._client = None
            self._available = False

    # ── Backend helpers ─────────────────────────────────────

    @property
    def backend(self) -> str:
        """Return the currently active backend (``redis`` | ``memory``)."""
        return "redis" if self._available else "memory"

    def _safe_call(self, op: str, fn: Any, *args: Any, **kwargs: Any) -> Any:
        """Execute *fn* and fall through to memory on any backend failure.

        We intentionally catch BaseException-subclass failures broadly
        (RedisError, ConnectionError, TimeoutError, RuntimeError) so
        any infrastructure-level glitch degrades to the in-memory
        backend rather than breaking the caller. The kill switch must
        never fail-open.
        """
        if not self._available:
            return None
        try:
            return fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 — fail-secure
            logger.warning(
                "RedisKillSwitch: %s failed (%s) — falling back to memory",
                op,
                exc,
            )
            self._available = False
            return None

    # ── State transitions ───────────────────────────────────

    def activate(
        self,
        *,
        actor: str,
        reason: str,
        trigger: KillSwitchTrigger | str = KillSwitchTrigger.MANUAL,
        evidence: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Flip to ACTIVE (idempotent) and return the persisted record.

        The record is always written to the in-memory switch as well so
        both backends converge on the same state.
        """
        trig = (
            trigger
            if isinstance(trigger, KillSwitchTrigger)
            else KillSwitchTrigger(trigger)
        )
        record = {
            "state": KillSwitchState.ACTIVE.value,
            "trigger": trig.value,
            "actor": actor,
            "reason": reason,
            "evidence": evidence or {},
            "activated_at": datetime.now(timezone.utc).isoformat(),
            "deactivated_at": None,
            "deactivated_by": None,
            "deactivation_reason": None,
        }
        payload = json.dumps(record, separators=(",", ":"))

        with self._lock:
            # Write to Redis first (persistent truth).
            wrote = self._safe_call("SET halt", self._client.set, self._halt_key, payload) \
                if self._available else None
            if self._available and wrote is not None:
                self._safe_call(
                    "LPUSH history",
                    self._client.lpush,
                    self._history_key,
                    payload,
                )
                self._safe_call(
                    "LTRIM history",
                    self._client.ltrim,
                    self._history_key,
                    0,
                    HISTORY_CAP - 1,
                )

            # Mirror into memory singleton so local fast-path reads
            # also reflect the ACTIVE state.
            try:
                self._memory_fallback.activate(
                    trigger=trig,
                    actor=actor,
                    reason=reason,
                    evidence=evidence,
                )
            except Exception as exc:  # noqa: BLE001
                logger.debug("memory mirror activate failed: %s", exc)

        logger.critical(
            "RedisKillSwitch ACTIVATED backend=%s trigger=%s actor=%s reason=%s",
            self.backend,
            trig.value,
            actor,
            reason,
        )
        return record

    def deactivate(
        self,
        *,
        actor: str,
        reason: str,
    ) -> dict[str, Any] | None:
        """Clear the switch. Returns the prior activation record or ``None``.

        Idempotent: calling when already inactive is a no-op (returns
        ``None``) and is logged at INFO.
        """
        with self._lock:
            prev_raw = None
            if self._available:
                prev_raw = self._safe_call("GET halt", self._client.get, self._halt_key)

            if prev_raw is None:
                # Redis says inactive (or unreachable) — consult memory.
                mem_prev = self._memory_fallback.deactivate(
                    actor=actor, reason=reason
                )
                if mem_prev is None:
                    logger.info(
                        "RedisKillSwitch deactivate: already inactive"
                    )
                    return None
                logger.warning(
                    "RedisKillSwitch DEACTIVATED (memory-only) actor=%s reason=%s",
                    actor,
                    reason,
                )
                return mem_prev.to_dict()

            try:
                record = json.loads(prev_raw)
            except (TypeError, ValueError):
                record = {}

            record["state"] = KillSwitchState.INACTIVE.value
            record["deactivated_at"] = datetime.now(timezone.utc).isoformat()
            record["deactivated_by"] = actor
            record["deactivation_reason"] = reason

            self._safe_call("DEL halt", self._client.delete, self._halt_key)
            self._safe_call(
                "LPUSH history deactivate",
                self._client.lpush,
                self._history_key,
                json.dumps(record, separators=(",", ":")),
            )
            self._safe_call(
                "LTRIM history",
                self._client.ltrim,
                self._history_key,
                0,
                HISTORY_CAP - 1,
            )

            # Mirror into memory
            try:
                self._memory_fallback.deactivate(actor=actor, reason=reason)
            except Exception as exc:  # noqa: BLE001
                logger.debug("memory mirror deactivate failed: %s", exc)

        logger.warning(
            "RedisKillSwitch DEACTIVATED backend=%s actor=%s reason=%s",
            self.backend,
            actor,
            reason,
        )
        return record

    # ── Reads ───────────────────────────────────────────────

    def is_active(self) -> bool:
        """Return True iff the switch is currently ACTIVE.

        Fast path: a single Redis GET when available, O(1) otherwise.
        On Redis failure we fall through to the memory singleton.
        """
        if self._available:
            raw = self._safe_call("GET halt", self._client.get, self._halt_key)
            if raw is None and not self._available:
                # A Redis failure during the call flipped _available.
                return self._memory_fallback.is_active()
            if raw is None:
                return False
            try:
                rec = json.loads(raw)
                return rec.get("state") == KillSwitchState.ACTIVE.value
            except (TypeError, ValueError):
                return False
        return self._memory_fallback.is_active()

    def status(self) -> dict[str, Any]:
        """Return the current halt record and recent history."""
        current: dict[str, Any] | None = None
        history: list[dict[str, Any]] = []

        if self._available:
            raw = self._safe_call("GET halt", self._client.get, self._halt_key)
            if raw is not None:
                try:
                    current = json.loads(raw)
                except (TypeError, ValueError):
                    current = None
            raw_hist = self._safe_call(
                "LRANGE history", self._client.lrange, self._history_key, 0, 9
            ) or []
            for item in raw_hist:
                try:
                    history.append(json.loads(item))
                except (TypeError, ValueError):
                    continue

        if current is None and not self._available:
            # Pure fallback view
            return {
                "backend": self.backend,
                "state": self._memory_fallback.state.value,
                "is_active": self._memory_fallback.is_active(),
                "current": (
                    self._memory_fallback.current_activation.to_dict()
                    if self._memory_fallback.current_activation
                    else None
                ),
                "recent_history": [],
            }

        return {
            "backend": self.backend,
            "state": (
                current.get("state") if current else KillSwitchState.INACTIVE.value
            ),
            "is_active": bool(current) and current.get("state") == KillSwitchState.ACTIVE.value,
            "current": current,
            "recent_history": history,
        }


# ── Singleton ─────────────────────────────────────────────────

_global_redis_switch: RedisKillSwitch | None = None
_init_lock = threading.Lock()


def get_redis_kill_switch(
    *,
    redis_url: str | None = None,
    force_new: bool = False,
) -> RedisKillSwitch:
    """Return the process-global :class:`RedisKillSwitch` singleton.

    If ``OCCP_KILL_SWITCH_BACKEND`` is not ``redis`` the caller usually
    does not need this; the integration in :mod:`orchestrator.pipeline`
    checks the env var before calling us.
    """
    global _global_redis_switch
    if force_new or _global_redis_switch is None:
        with _init_lock:
            if force_new or _global_redis_switch is None:
                _global_redis_switch = RedisKillSwitch(redis_url=redis_url)
    return _global_redis_switch


def reset_redis_kill_switch() -> None:
    """Test-only: discard the cached singleton."""
    global _global_redis_switch
    with _init_lock:
        _global_redis_switch = None


def kill_switch_backend() -> str:
    """Return the configured backend from the environment.

    Values: ``"redis"`` or ``"memory"`` (default).
    """
    return os.environ.get(ENV_BACKEND, "memory").strip().lower()
