"""Observability API routes (L6 foundation).

Exposes Prometheus-format metrics and JSON snapshots for dashboard
consumption. These endpoints are the read-side of OCCP's self-observation
capability.

Endpoints:
    GET  /observability/metrics        - Prometheus exposition text
    GET  /observability/snapshot       - JSON snapshot of all metrics
    GET  /observability/health         - Observability subsystem health
    POST /observability/reset          - Reset metrics (admin only)
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Response

from api.auth import get_current_user_payload
from api.deps import AppState, get_state
from api.rbac import PermissionChecker
from observability import get_collector

logger = logging.getLogger(__name__)

router = APIRouter(tags=["observability"])


@router.get("/observability/metrics", response_class=Response)
async def get_prometheus_metrics(
    current_user: dict = Depends(get_current_user_payload),
) -> Response:
    """Return metrics in Prometheus text exposition format.

    Authenticated endpoint — requires any valid JWT. Suitable for
    a Prometheus server with bearer_token configured, or for
    manual inspection by authorized users.
    """
    collector = get_collector()
    text = collector.render_prometheus()
    return Response(
        content=text,
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@router.get("/observability/snapshot")
async def get_metrics_snapshot(
    current_user: dict = Depends(get_current_user_payload),
) -> dict[str, Any]:
    """Return a JSON snapshot of all metrics for dashboard display."""
    collector = get_collector()
    return collector.snapshot()


@router.get("/observability/health")
async def observability_health() -> dict[str, Any]:
    """Public health endpoint for the observability subsystem."""
    collector = get_collector()
    snap = collector.snapshot()
    return {
        "status": "healthy",
        "uptime_seconds": snap["uptime_seconds"],
        "counters_registered": len(snap["counters"]),
        "gauges_registered": len(snap["gauges"]),
        "histograms_registered": len(snap["histograms"]),
    }


@router.post(
    "/observability/reset",
    dependencies=[Depends(PermissionChecker("admin", "reset"))],
)
async def reset_metrics(
    current_user: dict = Depends(get_current_user_payload),
) -> dict[str, str]:
    """Reset all metrics. Admin-only — intended for test harness usage."""
    collector = get_collector()
    collector.reset()
    logger.warning(
        "Observability metrics reset by user=%s role=%s",
        current_user.get("sub", "?"),
        current_user.get("role", "?"),
    )
    return {"status": "reset_ok"}
