"""Tests for OpenTelemetry bootstrap + gen_ai semconv instrumentation.

These tests are self-contained: they swap the global TracerProvider for one
backed by ``InMemorySpanExporter`` so that we can assert attribute/status
behaviour without any network I/O or OTLP collector.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

# Skip the entire module if the OTel SDK isn't available.
pytest.importorskip("opentelemetry")
pytest.importorskip("opentelemetry.sdk")

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import StatusCode

from observability import gen_ai_tracer, otel_setup
from observability.gen_ai_tracer import (
    GEN_AI_OPERATION_NAME,
    GEN_AI_REQUEST_MAX_TOKENS,
    GEN_AI_REQUEST_MODEL,
    GEN_AI_REQUEST_TEMPERATURE,
    GEN_AI_REQUEST_TOP_P,
    GEN_AI_RESPONSE_FINISH_REASONS,
    GEN_AI_RESPONSE_ID,
    GEN_AI_RESPONSE_MODEL,
    GEN_AI_SYSTEM,
    GEN_AI_USAGE_CACHE_CREATION_INPUT_TOKENS,
    GEN_AI_USAGE_CACHE_READ_INPUT_TOKENS,
    GEN_AI_USAGE_INPUT_TOKENS,
    GEN_AI_USAGE_OUTPUT_TOKENS,
    record_llm_call,
    record_response,
)


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------

@pytest.fixture
def in_memory_exporter():
    """Install a fresh TracerProvider wired to an InMemorySpanExporter.

    Uses ``SimpleSpanProcessor`` so finished spans appear synchronously.

    We bypass the ``set_tracer_provider`` "set-once" guard by writing to the
    private globals directly. This keeps tests isolated: each invocation
    gets its own provider + exporter, and the previous state is restored
    on teardown.
    """
    exporter = InMemorySpanExporter()
    provider = TracerProvider(resource=Resource.create({"service.name": "test"}))
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    prev_provider = getattr(trace, "_TRACER_PROVIDER", None)
    set_once = getattr(trace, "_TRACER_PROVIDER_SET_ONCE", None)
    prev_done = getattr(set_once, "_done", False) if set_once is not None else False

    trace._TRACER_PROVIDER = provider  # type: ignore[attr-defined]
    if set_once is not None:
        set_once._done = True  # type: ignore[attr-defined]

    try:
        yield exporter
    finally:
        exporter.clear()
        trace._TRACER_PROVIDER = prev_provider  # type: ignore[attr-defined]
        if set_once is not None:
            set_once._done = prev_done  # type: ignore[attr-defined]


@pytest.fixture(autouse=True)
def _reset_otel_state():
    """Ensure each test sees a clean otel_setup state.

    Resets both our module-level flags and the OTel global
    ``_TRACER_PROVIDER`` / ``_TRACER_PROVIDER_SET_ONCE`` so tests don't
    bleed state into one another.
    """
    otel_setup.reset_for_testing()
    prev_provider = getattr(trace, "_TRACER_PROVIDER", None)
    set_once = getattr(trace, "_TRACER_PROVIDER_SET_ONCE", None)
    prev_done = getattr(set_once, "_done", False) if set_once is not None else False

    yield

    otel_setup.reset_for_testing()
    trace._TRACER_PROVIDER = prev_provider  # type: ignore[attr-defined]
    if set_once is not None:
        set_once._done = prev_done  # type: ignore[attr-defined]


# --------------------------------------------------------------------------
# init_otel behaviour
# --------------------------------------------------------------------------

def test_init_otel_disabled_by_env(monkeypatch):
    """When OCCP_OTEL_ENABLED is not set/truthy, init_otel is a no-op."""
    monkeypatch.delenv("OCCP_OTEL_ENABLED", raising=False)
    result = otel_setup.init_otel(service_name="occp-test")
    assert result is None
    assert otel_setup.is_initialized() is False

    monkeypatch.setenv("OCCP_OTEL_ENABLED", "false")
    result = otel_setup.init_otel(service_name="occp-test")
    assert result is None
    assert otel_setup.is_initialized() is False


def test_init_otel_idempotent(monkeypatch):
    """Calling init_otel twice should not raise and must be idempotent."""
    monkeypatch.setenv("OCCP_OTEL_ENABLED", "true")
    monkeypatch.setenv("OCCP_OTEL_ENDPOINT", "http://127.0.0.1:4318")

    first = otel_setup.init_otel(service_name="occp-test", env="test")
    assert first is not None
    assert otel_setup.is_initialized() is True

    second = otel_setup.init_otel(service_name="occp-test", env="test")
    # Same provider object returned on subsequent calls.
    assert second is first


def test_init_otel_force_reinitialises(monkeypatch):
    monkeypatch.setenv("OCCP_OTEL_ENABLED", "true")
    first = otel_setup.init_otel(service_name="occp-test", env="test")
    second = otel_setup.init_otel(
        service_name="occp-test", env="test", force=True
    )
    assert first is not None
    assert second is not None
    # With force=True we build a new provider.
    assert first is not second


# --------------------------------------------------------------------------
# gen_ai span attributes
# --------------------------------------------------------------------------

def _fake_anthropic_response(
    *,
    usage_input: int = 120,
    usage_output: int = 64,
    cache_creation: int | None = None,
    cache_read: int | None = None,
    stop_reason: str = "end_turn",
    response_id: str = "msg_01ABCDEF",
    model: str = "claude-sonnet-4-6",
):
    """Build a SimpleNamespace mimicking an anthropic Message response."""
    usage = SimpleNamespace(
        input_tokens=usage_input,
        output_tokens=usage_output,
        cache_creation_input_tokens=cache_creation,
        cache_read_input_tokens=cache_read,
    )
    content = [SimpleNamespace(text='{"strategy":"test","steps":["a","b"]}')]
    return SimpleNamespace(
        id=response_id,
        model=model,
        stop_reason=stop_reason,
        usage=usage,
        content=content,
    )


def test_gen_ai_span_attributes(in_memory_exporter):
    """All core gen_ai.* attrs are populated from a successful call."""
    resp = _fake_anthropic_response(usage_input=200, usage_output=80)

    with record_llm_call(
        "chat",
        model="claude-sonnet-4-6",
        system="anthropic",
        request_kwargs={
            "max_tokens": 1024,
            "temperature": 0.2,
            "top_p": 0.9,
        },
    ) as span:
        record_response(span, response=resp, usage=resp.usage)

    spans = in_memory_exporter.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]

    # Span naming per semconv
    assert span.name == "chat claude-sonnet-4-6"

    attrs = dict(span.attributes)
    assert attrs[GEN_AI_SYSTEM] == "anthropic"
    assert attrs[GEN_AI_OPERATION_NAME] == "chat"
    assert attrs[GEN_AI_REQUEST_MODEL] == "claude-sonnet-4-6"
    assert attrs[GEN_AI_REQUEST_MAX_TOKENS] == 1024
    assert attrs[GEN_AI_REQUEST_TEMPERATURE] == pytest.approx(0.2)
    assert attrs[GEN_AI_REQUEST_TOP_P] == pytest.approx(0.9)

    assert attrs[GEN_AI_RESPONSE_ID] == "msg_01ABCDEF"
    assert attrs[GEN_AI_RESPONSE_MODEL] == "claude-sonnet-4-6"
    assert tuple(attrs[GEN_AI_RESPONSE_FINISH_REASONS]) == ("end_turn",)

    assert attrs[GEN_AI_USAGE_INPUT_TOKENS] == 200
    assert attrs[GEN_AI_USAGE_OUTPUT_TOKENS] == 80

    # Status OK on clean exit
    assert span.status.status_code == StatusCode.OK


def test_gen_ai_span_error(in_memory_exporter):
    """Exception inside the context records STATUS_ERROR + exception event."""
    with pytest.raises(RuntimeError, match="boom"):
        with record_llm_call(
            "chat",
            model="claude-sonnet-4-6",
            system="anthropic",
            request_kwargs={"max_tokens": 512},
        ) as span:
            # Some attrs should be set before the exception propagates.
            _ = span
            raise RuntimeError("boom")

    spans = in_memory_exporter.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]

    assert span.status.status_code == StatusCode.ERROR
    assert span.status.description == "boom"

    # Ensure an exception event was recorded.
    exception_events = [e for e in span.events if e.name == "exception"]
    assert exception_events, "expected at least one 'exception' event"
    ev_attrs = dict(exception_events[0].attributes)
    assert ev_attrs.get("exception.type") == "RuntimeError"
    assert "boom" in ev_attrs.get("exception.message", "")


def test_cache_fields_populated(in_memory_exporter):
    """Anthropic cache_creation/cache_read tokens map to gen_ai.usage attrs."""
    resp = _fake_anthropic_response(
        usage_input=100,
        usage_output=40,
        cache_creation=25,
        cache_read=75,
    )

    with record_llm_call(
        "chat",
        model="claude-sonnet-4-6",
        system="anthropic",
    ) as span:
        record_response(span, response=resp, usage=resp.usage)

    spans = in_memory_exporter.get_finished_spans()
    assert len(spans) == 1
    attrs = dict(spans[0].attributes)

    assert attrs[GEN_AI_USAGE_INPUT_TOKENS] == 100
    assert attrs[GEN_AI_USAGE_OUTPUT_TOKENS] == 40
    assert attrs[GEN_AI_USAGE_CACHE_CREATION_INPUT_TOKENS] == 25
    assert attrs[GEN_AI_USAGE_CACHE_READ_INPUT_TOKENS] == 75


def test_cache_fields_absent_when_not_present(in_memory_exporter):
    """When cache_* keys are None/missing, no cache attrs are emitted."""
    resp = _fake_anthropic_response(
        usage_input=50, usage_output=25, cache_creation=None, cache_read=None
    )

    with record_llm_call(
        "chat", model="claude-sonnet-4-6", system="anthropic"
    ) as span:
        record_response(span, response=resp, usage=resp.usage)

    attrs = dict(in_memory_exporter.get_finished_spans()[0].attributes)
    assert GEN_AI_USAGE_INPUT_TOKENS in attrs
    assert GEN_AI_USAGE_OUTPUT_TOKENS in attrs
    assert GEN_AI_USAGE_CACHE_CREATION_INPUT_TOKENS not in attrs
    assert GEN_AI_USAGE_CACHE_READ_INPUT_TOKENS not in attrs


def test_usage_extracted_from_dict(in_memory_exporter):
    """record_response accepts a plain dict usage (for tests/mocks)."""
    usage = {
        "input_tokens": 10,
        "output_tokens": 5,
        "cache_creation_input_tokens": 2,
        "cache_read_input_tokens": 3,
    }
    response = SimpleNamespace(
        id="msg_dict", model="claude-opus-4", stop_reason="end_turn"
    )

    with record_llm_call(
        "chat", model="claude-opus-4", system="anthropic"
    ) as span:
        record_response(span, response=response, usage=usage)

    attrs = dict(in_memory_exporter.get_finished_spans()[0].attributes)
    assert attrs[GEN_AI_USAGE_INPUT_TOKENS] == 10
    assert attrs[GEN_AI_USAGE_OUTPUT_TOKENS] == 5
    assert attrs[GEN_AI_USAGE_CACHE_CREATION_INPUT_TOKENS] == 2
    assert attrs[GEN_AI_USAGE_CACHE_READ_INPUT_TOKENS] == 3


def test_null_span_when_otel_unavailable(monkeypatch):
    """When tracer resolution fails, record_llm_call yields a NullSpan."""
    monkeypatch.setattr(gen_ai_tracer, "_get_tracer", lambda: None)
    with record_llm_call("chat", model="claude") as span:
        # Null span accepts arbitrary calls without raising.
        span.set_attribute("x", "y")
        record_response(
            span,
            response=SimpleNamespace(id="x", model="claude", stop_reason="end_turn"),
            usage={"input_tokens": 1, "output_tokens": 1},
        )


def test_openai_response_finish_reasons(in_memory_exporter):
    """OpenAI-style choices[].finish_reason is mapped to a list."""
    response = SimpleNamespace(
        id="cmpl_1",
        model="gpt-4o",
        choices=[SimpleNamespace(finish_reason="stop")],
    )
    usage = SimpleNamespace(prompt_tokens=12, completion_tokens=7)

    with record_llm_call("chat", model="gpt-4o", system="openai") as span:
        record_response(span, response=response, usage=usage)

    attrs = dict(in_memory_exporter.get_finished_spans()[0].attributes)
    assert tuple(attrs[GEN_AI_RESPONSE_FINISH_REASONS]) == ("stop",)
    assert attrs[GEN_AI_USAGE_INPUT_TOKENS] == 12
    assert attrs[GEN_AI_USAGE_OUTPUT_TOKENS] == 7
    assert attrs[GEN_AI_SYSTEM] == "openai"
