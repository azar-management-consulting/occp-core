"""OCCP middleware — security headers, request logging, rate limiting.

All middleware is implemented as Starlette-compatible classes for composability
with FastAPI's ``add_middleware`` pattern.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Security Headers
# ---------------------------------------------------------------------------

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Append hardened HTTP security headers to every response.

    Headers follow OWASP recommendations.  HSTS is only set when
    ``include_hsts=True`` (should be enabled in production behind TLS).
    """

    def __init__(self, app: Any, *, include_hsts: bool = False) -> None:
        super().__init__(app)
        self._include_hsts = include_hsts

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=()"
        )
        response.headers["Cache-Control"] = "no-store"
        if self._include_hsts:
            response.headers["Strict-Transport-Security"] = (
                "max-age=63072000; includeSubDomains; preload"
            )
        return response


# ---------------------------------------------------------------------------
# Request Logging
# ---------------------------------------------------------------------------

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every HTTP request with method, path, status, and duration.

    Uses structured key-value pairs so that JSON log formatters can index
    the fields automatically.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        start = time.monotonic()
        response: Response | None = None
        try:
            response = await call_next(request)
            return response
        finally:
            duration_ms = round((time.monotonic() - start) * 1000, 1)
            status = response.status_code if response else 500
            logger.info(
                "http_request method=%s path=%s status=%d duration_ms=%.1f",
                request.method,
                request.url.path,
                status,
                duration_ms,
            )


# ---------------------------------------------------------------------------
# Rate Limiting (in-memory sliding window)
# ---------------------------------------------------------------------------

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory sliding-window rate limiter.

    Limits are per client IP.  Only applies to paths listed in
    ``rate_limit_paths`` (defaults to auth endpoints).

    Parameters
    ----------
    requests_per_window : int
        Maximum requests allowed within the window.
    window_seconds : int
        Duration of the sliding window in seconds.
    rate_limit_paths : list[str] | None
        URL path prefixes to rate-limit.  ``None`` = all paths.
    """

    def __init__(
        self,
        app: Any,
        *,
        requests_per_window: int = 20,
        window_seconds: int = 60,
        rate_limit_paths: list[str] | None = None,
    ) -> None:
        super().__init__(app)
        self._max_requests = requests_per_window
        self._window = window_seconds
        self._paths = rate_limit_paths
        # {client_ip: [timestamp, ...]}
        self._hits: dict[str, list[float]] = defaultdict(list)

    def _client_ip(self, request: Request) -> str:
        """Extract client IP, respecting X-Forwarded-For behind a reverse proxy."""
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _should_limit(self, path: str) -> bool:
        """Return True if *path* is subject to rate limiting."""
        if self._paths is None:
            return True
        return any(path.startswith(p) for p in self._paths)

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if not self._should_limit(request.url.path):
            return await call_next(request)

        client = self._client_ip(request)
        now = time.monotonic()
        cutoff = now - self._window

        # Prune expired timestamps
        hits = self._hits[client]
        self._hits[client] = [t for t in hits if t > cutoff]

        if len(self._hits[client]) >= self._max_requests:
            retry_after = int(self._window - (now - self._hits[client][0]))
            logger.warning(
                "rate_limit_exceeded client=%s path=%s",
                client,
                request.url.path,
            )
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Too many requests",
                    "retry_after": max(retry_after, 1),
                },
                headers={"Retry-After": str(max(retry_after, 1))},
            )

        self._hits[client].append(now)
        return await call_next(request)
