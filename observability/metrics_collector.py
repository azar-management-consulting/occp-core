"""In-process metrics collector for OCCP L6 observability.

Implements Prometheus-style counters, histograms, and gauges without
introducing an external dependency. The collector is a thread-safe
singleton that produces text in Prometheus exposition format, suitable
for scraping by a Prometheus server or consumption by the dashboard.

Usage:
    from observability import get_collector

    coll = get_collector()
    coll.counter("occp.task.shipped", 1, {"agent_type": "eng-core"})

    with coll.time_histogram("occp.pipeline.stage_duration_ms",
                             {"stage": "execute"}):
        do_work()

Thread-safety: backed by threading.Lock; async-safe because all
operations are O(1) dict mutations.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator

logger = logging.getLogger(__name__)


_DEFAULT_HIST_BUCKETS_MS = (
    5.0, 10.0, 25.0, 50.0, 100.0, 250.0, 500.0,
    1000.0, 2500.0, 5000.0, 10000.0, 30000.0,
)


def _labels_key(labels: dict[str, str] | None) -> tuple[tuple[str, str], ...]:
    """Return a hashable key for a label set."""
    if not labels:
        return ()
    return tuple(sorted(labels.items()))


@dataclass
class Counter:
    """Monotonically increasing counter."""
    name: str
    help_text: str = ""
    values: dict[tuple[tuple[str, str], ...], float] = field(default_factory=lambda: defaultdict(float))

    def inc(self, amount: float = 1.0, labels: dict[str, str] | None = None) -> None:
        key = _labels_key(labels)
        self.values[key] = self.values.get(key, 0.0) + amount


@dataclass
class Gauge:
    """Gauge — can go up or down."""
    name: str
    help_text: str = ""
    values: dict[tuple[tuple[str, str], ...], float] = field(default_factory=lambda: defaultdict(float))

    def set(self, value: float, labels: dict[str, str] | None = None) -> None:
        self.values[_labels_key(labels)] = value

    def inc(self, amount: float = 1.0, labels: dict[str, str] | None = None) -> None:
        key = _labels_key(labels)
        self.values[key] = self.values.get(key, 0.0) + amount

    def dec(self, amount: float = 1.0, labels: dict[str, str] | None = None) -> None:
        self.inc(-amount, labels)


@dataclass
class Histogram:
    """Simple bucketed histogram (Prometheus-compatible)."""
    name: str
    help_text: str = ""
    buckets: tuple[float, ...] = _DEFAULT_HIST_BUCKETS_MS
    counts: dict[tuple[tuple[str, str], ...], list[int]] = field(default_factory=dict)
    sums: dict[tuple[tuple[str, str], ...], float] = field(default_factory=lambda: defaultdict(float))
    observations: dict[tuple[tuple[str, str], ...], int] = field(default_factory=lambda: defaultdict(int))

    def observe(self, value: float, labels: dict[str, str] | None = None) -> None:
        key = _labels_key(labels)
        if key not in self.counts:
            self.counts[key] = [0] * (len(self.buckets) + 1)
        for i, b in enumerate(self.buckets):
            if value <= b:
                self.counts[key][i] += 1
        self.counts[key][-1] += 1  # +Inf bucket
        self.sums[key] = self.sums.get(key, 0.0) + value
        self.observations[key] = self.observations.get(key, 0) + 1


class MetricsCollector:
    """Thread-safe in-process metrics collector."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[str, Counter] = {}
        self._gauges: dict[str, Gauge] = {}
        self._histograms: dict[str, Histogram] = {}
        self._startup_ts = time.time()

    # ── Counter ───────────────────────────────────────────────
    def counter(
        self,
        name: str,
        amount: float = 1.0,
        labels: dict[str, str] | None = None,
        help_text: str = "",
    ) -> None:
        with self._lock:
            c = self._counters.get(name)
            if c is None:
                c = Counter(name=name, help_text=help_text)
                self._counters[name] = c
            c.inc(amount, labels)

    # ── Gauge ─────────────────────────────────────────────────
    def gauge(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
        help_text: str = "",
    ) -> None:
        with self._lock:
            g = self._gauges.get(name)
            if g is None:
                g = Gauge(name=name, help_text=help_text)
                self._gauges[name] = g
            g.set(value, labels)

    # ── Histogram ─────────────────────────────────────────────
    def histogram(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
        help_text: str = "",
        buckets: tuple[float, ...] | None = None,
    ) -> None:
        with self._lock:
            h = self._histograms.get(name)
            if h is None:
                h = Histogram(
                    name=name,
                    help_text=help_text,
                    buckets=buckets or _DEFAULT_HIST_BUCKETS_MS,
                )
                self._histograms[name] = h
            h.observe(value, labels)

    @contextmanager
    def time_histogram(
        self,
        name: str,
        labels: dict[str, str] | None = None,
        help_text: str = "",
    ) -> Iterator[None]:
        """Context manager to record elapsed time (ms) into a histogram."""
        start = time.monotonic()
        try:
            yield
        finally:
            elapsed_ms = (time.monotonic() - start) * 1000.0
            self.histogram(name, elapsed_ms, labels, help_text)

    # ── Exposition format ─────────────────────────────────────
    def render_prometheus(self) -> str:
        """Render all metrics in Prometheus text exposition format."""
        lines: list[str] = []
        lines.append(f"# HELP occp_uptime_seconds OCCP metrics collector uptime")
        lines.append(f"# TYPE occp_uptime_seconds gauge")
        lines.append(f"occp_uptime_seconds {time.time() - self._startup_ts:.3f}")

        with self._lock:
            for c in self._counters.values():
                if c.help_text:
                    lines.append(f"# HELP {self._sanitize(c.name)} {c.help_text}")
                lines.append(f"# TYPE {self._sanitize(c.name)} counter")
                for label_key, val in c.values.items():
                    label_str = self._render_labels(label_key)
                    lines.append(f"{self._sanitize(c.name)}{label_str} {val}")

            for g in self._gauges.values():
                if g.help_text:
                    lines.append(f"# HELP {self._sanitize(g.name)} {g.help_text}")
                lines.append(f"# TYPE {self._sanitize(g.name)} gauge")
                for label_key, val in g.values.items():
                    label_str = self._render_labels(label_key)
                    lines.append(f"{self._sanitize(g.name)}{label_str} {val}")

            for h in self._histograms.values():
                if h.help_text:
                    lines.append(f"# HELP {self._sanitize(h.name)} {h.help_text}")
                lines.append(f"# TYPE {self._sanitize(h.name)} histogram")
                for label_key, counts in h.counts.items():
                    base_labels = dict(label_key)
                    for i, b in enumerate(h.buckets):
                        bucket_labels = {**base_labels, "le": str(b)}
                        label_str = self._render_labels(_labels_key(bucket_labels))
                        lines.append(
                            f"{self._sanitize(h.name)}_bucket{label_str} {counts[i]}"
                        )
                    # +Inf bucket
                    inf_labels = {**base_labels, "le": "+Inf"}
                    label_str = self._render_labels(_labels_key(inf_labels))
                    lines.append(
                        f"{self._sanitize(h.name)}_bucket{label_str} {counts[-1]}"
                    )
                    base_label_str = self._render_labels(label_key)
                    lines.append(
                        f"{self._sanitize(h.name)}_count{base_label_str} "
                        f"{h.observations.get(label_key, 0)}"
                    )
                    lines.append(
                        f"{self._sanitize(h.name)}_sum{base_label_str} "
                        f"{h.sums.get(label_key, 0.0):.3f}"
                    )
        lines.append("")  # trailing newline
        return "\n".join(lines)

    @staticmethod
    def _sanitize(name: str) -> str:
        """Prometheus metric names use underscores, not dots."""
        return name.replace(".", "_").replace("-", "_")

    @staticmethod
    def _render_labels(key: tuple[tuple[str, str], ...]) -> str:
        if not key:
            return ""
        parts = [f'{k}="{v}"' for k, v in key]
        return "{" + ",".join(parts) + "}"

    # ── JSON snapshot (for dashboard consumption) ─────────────
    def snapshot(self) -> dict[str, Any]:
        """Return a JSON-serializable snapshot of all metrics."""
        with self._lock:
            return {
                "uptime_seconds": time.time() - self._startup_ts,
                "counters": {
                    name: {
                        "help": c.help_text,
                        "values": [
                            {"labels": dict(k), "value": v}
                            for k, v in c.values.items()
                        ],
                    }
                    for name, c in self._counters.items()
                },
                "gauges": {
                    name: {
                        "help": g.help_text,
                        "values": [
                            {"labels": dict(k), "value": v}
                            for k, v in g.values.items()
                        ],
                    }
                    for name, g in self._gauges.items()
                },
                "histograms": {
                    name: {
                        "help": h.help_text,
                        "buckets": list(h.buckets),
                        "series": [
                            {
                                "labels": dict(k),
                                "count": h.observations.get(k, 0),
                                "sum": h.sums.get(k, 0.0),
                                "avg_ms": (
                                    h.sums.get(k, 0.0) / h.observations.get(k, 1)
                                    if h.observations.get(k, 0) > 0
                                    else 0.0
                                ),
                            }
                            for k in h.counts.keys()
                        ],
                    }
                    for name, h in self._histograms.items()
                },
            }

    def reset(self) -> None:
        """Reset all metrics (used by tests)."""
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()
            self._startup_ts = time.time()


# ── Singleton accessor ────────────────────────────────────────
_global_collector: MetricsCollector | None = None
_init_lock = threading.Lock()


def get_collector() -> MetricsCollector:
    """Return the process-global MetricsCollector singleton."""
    global _global_collector
    if _global_collector is None:
        with _init_lock:
            if _global_collector is None:
                _global_collector = MetricsCollector()
                logger.info("observability: MetricsCollector initialized")
    return _global_collector
