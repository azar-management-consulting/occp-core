"""OCCP observability layer (L6 foundation).

This package provides the telemetry, interpretation, and digest layers
for OCCP's L6 self-observation capability.

Layers:
    metrics_collector  — raw metrics (Counter, Histogram, Gauge)
    anomaly_detector   — interpretation layer producing Anomaly records
    behavior_digest    — narrative summary layer combining metrics+anomalies
"""

from observability.anomaly_detector import (
    Anomaly,
    AnomalyDetector,
    AnomalyThresholds,
    get_anomaly_detector,
)
from observability.behavior_digest import (
    BehaviorDigest,
    BehaviorDigestGenerator,
    get_digest_generator,
)
from observability.metrics_collector import (
    Counter,
    Gauge,
    Histogram,
    MetricsCollector,
    get_collector,
)

__all__ = [
    # Metrics primitives
    "Counter",
    "Histogram",
    "Gauge",
    "MetricsCollector",
    "get_collector",
    # Anomaly interpretation
    "Anomaly",
    "AnomalyDetector",
    "AnomalyThresholds",
    "get_anomaly_detector",
    # Behavior digest
    "BehaviorDigest",
    "BehaviorDigestGenerator",
    "get_digest_generator",
]
