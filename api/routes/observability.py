"""Observability API routes (L6 foundation, completed in v0.10.0).

Read-only interpretation layer over MetricsCollector and architecture memory.

Endpoints:
    GET  /observability/metrics        - Prometheus text exposition
    GET  /observability/snapshot       - JSON metrics snapshot
    GET  /observability/health         - Public health of observability
    GET  /observability/anomalies      - Current anomaly list
    GET  /observability/digest         - Narrative behavior digest
    GET  /observability/summary        - Combined summary (snapshot + anomalies + digest)
    GET  /observability/readiness      - L6 readiness markers (from governance.yaml)
    POST /observability/reset          - Reset metrics (admin)
"""

from __future__ import annotations

import logging
import pathlib
from typing import Any

import yaml
from fastapi import APIRouter, Depends, Response

from api.auth import get_current_user_payload
from api.deps import AppState, get_state
from api.rbac import PermissionChecker
from observability import (
    get_anomaly_detector,
    get_collector,
    get_digest_generator,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["observability"])

_ARCHITECTURE_DIR = pathlib.Path(__file__).parent.parent.parent / "architecture"


# ── Metrics / snapshot / health ───────────────────────────────

@router.get("/observability/metrics", response_class=Response)
async def get_prometheus_metrics(
    current_user: dict = Depends(get_current_user_payload),
) -> Response:
    """Prometheus text exposition format."""
    text = get_collector().render_prometheus()
    return Response(
        content=text,
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@router.get("/observability/snapshot")
async def get_metrics_snapshot(
    current_user: dict = Depends(get_current_user_payload),
) -> dict[str, Any]:
    """JSON snapshot of all metrics."""
    return get_collector().snapshot()


@router.get("/observability/health")
async def observability_health() -> dict[str, Any]:
    """Public health endpoint (no auth)."""
    snap = get_collector().snapshot()
    return {
        "status": "healthy",
        "uptime_seconds": snap["uptime_seconds"],
        "counters_registered": len(snap["counters"]),
        "gauges_registered": len(snap["gauges"]),
        "histograms_registered": len(snap["histograms"]),
    }


# ── Interpretation ────────────────────────────────────────────

@router.get("/observability/anomalies")
async def get_anomalies(
    current_user: dict = Depends(get_current_user_payload),
) -> dict[str, Any]:
    """Return the current anomaly list + thresholds."""
    detector = get_anomaly_detector()
    anomalies = detector.detect()
    return {
        "count": len(anomalies),
        "thresholds": {
            "min_samples": detector.thresholds.min_samples,
            "max_non_success_fraction": detector.thresholds.max_non_success_fraction,
            "max_denial_fraction": detector.thresholds.max_denial_fraction,
            "min_agent_success_rate": detector.thresholds.min_agent_success_rate,
            "slow_stage_absolute_p95_ms": detector.thresholds.slow_stage_absolute_p95_ms,
        },
        "anomalies": [a.to_dict() for a in anomalies],
    }


@router.get("/observability/digest")
async def get_digest(
    current_user: dict = Depends(get_current_user_payload),
) -> dict[str, Any]:
    """Return a behavior digest: narrative + metrics + anomalies."""
    digest = get_digest_generator().generate()
    return digest.to_dict()


@router.get("/observability/summary")
async def get_summary(
    current_user: dict = Depends(get_current_user_payload),
) -> dict[str, Any]:
    """Combined dashboard view: health + snapshot + anomalies + digest.

    Intended for the dashboard overview and for Telegram /status responses.
    """
    snap = get_collector().snapshot()
    anomalies = get_anomaly_detector().detect()
    digest = get_digest_generator().generate()
    return {
        "health": {
            "status": "healthy",
            "uptime_seconds": snap["uptime_seconds"],
            "counters_registered": len(snap["counters"]),
            "histograms_registered": len(snap["histograms"]),
        },
        "metrics": {
            "uptime_seconds": snap["uptime_seconds"],
            "counter_names": list(snap["counters"].keys()),
            "histogram_names": list(snap["histograms"].keys()),
        },
        "anomalies": {
            "count": len(anomalies),
            "items": [a.to_dict() for a in anomalies],
        },
        "digest": {
            "narrative": digest.narrative,
            "tasks_total": digest.tasks_total,
            "tasks_by_outcome": digest.tasks_by_outcome,
            "tasks_by_agent": digest.tasks_by_agent,
            "slowest_stages": digest.slowest_stages,
        },
    }


# ── L6 Readiness ──────────────────────────────────────────────

@router.get("/observability/readiness")
async def get_l6_readiness(
    current_user: dict = Depends(get_current_user_payload),
) -> dict[str, Any]:
    """Return L6 readiness markers from architecture/governance.yaml.

    This is the single source of truth for whether OCCP is L6-ready.
    """
    governance_path = _ARCHITECTURE_DIR / "governance.yaml"
    if not governance_path.exists():
        return {"error": "governance.yaml missing", "ready": False}

    with governance_path.open() as f:
        data = yaml.safe_load(f) or {}

    readiness = data.get("l6_readiness", {}).get("required", {})
    if not isinstance(readiness, dict):
        return {"error": "malformed l6_readiness section", "ready": False}

    total = len(readiness)
    achieved = sum(1 for v in readiness.values() if v is True)
    ready = achieved == total

    return {
        "ready": ready,
        "achieved": achieved,
        "total": total,
        "completion_percent": round((achieved / total * 100.0) if total else 0.0, 1),
        "markers": readiness,
        "generated_at": data.get("generated", "unknown"),
    }


# ── Admin ─────────────────────────────────────────────────────

@router.post(
    "/observability/reset",
    dependencies=[Depends(PermissionChecker("admin", "reset"))],
)
async def reset_metrics(
    current_user: dict = Depends(get_current_user_payload),
) -> dict[str, str]:
    """Reset all metrics. Admin-only."""
    get_collector().reset()
    logger.warning(
        "Observability metrics reset by user=%s role=%s",
        current_user.get("sub", "?"),
        current_user.get("role", "?"),
    )
    return {"status": "reset_ok"}
