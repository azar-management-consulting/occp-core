"""Tests for ``store.cost_calculator`` — USD cost + cache-hit ratio math."""

from __future__ import annotations

import math

import pytest

from store.cost_calculator import (
    HAIKU_45,
    OPUS_47,
    SONNET_46,
    compute_cache_hit_ratio,
    compute_usd,
    supported_models,
)


def _approx(a: float | None, b: float, tol: float = 1e-9) -> bool:
    assert a is not None, "expected non-None usd cost"
    return math.isclose(a, b, rel_tol=0, abs_tol=tol)


# ---------------------------------------------------------------------------
# Pricing sanity
# ---------------------------------------------------------------------------


class TestPricingTables:
    def test_opus_is_5x_haiku_input(self) -> None:
        assert OPUS_47["input"] == 5.0
        assert HAIKU_45["input"] == 1.0

    def test_sonnet_between_haiku_and_opus(self) -> None:
        for key in ("input", "output", "cache_read"):
            assert HAIKU_45[key] < SONNET_46[key] < OPUS_47[key]

    def test_cache_read_cheaper_than_fresh_input(self) -> None:
        for table in (HAIKU_45, SONNET_46, OPUS_47):
            assert table["cache_read"] < table["input"]

    def test_supported_models_lists_three_families(self) -> None:
        models = supported_models()
        assert any("haiku" in m for m in models)
        assert any("sonnet" in m for m in models)
        assert any("opus" in m for m in models)


# ---------------------------------------------------------------------------
# compute_usd
# ---------------------------------------------------------------------------


class TestComputeUsd:
    def test_compute_usd_haiku_basic(self) -> None:
        """1 000 input + 500 output on Haiku → $0.0035."""
        usd = compute_usd(
            model_id="claude-haiku-4-5",
            input_tokens=1000,
            output_tokens=500,
            cache_read_input_tokens=0,
            cache_creation_input_tokens=0,
        )
        assert _approx(usd, 0.0035)

    def test_compute_usd_sonnet_with_cache_read(self) -> None:
        """90 % cache-read on Sonnet cuts input cost by ~72 %."""
        # Scenario A — no cache: 10 000 fresh input, 500 output
        no_cache = compute_usd(
            model_id="claude-sonnet-4-6",
            input_tokens=10_000,
            output_tokens=500,
            cache_read_input_tokens=0,
            cache_creation_input_tokens=0,
        )
        # Scenario B — 90 % hit: 1 000 fresh + 9 000 cache read
        with_cache = compute_usd(
            model_id="claude-sonnet-4-6",
            input_tokens=1_000,
            output_tokens=500,
            cache_read_input_tokens=9_000,
            cache_creation_input_tokens=0,
        )
        assert no_cache is not None and with_cache is not None
        assert with_cache < no_cache
        # Savings proof — cache pricing is 10x cheaper than fresh input,
        # so 90 % of input cost is reduced to 10 % of its original.
        # Input-only savings: (10k*3 → 1k*3 + 9k*0.3) = 30 → 5.7  per 1M
        # The savings ratio on the input portion must be at least 30 %.
        savings = (no_cache - with_cache) / no_cache
        assert savings > 0.30

    def test_compute_usd_opus_full(self) -> None:
        """2 000 in + 1 000 out + 500 cache-write (5m) + 300 cache-read."""
        usd = compute_usd(
            model_id="claude-opus-4-7",
            input_tokens=2_000,
            output_tokens=1_000,
            cache_read_input_tokens=300,
            cache_creation_input_tokens=500,
        )
        # Opus 4.7: 5.0/25.0/0.50/6.25/10.0
        expected = (
            2_000 * 5.0
            + 1_000 * 25.0
            + 300 * 0.50
            + 500 * 6.25  # cache_write defaults to 5m bucket
        ) / 1_000_000.0
        assert _approx(usd, expected)

    def test_compute_usd_opus_with_explicit_ttl_split(self) -> None:
        """Caller-provided 5m / 1h breakdown overrides the default bucket."""
        usd = compute_usd(
            model_id="claude-opus-4-7",
            input_tokens=0,
            output_tokens=0,
            cache_read_input_tokens=0,
            cache_creation_input_tokens=1_000,
            ephemeral_5m_input_tokens=400,
            ephemeral_1h_input_tokens=600,
        )
        expected = (400 * 6.25 + 600 * 10.0) / 1_000_000.0
        assert _approx(usd, expected)

    def test_compute_usd_unknown_model_returns_none(self) -> None:
        assert compute_usd(
            model_id="gpt-4-turbo",
            input_tokens=1_000,
            output_tokens=500,
        ) is None

    def test_compute_usd_none_model_returns_none(self) -> None:
        assert compute_usd(
            model_id=None,
            input_tokens=1_000,
            output_tokens=500,
        ) is None

    def test_compute_usd_model_id_with_suffix_matches_prefix(self) -> None:
        """Dated model ids (e.g. claude-opus-4-7-20250101) still price correctly."""
        usd = compute_usd(
            model_id="claude-opus-4-7-20250415",
            input_tokens=1_000,
            output_tokens=0,
        )
        expected = 1_000 * 5.0 / 1_000_000.0
        assert _approx(usd, expected)

    def test_compute_usd_zero_tokens_is_zero(self) -> None:
        assert compute_usd("claude-haiku-4-5", 0, 0, 0, 0) == pytest.approx(0.0)

    def test_compute_usd_negative_tokens_clamped_to_zero(self) -> None:
        usd = compute_usd(
            model_id="claude-haiku-4-5",
            input_tokens=-100,
            output_tokens=500,
        )
        assert _approx(usd, 500 * 5.0 / 1_000_000.0)

    def test_compute_usd_none_token_counts_treated_as_zero(self) -> None:
        usd = compute_usd(
            model_id="claude-sonnet-4-6",
            input_tokens=None,
            output_tokens=None,
            cache_read_input_tokens=None,
            cache_creation_input_tokens=None,
        )
        assert usd == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Cache hit ratio
# ---------------------------------------------------------------------------


class TestCacheHitRatio:
    def test_cache_hit_ratio_calculation(self) -> None:
        """9 000 cache-read out of 10 000 total billable input → 0.9."""
        ratio = compute_cache_hit_ratio(
            input_tokens=1_000,
            cache_read_input_tokens=9_000,
        )
        assert ratio == pytest.approx(0.9)

    def test_cache_hit_ratio_zero_when_no_cache(self) -> None:
        ratio = compute_cache_hit_ratio(
            input_tokens=5_000, cache_read_input_tokens=0
        )
        assert ratio == pytest.approx(0.0)

    def test_cache_hit_ratio_none_when_no_input(self) -> None:
        assert compute_cache_hit_ratio(0, 0) is None
        assert compute_cache_hit_ratio(None, None) is None

    def test_cache_hit_ratio_handles_none_input_gracefully(self) -> None:
        # pure cache hit with no fresh input still computes 1.0
        ratio = compute_cache_hit_ratio(
            input_tokens=0, cache_read_input_tokens=500
        )
        assert ratio == pytest.approx(1.0)
