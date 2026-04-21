"""Tests for observability.phoenix_exporter — the stack selector hook.

Validates the three contract points:
    1. OCCP_OBSERVABILITY_STACK=phoenix  → delegates to init_otel with the
       Phoenix OTLP endpoint.
    2. Unset (default)                   → no-op, returns None, init_otel
       NOT called.
    3. Invalid value                     → logs warning, no-op, does not
       raise, init_otel NOT called.

These tests monkeypatch ``init_otel`` so they don't touch real OTLP
exporters or the global TracerProvider.
"""

from __future__ import annotations

import logging

import pytest

from observability import phoenix_exporter


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------

@pytest.fixture
def clean_env(monkeypatch):
    """Strip every env var phoenix_exporter or init_otel might read."""
    for key in (
        "OCCP_OBSERVABILITY_STACK",
        "OCCP_OTEL_ENDPOINT",
        "OCCP_OTEL_ENABLED",
        "OCCP_OTEL_HEADERS",
        "OCCP_ENV",
        "OTEL_EXPORTER_OTLP_ENDPOINT",
        "OTEL_EXPORTER_OTLP_HEADERS",
        "LANGFUSE_PUBLIC_KEY",
        "LANGFUSE_SECRET_KEY",
    ):
        monkeypatch.delenv(key, raising=False)
    return monkeypatch


@pytest.fixture
def fake_init_otel(monkeypatch):
    """Replace init_otel with a recorder; return the recorder."""
    calls: list[dict] = []

    def _fake(
        service_name: str = "occp-api",
        otlp_endpoint: str | None = None,
        env: str = "development",
        *,
        app=None,
        force: bool = False,
    ):
        calls.append(
            {
                "service_name": service_name,
                "otlp_endpoint": otlp_endpoint,
                "env": env,
                "app": app,
                "force": force,
            }
        )
        return object()  # sentinel "provider"

    monkeypatch.setattr(phoenix_exporter, "init_otel", _fake)
    return calls


# --------------------------------------------------------------------------
# Tests
# --------------------------------------------------------------------------

def test_auto_configure_phoenix_uses_default_endpoint(clean_env, fake_init_otel):
    """stack=phoenix with no explicit endpoint → default http://localhost:4318."""
    clean_env.setenv("OCCP_OBSERVABILITY_STACK", "phoenix")

    result = phoenix_exporter.auto_configure(service_name="occp-api", env="test")

    assert result is not None
    assert len(fake_init_otel) == 1
    call = fake_init_otel[0]
    assert call["service_name"] == "occp-api"
    assert call["otlp_endpoint"] == "http://localhost:4318"
    assert call["env"] == "test"


def test_auto_configure_phoenix_respects_explicit_endpoint(
    clean_env, fake_init_otel
):
    """OCCP_OTEL_ENDPOINT overrides the stack default."""
    clean_env.setenv("OCCP_OBSERVABILITY_STACK", "phoenix")
    clean_env.setenv("OCCP_OTEL_ENDPOINT", "https://traces.occp.ai:4318")

    phoenix_exporter.auto_configure(service_name="occp-api", env="production")

    assert fake_init_otel[0]["otlp_endpoint"] == "https://traces.occp.ai:4318"
    assert fake_init_otel[0]["env"] == "production"


def test_auto_configure_default_is_noop(clean_env, fake_init_otel):
    """No env var set → no-op, init_otel never called."""
    result = phoenix_exporter.auto_configure()

    assert result is None
    assert fake_init_otel == []


def test_auto_configure_blank_value_is_noop(clean_env, fake_init_otel):
    """Empty/whitespace stack value is treated as unset."""
    clean_env.setenv("OCCP_OBSERVABILITY_STACK", "   ")

    result = phoenix_exporter.auto_configure()

    assert result is None
    assert fake_init_otel == []


def test_auto_configure_invalid_stack_warns_and_noops(
    clean_env, fake_init_otel, caplog
):
    """Unknown stack → log.warning, no-op, no raise."""
    clean_env.setenv("OCCP_OBSERVABILITY_STACK", "datadog")

    with caplog.at_level(logging.WARNING, logger="observability.phoenix_exporter"):
        result = phoenix_exporter.auto_configure()

    assert result is None
    assert fake_init_otel == []
    assert any(
        "Unknown OCCP_OBSERVABILITY_STACK" in rec.message
        for rec in caplog.records
    ), "expected a warning about the unknown stack value"


def test_auto_configure_langfuse_uses_public_api_default(clean_env, fake_init_otel):
    """stack=langfuse → default http://localhost:3100/api/public/otel."""
    clean_env.setenv("OCCP_OBSERVABILITY_STACK", "langfuse")

    phoenix_exporter.auto_configure()

    assert len(fake_init_otel) == 1
    assert (
        fake_init_otel[0]["otlp_endpoint"]
        == "http://localhost:3100/api/public/otel"
    )


def test_auto_configure_langfuse_derives_basic_auth(
    clean_env, fake_init_otel, monkeypatch
):
    """stack=langfuse with public/secret keys → OTLP basic-auth header set."""
    clean_env.setenv("OCCP_OBSERVABILITY_STACK", "langfuse")
    clean_env.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-test")
    clean_env.setenv("LANGFUSE_SECRET_KEY", "sk-lf-test")

    import os as _os
    phoenix_exporter.auto_configure()

    header = _os.environ.get("OTEL_EXPORTER_OTLP_HEADERS", "")
    assert header.startswith("authorization=Basic ")
    # pk-lf-test:sk-lf-test -> cGstbGYtdGVzdDpzay1sZi10ZXN0
    assert "cGstbGYtdGVzdDpzay1sZi10ZXN0" in header


def test_auto_configure_case_insensitive(clean_env, fake_init_otel):
    """Stack value is normalised to lowercase."""
    clean_env.setenv("OCCP_OBSERVABILITY_STACK", "PHOENIX")

    phoenix_exporter.auto_configure()

    assert len(fake_init_otel) == 1
    assert fake_init_otel[0]["otlp_endpoint"] == "http://localhost:4318"


def test_auto_configure_swallows_init_otel_errors(
    clean_env, monkeypatch, caplog
):
    """If init_otel raises, auto_configure must log + return None (never raise)."""
    clean_env.setenv("OCCP_OBSERVABILITY_STACK", "phoenix")

    def _boom(**_kwargs):
        raise RuntimeError("simulated exporter failure")

    monkeypatch.setattr(phoenix_exporter, "init_otel", _boom)

    with caplog.at_level(logging.WARNING, logger="observability.phoenix_exporter"):
        result = phoenix_exporter.auto_configure()

    assert result is None
    assert any(
        "init_otel failed" in rec.message for rec in caplog.records
    )
