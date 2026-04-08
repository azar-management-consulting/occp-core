"""Feature flags runtime store (L6 foundation).

Simple in-memory feature flag store with a stable API. Future phases will
back this with a DB table (`feature_flags`) and add rollout percentage,
user-based targeting, and audit trail.

Usage:
    from evaluation import get_flag_store

    flags = get_flag_store()
    flags.set("l6.observability.enabled", enabled=True)
    if flags.is_enabled("l6.observability.enabled"):
        record_metrics()

Naming convention: dot-separated, lowercase, `<domain>.<feature>[.<subfeature>]`
Examples:
    l6.observability.enabled
    l6.rfc.auto_generation
    l6.canary.enabled
    experimental.planner.multi_llm_fallback
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class FeatureFlag:
    """A single feature flag."""

    key: str
    enabled: bool = False
    rollout_percent: int = 0  # 0..100 — future use for gradual rollout
    description: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "enabled": self.enabled,
            "rollout_percent": self.rollout_percent,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }


class FeatureFlagStore:
    """Thread-safe in-memory feature flag store.

    Intentionally minimal: no persistence, no rollout percentage logic yet.
    The API is stable so that a future DB-backed implementation can be
    swapped in transparently.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._flags: dict[str, FeatureFlag] = {}
        self._seed_defaults()

    def _seed_defaults(self) -> None:
        """Seed the default L6 feature flags. All default OFF for safety."""
        defaults = [
            ("l6.observability.metrics_enabled", True,
             "Enable /observability/metrics endpoint emission"),
            ("l6.observability.tracing_enabled", False,
             "Enable distributed trace correlation (future)"),
            ("l6.rfc.auto_generation", False,
             "Allow Claude Code to auto-generate RFC drafts"),
            ("l6.canary.enabled", False,
             "Enable canary traffic splitting (future)"),
            ("l6.self_modifier.log_only", True,
             "Self-modifier runs in log-only mode (safe default)"),
            ("l6.evaluation.replay_harness", False,
             "Enable historical workflow replay testing"),
        ]
        for key, enabled, desc in defaults:
            self._flags[key] = FeatureFlag(
                key=key, enabled=enabled, description=desc
            )

    def get(self, key: str) -> FeatureFlag | None:
        """Return a flag by key or None."""
        with self._lock:
            return self._flags.get(key)

    def is_enabled(self, key: str, default: bool = False) -> bool:
        """Check if a flag is enabled. Returns default if unknown."""
        flag = self.get(key)
        if flag is None:
            return default
        return flag.enabled

    def set(
        self,
        key: str,
        enabled: bool,
        description: str | None = None,
        rollout_percent: int | None = None,
    ) -> FeatureFlag:
        """Set or update a flag. rollout_percent is always clamped to [0,100]."""
        with self._lock:
            clamped = (
                max(0, min(100, rollout_percent)) if rollout_percent is not None else 0
            )
            flag = self._flags.get(key)
            if flag is None:
                flag = FeatureFlag(
                    key=key,
                    enabled=enabled,
                    description=description or "",
                    rollout_percent=clamped,
                )
                self._flags[key] = flag
            else:
                flag.enabled = enabled
                if description is not None:
                    flag.description = description
                if rollout_percent is not None:
                    flag.rollout_percent = clamped
                flag.updated_at = datetime.now(timezone.utc)
            logger.info(
                "feature_flag updated key=%s enabled=%s rollout=%d",
                key,
                flag.enabled,
                flag.rollout_percent,
            )
            return flag

    def delete(self, key: str) -> bool:
        """Delete a flag. Returns True if deleted."""
        with self._lock:
            if key in self._flags:
                del self._flags[key]
                return True
            return False

    def list_all(self) -> list[FeatureFlag]:
        """Return all flags."""
        with self._lock:
            return sorted(self._flags.values(), key=lambda f: f.key)

    def reset(self) -> None:
        """Reset to defaults (used by tests)."""
        with self._lock:
            self._flags.clear()
            self._seed_defaults()


# ── Singleton accessor ────────────────────────────────────────
_global_store: FeatureFlagStore | None = None
_init_lock = threading.Lock()


def get_flag_store() -> FeatureFlagStore:
    """Return the process-global FeatureFlagStore singleton."""
    global _global_store
    if _global_store is None:
        with _init_lock:
            if _global_store is None:
                _global_store = FeatureFlagStore()
                logger.info("feature_flag_store initialized with defaults")
    return _global_store
