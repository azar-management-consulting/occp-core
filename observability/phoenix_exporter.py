"""Stack selector for self-hosted observability backends.

This module is **additive** to :mod:`observability.otel_setup` — it does not
modify or replace ``init_otel``. Instead it reads ``OCCP_OBSERVABILITY_STACK``
from the environment and, when a known stack is configured, delegates to
``init_otel`` with the appropriate endpoint + headers.

Supported stacks:
    * ``phoenix`` (default when var unset is still no-op; must be set explicitly
      to activate) — Arize Phoenix self-host, OTLP HTTP on ``:4318``
    * ``langfuse`` — Langfuse v3 self-host, OTLP HTTP at
      ``/api/public/otel/v1/traces``

Opt-in semantics mirror ``init_otel``: if neither
``OCCP_OBSERVABILITY_STACK`` nor ``OCCP_OTEL_ENABLED`` is set, this module
is a no-op. Unknown stack values log a warning and no-op — never raise.

Env contract
------------
``OCCP_OBSERVABILITY_STACK``
    ``phoenix`` | ``langfuse`` | unset
``OCCP_OTEL_ENDPOINT``
    Full endpoint. When unset, defaults are derived from the stack:
    * phoenix  -> ``http://localhost:4318``
    * langfuse -> ``http://localhost:3100/api/public/otel``
``OCCP_OTEL_HEADERS``
    Comma-separated ``k=v`` pairs forwarded as OTLP headers (e.g.
    ``authorization=Bearer%20pk-lf-...``). Set via env so no rewriting of
    ``init_otel`` is needed.
``LANGFUSE_PUBLIC_KEY`` / ``LANGFUSE_SECRET_KEY``
    When the stack is ``langfuse`` and ``OCCP_OTEL_HEADERS`` is unset, we
    derive a basic-auth header automatically.
"""

from __future__ import annotations

import base64
import logging
import os
from typing import Any

from observability.otel_setup import init_otel

logger = logging.getLogger(__name__)


_KNOWN_STACKS = frozenset({"phoenix", "langfuse"})

_DEFAULT_ENDPOINTS: dict[str, str] = {
    "phoenix": "http://localhost:4318",
    "langfuse": "http://localhost:3100/api/public/otel",
}


def _current_stack() -> str | None:
    raw = os.getenv("OCCP_OBSERVABILITY_STACK")
    if raw is None:
        return None
    stack = raw.strip().lower()
    if not stack:
        return None
    return stack


def _resolve_endpoint(stack: str) -> str:
    explicit = os.getenv("OCCP_OTEL_ENDPOINT")
    if explicit:
        return explicit
    return _DEFAULT_ENDPOINTS[stack]


def _maybe_inject_langfuse_auth() -> None:
    """If langfuse keys are set and no OTEL headers configured, synthesise one.

    Langfuse OTLP ingestion uses HTTP Basic auth with
    ``public_key:secret_key``. We write the result to
    ``OTEL_EXPORTER_OTLP_HEADERS`` which the opentelemetry HTTP exporter
    picks up automatically — this avoids touching ``init_otel`` at all.
    """
    if os.getenv("OCCP_OTEL_HEADERS") or os.getenv("OTEL_EXPORTER_OTLP_HEADERS"):
        return
    pk = os.getenv("LANGFUSE_PUBLIC_KEY")
    sk = os.getenv("LANGFUSE_SECRET_KEY")
    if not pk or not sk:
        return
    token = base64.b64encode(f"{pk}:{sk}".encode("utf-8")).decode("ascii")
    os.environ["OTEL_EXPORTER_OTLP_HEADERS"] = f"authorization=Basic {token}"
    logger.debug("Langfuse basic-auth header derived from public/secret key")


def _promote_custom_headers() -> None:
    """Map ``OCCP_OTEL_HEADERS`` onto the standard OTLP exporter env var."""
    custom = os.getenv("OCCP_OTEL_HEADERS")
    if not custom:
        return
    if os.getenv("OTEL_EXPORTER_OTLP_HEADERS"):
        return  # caller already set it explicitly — don't clobber
    os.environ["OTEL_EXPORTER_OTLP_HEADERS"] = custom


def auto_configure(
    *,
    service_name: str = "occp-api",
    env: str | None = None,
    app: Any | None = None,
) -> Any | None:
    """Configure OTEL for the selected observability stack.

    Returns the ``TracerProvider`` from :func:`init_otel` when a stack was
    selected, otherwise ``None``. Never raises — any misconfiguration is
    logged and treated as a no-op.
    """
    stack = _current_stack()
    if stack is None:
        logger.debug("OCCP_OBSERVABILITY_STACK not set; auto_configure is a no-op")
        return None

    if stack not in _KNOWN_STACKS:
        logger.warning(
            "Unknown OCCP_OBSERVABILITY_STACK=%r; expected one of %s — skipping",
            stack,
            sorted(_KNOWN_STACKS),
        )
        return None

    # Derive auth headers BEFORE init_otel so the exporter sees them.
    if stack == "langfuse":
        _maybe_inject_langfuse_auth()
    _promote_custom_headers()

    endpoint = _resolve_endpoint(stack)
    deployment_env = env or os.getenv("OCCP_ENV") or "development"

    logger.info(
        "Observability stack selected: %s (endpoint=%s)", stack, endpoint
    )

    try:
        return init_otel(
            service_name=service_name,
            otlp_endpoint=endpoint,
            env=deployment_env,
            app=app,
        )
    except Exception as exc:  # defensive — telemetry must never break startup
        logger.warning("auto_configure: init_otel failed (%s); continuing", exc)
        return None


__all__ = ["auto_configure"]
