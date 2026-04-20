"""Tests for policy_engine.budget_policy.

The tests run without real Redis: they either use the in-memory
backend (when no client is passed) or a tiny in-repo MockRedis that
implements GET/SET/DELETE — this keeps the suite hermetic and fast.
"""

from __future__ import annotations

import json
import threading

import pytest

from policy_engine.budget_policy import (
    PRICING,
    BudgetExceededError,
    BudgetPolicy,
    BudgetSpend,
    CacheBreakdown,
    Model,
    estimate_tokens,
    price_call,
    reset_budget_policy,
)


# ── Hermetic Redis test double ────────────────────────────────


class MockRedis:
    """Minimal in-memory Redis-ish client — supports GET/SET/DELETE.

    Enough surface to drive _RedisBackend. Thread-safe because the
    real client is thread-safe and BudgetPolicy does concurrent work.
    """

    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self._lock = threading.Lock()

    def set(self, key: str, value: str, ex: int | None = None) -> bool:
        with self._lock:
            self._store[key] = value
        return True

    def get(self, key: str) -> str | None:
        with self._lock:
            return self._store.get(key)

    def delete(self, *keys: str) -> int:
        removed = 0
        with self._lock:
            for k in keys:
                if k in self._store:
                    del self._store[k]
                    removed += 1
        return removed

    def ping(self) -> bool:
        return True


@pytest.fixture(autouse=True)
def _reset_singleton():
    reset_budget_policy()
    yield
    reset_budget_policy()


@pytest.fixture
def memory_policy():
    """Policy backed purely by in-memory store."""
    return BudgetPolicy(default_budget_usd=5.0)


@pytest.fixture
def redis_policy():
    """Policy backed by MockRedis — exercises the Redis code path."""
    return BudgetPolicy(default_budget_usd=5.0, redis_client=MockRedis())


# ── Pricing math sanity ──────────────────────────────────────


class TestPricingTable:

    def test_haiku_rates(self):
        assert PRICING[Model.HAIKU_45.value]["input"] == 1.0
        assert PRICING[Model.HAIKU_45.value]["output"] == 5.0

    def test_sonnet_rates(self):
        assert PRICING[Model.SONNET_46.value]["input"] == 3.0
        assert PRICING[Model.SONNET_46.value]["output"] == 15.0

    def test_opus_rates(self):
        assert PRICING[Model.OPUS_47.value]["input"] == 5.0
        assert PRICING[Model.OPUS_47.value]["output"] == 25.0

    def test_cache_read_is_tenth_of_input(self):
        for rates in PRICING.values():
            assert rates["cache_read"] == pytest.approx(rates["input"] * 0.1)


class TestPriceCall:

    def test_sonnet_simple_call(self):
        # 1M input + 1M output on Sonnet = $3 + $15 = $18
        cost = price_call("sonnet", input_tokens=1_000_000, output_tokens=1_000_000)
        assert cost == pytest.approx(18.0)

    def test_haiku_simple_call(self):
        # 1M in + 1M out on Haiku = $1 + $5 = $6
        cost = price_call("haiku", input_tokens=1_000_000, output_tokens=1_000_000)
        assert cost == pytest.approx(6.0)

    def test_opus_simple_call(self):
        # 1M in + 1M out on Opus = $5 + $25 = $30
        cost = price_call("opus", input_tokens=1_000_000, output_tokens=1_000_000)
        assert cost == pytest.approx(30.0)

    def test_cache_read_discount_sonnet(self):
        # Cache read rate is 0.30 / 1M for Sonnet
        cost = price_call(
            "sonnet",
            cache_read_input_tokens=1_000_000,
        )
        assert cost == pytest.approx(0.30)

    def test_cache_write_sonnet(self):
        # 5m cache write is 3.75 / 1M
        cost = price_call(
            "sonnet",
            cache_creation_input_tokens=1_000_000,
        )
        assert cost == pytest.approx(3.75)

    def test_unknown_model_raises(self):
        with pytest.raises(ValueError):
            price_call("llama-99", input_tokens=100)


# ── estimate_tokens ──────────────────────────────────────────


class TestEstimateTokens:

    def test_empty_string_is_zero(self):
        assert estimate_tokens("") == 0

    def test_nonempty_string_is_positive(self):
        assert estimate_tokens("hello world") > 0

    def test_longer_string_has_more_tokens(self):
        a = estimate_tokens("hello")
        b = estimate_tokens("hello " * 100)
        assert b > a


# ── pre-flight check ─────────────────────────────────────────


class TestCheckPassesBelowBudget:

    def test_check_passes_below_budget(self, memory_policy):
        # 10k tokens on Haiku ≈ $0.0275 (well under $5 budget)
        passed, reason = memory_policy.check(
            "task-1", estimated_tokens=10_000, model="haiku"
        )
        assert passed is True
        assert reason is None

    def test_check_passes_with_redis_backend(self, redis_policy):
        passed, reason = redis_policy.check(
            "task-1", estimated_tokens=10_000, model="sonnet"
        )
        assert passed is True
        assert reason is None


class TestCheckRejectsAboveBudget:

    def test_check_rejects_above_budget(self, memory_policy):
        # Opus: 10M tokens (75/25 split) → 7.5M in * $5 + 2.5M out * $25
        #     = $37.5 + $62.5 = $100 > $5 budget
        passed, reason = memory_policy.check(
            "task-1", estimated_tokens=10_000_000, model="opus"
        )
        assert passed is False
        assert reason is not None
        assert "budget" in reason.lower()

    def test_check_rejects_after_accumulated_spend(self, memory_policy):
        # Pre-load spend near the budget, a small new call should fail.
        memory_policy.record_spend(
            "task-1",
            model="opus",
            cache_breakdown=CacheBreakdown(
                input_tokens=500_000, output_tokens=150_000
            ),
        )
        # Budget = $5, already spent ~$6.25 (500k×$5 + 150k×$25 / 1M = 2.5+3.75)
        # Next call must fail even for 1k tokens.
        passed, reason = memory_policy.check(
            "task-1", estimated_tokens=1_000, model="opus"
        )
        assert passed is False
        assert "budget" in reason.lower()

    def test_negative_tokens_rejected(self, memory_policy):
        passed, reason = memory_policy.check(
            "task-1", estimated_tokens=-1, model="sonnet"
        )
        assert passed is False
        assert "non-negative" in reason


# ── record_spend accounting ──────────────────────────────────


class TestRecordSpendTracksUSDCorrectly:

    def test_haiku_record(self, memory_policy):
        spend = memory_policy.record_spend(
            "task-1",
            model="haiku",
            cache_breakdown=CacheBreakdown(
                input_tokens=1_000_000, output_tokens=1_000_000
            ),
        )
        # 1M in × $1 + 1M out × $5 = $6.0
        assert spend.spent_usd == pytest.approx(6.0, rel=1e-6)
        assert memory_policy.get_spend("task-1") == pytest.approx(6.0, rel=1e-6)

    def test_sonnet_record(self, memory_policy):
        spend = memory_policy.record_spend(
            "task-1",
            model="sonnet",
            cache_breakdown=CacheBreakdown(
                input_tokens=1_000_000, output_tokens=1_000_000
            ),
        )
        # 1M × $3 + 1M × $15 = $18
        assert spend.spent_usd == pytest.approx(18.0, rel=1e-6)

    def test_opus_record(self, memory_policy):
        spend = memory_policy.record_spend(
            "task-1",
            model="opus",
            cache_breakdown=CacheBreakdown(
                input_tokens=100_000, output_tokens=50_000
            ),
        )
        # 100k × $5 + 50k × $25 = $0.5 + $1.25 = $1.75
        assert spend.spent_usd == pytest.approx(1.75, rel=1e-6)

    def test_record_accumulates_across_calls(self, memory_policy):
        for _ in range(3):
            memory_policy.record_spend(
                "task-1",
                model="haiku",
                cache_breakdown=CacheBreakdown(
                    input_tokens=100_000, output_tokens=100_000
                ),
            )
        # 3 × (100k × $1 + 100k × $5) / 1M = 3 × $0.6 = $1.80
        assert memory_policy.get_spend("task-1") == pytest.approx(1.80, rel=1e-6)

    def test_record_updates_metadata(self, memory_policy):
        spend = memory_policy.record_spend(
            "task-1",
            model="sonnet",
            input_tokens=1000,
            output_tokens=500,
        )
        assert spend.calls == 1
        assert spend.input_tokens == 1000
        assert spend.output_tokens == 500
        assert spend.last_model == Model.SONNET_46.value

    def test_record_spend_persists_in_redis(self, redis_policy):
        redis_policy.record_spend(
            "task-1",
            model="haiku",
            cache_breakdown=CacheBreakdown(
                input_tokens=1_000_000, output_tokens=1_000_000
            ),
        )
        assert redis_policy.get_spend("task-1") == pytest.approx(6.0, rel=1e-6)


# ── cache discount ───────────────────────────────────────────


class TestCacheDiscountCalculated:

    def test_cache_read_is_tenth_of_input(self):
        # Sonnet: input = $3/1M, cache_read must be $0.30/1M = 10%
        direct = price_call("sonnet", input_tokens=1_000_000)
        cached = price_call("sonnet", cache_read_input_tokens=1_000_000)
        assert cached == pytest.approx(direct * 0.1)

    def test_cache_discount_applied_in_record(self, memory_policy):
        # 1M cache_read on Sonnet = $0.30 (vs $3 uncached)
        memory_policy.record_spend(
            "task-1",
            model="sonnet",
            cache_breakdown=CacheBreakdown(
                cache_read_input_tokens=1_000_000,
            ),
        )
        assert memory_policy.get_spend("task-1") == pytest.approx(0.30, rel=1e-6)

    def test_mixed_cached_and_uncached(self, memory_policy):
        # Typical loop shape: 50k cache_read + 8k output on Sonnet
        # cost = (50k × $0.30 + 8k × $15) / 1M
        #      = 0.015 + 0.120 = $0.135
        memory_policy.record_spend(
            "task-1",
            model="sonnet",
            cache_breakdown=CacheBreakdown(
                cache_read_input_tokens=50_000,
                output_tokens=8_000,
            ),
        )
        assert memory_policy.get_spend("task-1") == pytest.approx(
            0.135, rel=1e-6
        )

    def test_cache_write_is_125x_input(self):
        # Cache write is 1.25× input rate on all tiers
        for model in ("haiku", "sonnet", "opus"):
            direct = price_call(model, input_tokens=1_000_000)
            written = price_call(model, cache_creation_input_tokens=1_000_000)
            assert written == pytest.approx(direct * 1.25)


# ── per-task isolation ───────────────────────────────────────


class TestBudgetPerTaskIsolated:

    def test_different_tasks_have_independent_spend(self, memory_policy):
        memory_policy.record_spend(
            "task-a",
            model="sonnet",
            cache_breakdown=CacheBreakdown(
                input_tokens=100_000, output_tokens=10_000
            ),
        )
        assert memory_policy.get_spend("task-a") > 0
        assert memory_policy.get_spend("task-b") == 0.0

    def test_per_task_budget_override(self, memory_policy):
        memory_policy.set_task_budget("task-vip", 100.0)
        memory_policy.set_task_budget("task-cheap", 0.01)
        assert memory_policy.get_task_budget("task-vip") == 100.0
        assert memory_policy.get_task_budget("task-cheap") == 0.01
        # Default untouched
        assert memory_policy.get_task_budget("task-other") == 5.0

    def test_check_uses_per_task_budget(self, memory_policy):
        memory_policy.set_task_budget("task-cheap", 0.01)
        # 100k tokens on Sonnet ≈ $0.525 — exceeds $0.01 cheap budget
        passed, _ = memory_policy.check(
            "task-cheap", estimated_tokens=100_000, model="sonnet"
        )
        assert passed is False
        # But passes for a task with the default $5 budget
        passed2, _ = memory_policy.check(
            "task-regular", estimated_tokens=100_000, model="sonnet"
        )
        assert passed2 is True

    def test_redis_isolation(self, redis_policy):
        redis_policy.record_spend(
            "task-a",
            model="haiku",
            cache_breakdown=CacheBreakdown(
                input_tokens=1_000_000, output_tokens=0
            ),
        )
        redis_policy.record_spend(
            "task-b",
            model="haiku",
            cache_breakdown=CacheBreakdown(
                input_tokens=500_000, output_tokens=0
            ),
        )
        assert redis_policy.get_spend("task-a") == pytest.approx(1.0)
        assert redis_policy.get_spend("task-b") == pytest.approx(0.5)

    def test_reset_clears_one_task_only(self, memory_policy):
        memory_policy.record_spend(
            "task-a",
            model="haiku",
            cache_breakdown=CacheBreakdown(input_tokens=1_000_000, output_tokens=0),
        )
        memory_policy.record_spend(
            "task-b",
            model="haiku",
            cache_breakdown=CacheBreakdown(input_tokens=1_000_000, output_tokens=0),
        )
        memory_policy.reset("task-a")
        assert memory_policy.get_spend("task-a") == 0.0
        assert memory_policy.get_spend("task-b") == pytest.approx(1.0)


# ── Serialization + snapshot ─────────────────────────────────


class TestBudgetSpendSerialization:

    def test_roundtrip(self):
        original = BudgetSpend(
            task_id="t-1",
            spent_usd=1.23456,
            calls=3,
            input_tokens=100,
            output_tokens=50,
            cache_read_tokens=20,
            cache_write_tokens=10,
            last_model="claude-sonnet-4-6",
        )
        restored = BudgetSpend.from_dict(original.to_dict())
        assert restored.task_id == original.task_id
        assert restored.spent_usd == pytest.approx(original.spent_usd, rel=1e-6)
        assert restored.calls == original.calls
        assert restored.last_model == original.last_model

    def test_snapshot_shape(self, memory_policy):
        memory_policy.record_spend(
            "t-snap",
            model="haiku",
            cache_breakdown=CacheBreakdown(input_tokens=1000, output_tokens=500),
        )
        snap = memory_policy.snapshot("t-snap")
        assert "backend" in snap
        assert "budget_usd" in snap
        assert "remaining_usd" in snap
        assert "spent_usd" in snap
        assert snap["remaining_usd"] == pytest.approx(
            snap["budget_usd"] - snap["spent_usd"], rel=1e-6
        )


# ── BudgetExceededError payload ──────────────────────────────


class TestBudgetExceededError:

    def test_error_carries_details(self):
        err = BudgetExceededError(
            "task-1",
            "limit reached",
            spent_usd=4.5,
            estimated_usd=1.0,
            budget_usd=5.0,
        )
        assert err.task_id == "task-1"
        assert err.spent_usd == 4.5
        assert err.estimated_usd == 1.0
        assert err.budget_usd == 5.0
        assert "task-1" in str(err)


# ── Redis backend edge cases ─────────────────────────────────


class TestRedisBackendRefusesGlobalWipe:

    def test_clear_without_task_id_raises(self, redis_policy):
        # Safety: never wipe all budgets at once
        with pytest.raises(ValueError):
            redis_policy._backend.clear()


class TestRedisPayload:

    def test_payload_round_trips(self):
        client = MockRedis()
        policy = BudgetPolicy(default_budget_usd=5.0, redis_client=client)
        policy.record_spend(
            "task-1",
            model="sonnet",
            cache_breakdown=CacheBreakdown(
                input_tokens=1000, output_tokens=500,
                cache_read_input_tokens=200,
                cache_creation_input_tokens=100,
            ),
        )
        raw = client.get("occp:budget:task-1")
        assert raw is not None
        decoded = json.loads(raw)
        assert decoded["task_id"] == "task-1"
        assert decoded["calls"] == 1
        assert decoded["cache_read_tokens"] == 200
        assert decoded["cache_write_tokens"] == 100


# ── Singleton ────────────────────────────────────────────────


class TestSingleton:

    def test_get_budget_policy_is_cached(self):
        from policy_engine.budget_policy import get_budget_policy
        p1 = get_budget_policy()
        p2 = get_budget_policy()
        assert p1 is p2
