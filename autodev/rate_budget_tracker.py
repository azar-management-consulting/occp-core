"""Rate + budget tracker for autonomous development operations.

Enforces per-day caps:
- Max runs per day (default 20)
- Max LOW-risk auto-merges per day (default 10)
- Max MEDIUM+ proposals per day (default 5)
- Max compute seconds per day (default 3600 = 1h)

Per 2026 industry practice (RSAC 2026, FinOps telemetry):
- Budgets are pre-flight checks (block before work)
- Telemetry exposed via /autodev/budget endpoint
- Resets at UTC midnight

Preservation: pure in-memory counter + time window logic.
Future: DB-backed persistence across restarts.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class BudgetLimits:
    """Default budget limits (per UTC day)."""

    max_runs_per_day: int = 20
    max_low_risk_merges_per_day: int = 10
    max_medium_plus_proposals_per_day: int = 5
    max_compute_seconds_per_day: float = 3600.0


@dataclass
class DailyUsage:
    """Usage counters for one UTC day."""

    date: str  # ISO format YYYY-MM-DD
    runs_started: int = 0
    low_risk_merges: int = 0
    medium_plus_proposals: int = 0
    compute_seconds_used: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": self.date,
            "runs_started": self.runs_started,
            "low_risk_merges": self.low_risk_merges,
            "medium_plus_proposals": self.medium_plus_proposals,
            "compute_seconds_used": self.compute_seconds_used,
        }


class BudgetExhausted(Exception):
    """Raised when a budget limit would be exceeded."""

    def __init__(self, limit_name: str, current: float, limit: float) -> None:
        self.limit_name = limit_name
        self.current = current
        self.limit = limit
        super().__init__(
            f"budget exhausted: {limit_name}={current} >= limit={limit}"
        )


class RateBudgetTracker:
    """Tracks per-day resource usage for autodev operations."""

    def __init__(self, limits: BudgetLimits | None = None) -> None:
        self._lock = threading.Lock()
        self._limits = limits or BudgetLimits()
        self._current: DailyUsage = DailyUsage(date=self._today_iso())

    @staticmethod
    def _today_iso() -> str:
        return datetime.now(timezone.utc).date().isoformat()

    def _rollover_if_needed(self) -> None:
        """Reset counters if a new UTC day has started."""
        today = self._today_iso()
        if self._current.date != today:
            logger.info(
                "autodev.budget: rolling over from %s → %s",
                self._current.date,
                today,
            )
            self._current = DailyUsage(date=today)

    # ── Pre-flight checks ─────────────────────────────────
    def check_can_start_run(self) -> None:
        """Raise BudgetExhausted if starting a new run is over budget."""
        with self._lock:
            self._rollover_if_needed()
            if self._current.runs_started >= self._limits.max_runs_per_day:
                raise BudgetExhausted(
                    "max_runs_per_day",
                    self._current.runs_started,
                    self._limits.max_runs_per_day,
                )

    def check_can_auto_merge_low(self) -> None:
        with self._lock:
            self._rollover_if_needed()
            if (
                self._current.low_risk_merges
                >= self._limits.max_low_risk_merges_per_day
            ):
                raise BudgetExhausted(
                    "max_low_risk_merges_per_day",
                    self._current.low_risk_merges,
                    self._limits.max_low_risk_merges_per_day,
                )

    def check_can_submit_medium_plus(self) -> None:
        with self._lock:
            self._rollover_if_needed()
            if (
                self._current.medium_plus_proposals
                >= self._limits.max_medium_plus_proposals_per_day
            ):
                raise BudgetExhausted(
                    "max_medium_plus_proposals_per_day",
                    self._current.medium_plus_proposals,
                    self._limits.max_medium_plus_proposals_per_day,
                )

    def check_compute_available(self, estimated_seconds: float) -> None:
        with self._lock:
            self._rollover_if_needed()
            if (
                self._current.compute_seconds_used + estimated_seconds
                >= self._limits.max_compute_seconds_per_day
            ):
                raise BudgetExhausted(
                    "max_compute_seconds_per_day",
                    self._current.compute_seconds_used + estimated_seconds,
                    self._limits.max_compute_seconds_per_day,
                )

    # ── Record usage ──────────────────────────────────────
    def record_run_started(self) -> None:
        with self._lock:
            self._rollover_if_needed()
            self._current.runs_started += 1

    def record_low_risk_merge(self) -> None:
        with self._lock:
            self._rollover_if_needed()
            self._current.low_risk_merges += 1

    def record_medium_plus_proposal(self) -> None:
        with self._lock:
            self._rollover_if_needed()
            self._current.medium_plus_proposals += 1

    def record_compute_seconds(self, seconds: float) -> None:
        with self._lock:
            self._rollover_if_needed()
            self._current.compute_seconds_used += max(0.0, seconds)

    # ── Introspection ─────────────────────────────────────
    @property
    def current(self) -> DailyUsage:
        with self._lock:
            self._rollover_if_needed()
            return DailyUsage(
                date=self._current.date,
                runs_started=self._current.runs_started,
                low_risk_merges=self._current.low_risk_merges,
                medium_plus_proposals=self._current.medium_plus_proposals,
                compute_seconds_used=self._current.compute_seconds_used,
            )

    @property
    def limits(self) -> BudgetLimits:
        return self._limits

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            self._rollover_if_needed()
            u = self._current
            limits = self._limits
            return {
                "date": u.date,
                "usage": u.to_dict(),
                "limits": {
                    "max_runs_per_day": limits.max_runs_per_day,
                    "max_low_risk_merges_per_day": limits.max_low_risk_merges_per_day,
                    "max_medium_plus_proposals_per_day": limits.max_medium_plus_proposals_per_day,
                    "max_compute_seconds_per_day": limits.max_compute_seconds_per_day,
                },
                "remaining": {
                    "runs": limits.max_runs_per_day - u.runs_started,
                    "low_risk_merges": limits.max_low_risk_merges_per_day - u.low_risk_merges,
                    "medium_plus_proposals": limits.max_medium_plus_proposals_per_day - u.medium_plus_proposals,
                    "compute_seconds": limits.max_compute_seconds_per_day - u.compute_seconds_used,
                },
            }

    def reset(self) -> None:
        with self._lock:
            self._current = DailyUsage(date=self._today_iso())


# ── Singleton accessor ────────────────────────────────────────
_global_tracker: RateBudgetTracker | None = None
_init_lock = threading.Lock()


def get_rate_budget_tracker() -> RateBudgetTracker:
    global _global_tracker
    if _global_tracker is None:
        with _init_lock:
            if _global_tracker is None:
                _global_tracker = RateBudgetTracker()
    return _global_tracker
