"""Tests for cost-attribution enrichment on :class:`AuditStore`."""

from __future__ import annotations

import pytest

from policy_engine.models import AuditEntry
from store.audit_store import AuditStore
from store.database import Database


@pytest.fixture
async def db(tmp_path):
    d = Database(url=f"sqlite+aiosqlite:///{tmp_path}/enrich.db")
    await d.connect()
    yield d
    await d.close()


@pytest.fixture
async def audit_store(db) -> AuditStore:
    return AuditStore(db.session())


def _seal(entry: AuditEntry) -> AuditEntry:
    """Populate the hash chain for *entry* so the insert is valid."""
    entry.prev_hash = "0" * 64
    entry.hash = entry.compute_hash(entry.prev_hash)
    return entry


# ---------------------------------------------------------------------------
# Full usage payload
# ---------------------------------------------------------------------------


class TestRecordWithUsage:
    async def test_record_with_usage_fields_stores_correctly(
        self, audit_store: AuditStore
    ) -> None:
        entry = _seal(AuditEntry(
            actor="orchestrator",
            action="llm_call",
            task_id="task-abc",
            detail={"prompt": "classify this"},
            input_tokens=1_000,
            output_tokens=500,
            cache_read_input_tokens=200,
            cache_creation_input_tokens=100,
            ephemeral_5m_input_tokens=100,
            ephemeral_1h_input_tokens=0,
            model_id="claude-sonnet-4-6",
        ))
        await audit_store.append(entry)

        [stored] = await audit_store.list_all()
        assert stored.input_tokens == 1_000
        assert stored.output_tokens == 500
        assert stored.cache_read_input_tokens == 200
        assert stored.cache_creation_input_tokens == 100
        assert stored.ephemeral_5m_input_tokens == 100
        assert stored.ephemeral_1h_input_tokens == 0
        assert stored.model_id == "claude-sonnet-4-6"
        # Computed fields populated on insert
        assert stored.computed_usd is not None and stored.computed_usd > 0
        assert stored.cache_hit_ratio is not None
        # 200 cache read / (1000 + 200) input total
        assert stored.cache_hit_ratio == pytest.approx(200 / 1200, rel=1e-4)


# ---------------------------------------------------------------------------
# Backward compatibility
# ---------------------------------------------------------------------------


class TestBackwardCompat:
    async def test_null_usage_fields_ok_backward_compat(
        self, audit_store: AuditStore
    ) -> None:
        """Legacy callers that don't populate usage fields still work."""
        entry = _seal(AuditEntry(
            actor="system",
            action="policy_check",
            task_id="legacy-1",
            detail={"rule": "no_prod"},
        ))
        await audit_store.append(entry)

        [stored] = await audit_store.list_all()
        assert stored.input_tokens is None
        assert stored.output_tokens is None
        assert stored.cache_read_input_tokens is None
        assert stored.model_id is None
        assert stored.computed_usd is None
        assert stored.cache_hit_ratio is None
        # Original hash-chain still intact
        assert stored.hash == entry.hash
        assert stored.prev_hash == entry.prev_hash

    async def test_hash_chain_unchanged_by_usage_fields(
        self, audit_store: AuditStore
    ) -> None:
        """Adding usage fields to the dataclass must not alter compute_hash."""
        base = AuditEntry(actor="a", action="b", task_id="c")
        base.detail = {"x": 1}
        base.timestamp = base.timestamp  # freeze

        enriched = AuditEntry(actor="a", action="b", task_id="c",
                              input_tokens=1000, output_tokens=500,
                              model_id="claude-opus-4-7")
        enriched.id = base.id
        enriched.timestamp = base.timestamp
        enriched.detail = {"x": 1}

        h_base = base.compute_hash("0" * 64)
        h_enriched = enriched.compute_hash("0" * 64)
        assert h_base == h_enriched


# ---------------------------------------------------------------------------
# Auto-computed fields
# ---------------------------------------------------------------------------


class TestComputedFields:
    async def test_computed_usd_populated_on_insert(
        self, audit_store: AuditStore
    ) -> None:
        """Insert supplies model + tokens but not USD — store computes it."""
        entry = _seal(AuditEntry(
            actor="orchestrator",
            action="llm_call",
            task_id="task-usd",
            detail={},
            input_tokens=2_000,
            output_tokens=500,
            cache_read_input_tokens=1_800,
            cache_creation_input_tokens=0,
            model_id="claude-haiku-4-5",
        ))
        assert entry.computed_usd is None  # pre-insert
        await audit_store.append(entry)

        [stored] = await audit_store.list_all()
        # Haiku 4.5: (2000*1.0 + 500*5.0 + 1800*0.10) / 1e6 = $0.00468
        assert stored.computed_usd == pytest.approx(0.00468, rel=1e-4)

    async def test_unknown_model_yields_null_usd_but_stores_tokens(
        self, audit_store: AuditStore
    ) -> None:
        entry = _seal(AuditEntry(
            actor="orchestrator",
            action="llm_call",
            task_id="task-unk",
            detail={},
            input_tokens=1_000,
            output_tokens=500,
            model_id="some-future-model",
        ))
        await audit_store.append(entry)

        [stored] = await audit_store.list_all()
        assert stored.input_tokens == 1_000
        assert stored.model_id == "some-future-model"
        assert stored.computed_usd is None

    async def test_explicit_usd_not_overwritten(
        self, audit_store: AuditStore
    ) -> None:
        """Caller-provided computed_usd takes precedence (backfill scenario)."""
        entry = _seal(AuditEntry(
            actor="orchestrator",
            action="llm_call",
            task_id="task-explicit",
            detail={},
            input_tokens=1_000,
            output_tokens=500,
            model_id="claude-haiku-4-5",
            computed_usd=0.9999,
        ))
        await audit_store.append(entry)

        [stored] = await audit_store.list_all()
        assert stored.computed_usd == pytest.approx(0.9999)
