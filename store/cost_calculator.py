"""Cost attribution helper — computes USD cost for Anthropic API usage.

Pricing is expressed in USD per 1 000 000 tokens.  Cache-related rates follow
Anthropic's prompt-caching tier pricing (5 minute / 1 hour ephemeral TTL).

This module is intentionally dependency-free so it can be used from the
audit store, the orchestrator, the dashboard and ad-hoc scripts alike.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Final

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pricing tables ($ per 1M tokens)
# ---------------------------------------------------------------------------

HAIKU_45: Final[dict[str, float]] = {
    "input": 1.0,
    "output": 5.0,
    "cache_read": 0.10,
    "cache_creation_5m": 1.25,
    "cache_creation_1h": 2.0,
}

SONNET_46: Final[dict[str, float]] = {
    "input": 3.0,
    "output": 15.0,
    "cache_read": 0.30,
    "cache_creation_5m": 3.75,
    "cache_creation_1h": 6.0,
}

OPUS_47: Final[dict[str, float]] = {
    "input": 5.0,
    "output": 25.0,
    "cache_read": 0.50,
    "cache_creation_5m": 6.25,
    "cache_creation_1h": 10.0,
}


# Model-id prefixes mapped to pricing tables.  Matching is performed by
# longest-prefix wins against the provided ``model_id``.
_MODEL_PRICING: Final[dict[str, dict[str, float]]] = {
    # Haiku family
    "claude-haiku-4-5": HAIKU_45,
    "claude-haiku-45": HAIKU_45,
    # Sonnet family
    "claude-sonnet-4-6": SONNET_46,
    "claude-sonnet-46": SONNET_46,
    # Opus family
    "claude-opus-4-7": OPUS_47,
    "claude-opus-47": OPUS_47,
}


_PER_MILLION: Final[float] = 1_000_000.0


@dataclass(frozen=True, slots=True)
class UsageBreakdown:
    """Structured usage payload from ``response.usage`` + computed USD."""

    model_id: str | None
    input_tokens: int
    output_tokens: int
    cache_read_input_tokens: int
    cache_creation_input_tokens: int
    ephemeral_5m_input_tokens: int
    ephemeral_1h_input_tokens: int
    computed_usd: float | None
    cache_hit_ratio: float | None


def _lookup_pricing(model_id: str) -> dict[str, float] | None:
    """Return the pricing row for *model_id* or ``None`` if unknown."""
    if not model_id:
        return None
    # Exact match first
    if model_id in _MODEL_PRICING:
        return _MODEL_PRICING[model_id]
    # Longest-prefix fallback (handles claude-opus-4-7-20250101 style suffixes)
    best_key: str | None = None
    for key in _MODEL_PRICING:
        if model_id.startswith(key) and (
            best_key is None or len(key) > len(best_key)
        ):
            best_key = key
    if best_key is None:
        return None
    return _MODEL_PRICING[best_key]


def compute_usd(
    model_id: str | None,
    input_tokens: int | None = 0,
    output_tokens: int | None = 0,
    cache_read_input_tokens: int | None = 0,
    cache_creation_input_tokens: int | None = 0,
    *,
    ephemeral_5m_input_tokens: int | None = None,
    ephemeral_1h_input_tokens: int | None = None,
) -> float | None:
    """Return the USD cost for a single Anthropic completion.

    ``cache_creation_input_tokens`` represents *writes* to the prompt cache.
    If the caller supplies the per-TTL split (``ephemeral_5m_input_tokens`` +
    ``ephemeral_1h_input_tokens``), those values are used directly; otherwise
    the entire write volume is charged at the 5-minute rate (cheaper and
    matches the Anthropic SDK default TTL).

    Returns ``None`` if *model_id* is unknown.  Missing token counts are
    treated as zero.
    """
    if model_id is None:
        logger.warning("compute_usd: model_id is None — returning None")
        return None

    pricing = _lookup_pricing(model_id)
    if pricing is None:
        logger.warning("compute_usd: unknown model_id=%r — returning None", model_id)
        return None

    in_tok = max(0, int(input_tokens or 0))
    out_tok = max(0, int(output_tokens or 0))
    cache_read = max(0, int(cache_read_input_tokens or 0))
    cache_write = max(0, int(cache_creation_input_tokens or 0))

    if ephemeral_5m_input_tokens is None and ephemeral_1h_input_tokens is None:
        write_5m = cache_write
        write_1h = 0
    else:
        write_5m = max(0, int(ephemeral_5m_input_tokens or 0))
        write_1h = max(0, int(ephemeral_1h_input_tokens or 0))
        # If caller provided both but they don't sum to the total, trust
        # the per-TTL split (authoritative from the API response).

    cost = (
        in_tok * pricing["input"]
        + out_tok * pricing["output"]
        + cache_read * pricing["cache_read"]
        + write_5m * pricing["cache_creation_5m"]
        + write_1h * pricing["cache_creation_1h"]
    ) / _PER_MILLION

    return round(cost, 8)


def compute_cache_hit_ratio(
    input_tokens: int | None,
    cache_read_input_tokens: int | None,
) -> float | None:
    """Return ``cache_read / (cache_read + input_tokens)`` or ``None``.

    The denominator is the total *billable* input (fresh input + cache reads);
    cache creation writes are excluded because they represent future savings,
    not current hits.  Returns ``None`` when there is no billable input.
    """
    in_tok = max(0, int(input_tokens or 0))
    cache_read = max(0, int(cache_read_input_tokens or 0))
    total = in_tok + cache_read
    if total == 0:
        return None
    return round(cache_read / total, 6)


def supported_models() -> list[str]:
    """Return the list of model ids with known pricing."""
    return sorted(_MODEL_PRICING.keys())
