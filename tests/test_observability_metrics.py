"""Tests for observability.metrics_collector (L6 foundation)."""

from __future__ import annotations

import pytest

from observability import Counter, Gauge, Histogram, MetricsCollector, get_collector


class TestCounter:

    def test_inc_default(self):
        c = Counter(name="test.counter")
        c.inc()
        assert c.values[()] == 1.0

    def test_inc_with_labels(self):
        c = Counter(name="test.counter")
        c.inc(1, {"agent": "eng-core"})
        c.inc(2, {"agent": "eng-core"})
        c.inc(1, {"agent": "wp-web"})
        assert c.values[(("agent", "eng-core"),)] == 3.0
        assert c.values[(("agent", "wp-web"),)] == 1.0

    def test_counter_is_monotonic(self):
        c = Counter(name="test.counter")
        for i in range(100):
            c.inc()
        assert c.values[()] == 100


class TestGauge:

    def test_set_and_inc_dec(self):
        g = Gauge(name="test.gauge")
        g.set(10.0)
        assert g.values[()] == 10.0
        g.inc(5.0)
        assert g.values[()] == 15.0
        g.dec(3.0)
        assert g.values[()] == 12.0


class TestHistogram:

    def test_observe_populates_buckets(self):
        h = Histogram(name="test.hist")
        h.observe(15.0)  # > 10.0 bucket, ≤ 25.0
        h.observe(30.0)  # > 25.0 bucket, ≤ 50.0
        h.observe(100.0)  # ≤ 100.0

        counts = h.counts[()]
        # buckets (default ms): 5, 10, 25, 50, 100, 250, ...
        # 15 passes 25, 50, 100, 250...
        assert counts[2] == 1  # ≤ 25
        assert counts[3] == 2  # ≤ 50 (15 + 30)
        assert counts[4] == 3  # ≤ 100 (all 3)
        assert counts[-1] == 3  # +Inf

    def test_sum_and_count(self):
        h = Histogram(name="test.hist")
        h.observe(10.0)
        h.observe(20.0)
        h.observe(30.0)
        assert h.sums[()] == 60.0
        assert h.observations[()] == 3


class TestMetricsCollector:

    @pytest.fixture
    def coll(self):
        c = MetricsCollector()
        return c

    def test_counter_via_collector(self, coll):
        coll.counter("occp.test.counter", 1, {"label": "v1"})
        coll.counter("occp.test.counter", 2, {"label": "v1"})
        snap = coll.snapshot()
        assert "occp.test.counter" in snap["counters"]

    def test_time_histogram_context_manager(self, coll):
        import time
        with coll.time_histogram("occp.test.hist"):
            time.sleep(0.01)
        snap = coll.snapshot()
        assert "occp.test.hist" in snap["histograms"]
        series = snap["histograms"]["occp.test.hist"]["series"]
        assert len(series) == 1
        assert series[0]["count"] == 1
        assert series[0]["sum"] >= 10.0  # at least 10ms

    def test_render_prometheus_format(self, coll):
        coll.counter("occp.test.requests", 5, {"endpoint": "/health"})
        coll.histogram("occp.test.latency", 50.0, {"endpoint": "/health"})
        coll.gauge("occp.test.active", 3)

        text = coll.render_prometheus()
        assert "# HELP occp_uptime_seconds" in text
        assert "# TYPE occp_test_requests counter" in text
        assert 'occp_test_requests{endpoint="/health"}' in text
        assert "# TYPE occp_test_latency histogram" in text
        assert "occp_test_latency_bucket" in text
        assert "# TYPE occp_test_active gauge" in text

    def test_reset(self, coll):
        coll.counter("occp.test.counter", 1)
        coll.reset()
        snap = coll.snapshot()
        assert not snap["counters"]
        assert not snap["gauges"]
        assert not snap["histograms"]


class TestSingleton:

    def test_get_collector_returns_same_instance(self):
        c1 = get_collector()
        c2 = get_collector()
        assert c1 is c2
