"""Gen-AI span helpers following OpenTelemetry GenAI semantic conventions.

Reference: https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-spans/

The ``record_llm_call`` context manager emits a single span per LLM request
with the standardised ``gen_ai.*`` attributes plus Anthropic-specific prompt
caching counters (``gen_ai.usage.cache_creation.input_tokens`` and
``gen_ai.usage.cache_read.input_tokens``).

Design goals:

* **No hard dependency on OTel** — when the SDK is missing or OTEL is
  disabled, ``record_llm_call`` still yields a lightweight object so callers
  do not have to branch.
* **Vendor-agnostic** — works for Anthropic, OpenAI, and others through the
  ``system`` parameter (``anthropic`` / ``openai`` / ``cohere`` / ...).
* **Error-safe** — exceptions raised inside the ``with`` block are recorded
  as ``STATUS_ERROR`` with a ``exception`` event and re-raised.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

logger = logging.getLogger(__name__)


# GenAI semantic-convention attribute keys (subset of
# https://opentelemetry.io/docs/specs/semconv/attributes-registry/gen-ai/).
GEN_AI_SYSTEM = "gen_ai.system"
GEN_AI_OPERATION_NAME = "gen_ai.operation.name"
GEN_AI_REQUEST_MODEL = "gen_ai.request.model"
GEN_AI_REQUEST_TEMPERATURE = "gen_ai.request.temperature"
GEN_AI_REQUEST_MAX_TOKENS = "gen_ai.request.max_tokens"
GEN_AI_REQUEST_TOP_P = "gen_ai.request.top_p"
GEN_AI_REQUEST_TOP_K = "gen_ai.request.top_k"
GEN_AI_REQUEST_STOP_SEQUENCES = "gen_ai.request.stop_sequences"

GEN_AI_RESPONSE_ID = "gen_ai.response.id"
GEN_AI_RESPONSE_MODEL = "gen_ai.response.model"
GEN_AI_RESPONSE_FINISH_REASONS = "gen_ai.response.finish_reasons"

GEN_AI_USAGE_INPUT_TOKENS = "gen_ai.usage.input_tokens"
GEN_AI_USAGE_OUTPUT_TOKENS = "gen_ai.usage.output_tokens"
# Anthropic-specific prompt caching tokens
GEN_AI_USAGE_CACHE_CREATION_INPUT_TOKENS = (
    "gen_ai.usage.cache_creation.input_tokens"
)
GEN_AI_USAGE_CACHE_READ_INPUT_TOKENS = "gen_ai.usage.cache_read.input_tokens"


# Request param whitelist → OTel attribute key mapping.
_REQUEST_PARAM_MAP: dict[str, str] = {
    "temperature": GEN_AI_REQUEST_TEMPERATURE,
    "max_tokens": GEN_AI_REQUEST_MAX_TOKENS,
    "max_output_tokens": GEN_AI_REQUEST_MAX_TOKENS,
    "top_p": GEN_AI_REQUEST_TOP_P,
    "top_k": GEN_AI_REQUEST_TOP_K,
    "stop_sequences": GEN_AI_REQUEST_STOP_SEQUENCES,
}


class _NullSpan:
    """Fallback span used when OTel is unavailable. Quietly accepts calls."""

    def set_attribute(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    def set_attributes(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    def record_exception(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    def set_status(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    def add_event(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    def update_name(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    def end(self) -> None:  # pragma: no cover — trivial
        return None


def _get_tracer() -> Any | None:
    try:
        from opentelemetry import trace
    except Exception:
        return None
    return trace.get_tracer("occp.gen_ai")


def _set_if_present(span: Any, attrs: dict[str, Any]) -> None:
    for key, value in attrs.items():
        if value is None:
            continue
        try:
            span.set_attribute(key, value)
        except Exception as exc:  # pragma: no cover — defensive
            logger.debug("Failed to set span attribute %s: %s", key, exc)


def _coerce_int(value: Any) -> int | None:
    """Safely convert ``value`` to ``int`` — returns ``None`` on failure.

    Guards against ``MagicMock`` / sentinel objects returned by fake SDKs
    where ``int(value)`` would raise ``TypeError``.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
    return None


def _extract_usage(usage: Any) -> dict[str, int]:
    """Normalise an Anthropic/OpenAI ``usage`` payload into a flat dict.

    Accepts either a dict-like object or an SDK model (e.g.
    ``anthropic.types.Usage``). Non-integer values (e.g. ``MagicMock``) are
    silently dropped so that fake-response fixtures don't crash callers.
    """
    if usage is None:
        return {}

    def _get(obj: Any, key: str) -> Any:
        if isinstance(obj, dict):
            return obj.get(key)
        return getattr(obj, key, None)

    out: dict[str, int] = {}

    # Anthropic + our internal naming
    input_tokens = _coerce_int(_get(usage, "input_tokens"))
    output_tokens = _coerce_int(_get(usage, "output_tokens"))

    # OpenAI naming fallback
    if input_tokens is None:
        input_tokens = _coerce_int(_get(usage, "prompt_tokens"))
    if output_tokens is None:
        output_tokens = _coerce_int(_get(usage, "completion_tokens"))

    if input_tokens is not None:
        out["input_tokens"] = input_tokens
    if output_tokens is not None:
        out["output_tokens"] = output_tokens

    cache_creation = _coerce_int(_get(usage, "cache_creation_input_tokens"))
    cache_read = _coerce_int(_get(usage, "cache_read_input_tokens"))
    if cache_creation is not None:
        out["cache_creation_input_tokens"] = cache_creation
    if cache_read is not None:
        out["cache_read_input_tokens"] = cache_read

    return out


def _extract_response_meta(response: Any) -> dict[str, Any]:
    """Pull the response id / model / finish-reason out of an SDK payload."""
    if response is None:
        return {}

    def _get(obj: Any, key: str) -> Any:
        if isinstance(obj, dict):
            return obj.get(key)
        return getattr(obj, key, None)

    response_id = _get(response, "id")
    model = _get(response, "model")
    # Anthropic: ``stop_reason`` (string). OpenAI: ``choices[].finish_reason``.
    finish = _get(response, "stop_reason")
    finish_reasons: list[str] | None = None
    if finish:
        finish_reasons = [str(finish)]
    else:
        choices = _get(response, "choices")
        if isinstance(choices, list) and choices:
            reasons = []
            for choice in choices:
                reason = _get(choice, "finish_reason")
                if reason:
                    reasons.append(str(reason))
            if reasons:
                finish_reasons = reasons

    meta: dict[str, Any] = {}
    if response_id:
        meta[GEN_AI_RESPONSE_ID] = str(response_id)
    if model:
        meta[GEN_AI_RESPONSE_MODEL] = str(model)
    if finish_reasons:
        meta[GEN_AI_RESPONSE_FINISH_REASONS] = finish_reasons

    return meta


def _apply_request_attrs(span: Any, request_kwargs: dict[str, Any] | None) -> None:
    if not request_kwargs:
        return
    attrs: dict[str, Any] = {}
    for key, attr_name in _REQUEST_PARAM_MAP.items():
        if key not in request_kwargs:
            continue
        value = request_kwargs[key]
        if value is None:
            continue
        if key == "stop_sequences" and isinstance(value, (list, tuple)):
            attrs[attr_name] = [str(v) for v in value]
        elif isinstance(value, bool):
            # Guard against bool-as-int edge case; keep as-is.
            attrs[attr_name] = value
        else:
            attrs[attr_name] = value
    _set_if_present(span, attrs)


def record_response(
    span: Any,
    response: Any = None,
    usage: Any = None,
) -> None:
    """Attach response + usage attributes to an existing span.

    Exposed as a standalone helper so that streaming callers (which receive
    the final usage payload *after* the initial response arrives) can update
    their spans without holding the context-manager open.
    """
    if span is None:
        return

    _set_if_present(span, _extract_response_meta(response))

    usage_dict = _extract_usage(usage if usage is not None else response and _get_attr(response, "usage"))
    attr_map = {
        GEN_AI_USAGE_INPUT_TOKENS: usage_dict.get("input_tokens"),
        GEN_AI_USAGE_OUTPUT_TOKENS: usage_dict.get("output_tokens"),
        GEN_AI_USAGE_CACHE_CREATION_INPUT_TOKENS: usage_dict.get(
            "cache_creation_input_tokens"
        ),
        GEN_AI_USAGE_CACHE_READ_INPUT_TOKENS: usage_dict.get(
            "cache_read_input_tokens"
        ),
    }
    _set_if_present(span, attr_map)


def _get_attr(obj: Any, key: str) -> Any:
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


@contextmanager
def record_llm_call(
    operation: str,
    model: str,
    *,
    system: str = "anthropic",
    request_kwargs: dict[str, Any] | None = None,
) -> Iterator[Any]:
    """Context manager that emits a single ``gen_ai.*`` span for an LLM call.

    Typical usage::

        with record_llm_call(
            "chat",
            model="claude-sonnet-4-6",
            system="anthropic",
            request_kwargs={"temperature": 0.2, "max_tokens": 1024},
        ) as span:
            response = await client.messages.create(...)
            record_response(span, response=response, usage=response.usage)

    The span name follows the GenAI semconv convention
    ``"{operation} {model}"`` (e.g. ``"chat claude-sonnet-4-6"``).

    On success the span is closed with ``StatusCode.OK``. On exception the
    exception is recorded (with stacktrace) and the span is closed with
    ``StatusCode.ERROR`` before the exception is re-raised.
    """
    tracer = _get_tracer()
    span_name = f"{operation} {model}".strip()

    if tracer is None:
        # OTel unavailable → yield a null span so callers are unaffected.
        yield _NullSpan()
        return

    try:
        from opentelemetry.trace import SpanKind, Status, StatusCode
    except Exception:
        yield _NullSpan()
        return

    with tracer.start_as_current_span(
        span_name,
        kind=SpanKind.CLIENT,
        # We take full responsibility for exception recording + status so
        # that gen_ai spans get a clean, single 'exception' event and a
        # predictable status description.
        record_exception=False,
        set_status_on_exception=False,
    ) as span:
        try:
            _set_if_present(
                span,
                {
                    GEN_AI_SYSTEM: system,
                    GEN_AI_OPERATION_NAME: operation,
                    GEN_AI_REQUEST_MODEL: model,
                },
            )
            _apply_request_attrs(span, request_kwargs)
        except Exception as exc:  # pragma: no cover — defensive
            logger.debug("Failed to apply gen_ai request attrs: %s", exc)

        try:
            yield span
        except Exception as exc:
            try:
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR, str(exc)))
            except Exception:  # pragma: no cover — defensive
                pass
            raise
        else:
            try:
                span.set_status(Status(StatusCode.OK))
            except Exception:  # pragma: no cover — defensive
                pass


__all__ = [
    "record_llm_call",
    "record_response",
    # Attribute key constants (exported for tests / external integrations)
    "GEN_AI_SYSTEM",
    "GEN_AI_OPERATION_NAME",
    "GEN_AI_REQUEST_MODEL",
    "GEN_AI_REQUEST_TEMPERATURE",
    "GEN_AI_REQUEST_MAX_TOKENS",
    "GEN_AI_REQUEST_TOP_P",
    "GEN_AI_RESPONSE_ID",
    "GEN_AI_RESPONSE_MODEL",
    "GEN_AI_RESPONSE_FINISH_REASONS",
    "GEN_AI_USAGE_INPUT_TOKENS",
    "GEN_AI_USAGE_OUTPUT_TOKENS",
    "GEN_AI_USAGE_CACHE_CREATION_INPUT_TOKENS",
    "GEN_AI_USAGE_CACHE_READ_INPUT_TOKENS",
]
