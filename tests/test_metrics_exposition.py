"""Tests for the 6 Grafana-SLO metrics added to observability.metrics_collector.

Covers:
  - render_prometheus() emits HELP + TYPE lines for each SLO metric name
  - HTTP middleware increments occp_http_requests_total on real requests
  - BudgetPolicy.record_spend() increments occp_llm_cost_usd_total
  - KillSwitch.activate()/deactivate() toggles gauge + activations counter
  - Pipeline outcome=success emits occp_pipeline_runs_total{result="pass"}
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.middleware_metrics import MetricsMiddleware
from evaluation.kill_switch import (
    KillSwitch,
    KillSwitchTrigger,
)
from observability.metrics_collector import (
    HTTP_REQUESTS_TOTAL,
    HTTP_REQUEST_DURATION_SECONDS,
    KILL_SWITCH_ACTIVATIONS_TOTAL,
    KILL_SWITCH_ACTIVE,
    LLM_COST_USD_TOTAL,
    PIPELINE_RUNS_TOTAL,
    MetricsCollector,
    get_collector,
)
from policy_engine.budget_policy import BudgetPolicy, CacheBreakdown


@pytest.fixture(autouse=True)
def _fresh_collector(monkeypatch):
    """Each test gets a clean singleton collector."""
    import observability.metrics_collector as mc

    fresh = MetricsCollector()
    monkeypatch.setattr(mc, "_global_collector", fresh)
    yield fresh


# ────────────────────────────────────────────────────────────────
# 1. render_prometheus() exposes all 6 metric names + HELP + TYPE
# ────────────────────────────────────────────────────────────────


def test_render_prometheus_emits_all_slo_metrics():
    coll = get_collector()
    text = coll.render_prometheus()

    # All 6 required metric names must appear.
    required = [
        HTTP_REQUESTS_TOTAL,
        HTTP_REQUEST_DURATION_SECONDS,
        LLM_COST_USD_TOTAL,
        KILL_SWITCH_ACTIVE,
        KILL_SWITCH_ACTIVATIONS_TOTAL,
        PIPELINE_RUNS_TOTAL,
    ]
    for name in required:
        assert f"# HELP {name} " in text, f"missing HELP line for {name}"

    # TYPE lines with correct kinds.
    assert f"# TYPE {HTTP_REQUESTS_TOTAL} counter" in text
    assert f"# TYPE {HTTP_REQUEST_DURATION_SECONDS} histogram" in text
    assert f"# TYPE {LLM_COST_USD_TOTAL} counter" in text
    assert f"# TYPE {KILL_SWITCH_ACTIVE} gauge" in text
    assert f"# TYPE {KILL_SWITCH_ACTIVATIONS_TOTAL} counter" in text
    assert f"# TYPE {PIPELINE_RUNS_TOTAL} counter" in text


def test_http_histogram_has_required_buckets():
    coll = get_collector()
    coll.record_http_request(
        method="GET", path="/api/v1/status", status=200, duration_seconds=0.03
    )
    text = coll.render_prometheus()
    # Prometheus-standard buckets for seconds.
    for le in ("0.005", "0.01", "0.025", "0.05", "0.1", "0.25",
               "0.5", "1.0", "2.5", "5.0", "10.0", "+Inf"):
        assert f'le="{le}"' in text, f"missing bucket {le}"


# ────────────────────────────────────────────────────────────────
# 2. HTTP middleware increments the counter
# ────────────────────────────────────────────────────────────────


def test_http_middleware_increments_requests_total():
    app = FastAPI()
    app.add_middleware(MetricsMiddleware)

    @app.get("/ping")
    def ping() -> dict[str, str]:
        return {"ok": "yes"}

    client = TestClient(app)
    r = client.get("/ping")
    assert r.status_code == 200

    text = get_collector().render_prometheus()
    # Expect: occp_http_requests_total{method="GET",path="/ping",status="200"} 1.0
    pattern = re.compile(
        rf'{HTTP_REQUESTS_TOTAL}\{{[^}}]*method="GET"[^}}]*path="/ping"[^}}]*status="200"[^}}]*\}}\s+([0-9.]+)'
    )
    match = pattern.search(text)
    assert match is not None, f"no matching counter line in:\n{text}"
    assert float(match.group(1)) >= 1.0


def test_http_middleware_records_5xx_on_exception():
    app = FastAPI()
    app.add_middleware(MetricsMiddleware)

    @app.get("/boom")
    def boom() -> dict[str, str]:
        raise RuntimeError("kaboom")

    client = TestClient(app, raise_server_exceptions=False)
    client.get("/boom")

    text = get_collector().render_prometheus()
    # Must have a 500 entry even though the handler raised.
    assert 'status="500"' in text


# ────────────────────────────────────────────────────────────────
# 3. BudgetPolicy.record_spend → occp_llm_cost_usd_total
# ────────────────────────────────────────────────────────────────


def test_record_spend_emits_llm_cost():
    # Isolate: force a fresh in-memory backend (no redis ping).
    from policy_engine.budget_policy import _MemoryBackend

    policy = BudgetPolicy(default_budget_usd=100.0, redis_client=None)
    policy._backend = _MemoryBackend()
    policy._backend_name = "memory"

    # Drive ~$5 of spend through the sonnet pricing:
    #   sonnet output = $15 / 1M → 5 / 15 = 0.333M output tokens.
    policy.record_spend(
        "task-cost-1",
        model="sonnet",
        cache_breakdown=CacheBreakdown(
            input_tokens=0,
            output_tokens=334_000,  # $5.01
        ),
    )

    text = get_collector().render_prometheus()
    pattern = re.compile(
        rf'{LLM_COST_USD_TOTAL}\{{[^}}]*model_id="claude-sonnet-4-6"[^}}]*\}}\s+([0-9.]+)'
    )
    match = pattern.search(text)
    assert match is not None, f"llm cost counter missing:\n{text}"
    assert float(match.group(1)) >= 5.0


# ────────────────────────────────────────────────────────────────
# 4. KillSwitch activate/deactivate → gauge + counter
# ────────────────────────────────────────────────────────────────


def test_kill_switch_activate_sets_gauge_and_counter():
    ks = KillSwitch()
    ks.activate(
        trigger=KillSwitchTrigger.MANUAL,
        actor="test",
        reason="unit test",
    )

    text = get_collector().render_prometheus()
    # Gauge = 1.
    gauge_pat = re.compile(rf'^{KILL_SWITCH_ACTIVE}(?:\{{[^}}]*\}})?\s+1(?:\.0+)?$', re.M)
    assert gauge_pat.search(text), f"gauge not 1:\n{text}"
    # Activations counter incremented with labels.
    act_pat = re.compile(
        rf'{KILL_SWITCH_ACTIVATIONS_TOTAL}\{{[^}}]*actor="test"[^}}]*trigger="manual"[^}}]*\}}\s+([0-9.]+)'
    )
    match = act_pat.search(text)
    assert match is not None, f"activations counter missing:\n{text}"
    assert float(match.group(1)) >= 1.0

    # After deactivate, gauge drops to 0.
    ks.deactivate(actor="test", reason="clear")
    text2 = get_collector().render_prometheus()
    assert re.search(
        rf'^{KILL_SWITCH_ACTIVE}(?:\{{[^}}]*\}})?\s+0(?:\.0+)?$', text2, re.M
    ), f"gauge not 0 after deactivate:\n{text2}"


# ────────────────────────────────────────────────────────────────
# 5. Pipeline outcome PASS → occp_pipeline_runs_total{result="pass"}
# ────────────────────────────────────────────────────────────────


def test_pipeline_run_counter_pass():
    from orchestrator.pipeline import Pipeline

    # Map a fake outcome directly via _emit_metrics without running the
    # full pipeline (that would require a huge adapter set). We verify
    # the outcome→result label mapping + counter emission.
    class _FakeTask:
        id = "t-1"
        agent_type = "general"

    # Create a minimal pipeline-like shim that only reuses _emit_metrics.
    p = Pipeline.__new__(Pipeline)
    Pipeline._emit_metrics(
        p, _FakeTask(), "general", "success", {"plan": 0.01}
    )

    text = get_collector().render_prometheus()
    pat = re.compile(
        rf'{PIPELINE_RUNS_TOTAL}\{{[^}}]*result="pass"[^}}]*\}}\s+([0-9.]+)'
    )
    match = pat.search(text)
    assert match is not None, f"pipeline_runs_total result=pass missing:\n{text}"
    assert float(match.group(1)) >= 1.0


def test_pipeline_run_counter_outcome_mapping():
    from orchestrator.pipeline import Pipeline

    class _FakeTask:
        id = "t-2"
        agent_type = "general"

    p = Pipeline.__new__(Pipeline)
    for outcome, expected in [
        ("gate_rejected", "gated"),
        ("kill_switch", "halted"),
        ("budget_exceeded", "halted"),
        ("failed", "fail"),
    ]:
        Pipeline._emit_metrics(p, _FakeTask(), "general", outcome, {})

    text = get_collector().render_prometheus()
    for result in ("gated", "halted", "fail"):
        assert f'result="{result}"' in text, f"missing result={result}"
