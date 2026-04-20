"""OpenTelemetry bootstrap for OCCP.

This module wires up an OTLP-exporting ``TracerProvider`` and opportunistically
instruments FastAPI, httpx, and SQLAlchemy when the corresponding
``opentelemetry-instrumentation-*`` packages are available.

Activation is **opt-in**: ``init_otel`` only performs real initialisation when
``OCCP_OTEL_ENABLED`` evaluates truthy (``1``, ``true``, ``yes``, ``on``).
Otherwise the call is a no-op so that production deployments can ship this
code path safely without any additional egress or overhead.

Usage::

    from observability.otel_setup import init_otel

    init_otel(
        service_name="occp-api",
        otlp_endpoint="http://otel-collector:4318",
        env="production",
    )

Calling ``init_otel`` more than once is safe: the second and subsequent calls
return the already-configured ``TracerProvider`` without mutating global
state.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


# Module-level state -------------------------------------------------------
_INITIALIZED: bool = False
_PROVIDER: Any = None
_INSTRUMENTED_TARGETS: set[str] = set()


_TRUTHY = {"1", "true", "yes", "on", "y", "t"}


def _is_truthy(value: str | None) -> bool:
    if not value:
        return False
    return value.strip().lower() in _TRUTHY


def _otel_enabled_from_env() -> bool:
    """Return ``True`` when OTEL should be initialised based on env flag."""
    return _is_truthy(os.getenv("OCCP_OTEL_ENABLED"))


def is_initialized() -> bool:
    """Return whether ``init_otel`` has already been run successfully."""
    return _INITIALIZED


def _build_resource(service_name: str, env: str) -> Any:
    from opentelemetry.sdk.resources import Resource

    attrs: dict[str, str] = {
        "service.name": service_name,
        "service.namespace": "occp",
        "deployment.environment": env,
    }
    version = os.getenv("OCCP_VERSION")
    if version:
        attrs["service.version"] = version
    return Resource.create(attrs)


def _build_exporter(otlp_endpoint: str) -> Any:
    """Pick the appropriate OTLP exporter (http vs grpc) based on endpoint.

    * ``http://`` / ``https://`` → proto/http exporter
    * anything else → gRPC exporter
    """
    lowered = otlp_endpoint.lower()
    if lowered.startswith(("http://", "https://")):
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
        return OTLPSpanExporter(endpoint=otlp_endpoint)

    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
        OTLPSpanExporter as GrpcOTLPSpanExporter,
    )
    # For non-http schemes (e.g. raw host:port), default to insecure gRPC —
    # callers should prepend https:// in production to enable TLS.
    return GrpcOTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)


def _instrument_fastapi(app: Any | None) -> None:
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    except Exception as exc:  # ImportError or runtime init errors
        logger.debug("FastAPI instrumentation unavailable: %s", exc)
        return
    try:
        if app is not None:
            FastAPIInstrumentor.instrument_app(app)
        else:
            FastAPIInstrumentor().instrument()
        _INSTRUMENTED_TARGETS.add("fastapi")
    except Exception as exc:
        logger.warning("FastAPI instrumentation failed: %s", exc)


def _instrument_httpx() -> None:
    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    except Exception as exc:
        logger.debug("httpx instrumentation unavailable: %s", exc)
        return
    try:
        HTTPXClientInstrumentor().instrument()
        _INSTRUMENTED_TARGETS.add("httpx")
    except Exception as exc:
        logger.warning("httpx instrumentation failed: %s", exc)


def _instrument_sqlalchemy() -> None:
    try:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    except Exception as exc:
        logger.debug("SQLAlchemy instrumentation unavailable: %s", exc)
        return
    try:
        SQLAlchemyInstrumentor().instrument()
        _INSTRUMENTED_TARGETS.add("sqlalchemy")
    except Exception as exc:
        logger.warning("SQLAlchemy instrumentation failed: %s", exc)


def init_otel(
    service_name: str = "occp-api",
    otlp_endpoint: str | None = None,
    env: str = "development",
    *,
    app: Any | None = None,
    force: bool = False,
) -> Any | None:
    """Initialise OpenTelemetry tracing for OCCP.

    Parameters
    ----------
    service_name:
        ``service.name`` resource attribute attached to every exported span.
    otlp_endpoint:
        OTLP collector endpoint. Falls back to ``OCCP_OTEL_ENDPOINT`` or the
        standard ``OTEL_EXPORTER_OTLP_ENDPOINT``. If none is set, defaults to
        ``http://localhost:4318``.
    env:
        Deployment environment tag (``development``, ``staging``,
        ``production``).
    app:
        Optional FastAPI app to instrument directly. When ``None`` the
        FastAPI instrumentor is applied globally instead.
    force:
        When ``True`` re-run initialisation even if a provider has already
        been installed. Primarily useful for tests.

    Returns
    -------
    Optional[TracerProvider]
        The installed ``TracerProvider`` or ``None`` when OTEL is disabled.
    """
    global _INITIALIZED, _PROVIDER

    if not force and not _otel_enabled_from_env():
        logger.debug("OTEL disabled (OCCP_OTEL_ENABLED not truthy)")
        return None

    if _INITIALIZED and not force:
        # Idempotent: just re-apply instrumentation for a newly supplied app.
        if app is not None and "fastapi" not in _INSTRUMENTED_TARGETS:
            _instrument_fastapi(app)
        return _PROVIDER

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except Exception as exc:
        logger.warning("opentelemetry-sdk not importable (%s); OTEL disabled", exc)
        return None

    endpoint = (
        otlp_endpoint
        or os.getenv("OCCP_OTEL_ENDPOINT")
        or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
        or "http://localhost:4318"
    )

    resource = _build_resource(service_name=service_name, env=env)
    provider = TracerProvider(resource=resource)

    try:
        exporter = _build_exporter(endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))
    except Exception as exc:
        logger.warning(
            "OTLP exporter init failed (%s); continuing without remote export",
            exc,
        )

    trace.set_tracer_provider(provider)

    # Opt-in auto-instrumentations (each is best-effort).
    _instrument_fastapi(app)
    _instrument_httpx()
    _instrument_sqlalchemy()

    _PROVIDER = provider
    _INITIALIZED = True
    logger.info(
        "OTEL initialised: service=%s env=%s endpoint=%s targets=%s",
        service_name,
        env,
        endpoint,
        sorted(_INSTRUMENTED_TARGETS),
    )
    return provider


def reset_for_testing() -> None:
    """Reset module-level state. Intended for test suites only."""
    global _INITIALIZED, _PROVIDER
    _INITIALIZED = False
    _PROVIDER = None
    _INSTRUMENTED_TARGETS.clear()


__all__ = [
    "init_otel",
    "is_initialized",
    "reset_for_testing",
]
