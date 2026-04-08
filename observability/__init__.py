"""OCCP observability layer (L6 foundation).

This package provides the telemetry foundation for OCCP's L6 self-observation
capability. It is intentionally minimal — Prometheus-style counters and
histograms in-process — to avoid introducing an external dependency chain
before the foundation is validated.

Future phases will add OpenTelemetry exporters, trace correlation, and
anomaly detection hooks driven by this data.
"""

from observability.metrics_collector import (
    MetricsCollector,
    get_collector,
    Counter,
    Histogram,
    Gauge,
)

__all__ = [
    "MetricsCollector",
    "get_collector",
    "Counter",
    "Histogram",
    "Gauge",
]
