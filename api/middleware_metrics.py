"""HTTP metrics middleware — feeds Grafana SLO dashboard.

Records every request into the in-process :class:`MetricsCollector` so
the panels ``occp_http_requests_total`` and
``occp_http_request_duration_seconds_bucket`` have data.

Labels:
    method  — HTTP method (GET, POST, ...)
    path    — *normalized path template* (e.g. ``/api/v1/tasks/{task_id}``)
              so we don't explode cardinality with per-ID labels.
    status  — numeric HTTP status code as a string.

Safe on exception paths: the counter + histogram always increment, even
when the route handler raises. In that case we emit status=500 so the
"5xx error rate" SLO panel sees the failure.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from observability.metrics_collector import get_collector

logger = logging.getLogger(__name__)


def _resolve_path_template(request: Request) -> str:
    """Return the normalized path template, or the raw URL path as fallback.

    FastAPI stores the matched route on ``request.scope["route"]`` once
    routing has run. Its ``path`` attribute is the template (e.g.
    ``/api/v1/tasks/{task_id}``). Falling back to ``request.url.path``
    is fine for 404s and paths that never matched a route.
    """
    route = request.scope.get("route") if request.scope else None
    path = getattr(route, "path", None)
    if isinstance(path, str) and path:
        return path
    return request.url.path


class MetricsMiddleware(BaseHTTPMiddleware):
    """Instrument every request with Prometheus-style counters + histogram."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        start = time.monotonic()
        method = request.method
        status_code = 500  # Default for the exception path
        response: Response | None = None
        exc: BaseException | None = None
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except BaseException as e:  # noqa: BLE001 — re-raised below
            exc = e
            raise
        finally:
            duration = time.monotonic() - start
            try:
                coll = get_collector()
                path = _resolve_path_template(request)
                coll.record_http_request(
                    method=method,
                    path=path,
                    status=status_code,
                    duration_seconds=duration,
                )
            except Exception as metrics_exc:  # noqa: BLE001
                # Metrics must never break the request path.
                logger.debug(
                    "metrics middleware emit failed: %s (orig_exc=%r)",
                    metrics_exc,
                    exc,
                )
