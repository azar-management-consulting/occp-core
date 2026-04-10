"""Tests for Adaptive Rate Limiter — REQ-SEC-04.

Covers:
- Config validation
- Basic rate tracking (record + check)
- Hard limit enforcement
- Statistical anomaly detection (3σ)
- Cooldown mechanism
- Per-agent per-tool isolation
- Thread safety
- Stats and key listing
- ThrottleDecision serialization
"""

from __future__ import annotations

import math
import threading
import time

import pytest

from policy_engine.rate_limiter import (
    AdaptiveRateLimiter,
    RateLimiterConfig,
    ThrottleDecision,
    ThrottleReason,
    _RateTracker,
)


# ---------------------------------------------------------------------------
# RateLimiterConfig
# ---------------------------------------------------------------------------


class TestRateLimiterConfig:
    def test_defaults(self) -> None:
        cfg = RateLimiterConfig()
        assert cfg.window_seconds == 60.0
        assert cfg.bucket_seconds == 5.0
        assert cfg.sigma_threshold == 3.0
        assert cfg.min_samples == 5
        assert cfg.hard_limit == 100
        assert cfg.cooldown_seconds == 10.0

    def test_validate_ok(self) -> None:
        cfg = RateLimiterConfig(window_seconds=30, bucket_seconds=5)
        cfg.validate()  # Should not raise

    def test_validate_window_zero(self) -> None:
        cfg = RateLimiterConfig(window_seconds=0)
        with pytest.raises(ValueError, match="window_seconds"):
            cfg.validate()

    def test_validate_bucket_too_large(self) -> None:
        cfg = RateLimiterConfig(window_seconds=10, bucket_seconds=20)
        with pytest.raises(ValueError, match="bucket_seconds"):
            cfg.validate()

    def test_validate_bucket_zero(self) -> None:
        cfg = RateLimiterConfig(bucket_seconds=0)
        with pytest.raises(ValueError, match="bucket_seconds"):
            cfg.validate()

    def test_validate_sigma_negative(self) -> None:
        cfg = RateLimiterConfig(sigma_threshold=-1)
        with pytest.raises(ValueError, match="sigma_threshold"):
            cfg.validate()

    def test_validate_hard_limit_zero(self) -> None:
        cfg = RateLimiterConfig(hard_limit=0)
        with pytest.raises(ValueError, match="hard_limit"):
            cfg.validate()


# ---------------------------------------------------------------------------
# ThrottleDecision
# ---------------------------------------------------------------------------


class TestThrottleDecision:
    def test_default_not_throttled(self) -> None:
        d = ThrottleDecision(throttled=False)
        assert d.throttled is False
        assert d.reason == ThrottleReason.NONE
        assert d.detail == ""

    def test_to_dict(self) -> None:
        d = ThrottleDecision(
            throttled=True,
            reason=ThrottleReason.HARD_LIMIT,
            detail="hit limit",
            current_rate=12.345,
            mean_rate=5.678,
            stddev=2.111,
            window_count=50,
        )
        out = d.to_dict()
        assert out["throttled"] is True
        assert out["reason"] == "hard_limit"
        assert out["current_rate"] == 12.35
        assert out["mean_rate"] == 5.68
        assert out["stddev"] == 2.11
        assert out["window_count"] == 50

    def test_to_dict_none_reason(self) -> None:
        d = ThrottleDecision(throttled=False, reason=ThrottleReason.NONE)
        assert d.to_dict()["reason"] == "none"


# ---------------------------------------------------------------------------
# _RateTracker — internal
# ---------------------------------------------------------------------------


class TestRateTracker:
    def _cfg(self, **kw) -> RateLimiterConfig:
        defaults = dict(
            window_seconds=60.0,
            bucket_seconds=5.0,
            sigma_threshold=3.0,
            min_samples=5,
            hard_limit=100,
            cooldown_seconds=10.0,
        )
        defaults.update(kw)
        return RateLimiterConfig(**defaults)

    def test_record_and_check_no_throttle(self) -> None:
        tracker = _RateTracker(self._cfg())
        now = 1000.0
        tracker.record(now)
        decision = tracker.check(now)
        assert decision.throttled is False
        assert decision.window_count == 1

    def test_hard_limit_triggers(self) -> None:
        cfg = self._cfg(hard_limit=10)
        tracker = _RateTracker(cfg)
        now = 1000.0
        for i in range(10):
            tracker.record(now + i * 0.01)
        decision = tracker.check(now + 0.11)
        assert decision.throttled is True
        assert decision.reason == ThrottleReason.HARD_LIMIT

    def test_cooldown_after_hard_limit(self) -> None:
        cfg = self._cfg(hard_limit=5, cooldown_seconds=10.0, window_seconds=10.0)
        tracker = _RateTracker(cfg)
        now = 1000.0
        for i in range(5):
            tracker.record(now + i * 0.01)
        # Trigger hard limit
        tracker.check(now + 0.1)
        # During cooldown
        decision = tracker.check(now + 5.0)
        assert decision.throttled is True
        assert decision.reason == ThrottleReason.COOLDOWN
        # After cooldown AND window expiry (events pruned)
        decision = tracker.check(now + 11.0)
        assert decision.throttled is False

    def test_reset_cooldown(self) -> None:
        cfg = self._cfg(hard_limit=5, cooldown_seconds=60.0, window_seconds=5.0)
        tracker = _RateTracker(cfg)
        now = 1000.0
        for i in range(5):
            tracker.record(now + i * 0.01)
        tracker.check(now + 0.1)  # Trigger hard limit → cooldown
        # Still in cooldown
        assert tracker.check(now + 1.0).throttled is True
        assert tracker.check(now + 1.0).reason == ThrottleReason.COOLDOWN
        # Reset cooldown, check after window expiry so events are pruned
        tracker.reset_cooldown()
        assert tracker.check(now + 6.0).throttled is False

    def test_statistical_anomaly_detection(self) -> None:
        """Simulate steady rate then burst → triggers 3σ detection."""
        cfg = self._cfg(
            window_seconds=60.0,
            bucket_seconds=5.0,
            sigma_threshold=3.0,
            min_samples=5,
            hard_limit=10000,
        )
        tracker = _RateTracker(cfg)

        # Build baseline: 2 events per bucket for 6 buckets (30s)
        base_time = 1000.0
        for bucket_idx in range(6):
            bucket_start = base_time + bucket_idx * 5.0
            tracker.record(bucket_start + 0.1)
            tracker.record(bucket_start + 0.2)
            # Flush bucket by recording in next bucket
        # Each completed bucket: 2 events / 5s = 0.4/s

        # Now create a burst in current bucket: 50 events
        burst_time = base_time + 6 * 5.0
        for i in range(50):
            tracker.record(burst_time + i * 0.01)

        decision = tracker.check(burst_time + 0.6)
        assert decision.throttled is True
        assert decision.reason == ThrottleReason.STATISTICAL_ANOMALY
        assert decision.current_rate > decision.mean_rate

    def test_not_enough_samples_no_anomaly(self) -> None:
        """With fewer than min_samples buckets, skip statistical check."""
        cfg = self._cfg(min_samples=10)
        tracker = _RateTracker(cfg)
        now = 1000.0
        # Only 2 buckets of data
        tracker.record(now)
        tracker.record(now + 5.0)
        decision = tracker.check(now + 10.0)
        assert decision.throttled is False

    def test_window_prune(self) -> None:
        """Old buckets beyond window are pruned."""
        cfg = self._cfg(window_seconds=10.0, bucket_seconds=2.0)
        tracker = _RateTracker(cfg)
        # Record at t=0
        tracker.record(0.0)
        tracker.record(1.0)
        # Record at t=20 (way past window)
        tracker.record(20.0)
        decision = tracker.check(20.0)
        # Old record should be pruned, only 1 event in window
        assert decision.window_count == 1


# ---------------------------------------------------------------------------
# AdaptiveRateLimiter — public API
# ---------------------------------------------------------------------------


class TestAdaptiveRateLimiter:
    def test_basic_check_not_throttled(self) -> None:
        limiter = AdaptiveRateLimiter()
        decision = limiter.check("agent-001", "shell.exec", now=1000.0)
        assert decision.throttled is False

    def test_record_then_check(self) -> None:
        limiter = AdaptiveRateLimiter()
        limiter.record("agent-001", "shell.exec", now=1000.0)
        decision = limiter.check("agent-001", "shell.exec", now=1000.1)
        assert decision.throttled is False
        assert decision.window_count == 1

    def test_record_and_check_combined(self) -> None:
        limiter = AdaptiveRateLimiter()
        decision = limiter.record_and_check("agent-001", "shell.exec", now=1000.0)
        assert decision.window_count == 1

    def test_per_agent_isolation(self) -> None:
        """Different agents have independent trackers."""
        cfg = RateLimiterConfig(hard_limit=5)
        limiter = AdaptiveRateLimiter(cfg)
        now = 1000.0

        # Fill agent-001 to hard limit
        for i in range(5):
            limiter.record("agent-001", "tool", now=now + i * 0.01)

        # agent-001 throttled
        assert limiter.check("agent-001", "tool", now=now + 0.1).throttled is True
        # agent-002 NOT throttled
        assert limiter.check("agent-002", "tool", now=now + 0.1).throttled is False

    def test_per_tool_isolation(self) -> None:
        """Different tools on same agent have independent trackers."""
        cfg = RateLimiterConfig(hard_limit=5)
        limiter = AdaptiveRateLimiter(cfg)
        now = 1000.0

        for i in range(5):
            limiter.record("agent-001", "shell.exec", now=now + i * 0.01)

        assert limiter.check("agent-001", "shell.exec", now=now + 0.1).throttled is True
        assert limiter.check("agent-001", "file.read", now=now + 0.1).throttled is False

    def test_reset_specific_key(self) -> None:
        cfg = RateLimiterConfig(hard_limit=5, cooldown_seconds=60.0, window_seconds=5.0)
        limiter = AdaptiveRateLimiter(cfg)
        now = 1000.0

        for i in range(5):
            limiter.record("a", "t", now=now + i * 0.01)
        limiter.check("a", "t", now=now + 0.1)  # Trigger hard limit

        assert limiter.check("a", "t", now=now + 1.0).throttled is True
        limiter.reset("a", "t")
        # After reset + window expiry, events pruned → not throttled
        assert limiter.check("a", "t", now=now + 6.0).throttled is False

    def test_reset_nonexistent_key(self) -> None:
        limiter = AdaptiveRateLimiter()
        limiter.reset("no-agent", "no-tool")  # Should not raise

    def test_clear_all(self) -> None:
        limiter = AdaptiveRateLimiter()
        limiter.record("a", "t", now=1000.0)
        assert len(limiter.tracked_keys()) == 1
        limiter.clear()
        assert len(limiter.tracked_keys()) == 0

    def test_tracked_keys(self) -> None:
        limiter = AdaptiveRateLimiter()
        limiter.record("agent-1", "tool-a", now=1000.0)
        limiter.record("agent-2", "tool-b", now=1000.0)
        keys = limiter.tracked_keys()
        assert "agent-1:tool-a" in keys
        assert "agent-2:tool-b" in keys

    def test_get_stats_untracked(self) -> None:
        limiter = AdaptiveRateLimiter()
        stats = limiter.get_stats("unknown", "unknown")
        assert stats["tracked"] is False

    def test_get_stats_tracked(self) -> None:
        limiter = AdaptiveRateLimiter()
        # Use real time since get_stats uses time.monotonic() internally
        limiter.record("a", "t")
        stats = limiter.get_stats("a", "t")
        assert stats["tracked"] is True
        assert stats["window_count"] >= 1
        assert "current_rate" in stats
        assert "mean_rate" in stats
        assert "reason" in stats

    def test_config_property(self) -> None:
        cfg = RateLimiterConfig(hard_limit=42)
        limiter = AdaptiveRateLimiter(cfg)
        assert limiter.config.hard_limit == 42

    def test_invalid_config_rejected(self) -> None:
        cfg = RateLimiterConfig(window_seconds=-1)
        with pytest.raises(ValueError):
            AdaptiveRateLimiter(cfg)

    def test_throttle_response_latency(self) -> None:
        """REQ-SEC-04: Throttle response target <500ms."""
        limiter = AdaptiveRateLimiter()
        # Pre-warm
        for i in range(20):
            limiter.record("a", "t", now=1000.0 + i * 0.1)

        latencies: list[float] = []
        for _ in range(100):
            start = time.monotonic()
            limiter.check("a", "t")
            elapsed_ms = (time.monotonic() - start) * 1000
            latencies.append(elapsed_ms)

        latencies.sort()
        p95 = latencies[94]
        assert p95 < 500.0, f"p95 latency {p95:.1f}ms exceeds 500ms target"


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------


class TestThreadSafety:
    def test_concurrent_record_and_check(self) -> None:
        """Multiple threads recording and checking simultaneously."""
        limiter = AdaptiveRateLimiter()
        errors: list[str] = []
        barrier = threading.Barrier(4)

        def worker(agent_id: str) -> None:
            try:
                barrier.wait(timeout=5)
                for i in range(50):
                    limiter.record(agent_id, "tool")
                    decision = limiter.check(agent_id, "tool")
                    # Should not raise
                    _ = decision.throttled
            except Exception as e:
                errors.append(str(e))

        threads = [
            threading.Thread(target=worker, args=(f"agent-{i}",))
            for i in range(4)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert errors == [], f"Thread errors: {errors}"
