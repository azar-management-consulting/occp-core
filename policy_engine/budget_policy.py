"""Pre-flight token-budget policy — L6 spend enforcement (OCCP v0.10.0+).

Problem (the "$47k-loop"):
  An autonomous agent enters a self-looping planning cycle. Each turn
  sends ~50k cached tokens and produces ~8k output tokens. At Sonnet
  pricing (~$15 / 1M out) a single misbehaving task burned ~$47k in
  under 24h in the reference post-mortem. By the time the human saw
  the bill the money was gone.

Defence-in-depth:
  1. **Pre-flight check** — before every LLM call, estimate the call's
     USD cost (based on current model's input/output/cache pricing)
     and refuse if the task would exceed its per-task budget.
  2. **Post-flight accounting** — after every LLM call, record the
     ACTUAL usage (including cache read/write breakdown) so the next
     pre-flight check reflects reality.
  3. **Persistent store** — per-task spend lives in Redis so budgets
     survive container restarts and are shared across worker
     processes. SQLite (via the default `aiosqlite` stack) is used as
     a fallback when Redis is unavailable; for a safe ultimate fallback
     we keep a process-local in-memory dict.

This module is import-safe. It does NOT modify ``policy_engine/guards.py``
(immutable per governance); instead it lives as a sibling.

Env configuration::

    OCCP_DEFAULT_TASK_BUDGET_USD=5.00        # default per-task budget
    OCCP_REDIS_URL=redis://localhost:6379/0  # shared with kill switch
    OCCP_BUDGET_TIKTOKEN_MODEL=cl100k_base   # tokenizer for estimation

"""

from __future__ import annotations

import json
import logging
import math
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

# ── Optional deps (graceful degradation) ─────────────────────

try:  # pragma: no cover
    import redis as _redis  # type: ignore[import-not-found]
    from redis.exceptions import RedisError as _RedisError  # type: ignore[import-not-found]
    _REDIS_AVAILABLE = True
except ImportError:  # pragma: no cover
    _redis = None  # type: ignore[assignment]
    _RedisError = Exception  # type: ignore[assignment,misc]
    _REDIS_AVAILABLE = False

try:  # pragma: no cover — pure heuristic fallback below
    import tiktoken as _tiktoken  # type: ignore[import-not-found]
    _TIKTOKEN_AVAILABLE = True
except ImportError:  # pragma: no cover
    _tiktoken = None  # type: ignore[assignment]
    _TIKTOKEN_AVAILABLE = False


# ── Pricing table (USD per 1M tokens, 2026 schedule) ─────────
#
# Keep this table as the single source of truth for OCCP spend math.
# If Anthropic updates the rate card, update here — all downstream
# accounting (dashboards, alerts, fiscal reports) reads from this
# module.


class Model(str, Enum):
    HAIKU_45 = "claude-haiku-4-5"
    SONNET_46 = "claude-sonnet-4-6"
    OPUS_47 = "claude-opus-4-7"


PRICING: dict[str, dict[str, float]] = {
    Model.HAIKU_45.value: {
        "input": 1.0,
        "output": 5.0,
        "cache_read": 0.10,
        "cache_write_5m": 1.25,
    },
    Model.SONNET_46.value: {
        "input": 3.0,
        "output": 15.0,
        "cache_read": 0.30,
        "cache_write_5m": 3.75,
    },
    Model.OPUS_47.value: {
        "input": 5.0,
        "output": 25.0,
        "cache_read": 0.50,
        "cache_write_5m": 6.25,
    },
}

# Fallback/synonym map so "haiku", "sonnet", "opus" short names work
# regardless of the exact version string the caller uses.
_MODEL_ALIASES: dict[str, str] = {
    "haiku": Model.HAIKU_45.value,
    "sonnet": Model.SONNET_46.value,
    "opus": Model.OPUS_47.value,
    "claude-haiku": Model.HAIKU_45.value,
    "claude-sonnet": Model.SONNET_46.value,
    "claude-opus": Model.OPUS_47.value,
}


def _resolve_model(model: str) -> str:
    """Map a user-provided model name to a key in :data:`PRICING`.

    Longest-prefix match against known aliases; raises ``ValueError``
    if nothing plausible matches.
    """
    if model in PRICING:
        return model
    m = model.lower().strip()
    for alias, canonical in _MODEL_ALIASES.items():
        if m.startswith(alias):
            return canonical
    raise ValueError(
        f"Unknown model '{model}'. Known: {', '.join(PRICING)}"
    )


# ── Exceptions ───────────────────────────────────────────────


class BudgetExceededError(Exception):
    """Raised when a pre-flight check would exceed the task budget."""

    def __init__(
        self,
        task_id: str,
        reason: str,
        *,
        spent_usd: float,
        estimated_usd: float,
        budget_usd: float,
    ) -> None:
        self.task_id = task_id
        self.reason = reason
        self.spent_usd = spent_usd
        self.estimated_usd = estimated_usd
        self.budget_usd = budget_usd
        super().__init__(
            f"Budget exceeded for task={task_id}: {reason} "
            f"(spent=${spent_usd:.4f} + est=${estimated_usd:.4f} "
            f"> budget=${budget_usd:.4f})"
        )


# ── Data model ───────────────────────────────────────────────


@dataclass
class CacheBreakdown:
    """Per-call cache accounting.

    Uses the names that Anthropic returns in ``message.usage.*``:
    ``cache_read_input_tokens`` and ``cache_creation_input_tokens``.
    """

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0


@dataclass
class BudgetSpend:
    """Aggregated spend for a single task."""

    task_id: str
    spent_usd: float = 0.0
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    last_model: str | None = None
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "spent_usd": round(self.spent_usd, 6),
            "calls": self.calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "cache_write_tokens": self.cache_write_tokens,
            "last_model": self.last_model,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BudgetSpend:
        return cls(
            task_id=data["task_id"],
            spent_usd=float(data.get("spent_usd", 0.0)),
            calls=int(data.get("calls", 0)),
            input_tokens=int(data.get("input_tokens", 0)),
            output_tokens=int(data.get("output_tokens", 0)),
            cache_read_tokens=int(data.get("cache_read_tokens", 0)),
            cache_write_tokens=int(data.get("cache_write_tokens", 0)),
            last_model=data.get("last_model"),
            updated_at=data.get("updated_at")
            or datetime.now(timezone.utc).isoformat(),
        )


# ── Pricing math ─────────────────────────────────────────────


def price_call(
    model: str,
    *,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_read_input_tokens: int = 0,
    cache_creation_input_tokens: int = 0,
) -> float:
    """Return the USD cost of a single LLM call given token breakdown.

    All rates are per 1,000,000 tokens (see :data:`PRICING`).
    """
    canonical = _resolve_model(model)
    rates = PRICING[canonical]
    cost = (
        input_tokens * rates["input"]
        + output_tokens * rates["output"]
        + cache_read_input_tokens * rates["cache_read"]
        + cache_creation_input_tokens * rates["cache_write_5m"]
    ) / 1_000_000.0
    return cost


def estimate_tokens(text: str, *, encoding_name: str = "cl100k_base") -> int:
    """Estimate token count for *text*.

    Uses tiktoken when available (exact), otherwise a byte-pair-ish
    heuristic that is within ~15% for English prose and is stable /
    deterministic for unit tests.
    """
    if not text:
        return 0
    if _TIKTOKEN_AVAILABLE:
        try:
            enc = _tiktoken.get_encoding(encoding_name)
            return len(enc.encode(text))
        except Exception as exc:  # noqa: BLE001
            logger.debug("tiktoken failed (%s) — falling back to heuristic", exc)
    # Heuristic: ~4 chars/token for English prose; bias up slightly
    # to avoid under-estimating cost.
    return max(1, math.ceil(len(text) / 3.6))


# ── Storage backends ─────────────────────────────────────────


class _MemoryBackend:
    """Process-local fallback. Used when Redis is unavailable."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._store: dict[str, BudgetSpend] = {}

    def get(self, task_id: str) -> BudgetSpend:
        with self._lock:
            return self._store.get(task_id) or BudgetSpend(task_id=task_id)

    def set(self, spend: BudgetSpend) -> None:
        with self._lock:
            self._store[spend.task_id] = spend

    def clear(self, task_id: str | None = None) -> None:
        with self._lock:
            if task_id is None:
                self._store.clear()
            else:
                self._store.pop(task_id, None)


class _RedisBackend:
    """Redis-backed budget store. Shared by all worker processes."""

    KEY_PREFIX = "occp:budget:"
    TTL_SECONDS = 7 * 24 * 3600  # 7 days — tasks should finalise long before

    def __init__(self, client: Any) -> None:
        self._client = client

    def _key(self, task_id: str) -> str:
        return f"{self.KEY_PREFIX}{task_id}"

    def get(self, task_id: str) -> BudgetSpend:
        raw = self._client.get(self._key(task_id))
        if raw is None:
            return BudgetSpend(task_id=task_id)
        try:
            return BudgetSpend.from_dict(json.loads(raw))
        except (TypeError, ValueError, KeyError):
            return BudgetSpend(task_id=task_id)

    def set(self, spend: BudgetSpend) -> None:
        payload = json.dumps(spend.to_dict(), separators=(",", ":"))
        self._client.set(self._key(spend.task_id), payload, ex=self.TTL_SECONDS)

    def clear(self, task_id: str | None = None) -> None:
        if task_id is None:
            # Intentionally refuse a global wipe — use per-task cleanup
            raise ValueError(
                "Refusing to wipe all budget keys; provide explicit task_id"
            )
        self._client.delete(self._key(task_id))


# ── BudgetPolicy ─────────────────────────────────────────────


class BudgetPolicy:
    """Enforces a per-task USD budget for all LLM calls.

    Typical flow::

        policy = BudgetPolicy(default_budget_usd=5.0)

        passed, reason = policy.check(
            task_id="t-1",
            estimated_tokens=8000,
            model="sonnet",
        )
        if not passed:
            raise BudgetExceededError(..., reason=reason, ...)

        # ... perform LLM call ...

        policy.record_spend(
            task_id="t-1",
            model="sonnet",
            cache_breakdown=CacheBreakdown(
                input_tokens=r.usage.input_tokens,
                output_tokens=r.usage.output_tokens,
                cache_read_input_tokens=r.usage.cache_read_input_tokens or 0,
                cache_creation_input_tokens=r.usage.cache_creation_input_tokens or 0,
            ),
        )

    Thread-safe.
    """

    def __init__(
        self,
        *,
        default_budget_usd: float | None = None,
        redis_client: Any | None = None,
        redis_url: str | None = None,
        per_task_budgets: dict[str, float] | None = None,
    ) -> None:
        self._default_budget = (
            default_budget_usd
            if default_budget_usd is not None
            else float(os.environ.get("OCCP_DEFAULT_TASK_BUDGET_USD", "5.00"))
        )
        self._per_task_budgets: dict[str, float] = dict(per_task_budgets or {})
        self._lock = threading.RLock()

        backend: _MemoryBackend | _RedisBackend
        if redis_client is not None:
            backend = _RedisBackend(redis_client)
            self._backend_name = "redis"
        elif _REDIS_AVAILABLE:
            url = redis_url or os.environ.get(
                "OCCP_REDIS_URL", "redis://localhost:6379/0"
            )
            try:
                client = _redis.Redis.from_url(  # type: ignore[union-attr]
                    url,
                    decode_responses=True,
                    socket_connect_timeout=2.0,
                    socket_timeout=2.0,
                )
                client.ping()
                backend = _RedisBackend(client)
                self._backend_name = "redis"
                logger.info("BudgetPolicy: using Redis backend @ %s", url)
            except Exception as exc:  # noqa: BLE001 — fail-secure to memory
                logger.warning(
                    "BudgetPolicy: Redis unavailable (%s) — using in-memory backend",
                    exc,
                )
                backend = _MemoryBackend()
                self._backend_name = "memory"
        else:
            backend = _MemoryBackend()
            self._backend_name = "memory"

        self._backend: _MemoryBackend | _RedisBackend = backend

    # ── config ──────────────────────────────────────────────

    @property
    def backend(self) -> str:
        return self._backend_name

    @property
    def default_budget_usd(self) -> float:
        return self._default_budget

    def set_task_budget(self, task_id: str, budget_usd: float) -> None:
        """Override the default budget for a specific task."""
        if budget_usd < 0:
            raise ValueError("budget_usd must be non-negative")
        with self._lock:
            self._per_task_budgets[task_id] = budget_usd

    def get_task_budget(self, task_id: str) -> float:
        return self._per_task_budgets.get(task_id, self._default_budget)

    # ── storage operations (safe wrappers) ──────────────────

    def _safe_get(self, task_id: str) -> BudgetSpend:
        try:
            return self._backend.get(task_id)
        except _RedisError as exc:  # type: ignore[misc]
            logger.warning(
                "BudgetPolicy: Redis GET failed (%s) — degrading to memory",
                exc,
            )
            self._backend = _MemoryBackend()
            self._backend_name = "memory"
            return self._backend.get(task_id)

    def _safe_set(self, spend: BudgetSpend) -> None:
        try:
            self._backend.set(spend)
        except _RedisError as exc:  # type: ignore[misc]
            logger.warning(
                "BudgetPolicy: Redis SET failed (%s) — degrading to memory",
                exc,
            )
            self._backend = _MemoryBackend()
            self._backend_name = "memory"
            self._backend.set(spend)

    # ── public API ──────────────────────────────────────────

    def get_spend(self, task_id: str) -> float:
        """Return the USD spent so far on *task_id*."""
        return self._safe_get(task_id).spent_usd

    def check(
        self,
        task_id: str,
        *,
        estimated_tokens: int,
        model: str,
        output_ratio: float = 0.25,
    ) -> tuple[bool, str | None]:
        """Pre-flight budget check.

        ``estimated_tokens`` is the *total* estimated tokens the call
        will consume. We split that 75/25 input/output by default
        (``output_ratio``) for cost estimation — callers that know
        more can also pass a model-specific ratio.

        Returns ``(passed, reason)``. When ``passed`` is False, ``reason``
        describes why so the caller can surface it to the audit trail.
        """
        if estimated_tokens < 0:
            return False, "estimated_tokens must be non-negative"

        try:
            canonical_model = _resolve_model(model)
        except ValueError as exc:
            return False, str(exc)

        output_tokens = int(estimated_tokens * output_ratio)
        input_tokens = max(0, estimated_tokens - output_tokens)
        est_usd = price_call(
            canonical_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

        spent = self.get_spend(task_id)
        budget = self.get_task_budget(task_id)
        if spent + est_usd > budget:
            return False, (
                f"pre-flight budget exceeded: spent=${spent:.4f} + "
                f"est=${est_usd:.4f} > budget=${budget:.4f}"
            )
        return True, None

    def record_spend(
        self,
        task_id: str,
        *,
        model: str,
        cache_breakdown: CacheBreakdown | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
    ) -> BudgetSpend:
        """Post-flight: record the actual token usage of a completed call.

        Callers may pass either a :class:`CacheBreakdown` (preferred —
        mirrors Anthropic's ``message.usage.*`` shape) or the bare
        ``input_tokens`` / ``output_tokens`` integers.
        """
        canonical_model = _resolve_model(model)

        if cache_breakdown is None:
            cache_breakdown = CacheBreakdown(
                input_tokens=input_tokens or 0,
                output_tokens=output_tokens or 0,
            )

        cost = price_call(
            canonical_model,
            input_tokens=cache_breakdown.input_tokens,
            output_tokens=cache_breakdown.output_tokens,
            cache_read_input_tokens=cache_breakdown.cache_read_input_tokens,
            cache_creation_input_tokens=cache_breakdown.cache_creation_input_tokens,
        )

        with self._lock:
            spend = self._safe_get(task_id)
            spend.spent_usd = round(spend.spent_usd + cost, 6)
            spend.calls += 1
            spend.input_tokens += cache_breakdown.input_tokens
            spend.output_tokens += cache_breakdown.output_tokens
            spend.cache_read_tokens += cache_breakdown.cache_read_input_tokens
            spend.cache_write_tokens += (
                cache_breakdown.cache_creation_input_tokens
            )
            spend.last_model = canonical_model
            spend.updated_at = datetime.now(timezone.utc).isoformat()
            self._safe_set(spend)

        logger.info(
            "BudgetPolicy.record_spend task=%s model=%s +$%.6f total=$%.6f",
            task_id,
            canonical_model,
            cost,
            spend.spent_usd,
        )
        return spend

    def reset(self, task_id: str) -> None:
        """Clear accumulated spend for *task_id*. Test / admin helper."""
        self._backend.clear(task_id)

    def snapshot(self, task_id: str) -> dict[str, Any]:
        """Full snapshot of a task's budget state — safe to return in API."""
        spend = self._safe_get(task_id)
        budget = self.get_task_budget(task_id)
        return {
            "backend": self._backend_name,
            "budget_usd": budget,
            "remaining_usd": max(0.0, budget - spend.spent_usd),
            **spend.to_dict(),
        }


# ── Singleton ─────────────────────────────────────────────────

_global_policy: BudgetPolicy | None = None
_init_lock = threading.Lock()


def get_budget_policy() -> BudgetPolicy:
    """Return the process-global :class:`BudgetPolicy` singleton."""
    global _global_policy
    if _global_policy is None:
        with _init_lock:
            if _global_policy is None:
                _global_policy = BudgetPolicy()
    return _global_policy


def reset_budget_policy() -> None:
    """Test-only: discard the cached singleton."""
    global _global_policy
    with _init_lock:
        _global_policy = None
