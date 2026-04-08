"""Adaptive rate throttling — REQ-SEC-04.

Detects anomalous request rates using a rolling-window statistical model
(3σ deviation from rolling mean) and throttles per-agent, per-tool.

Throttle response target: <500ms from anomaly detection.

Usage::

    limiter = AdaptiveRateLimiter()
    decision = limiter.check("agent-001", "shell.exec")
    if decision.throttled:
        raise RateLimitExceeded(decision.reason)

    # After action completes:
    limiter.record("agent-001", "shell.exec")
"""

from __future__ import annotations

import math
import time
import threading
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class RateLimiterConfig:
    """Configuration for adaptive rate limiter."""

    window_seconds: float = 60.0
    """Rolling window duration in seconds."""

    bucket_seconds: float = 5.0
    """Bucket granularity for rate aggregation."""

    sigma_threshold: float = 3.0
    """Standard deviation multiplier for anomaly detection."""

    min_samples: int = 5
    """Minimum number of buckets before statistical detection activates."""

    hard_limit: int = 100
    """Absolute maximum requests per window (regardless of stats)."""

    cooldown_seconds: float = 10.0
    """Duration of throttle cooldown after anomaly detection."""

    def validate(self) -> None:
        """Raise if config values are nonsensical."""
        if self.window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        if self.bucket_seconds <= 0 or self.bucket_seconds > self.window_seconds:
            raise ValueError("bucket_seconds must be positive and <= window_seconds")
        if self.sigma_threshold <= 0:
            raise ValueError("sigma_threshold must be positive")
        if self.hard_limit <= 0:
            raise ValueError("hard_limit must be positive")


# ---------------------------------------------------------------------------
# Decision model
# ---------------------------------------------------------------------------


class ThrottleReason(str, Enum):
    """Why a request was throttled."""

    NONE = "none"
    STATISTICAL_ANOMALY = "statistical_anomaly"
    HARD_LIMIT = "hard_limit"
    COOLDOWN = "cooldown"


@dataclass
class ThrottleDecision:
    """Result of a rate-limit check."""

    throttled: bool
    reason: ThrottleReason = ThrottleReason.NONE
    detail: str = ""
    current_rate: float = 0.0
    mean_rate: float = 0.0
    stddev: float = 0.0
    window_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize for audit trail."""
        return {
            "throttled": self.throttled,
            "reason": self.reason.value,
            "detail": self.detail,
            "current_rate": round(self.current_rate, 2),
            "mean_rate": round(self.mean_rate, 2),
            "stddev": round(self.stddev, 2),
            "window_count": self.window_count,
        }


# ---------------------------------------------------------------------------
# Rate tracking per key
# ---------------------------------------------------------------------------


class _RateTracker:
    """Tracks request rates in a rolling window using time buckets."""

    def __init__(self, config: RateLimiterConfig) -> None:
        self._config = config
        self._buckets: deque[tuple[float, int]] = deque()
        self._current_bucket_time: float = 0.0
        self._current_bucket_count: int = 0
        self._throttled_until: float = 0.0

    def record(self, now: float) -> None:
        """Record a single event at time *now*."""
        bucket_time = self._bucket_time(now)

        if bucket_time == self._current_bucket_time:
            self._current_bucket_count += 1
        else:
            # Flush current bucket
            if self._current_bucket_count > 0:
                self._buckets.append((self._current_bucket_time, self._current_bucket_count))
            self._current_bucket_time = bucket_time
            self._current_bucket_count = 1

        self._prune(now)

    def check(self, now: float) -> ThrottleDecision:
        """Check if the current rate is anomalous."""
        self._prune(now)

        # Check cooldown
        if now < self._throttled_until:
            remaining = self._throttled_until - now
            return ThrottleDecision(
                throttled=True,
                reason=ThrottleReason.COOLDOWN,
                detail=f"Cooldown active ({remaining:.1f}s remaining)",
                window_count=self._window_count(now),
            )

        window_count = self._window_count(now)

        # Hard limit check
        if window_count >= self._config.hard_limit:
            self._throttled_until = now + self._config.cooldown_seconds
            return ThrottleDecision(
                throttled=True,
                reason=ThrottleReason.HARD_LIMIT,
                detail=f"Hard limit reached: {window_count}/{self._config.hard_limit}",
                window_count=window_count,
            )

        # Statistical anomaly detection
        rates = self._bucket_rates()

        if len(rates) < self._config.min_samples:
            return ThrottleDecision(
                throttled=False,
                window_count=window_count,
                current_rate=self._current_bucket_count / self._config.bucket_seconds,
            )

        mean = sum(rates) / len(rates)
        variance = sum((r - mean) ** 2 for r in rates) / len(rates)
        stddev = math.sqrt(variance)

        current_rate = self._current_bucket_count / self._config.bucket_seconds
        threshold = mean + self._config.sigma_threshold * stddev

        if current_rate > threshold and stddev > 0:
            self._throttled_until = now + self._config.cooldown_seconds
            return ThrottleDecision(
                throttled=True,
                reason=ThrottleReason.STATISTICAL_ANOMALY,
                detail=(
                    f"Rate {current_rate:.1f}/s exceeds "
                    f"{mean:.1f} + {self._config.sigma_threshold}σ ({stddev:.1f}) = "
                    f"{threshold:.1f}/s"
                ),
                current_rate=current_rate,
                mean_rate=mean,
                stddev=stddev,
                window_count=window_count,
            )

        return ThrottleDecision(
            throttled=False,
            current_rate=current_rate,
            mean_rate=mean,
            stddev=stddev,
            window_count=window_count,
        )

    def reset_cooldown(self) -> None:
        """Manually reset throttle cooldown."""
        self._throttled_until = 0.0

    def _bucket_time(self, now: float) -> float:
        """Quantize time to bucket boundary."""
        return now - (now % self._config.bucket_seconds)

    def _prune(self, now: float) -> None:
        """Remove expired buckets outside the rolling window."""
        cutoff = now - self._config.window_seconds
        while self._buckets and self._buckets[0][0] < cutoff:
            self._buckets.popleft()

    def _window_count(self, now: float) -> int:
        """Total events in the current window."""
        cutoff = now - self._config.window_seconds
        total = 0
        # Include current bucket only if within window
        if self._current_bucket_time >= cutoff:
            total = self._current_bucket_count
        for bucket_time, count in self._buckets:
            if bucket_time >= cutoff:
                total += count
        return total

    def _bucket_rates(self) -> list[float]:
        """Per-bucket rates (events/second) for completed buckets."""
        return [
            count / self._config.bucket_seconds
            for _, count in self._buckets
        ]


# ---------------------------------------------------------------------------
# Adaptive Rate Limiter
# ---------------------------------------------------------------------------


class AdaptiveRateLimiter:
    """Per-agent, per-tool adaptive rate limiter.

    REQ-SEC-04: Statistical anomaly detection (3σ deviation from rolling mean).

    Thread-safe. Each (agent_id, tool_name) pair has its own rate tracker.
    """

    def __init__(self, config: RateLimiterConfig | None = None) -> None:
        self._config = config or RateLimiterConfig()
        self._config.validate()
        self._trackers: dict[str, _RateTracker] = defaultdict(
            lambda: _RateTracker(self._config)
        )
        self._lock = threading.Lock()

    @property
    def config(self) -> RateLimiterConfig:
        """Current limiter configuration."""
        return self._config

    def _key(self, agent_id: str, tool_name: str) -> str:
        return f"{agent_id}:{tool_name}"

    def record(self, agent_id: str, tool_name: str, now: float | None = None) -> None:
        """Record a completed action for rate tracking."""
        t = now if now is not None else time.monotonic()
        key = self._key(agent_id, tool_name)
        with self._lock:
            self._trackers[key].record(t)

    def check(self, agent_id: str, tool_name: str, now: float | None = None) -> ThrottleDecision:
        """Check if a request should be throttled.

        Returns decision within target latency (<500ms).
        """
        t = now if now is not None else time.monotonic()
        key = self._key(agent_id, tool_name)
        with self._lock:
            return self._trackers[key].check(t)

    def record_and_check(
        self, agent_id: str, tool_name: str, now: float | None = None,
    ) -> ThrottleDecision:
        """Record an event and immediately check for throttling."""
        t = now if now is not None else time.monotonic()
        key = self._key(agent_id, tool_name)
        with self._lock:
            tracker = self._trackers[key]
            tracker.record(t)
            return tracker.check(t)

    def reset(self, agent_id: str, tool_name: str) -> None:
        """Reset cooldown for a specific agent+tool pair."""
        key = self._key(agent_id, tool_name)
        with self._lock:
            if key in self._trackers:
                self._trackers[key].reset_cooldown()

    def clear(self) -> None:
        """Remove all tracked state."""
        with self._lock:
            self._trackers.clear()

    def get_stats(self, agent_id: str, tool_name: str) -> dict[str, Any]:
        """Return current tracking stats for a key."""
        t = time.monotonic()
        key = self._key(agent_id, tool_name)
        with self._lock:
            if key not in self._trackers:
                return {"tracked": False}
            tracker = self._trackers[key]
            decision = tracker.check(t)
            return {
                "tracked": True,
                "window_count": decision.window_count,
                "current_rate": decision.current_rate,
                "mean_rate": decision.mean_rate,
                "stddev": decision.stddev,
                "throttled": decision.throttled,
                "reason": decision.reason.value,
            }

    def tracked_keys(self) -> list[str]:
        """List all tracked agent:tool pairs."""
        with self._lock:
            return list(self._trackers.keys())
