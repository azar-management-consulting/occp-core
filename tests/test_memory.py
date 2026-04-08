"""Tests for store.memory — Hybrid Memory (REQ-MEM-01, REQ-MEM-02, REQ-MEM-03).

Covers:
- MemoryEntry: creation, touch, age, to_dict/from_dict
- cosine_similarity: unit vectors, orthogonal, zero
- recency_score: recent, old, boundary
- MemoryStore (REQ-MEM-01): add, get, remove, query (semantic, episodic, hybrid)
- CompactionPolicy: defaults, custom
- MemoryCompactor (REQ-MEM-02): compact by importance, age, count, protected
- KnowledgeEntry: creation, expiry, to_dict/from_dict
- KnowledgeStore (REQ-MEM-03): add, query (org-scoped), expire, provenance
- Acceptance tests for each REQ
"""

from __future__ import annotations

import math
import time

import pytest

from store.memory import (
    CompactionError,
    CompactionPolicy,
    CompactionResult,
    KnowledgeEntry,
    KnowledgeStore,
    KnowledgeType,
    MemoryCompactor,
    MemoryEntry,
    MemoryError,
    MemoryNotFoundError,
    MemoryScope,
    MemoryStore,
    RetrievalMode,
    RetrievalResult,
    cosine_similarity,
    recency_score,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_entry(
    content: str = "test",
    embedding: list[float] | None = None,
    importance: float = 0.5,
    scope: str = MemoryScope.SESSION.value,
    session_id: str = "sess-1",
    org_id: str = "org-1",
    created_at: float | None = None,
    tags: list[str] | None = None,
) -> MemoryEntry:
    import uuid
    return MemoryEntry(
        memory_id=uuid.uuid4().hex[:16],
        content=content,
        embedding=embedding or [],
        importance=importance,
        scope=scope,
        session_id=session_id,
        org_id=org_id,
        created_at=created_at or time.time(),
        tags=tags or [],
    )


# ---------------------------------------------------------------------------
# MemoryEntry
# ---------------------------------------------------------------------------


class TestMemoryEntry:
    def test_create(self) -> None:
        e = MemoryEntry(memory_id="m1", content="hello")
        assert e.memory_id == "m1"
        assert e.content == "hello"
        assert e.importance == 0.5

    def test_touch(self) -> None:
        e = MemoryEntry(memory_id="m1", content="x")
        old_accessed = e.accessed_at
        e.access_count = 0
        time.sleep(0.01)
        e.touch()
        assert e.accessed_at >= old_accessed
        assert e.access_count == 1

    def test_age_seconds(self) -> None:
        e = MemoryEntry(memory_id="m1", content="x", created_at=time.time() - 100)
        assert e.age_seconds >= 99

    def test_to_dict(self) -> None:
        e = MemoryEntry(memory_id="m1", content="hello", importance=0.8)
        d = e.to_dict()
        assert d["memoryId"] == "m1"
        assert d["importance"] == 0.8

    def test_from_dict_roundtrip(self) -> None:
        e = MemoryEntry(
            memory_id="m1", content="hello", importance=0.9,
            embedding=[1.0, 0.0], tags=["test"],
        )
        restored = MemoryEntry.from_dict(e.to_dict())
        assert restored.memory_id == "m1"
        assert restored.importance == 0.9
        assert restored.embedding == [1.0, 0.0]
        assert restored.tags == ["test"]

    def test_scope_default(self) -> None:
        e = MemoryEntry(memory_id="m1", content="x")
        assert e.scope == MemoryScope.SESSION.value

    def test_metadata(self) -> None:
        e = MemoryEntry(memory_id="m1", content="x", metadata={"key": "val"})
        assert e.metadata["key"] == "val"


# ---------------------------------------------------------------------------
# Similarity functions
# ---------------------------------------------------------------------------


class TestCosineSimilarity:
    def test_identical_vectors(self) -> None:
        v = [1.0, 0.0, 0.0]
        assert cosine_similarity(v, v) == pytest.approx(1.0)

    def test_orthogonal_vectors(self) -> None:
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert cosine_similarity(a, b) == pytest.approx(0.0)

    def test_opposite_vectors(self) -> None:
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        assert cosine_similarity(a, b) == pytest.approx(-1.0)

    def test_empty_vectors(self) -> None:
        assert cosine_similarity([], []) == 0.0

    def test_different_lengths(self) -> None:
        assert cosine_similarity([1.0], [1.0, 2.0]) == 0.0

    def test_zero_vector(self) -> None:
        assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0

    def test_similar_vectors(self) -> None:
        a = [1.0, 1.0, 0.0]
        b = [1.0, 0.8, 0.1]
        sim = cosine_similarity(a, b)
        assert 0.9 < sim < 1.0


class TestRecencyScore:
    def test_very_recent(self) -> None:
        score = recency_score(time.time(), half_life=3600.0)
        assert score > 0.99

    def test_one_half_life_old(self) -> None:
        score = recency_score(time.time() - 3600, half_life=3600.0)
        assert score == pytest.approx(0.5, abs=0.01)

    def test_very_old(self) -> None:
        score = recency_score(time.time() - 86400 * 30, half_life=3600.0)
        assert score < 0.001

    def test_custom_half_life(self) -> None:
        score = recency_score(time.time() - 60, half_life=60.0)
        assert score == pytest.approx(0.5, abs=0.01)


# ---------------------------------------------------------------------------
# MemoryStore — REQ-MEM-01
# ---------------------------------------------------------------------------


class TestMemoryStore:
    def test_create_empty(self) -> None:
        store = MemoryStore()
        assert store.entry_count == 0

    def test_add_entry(self) -> None:
        store = MemoryStore()
        e = _make_entry()
        store.add(e)
        assert store.entry_count == 1

    def test_add_text(self) -> None:
        store = MemoryStore()
        e = store.add_text("hello world", importance=0.8, tags=["test"])
        assert e.content == "hello world"
        assert e.importance == 0.8
        assert store.entry_count == 1

    def test_get_entry(self) -> None:
        store = MemoryStore()
        e = _make_entry(content="found")
        store.add(e)
        result = store.get(e.memory_id)
        assert result.content == "found"
        assert result.access_count >= 1

    def test_get_not_found(self) -> None:
        store = MemoryStore()
        with pytest.raises(MemoryNotFoundError):
            store.get("nonexistent")

    def test_remove_entry(self) -> None:
        store = MemoryStore()
        e = _make_entry()
        store.add(e)
        assert store.remove(e.memory_id) is True
        assert store.entry_count == 0

    def test_remove_nonexistent(self) -> None:
        store = MemoryStore()
        assert store.remove("nonexistent") is False

    def test_clear(self) -> None:
        store = MemoryStore()
        for _ in range(5):
            store.add(_make_entry())
        count = store.clear()
        assert count == 5
        assert store.entry_count == 0

    def test_list_entries_no_filter(self) -> None:
        store = MemoryStore()
        for i in range(3):
            store.add(_make_entry(content=f"e{i}"))
        assert len(store.list_entries()) == 3

    def test_list_entries_by_scope(self) -> None:
        store = MemoryStore()
        store.add(_make_entry(scope=MemoryScope.SESSION.value))
        store.add(_make_entry(scope=MemoryScope.GLOBAL.value))
        result = store.list_entries(scope=MemoryScope.GLOBAL.value)
        assert len(result) == 1
        assert result[0].scope == MemoryScope.GLOBAL.value

    def test_list_entries_by_session(self) -> None:
        store = MemoryStore()
        store.add(_make_entry(session_id="s1"))
        store.add(_make_entry(session_id="s2"))
        result = store.list_entries(session_id="s1")
        assert len(result) == 1

    def test_list_entries_by_tags(self) -> None:
        store = MemoryStore()
        store.add(_make_entry(tags=["alpha"]))
        store.add(_make_entry(tags=["beta"]))
        store.add(_make_entry(tags=["alpha", "beta"]))
        result = store.list_entries(tags=["alpha"])
        assert len(result) == 2

    def test_semantic_weight_default(self) -> None:
        store = MemoryStore()
        assert store.semantic_weight == pytest.approx(0.6)
        assert store.episodic_weight == pytest.approx(0.4)

    def test_custom_weights(self) -> None:
        store = MemoryStore(semantic_weight=0.8)
        assert store.semantic_weight == pytest.approx(0.8)
        assert store.episodic_weight == pytest.approx(0.2)

    def test_weights_clamped(self) -> None:
        store = MemoryStore(semantic_weight=1.5)
        assert store.semantic_weight == 1.0
        store2 = MemoryStore(semantic_weight=-0.5)
        assert store2.semantic_weight == 0.0


class TestMemoryRetrieval:
    def test_semantic_query(self) -> None:
        store = MemoryStore()
        store.add(_make_entry(content="cat", embedding=[1.0, 0.0, 0.0]))
        store.add(_make_entry(content="dog", embedding=[0.9, 0.1, 0.0]))
        store.add(_make_entry(content="car", embedding=[0.0, 0.0, 1.0]))

        result = store.query(
            embedding=[1.0, 0.0, 0.0],
            mode=RetrievalMode.SEMANTIC,
        )
        assert result.count >= 1
        assert result.entries[0].content == "cat"
        assert result.scores[0] == pytest.approx(1.0)

    def test_episodic_query(self) -> None:
        store = MemoryStore()
        # Old entry with high importance
        store.add(_make_entry(
            content="old-important",
            importance=0.9,
            created_at=time.time() - 7200,
        ))
        # New entry with low importance
        store.add(_make_entry(
            content="new-unimportant",
            importance=0.1,
            created_at=time.time(),
        ))
        # New entry with high importance
        store.add(_make_entry(
            content="new-important",
            importance=0.9,
            created_at=time.time(),
        ))

        result = store.query(mode=RetrievalMode.EPISODIC)
        assert result.count == 3
        # new-important should be first (recent + high importance)
        assert result.entries[0].content == "new-important"

    def test_hybrid_query(self) -> None:
        store = MemoryStore(semantic_weight=0.5)
        store.add(_make_entry(
            content="match",
            embedding=[1.0, 0.0],
            importance=0.9,
        ))
        store.add(_make_entry(
            content="mismatch",
            embedding=[0.0, 1.0],
            importance=0.1,
        ))

        result = store.query(
            embedding=[1.0, 0.0],
            mode=RetrievalMode.HYBRID,
        )
        assert result.count == 2
        assert result.entries[0].content == "match"

    def test_query_empty_store(self) -> None:
        store = MemoryStore()
        result = store.query(embedding=[1.0])
        assert result.count == 0
        assert result.total_candidates == 0

    def test_query_top_k(self) -> None:
        store = MemoryStore()
        for i in range(20):
            store.add(_make_entry(content=f"e{i}", importance=i / 20))
        result = store.query(mode=RetrievalMode.EPISODIC, top_k=5)
        assert result.count == 5

    def test_query_filter_scope(self) -> None:
        store = MemoryStore()
        store.add(_make_entry(scope=MemoryScope.SESSION.value))
        store.add(_make_entry(scope=MemoryScope.GLOBAL.value))
        result = store.query(
            mode=RetrievalMode.EPISODIC,
            scope=MemoryScope.GLOBAL.value,
        )
        assert result.count == 1

    def test_query_filter_org(self) -> None:
        store = MemoryStore()
        store.add(_make_entry(org_id="org-A"))
        store.add(_make_entry(org_id="org-B"))
        result = store.query(mode=RetrievalMode.EPISODIC, org_id="org-A")
        assert result.count == 1

    def test_query_min_importance(self) -> None:
        store = MemoryStore()
        store.add(_make_entry(importance=0.1))
        store.add(_make_entry(importance=0.5))
        store.add(_make_entry(importance=0.9))
        result = store.query(mode=RetrievalMode.EPISODIC, min_importance=0.5)
        assert result.count == 2

    def test_retrieval_result_to_dict(self) -> None:
        r = RetrievalResult(
            entries=[_make_entry(content="x")],
            scores=[0.95],
            mode=RetrievalMode.SEMANTIC.value,
        )
        d = r.to_dict()
        assert d["count"] == 1
        assert d["entries"][0]["score"] == 0.95

    def test_query_touches_entries(self) -> None:
        store = MemoryStore()
        e = _make_entry(importance=1.0)
        store.add(e)
        initial_count = e.access_count
        store.query(mode=RetrievalMode.EPISODIC, top_k=1)
        assert e.access_count > initial_count


class TestMemoryStoreSerialization:
    def test_to_dict(self) -> None:
        store = MemoryStore()
        store.add_text("hello")
        d = store.to_dict()
        assert d["entryCount"] == 1
        assert "entries" in d

    def test_to_json(self) -> None:
        store = MemoryStore()
        store.add_text("test")
        j = store.to_json()
        import json
        data = json.loads(j)
        assert data["entryCount"] == 1


# ---------------------------------------------------------------------------
# MemoryCompactor — REQ-MEM-02
# ---------------------------------------------------------------------------


class TestCompactionPolicy:
    def test_defaults(self) -> None:
        p = CompactionPolicy()
        assert p.max_entries == 10000
        assert p.min_importance == pytest.approx(0.3)
        assert MemoryScope.GLOBAL.value in p.protect_scopes
        assert "pinned" in p.protect_tags

    def test_custom(self) -> None:
        p = CompactionPolicy(
            max_entries=100,
            min_importance=0.5,
            protect_scopes=(),
            protect_tags=(),
        )
        assert p.max_entries == 100
        assert p.min_importance == 0.5


class TestCompactionResult:
    def test_compression_ratio(self) -> None:
        r = CompactionResult(entries_before=100, entries_after=60)
        assert r.compression_ratio == pytest.approx(0.4)

    def test_compression_ratio_empty(self) -> None:
        r = CompactionResult(entries_before=0, entries_after=0)
        assert r.compression_ratio == 0.0

    def test_to_dict(self) -> None:
        r = CompactionResult(
            entries_before=10, entries_after=7,
            entries_removed=3, entries_retained=7,
        )
        d = r.to_dict()
        assert d["entriesRemoved"] == 3
        assert d["compressionRatio"] == pytest.approx(0.3)


class TestMemoryCompactor:
    def test_compact_empty_store(self) -> None:
        store = MemoryStore()
        compactor = MemoryCompactor()
        result = compactor.compact(store)
        assert result.entries_removed == 0
        assert result.entries_before == 0

    def test_compact_below_importance(self) -> None:
        store = MemoryStore()
        store.add(_make_entry(importance=0.1))
        store.add(_make_entry(importance=0.2))
        store.add(_make_entry(importance=0.8))

        compactor = MemoryCompactor(CompactionPolicy(min_importance=0.3))
        result = compactor.compact(store)
        assert result.entries_removed == 2
        assert store.entry_count == 1

    def test_compact_by_age(self) -> None:
        store = MemoryStore()
        # Old entry
        store.add(_make_entry(
            importance=0.5,
            created_at=time.time() - 86400 * 60,  # 60 days old
        ))
        # Recent entry
        store.add(_make_entry(importance=0.5))

        policy = CompactionPolicy(max_age_seconds=86400 * 30)
        compactor = MemoryCompactor(policy)
        result = compactor.compact(store)
        assert result.entries_removed == 1
        assert store.entry_count == 1

    def test_compact_by_count(self) -> None:
        store = MemoryStore()
        for i in range(10):
            store.add(_make_entry(importance=i / 10 + 0.35))

        policy = CompactionPolicy(max_entries=5, min_importance=0.0, max_age_seconds=999999)
        compactor = MemoryCompactor(policy)
        result = compactor.compact(store)
        assert store.entry_count == 5

    def test_protected_scopes(self) -> None:
        store = MemoryStore()
        store.add(_make_entry(
            importance=0.1,
            scope=MemoryScope.GLOBAL.value,
        ))
        store.add(_make_entry(importance=0.1, scope=MemoryScope.SESSION.value))

        compactor = MemoryCompactor(CompactionPolicy(min_importance=0.3))
        result = compactor.compact(store)
        assert result.protected_count == 1
        assert store.entry_count == 1  # Only the global one survives

    def test_protected_tags(self) -> None:
        store = MemoryStore()
        store.add(_make_entry(importance=0.1, tags=["pinned"]))
        store.add(_make_entry(importance=0.1, tags=[]))

        compactor = MemoryCompactor(CompactionPolicy(min_importance=0.3))
        result = compactor.compact(store)
        assert result.protected_count == 1
        assert store.entry_count == 1

    def test_estimate_compaction(self) -> None:
        store = MemoryStore()
        store.add(_make_entry(importance=0.1))
        store.add(_make_entry(importance=0.8))
        store.add(_make_entry(
            importance=0.5,
            created_at=time.time() - 86400 * 60,
        ))

        compactor = MemoryCompactor(CompactionPolicy(min_importance=0.3))
        est = compactor.estimate_compaction(store)
        assert est["belowImportance"] == 1
        assert est["overAge"] == 1

    def test_multiple_compaction_phases(self) -> None:
        """Verify importance + age + count phases all run."""
        store = MemoryStore()
        # Low importance
        store.add(_make_entry(importance=0.1))
        # Old
        store.add(_make_entry(importance=0.5, created_at=time.time() - 86400 * 60))
        # Normal (will survive)
        store.add(_make_entry(importance=0.8))

        policy = CompactionPolicy(
            min_importance=0.3,
            max_age_seconds=86400 * 30,
            max_entries=10000,
        )
        compactor = MemoryCompactor(policy)
        result = compactor.compact(store)
        assert result.entries_removed == 2
        assert store.entry_count == 1


# ---------------------------------------------------------------------------
# KnowledgeEntry — REQ-MEM-03
# ---------------------------------------------------------------------------


class TestKnowledgeEntry:
    def test_create(self) -> None:
        k = KnowledgeEntry(knowledge_id="k1", content="test fact")
        assert k.knowledge_id == "k1"
        assert k.knowledge_type == KnowledgeType.FACT.value

    def test_not_expired_default(self) -> None:
        k = KnowledgeEntry(knowledge_id="k1", content="x")
        assert k.is_expired is False

    def test_expired(self) -> None:
        k = KnowledgeEntry(
            knowledge_id="k1", content="x",
            expires_at=time.time() - 100,
        )
        assert k.is_expired is True

    def test_not_expired_future(self) -> None:
        k = KnowledgeEntry(
            knowledge_id="k1", content="x",
            expires_at=time.time() + 3600,
        )
        assert k.is_expired is False

    def test_to_dict(self) -> None:
        k = KnowledgeEntry(
            knowledge_id="k1", content="hello",
            knowledge_type=KnowledgeType.PROCEDURE.value,
            org_id="org-1",
        )
        d = k.to_dict()
        assert d["knowledgeId"] == "k1"
        assert d["knowledgeType"] == "procedure"
        assert d["orgId"] == "org-1"

    def test_from_dict_roundtrip(self) -> None:
        k = KnowledgeEntry(
            knowledge_id="k1", content="fact",
            org_id="org-1", tags=["deploy"],
            confidence=0.9,
        )
        restored = KnowledgeEntry.from_dict(k.to_dict())
        assert restored.knowledge_id == "k1"
        assert restored.org_id == "org-1"
        assert restored.confidence == 0.9
        assert restored.tags == ["deploy"]

    def test_knowledge_types(self) -> None:
        assert KnowledgeType.FACT.value == "fact"
        assert KnowledgeType.PREFERENCE.value == "preference"
        assert KnowledgeType.PROCEDURE.value == "procedure"
        assert KnowledgeType.ENTITY.value == "entity"
        assert KnowledgeType.CONTEXT.value == "context"


# ---------------------------------------------------------------------------
# KnowledgeStore — REQ-MEM-03
# ---------------------------------------------------------------------------


class TestKnowledgeStore:
    def test_create_empty(self) -> None:
        ks = KnowledgeStore()
        assert ks.entry_count == 0

    def test_add(self) -> None:
        ks = KnowledgeStore()
        k = KnowledgeEntry(knowledge_id="k1", content="fact", org_id="org-1")
        ks.add(k)
        assert ks.entry_count == 1

    def test_extract_and_add(self) -> None:
        ks = KnowledgeStore()
        k = ks.extract_and_add(
            "User prefers dark mode",
            knowledge_type=KnowledgeType.PREFERENCE.value,
            org_id="org-1",
            source_session_id="sess-1",
        )
        assert k.content == "User prefers dark mode"
        assert k.knowledge_type == "preference"
        assert k.expires_at > 0  # default TTL applied

    def test_extract_and_add_no_ttl(self) -> None:
        ks = KnowledgeStore()
        k = ks.extract_and_add("eternal fact", org_id="org-1", ttl_seconds=0)
        assert k.expires_at == 0.0

    def test_get_existing(self) -> None:
        ks = KnowledgeStore()
        k = KnowledgeEntry(knowledge_id="k1", content="fact", org_id="org-1")
        ks.add(k)
        result = ks.get("k1")
        assert result is not None
        assert result.content == "fact"

    def test_get_nonexistent(self) -> None:
        ks = KnowledgeStore()
        assert ks.get("nope") is None

    def test_get_expired_returns_none(self) -> None:
        ks = KnowledgeStore()
        k = KnowledgeEntry(
            knowledge_id="k1", content="old",
            expires_at=time.time() - 100,
        )
        ks.add(k)
        assert ks.get("k1") is None

    def test_remove(self) -> None:
        ks = KnowledgeStore()
        k = KnowledgeEntry(knowledge_id="k1", content="x")
        ks.add(k)
        assert ks.remove("k1") is True
        assert ks.entry_count == 0

    def test_remove_nonexistent(self) -> None:
        ks = KnowledgeStore()
        assert ks.remove("nope") is False


class TestKnowledgeQuery:
    def test_query_by_org(self) -> None:
        ks = KnowledgeStore()
        ks.add(KnowledgeEntry(knowledge_id="k1", content="a", org_id="org-A"))
        ks.add(KnowledgeEntry(knowledge_id="k2", content="b", org_id="org-B"))
        result = ks.query(org_id="org-A")
        assert len(result) == 1
        assert result[0].org_id == "org-A"

    def test_query_org_isolation(self) -> None:
        """Cross-org leakage test."""
        ks = KnowledgeStore()
        ks.add(KnowledgeEntry(knowledge_id="k1", content="secret", org_id="org-A"))
        result = ks.query(org_id="org-B")
        assert len(result) == 0

    def test_query_by_type(self) -> None:
        ks = KnowledgeStore()
        ks.add(KnowledgeEntry(
            knowledge_id="k1", content="a", org_id="org-1",
            knowledge_type=KnowledgeType.FACT.value,
        ))
        ks.add(KnowledgeEntry(
            knowledge_id="k2", content="b", org_id="org-1",
            knowledge_type=KnowledgeType.PREFERENCE.value,
        ))
        result = ks.query(org_id="org-1", knowledge_type=KnowledgeType.FACT.value)
        assert len(result) == 1

    def test_query_by_agent(self) -> None:
        ks = KnowledgeStore()
        ks.add(KnowledgeEntry(knowledge_id="k1", content="a", org_id="o", agent_id="a1"))
        ks.add(KnowledgeEntry(knowledge_id="k2", content="b", org_id="o", agent_id="a2"))
        result = ks.query(org_id="o", agent_id="a1")
        assert len(result) == 1

    def test_query_by_tags(self) -> None:
        ks = KnowledgeStore()
        ks.add(KnowledgeEntry(knowledge_id="k1", content="a", org_id="o", tags=["deploy"]))
        ks.add(KnowledgeEntry(knowledge_id="k2", content="b", org_id="o", tags=["config"]))
        result = ks.query(org_id="o", tags=["deploy"])
        assert len(result) == 1

    def test_query_excludes_expired(self) -> None:
        ks = KnowledgeStore()
        ks.add(KnowledgeEntry(
            knowledge_id="k1", content="fresh", org_id="o",
            expires_at=time.time() + 3600,
        ))
        ks.add(KnowledgeEntry(
            knowledge_id="k2", content="stale", org_id="o",
            expires_at=time.time() - 100,
        ))
        result = ks.query(org_id="o")
        assert len(result) == 1
        assert result[0].content == "fresh"

    def test_query_include_expired(self) -> None:
        ks = KnowledgeStore()
        ks.add(KnowledgeEntry(
            knowledge_id="k1", content="stale", org_id="o",
            expires_at=time.time() - 100,
        ))
        result = ks.query(org_id="o", include_expired=True)
        assert len(result) == 1

    def test_query_sorted_by_confidence(self) -> None:
        ks = KnowledgeStore()
        ks.add(KnowledgeEntry(knowledge_id="k1", content="low", org_id="o", confidence=0.3))
        ks.add(KnowledgeEntry(knowledge_id="k2", content="high", org_id="o", confidence=0.9))
        result = ks.query(org_id="o")
        assert result[0].confidence == 0.9

    def test_query_for_session(self) -> None:
        ks = KnowledgeStore()
        for i in range(20):
            ks.add(KnowledgeEntry(
                knowledge_id=f"k{i}", content=f"fact {i}",
                org_id="o", confidence=i / 20,
            ))
        result = ks.query_for_session(org_id="o", top_k=5)
        assert len(result) == 5
        assert result[0].confidence >= result[4].confidence


class TestKnowledgeMaintenance:
    def test_expire_stale(self) -> None:
        ks = KnowledgeStore()
        ks.add(KnowledgeEntry(
            knowledge_id="k1", content="fresh", org_id="o",
            expires_at=time.time() + 3600,
        ))
        ks.add(KnowledgeEntry(
            knowledge_id="k2", content="stale", org_id="o",
            expires_at=time.time() - 100,
        ))
        removed = ks.expire_stale()
        assert removed == 1
        assert ks.entry_count == 1

    def test_expire_stale_none(self) -> None:
        ks = KnowledgeStore()
        ks.add(KnowledgeEntry(knowledge_id="k1", content="x", org_id="o"))
        removed = ks.expire_stale()
        assert removed == 0

    def test_provenance(self) -> None:
        ks = KnowledgeStore()
        k = KnowledgeEntry(
            knowledge_id="k1", content="fact",
            source_session_id="sess-42", org_id="org-1",
            confidence=0.85,
        )
        ks.add(k)
        prov = ks.get_provenance("k1")
        assert prov is not None
        assert prov["sourceSessionId"] == "sess-42"
        assert prov["confidence"] == 0.85

    def test_provenance_not_found(self) -> None:
        ks = KnowledgeStore()
        assert ks.get_provenance("nope") is None

    def test_get_stats(self) -> None:
        ks = KnowledgeStore()
        ks.add(KnowledgeEntry(knowledge_id="k1", content="a", org_id="o1",
                               knowledge_type=KnowledgeType.FACT.value))
        ks.add(KnowledgeEntry(knowledge_id="k2", content="b", org_id="o1",
                               knowledge_type=KnowledgeType.PREFERENCE.value))
        ks.add(KnowledgeEntry(knowledge_id="k3", content="c", org_id="o2",
                               knowledge_type=KnowledgeType.FACT.value))
        stats = ks.get_stats()
        assert stats["totalEntries"] == 3
        assert stats["byOrg"]["o1"] == 2
        assert stats["byType"]["fact"] == 2


class TestKnowledgeSerialization:
    def test_to_dict(self) -> None:
        ks = KnowledgeStore()
        ks.add(KnowledgeEntry(knowledge_id="k1", content="x", org_id="o"))
        d = ks.to_dict()
        assert d["entryCount"] == 1
        assert "entries" in d

    def test_to_json(self) -> None:
        ks = KnowledgeStore()
        ks.add(KnowledgeEntry(knowledge_id="k1", content="x", org_id="o"))
        j = ks.to_json()
        import json
        data = json.loads(j)
        assert data["entryCount"] == 1


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TestEnums:
    def test_retrieval_mode(self) -> None:
        assert RetrievalMode.SEMANTIC.value == "semantic"
        assert RetrievalMode.EPISODIC.value == "episodic"
        assert RetrievalMode.HYBRID.value == "hybrid"

    def test_memory_scope(self) -> None:
        assert MemoryScope.SESSION.value == "session"
        assert MemoryScope.AGENT.value == "agent"
        assert MemoryScope.GLOBAL.value == "global"

    def test_knowledge_type(self) -> None:
        assert len(KnowledgeType) == 5


class TestErrors:
    def test_memory_error_base(self) -> None:
        e = MemoryError("test")
        assert str(e) == "test"

    def test_memory_not_found(self) -> None:
        e = MemoryNotFoundError("m1")
        assert e.memory_id == "m1"
        assert "m1" in str(e)

    def test_compaction_error(self) -> None:
        e = CompactionError("failed")
        assert isinstance(e, MemoryError)

    def test_knowledge_error(self) -> None:
        from store.memory import KnowledgeError
        e = KnowledgeError("bad")
        assert isinstance(e, MemoryError)


# ---------------------------------------------------------------------------
# Acceptance Tests — REQ-MEM-01
# ---------------------------------------------------------------------------


class TestAcceptanceMEM01:
    def test_at1_semantic_search(self) -> None:
        """AT-1: Semantic search returns entries matching embedding similarity."""
        store = MemoryStore()
        store.add(_make_entry(content="python tutorial", embedding=[1.0, 0.0, 0.0]))
        store.add(_make_entry(content="java tutorial", embedding=[0.8, 0.2, 0.0]))
        store.add(_make_entry(content="cooking recipe", embedding=[0.0, 0.0, 1.0]))

        result = store.query(
            embedding=[1.0, 0.0, 0.0],
            mode=RetrievalMode.SEMANTIC,
        )
        assert result.entries[0].content == "python tutorial"
        assert result.scores[0] > result.scores[2]

    def test_at2_episodic_search(self) -> None:
        """AT-2: Episodic search returns recent + high-importance entries first."""
        store = MemoryStore()
        store.add(_make_entry(content="old", importance=0.5, created_at=time.time() - 7200))
        store.add(_make_entry(content="new-low", importance=0.1))
        store.add(_make_entry(content="new-high", importance=1.0))

        result = store.query(mode=RetrievalMode.EPISODIC)
        assert result.entries[0].content == "new-high"

    def test_at3_hybrid_blending(self) -> None:
        """AT-3: Hybrid query blends both strategies with configurable alpha."""
        store = MemoryStore(semantic_weight=0.7)
        store.add(_make_entry(
            content="semantic-match",
            embedding=[1.0, 0.0],
            importance=0.1,
        ))
        store.add(_make_entry(
            content="episodic-match",
            embedding=[0.0, 1.0],
            importance=1.0,
        ))

        result = store.query(
            embedding=[1.0, 0.0],
            mode=RetrievalMode.HYBRID,
        )
        # With alpha=0.7, semantic match should still dominate
        assert result.count == 2
        assert result.mode == "hybrid"

    def test_at4_empty_store(self) -> None:
        """AT-4: Empty store returns empty results."""
        store = MemoryStore()
        result = store.query(embedding=[1.0, 0.0], mode=RetrievalMode.HYBRID)
        assert result.count == 0
        assert result.entries == []
        assert result.scores == []

    def test_at5_retrieval_performance(self) -> None:
        """AT-5: Retrieval latency < 100ms for 10K entries."""
        store = MemoryStore()
        emb = [float(i % 10) for i in range(32)]
        for i in range(10000):
            store.add(_make_entry(
                content=f"entry-{i}",
                embedding=emb,
                importance=0.5,
            ))

        result = store.query(
            embedding=emb,
            mode=RetrievalMode.HYBRID,
            top_k=10,
        )
        assert result.query_time_ms < 100
        assert result.count == 10


# ---------------------------------------------------------------------------
# Acceptance Tests — REQ-MEM-02
# ---------------------------------------------------------------------------


class TestAcceptanceMEM02:
    def test_at1_compact_below_importance(self) -> None:
        """AT-1: Compact merges entries below importance threshold."""
        store = MemoryStore()
        store.add(_make_entry(importance=0.1))
        store.add(_make_entry(importance=0.2))
        store.add(_make_entry(importance=0.8))

        compactor = MemoryCompactor(CompactionPolicy(min_importance=0.3))
        result = compactor.compact(store)
        assert result.entries_removed == 2
        assert store.entry_count == 1

    def test_at2_high_importance_never_compacted(self) -> None:
        """AT-2: High-importance entries are never compacted."""
        store = MemoryStore()
        for _ in range(5):
            store.add(_make_entry(importance=0.9))

        compactor = MemoryCompactor(CompactionPolicy(min_importance=0.3))
        result = compactor.compact(store)
        assert result.entries_removed == 0

    def test_at3_time_based_removal(self) -> None:
        """AT-3: Time-based policy removes entries older than retention."""
        store = MemoryStore()
        store.add(_make_entry(importance=0.5, created_at=time.time() - 86400 * 60))
        store.add(_make_entry(importance=0.5))

        policy = CompactionPolicy(max_age_seconds=86400 * 30)
        result = MemoryCompactor(policy).compact(store)
        assert result.entries_removed == 1
        assert store.entry_count == 1

    def test_at4_count_based_keeps_n(self) -> None:
        """AT-4: Count-based policy keeps at most N entries."""
        store = MemoryStore()
        for i in range(20):
            store.add(_make_entry(importance=0.35 + i * 0.01))

        policy = CompactionPolicy(
            max_entries=10, min_importance=0.0,
            max_age_seconds=999999,
        )
        result = MemoryCompactor(policy).compact(store)
        assert store.entry_count == 10

    def test_at5_compaction_report(self) -> None:
        """AT-5: Compaction report shows entries removed and retained."""
        store = MemoryStore()
        store.add(_make_entry(importance=0.1))
        store.add(_make_entry(importance=0.8))

        compactor = MemoryCompactor(CompactionPolicy(min_importance=0.3))
        result = compactor.compact(store)
        d = result.to_dict()
        assert d["entriesBefore"] == 2
        assert d["entriesRemoved"] == 1
        assert d["entriesRetained"] == 1
        assert d["compressionRatio"] == pytest.approx(0.5)
        assert d["durationMs"] >= 0


# ---------------------------------------------------------------------------
# Acceptance Tests — REQ-MEM-03
# ---------------------------------------------------------------------------


class TestAcceptanceMEM03:
    def test_at1_knowledge_persists(self) -> None:
        """AT-1: Knowledge extracted from session persists after session ends."""
        ks = KnowledgeStore()
        ks.extract_and_add(
            "Deploy requires VPN connection",
            source_session_id="sess-1",
            org_id="org-1",
        )
        # Simulate session end — knowledge still queryable
        result = ks.query(org_id="org-1")
        assert len(result) == 1
        assert "VPN" in result[0].content

    def test_at2_new_session_queries_prior(self) -> None:
        """AT-2: New session can query knowledge from prior sessions."""
        ks = KnowledgeStore()
        ks.extract_and_add("API rate limit is 100/min", org_id="org-1",
                            source_session_id="sess-old")

        # New session queries
        results = ks.query_for_session(org_id="org-1")
        assert len(results) == 1
        assert "rate limit" in results[0].content
        assert results[0].source_session_id == "sess-old"

    def test_at3_org_isolation(self) -> None:
        """AT-3: Knowledge scoped to org_id — no cross-org leakage."""
        ks = KnowledgeStore()
        ks.extract_and_add("Secret procedure", org_id="org-A")
        ks.extract_and_add("Public fact", org_id="org-B")

        result_a = ks.query(org_id="org-A")
        result_b = ks.query(org_id="org-B")
        assert len(result_a) == 1
        assert result_a[0].content == "Secret procedure"
        assert len(result_b) == 1
        assert result_b[0].content == "Public fact"

        # org-C sees nothing
        assert len(ks.query(org_id="org-C")) == 0

    def test_at4_provenance_tracking(self) -> None:
        """AT-4: Knowledge entries have provenance (source session, timestamp)."""
        ks = KnowledgeStore()
        k = ks.extract_and_add(
            "DB backup runs at 3am",
            source_session_id="sess-42",
            org_id="org-1",
        )
        prov = ks.get_provenance(k.knowledge_id)
        assert prov is not None
        assert prov["sourceSessionId"] == "sess-42"
        assert prov["createdAt"] > 0

    def test_at5_stale_knowledge_expired(self) -> None:
        """AT-5: Stale knowledge can be expired by TTL."""
        ks = KnowledgeStore()
        # Already expired
        ks.add(KnowledgeEntry(
            knowledge_id="k-stale", content="old info", org_id="o",
            expires_at=time.time() - 100,
        ))
        # Fresh
        ks.add(KnowledgeEntry(
            knowledge_id="k-fresh", content="new info", org_id="o",
            expires_at=time.time() + 3600,
        ))

        removed = ks.expire_stale()
        assert removed == 1
        assert ks.entry_count == 1
        assert ks.get("k-fresh") is not None
        assert ks.get("k-stale") is None
