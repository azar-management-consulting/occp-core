"""Hybrid Memory Store — REQ-MEM-01, REQ-MEM-02, REQ-MEM-03.

REQ-MEM-01: Hybrid Memory Retrieval
  Combines semantic (embedding-based) and episodic (recency/importance)
  retrieval with configurable blending weights.

  Acceptance Tests:
    (1) Semantic search returns entries matching embedding similarity.
    (2) Episodic search returns recent + high-importance entries first.
    (3) Hybrid query blends both strategies with configurable alpha.
    (4) Empty store returns empty results.
    (5) Retrieval latency < 100ms for 10K entries.

REQ-MEM-02: Memory Compaction
  Compresses old/low-importance memories to reduce storage while
  preserving critical knowledge.

  Acceptance Tests:
    (1) Compact merges entries below importance threshold.
    (2) High-importance entries are never compacted.
    (3) Time-based policy removes entries older than retention window.
    (4) Count-based policy keeps at most N entries.
    (5) Compaction report shows entries removed and retained.

REQ-MEM-03: Cross-Session Knowledge
  Persists knowledge across sessions. Extracts facts from session
  context and makes them available to future sessions.

  Acceptance Tests:
    (1) Knowledge extracted from session persists after session ends.
    (2) New session can query knowledge from prior sessions.
    (3) Knowledge scoped to org_id — no cross-org leakage.
    (4) Knowledge entries have provenance (source session, timestamp).
    (5) Stale knowledge can be expired by TTL.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_SEMANTIC_WEIGHT = 0.6  # alpha for hybrid: semantic weight
DEFAULT_EPISODIC_WEIGHT = 0.4  # 1 - alpha: episodic weight
DEFAULT_TOP_K = 10
COMPACTION_MIN_IMPORTANCE = 0.3
COMPACTION_MAX_AGE_SECONDS = 86400 * 30  # 30 days
KNOWLEDGE_DEFAULT_TTL_SECONDS = 86400 * 90  # 90 days


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class RetrievalMode(str, Enum):
    """Memory retrieval strategy."""
    SEMANTIC = "semantic"
    EPISODIC = "episodic"
    HYBRID = "hybrid"


class MemoryScope(str, Enum):
    """Scope of a memory entry."""
    SESSION = "session"       # Only within one session
    AGENT = "agent"           # Persists for an agent across sessions
    GLOBAL = "global"         # Org-wide knowledge


class KnowledgeType(str, Enum):
    """Type of extracted knowledge."""
    FACT = "fact"
    PREFERENCE = "preference"
    PROCEDURE = "procedure"
    ENTITY = "entity"
    CONTEXT = "context"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class MemoryError(Exception):
    """Base error for memory operations."""


class MemoryNotFoundError(MemoryError):
    """Memory entry not found."""

    def __init__(self, memory_id: str) -> None:
        self.memory_id = memory_id
        super().__init__(f"Memory entry not found: {memory_id}")


class CompactionError(MemoryError):
    """Compaction operation failed."""


class KnowledgeError(MemoryError):
    """Knowledge store operation failed."""


# ---------------------------------------------------------------------------
# MemoryEntry
# ---------------------------------------------------------------------------


@dataclass
class MemoryEntry:
    """A single memory entry with optional embedding vector."""

    memory_id: str
    content: str
    embedding: list[float] = field(default_factory=list)
    importance: float = 0.5
    scope: str = MemoryScope.SESSION.value
    session_id: str = ""
    org_id: str = ""
    agent_id: str = ""
    created_at: float = field(default_factory=time.time)
    accessed_at: float = field(default_factory=time.time)
    access_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)

    def touch(self) -> None:
        """Update access timestamp and count."""
        self.accessed_at = time.time()
        self.access_count += 1

    @property
    def age_seconds(self) -> float:
        """Age of the entry in seconds."""
        return time.time() - self.created_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "memoryId": self.memory_id,
            "content": self.content,
            "embedding": self.embedding,
            "importance": self.importance,
            "scope": self.scope,
            "sessionId": self.session_id,
            "orgId": self.org_id,
            "agentId": self.agent_id,
            "createdAt": self.created_at,
            "accessedAt": self.accessed_at,
            "accessCount": self.access_count,
            "metadata": self.metadata,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryEntry:
        return cls(
            memory_id=data["memoryId"],
            content=data["content"],
            embedding=data.get("embedding", []),
            importance=data.get("importance", 0.5),
            scope=data.get("scope", MemoryScope.SESSION.value),
            session_id=data.get("sessionId", ""),
            org_id=data.get("orgId", ""),
            agent_id=data.get("agentId", ""),
            created_at=data.get("createdAt", time.time()),
            accessed_at=data.get("accessedAt", time.time()),
            access_count=data.get("accessCount", 0),
            metadata=data.get("metadata", {}),
            tags=data.get("tags", []),
        )


# ---------------------------------------------------------------------------
# RetrievalResult
# ---------------------------------------------------------------------------


@dataclass
class RetrievalResult:
    """Result from a memory retrieval query."""

    entries: list[MemoryEntry] = field(default_factory=list)
    scores: list[float] = field(default_factory=list)
    mode: str = RetrievalMode.HYBRID.value
    query_time_ms: float = 0.0
    total_candidates: int = 0

    @property
    def count(self) -> int:
        return len(self.entries)

    def to_dict(self) -> dict[str, Any]:
        return {
            "count": self.count,
            "mode": self.mode,
            "queryTimeMs": self.query_time_ms,
            "totalCandidates": self.total_candidates,
            "entries": [
                {**e.to_dict(), "score": s}
                for e, s in zip(self.entries, self.scores)
            ],
        }


# ---------------------------------------------------------------------------
# Similarity functions
# ---------------------------------------------------------------------------


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0

    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    return dot / (norm_a * norm_b)


def recency_score(created_at: float, half_life: float = 3600.0) -> float:
    """Exponential decay based on age. Half-life in seconds."""
    age = max(0.0, time.time() - created_at)
    return math.exp(-0.693 * age / half_life)  # ln(2) ≈ 0.693


# ---------------------------------------------------------------------------
# MemoryStore — REQ-MEM-01
# ---------------------------------------------------------------------------


class MemoryStore:
    """Hybrid memory store with semantic + episodic retrieval.

    Supports three retrieval modes:
    - SEMANTIC: cosine similarity on embeddings
    - EPISODIC: recency * importance weighted
    - HYBRID: alpha * semantic + (1-alpha) * episodic
    """

    def __init__(
        self,
        *,
        semantic_weight: float = DEFAULT_SEMANTIC_WEIGHT,
        recency_half_life: float = 3600.0,
    ) -> None:
        self._entries: dict[str, MemoryEntry] = {}
        self._semantic_weight = max(0.0, min(1.0, semantic_weight))
        self._recency_half_life = recency_half_life

    # -- Properties --

    @property
    def entry_count(self) -> int:
        return len(self._entries)

    @property
    def semantic_weight(self) -> float:
        return self._semantic_weight

    @property
    def episodic_weight(self) -> float:
        return 1.0 - self._semantic_weight

    # -- CRUD --

    def add(self, entry: MemoryEntry) -> MemoryEntry:
        """Add a memory entry to the store."""
        self._entries[entry.memory_id] = entry
        logger.debug("Memory added: id=%s scope=%s", entry.memory_id, entry.scope)
        return entry

    def add_text(
        self,
        content: str,
        *,
        embedding: list[float] | None = None,
        importance: float = 0.5,
        scope: str = MemoryScope.SESSION.value,
        session_id: str = "",
        org_id: str = "",
        agent_id: str = "",
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryEntry:
        """Convenience: create and add a text memory entry."""
        entry = MemoryEntry(
            memory_id=uuid.uuid4().hex[:16],
            content=content,
            embedding=embedding or [],
            importance=importance,
            scope=scope,
            session_id=session_id,
            org_id=org_id,
            agent_id=agent_id,
            tags=tags or [],
            metadata=metadata or {},
        )
        return self.add(entry)

    def get(self, memory_id: str) -> MemoryEntry:
        """Get a memory entry by ID."""
        entry = self._entries.get(memory_id)
        if entry is None:
            raise MemoryNotFoundError(memory_id)
        entry.touch()
        return entry

    def remove(self, memory_id: str) -> bool:
        """Remove a memory entry. Returns True if removed."""
        return self._entries.pop(memory_id, None) is not None

    def clear(self) -> int:
        """Remove all entries. Returns count removed."""
        count = len(self._entries)
        self._entries.clear()
        return count

    def list_entries(
        self,
        *,
        scope: str | None = None,
        session_id: str | None = None,
        org_id: str | None = None,
        tags: list[str] | None = None,
    ) -> list[MemoryEntry]:
        """List entries with optional filters."""
        result = list(self._entries.values())

        if scope is not None:
            result = [e for e in result if e.scope == scope]
        if session_id is not None:
            result = [e for e in result if e.session_id == session_id]
        if org_id is not None:
            result = [e for e in result if e.org_id == org_id]
        if tags is not None:
            tag_set = set(tags)
            result = [e for e in result if tag_set.intersection(e.tags)]

        return result

    # -- Retrieval (REQ-MEM-01) --

    def query(
        self,
        *,
        embedding: list[float] | None = None,
        mode: RetrievalMode = RetrievalMode.HYBRID,
        top_k: int = DEFAULT_TOP_K,
        scope: str | None = None,
        org_id: str | None = None,
        session_id: str | None = None,
        min_importance: float = 0.0,
    ) -> RetrievalResult:
        """Query memory store with specified retrieval mode.

        Args:
            embedding: Query embedding vector (required for SEMANTIC/HYBRID).
            mode: Retrieval strategy.
            top_k: Maximum results to return.
            scope: Filter by scope.
            org_id: Filter by org.
            session_id: Filter by session.
            min_importance: Minimum importance threshold.

        Returns:
            RetrievalResult with scored entries.
        """
        start = time.time()

        # Filter candidates
        candidates = list(self._entries.values())
        if scope is not None:
            candidates = [e for e in candidates if e.scope == scope]
        if org_id is not None:
            candidates = [e for e in candidates if e.org_id == org_id]
        if session_id is not None:
            candidates = [e for e in candidates if e.session_id == session_id]
        if min_importance > 0:
            candidates = [e for e in candidates if e.importance >= min_importance]

        total_candidates = len(candidates)

        if not candidates:
            return RetrievalResult(
                mode=mode.value,
                query_time_ms=(time.time() - start) * 1000,
                total_candidates=0,
            )

        # Score candidates
        scored: list[tuple[MemoryEntry, float]] = []

        if mode == RetrievalMode.SEMANTIC:
            scored = self._score_semantic(candidates, embedding or [])
        elif mode == RetrievalMode.EPISODIC:
            scored = self._score_episodic(candidates)
        else:  # HYBRID
            scored = self._score_hybrid(candidates, embedding or [])

        # Sort by score descending, take top_k
        scored.sort(key=lambda x: x[1], reverse=True)
        top = scored[:top_k]

        # Touch accessed entries
        for entry, _ in top:
            entry.touch()

        elapsed = (time.time() - start) * 1000
        return RetrievalResult(
            entries=[e for e, _ in top],
            scores=[s for _, s in top],
            mode=mode.value,
            query_time_ms=elapsed,
            total_candidates=total_candidates,
        )

    def _score_semantic(
        self,
        candidates: list[MemoryEntry],
        query_embedding: list[float],
    ) -> list[tuple[MemoryEntry, float]]:
        """Score entries by embedding cosine similarity."""
        return [
            (e, cosine_similarity(query_embedding, e.embedding))
            for e in candidates
        ]

    def _score_episodic(
        self,
        candidates: list[MemoryEntry],
    ) -> list[tuple[MemoryEntry, float]]:
        """Score entries by recency * importance."""
        return [
            (e, recency_score(e.created_at, self._recency_half_life) * e.importance)
            for e in candidates
        ]

    def _score_hybrid(
        self,
        candidates: list[MemoryEntry],
        query_embedding: list[float],
    ) -> list[tuple[MemoryEntry, float]]:
        """Blend semantic and episodic scores."""
        alpha = self._semantic_weight
        result = []
        for entry in candidates:
            sem = cosine_similarity(query_embedding, entry.embedding)
            epi = recency_score(entry.created_at, self._recency_half_life) * entry.importance
            blended = alpha * sem + (1 - alpha) * epi
            result.append((entry, blended))
        return result

    # -- Serialization --

    def to_dict(self) -> dict[str, Any]:
        return {
            "entryCount": self.entry_count,
            "semanticWeight": self._semantic_weight,
            "entries": {eid: e.to_dict() for eid, e in self._entries.items()},
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, indent=2)


# ---------------------------------------------------------------------------
# CompactionPolicy
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CompactionPolicy:
    """Defines when and how memories get compacted."""

    max_entries: int = 10000
    max_age_seconds: float = COMPACTION_MAX_AGE_SECONDS
    min_importance: float = COMPACTION_MIN_IMPORTANCE
    protect_scopes: tuple[str, ...] = (MemoryScope.GLOBAL.value,)
    protect_tags: tuple[str, ...] = ("pinned", "critical")


# ---------------------------------------------------------------------------
# CompactionResult
# ---------------------------------------------------------------------------


@dataclass
class CompactionResult:
    """Outcome of a compaction operation."""

    entries_before: int = 0
    entries_after: int = 0
    entries_removed: int = 0
    entries_retained: int = 0
    protected_count: int = 0
    duration_ms: float = 0.0

    @property
    def compression_ratio(self) -> float:
        if self.entries_before == 0:
            return 0.0
        return 1.0 - (self.entries_after / self.entries_before)

    def to_dict(self) -> dict[str, Any]:
        return {
            "entriesBefore": self.entries_before,
            "entriesAfter": self.entries_after,
            "entriesRemoved": self.entries_removed,
            "entriesRetained": self.entries_retained,
            "protectedCount": self.protected_count,
            "compressionRatio": round(self.compression_ratio, 4),
            "durationMs": self.duration_ms,
        }


# ---------------------------------------------------------------------------
# MemoryCompactor — REQ-MEM-02
# ---------------------------------------------------------------------------


class MemoryCompactor:
    """Compacts memory store by removing old/low-importance entries.

    Policies:
    - Time-based: remove entries older than max_age_seconds
    - Count-based: keep at most max_entries (remove lowest importance first)
    - Importance-based: remove entries below min_importance threshold
    - Protected: never compact entries in protect_scopes or with protect_tags
    """

    def __init__(self, policy: CompactionPolicy | None = None) -> None:
        self._policy = policy or CompactionPolicy()

    @property
    def policy(self) -> CompactionPolicy:
        return self._policy

    def compact(self, store: MemoryStore) -> CompactionResult:
        """Run compaction on the memory store.

        Returns CompactionResult with statistics.
        """
        start = time.time()
        result = CompactionResult(entries_before=store.entry_count)

        all_entries = store.list_entries()

        # Classify: protected vs candidates
        protected: list[MemoryEntry] = []
        candidates: list[MemoryEntry] = []

        for entry in all_entries:
            if self._is_protected(entry):
                protected.append(entry)
            else:
                candidates.append(entry)

        result.protected_count = len(protected)

        # Phase 1: Remove entries below importance threshold
        to_remove: list[str] = []
        remaining: list[MemoryEntry] = []

        for entry in candidates:
            if entry.importance < self._policy.min_importance:
                to_remove.append(entry.memory_id)
            else:
                remaining.append(entry)

        # Phase 2: Remove entries older than max_age
        still_remaining: list[MemoryEntry] = []
        for entry in remaining:
            if entry.age_seconds > self._policy.max_age_seconds:
                to_remove.append(entry.memory_id)
            else:
                still_remaining.append(entry)

        # Phase 3: Count-based — if still over max, remove lowest importance
        total_after_phases = len(protected) + len(still_remaining)
        if total_after_phases > self._policy.max_entries:
            overshoot = total_after_phases - self._policy.max_entries
            # Sort by importance ascending (remove least important first)
            still_remaining.sort(key=lambda e: e.importance)
            for entry in still_remaining[:overshoot]:
                to_remove.append(entry.memory_id)
            still_remaining = still_remaining[overshoot:]

        # Execute removals
        for memory_id in to_remove:
            store.remove(memory_id)

        result.entries_removed = len(to_remove)
        result.entries_after = store.entry_count
        result.entries_retained = result.entries_after
        result.duration_ms = (time.time() - start) * 1000

        logger.info(
            "Compaction complete: removed=%d retained=%d ratio=%.2f",
            result.entries_removed,
            result.entries_retained,
            result.compression_ratio,
        )

        return result

    def _is_protected(self, entry: MemoryEntry) -> bool:
        """Check if entry is protected from compaction."""
        if entry.scope in self._policy.protect_scopes:
            return True
        if any(t in self._policy.protect_tags for t in entry.tags):
            return True
        return False

    def estimate_compaction(self, store: MemoryStore) -> dict[str, int]:
        """Estimate compaction outcome without actually removing entries."""
        all_entries = store.list_entries()
        protected = 0
        below_importance = 0
        over_age = 0

        for entry in all_entries:
            if self._is_protected(entry):
                protected += 1
            elif entry.importance < self._policy.min_importance:
                below_importance += 1
            elif entry.age_seconds > self._policy.max_age_seconds:
                over_age += 1

        return {
            "total": len(all_entries),
            "protected": protected,
            "belowImportance": below_importance,
            "overAge": over_age,
            "estimatedRemoval": below_importance + over_age,
        }


# ---------------------------------------------------------------------------
# KnowledgeEntry — REQ-MEM-03
# ---------------------------------------------------------------------------


@dataclass
class KnowledgeEntry:
    """A persisted knowledge fact extracted from session context."""

    knowledge_id: str
    content: str
    knowledge_type: str = KnowledgeType.FACT.value
    source_session_id: str = ""
    org_id: str = ""
    agent_id: str = ""
    confidence: float = 1.0
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0.0  # 0 = no expiry
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        if self.expires_at <= 0:
            return False
        return time.time() > self.expires_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "knowledgeId": self.knowledge_id,
            "content": self.content,
            "knowledgeType": self.knowledge_type,
            "sourceSessionId": self.source_session_id,
            "orgId": self.org_id,
            "agentId": self.agent_id,
            "confidence": self.confidence,
            "createdAt": self.created_at,
            "expiresAt": self.expires_at,
            "tags": self.tags,
            "metadata": self.metadata,
            "isExpired": self.is_expired,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KnowledgeEntry:
        return cls(
            knowledge_id=data["knowledgeId"],
            content=data["content"],
            knowledge_type=data.get("knowledgeType", KnowledgeType.FACT.value),
            source_session_id=data.get("sourceSessionId", ""),
            org_id=data.get("orgId", ""),
            agent_id=data.get("agentId", ""),
            confidence=data.get("confidence", 1.0),
            created_at=data.get("createdAt", time.time()),
            expires_at=data.get("expiresAt", 0.0),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
        )


# ---------------------------------------------------------------------------
# KnowledgeStore — REQ-MEM-03
# ---------------------------------------------------------------------------


class KnowledgeStore:
    """Cross-session knowledge persistence.

    Stores extracted knowledge from session contexts,
    scoped by org_id to prevent cross-org leakage.

    Features:
    - Extract knowledge from session messages
    - Query knowledge by org, type, tags
    - TTL-based expiry for stale knowledge
    - Provenance tracking (source session, timestamp)
    """

    def __init__(
        self,
        *,
        default_ttl_seconds: float = KNOWLEDGE_DEFAULT_TTL_SECONDS,
    ) -> None:
        self._entries: dict[str, KnowledgeEntry] = {}
        self._default_ttl = default_ttl_seconds

    # -- Properties --

    @property
    def entry_count(self) -> int:
        return len(self._entries)

    # -- CRUD --

    def add(self, entry: KnowledgeEntry) -> KnowledgeEntry:
        """Add a knowledge entry."""
        self._entries[entry.knowledge_id] = entry
        logger.debug(
            "Knowledge added: id=%s type=%s org=%s",
            entry.knowledge_id, entry.knowledge_type, entry.org_id,
        )
        return entry

    def extract_and_add(
        self,
        content: str,
        *,
        knowledge_type: str = KnowledgeType.FACT.value,
        source_session_id: str = "",
        org_id: str = "",
        agent_id: str = "",
        confidence: float = 1.0,
        ttl_seconds: float | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> KnowledgeEntry:
        """Create and add a knowledge entry with optional TTL."""
        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl
        expires_at = time.time() + ttl if ttl > 0 else 0.0

        entry = KnowledgeEntry(
            knowledge_id=uuid.uuid4().hex[:16],
            content=content,
            knowledge_type=knowledge_type,
            source_session_id=source_session_id,
            org_id=org_id,
            agent_id=agent_id,
            confidence=confidence,
            expires_at=expires_at,
            tags=tags or [],
            metadata=metadata or {},
        )
        return self.add(entry)

    def get(self, knowledge_id: str) -> KnowledgeEntry | None:
        """Get a knowledge entry by ID (returns None if expired)."""
        entry = self._entries.get(knowledge_id)
        if entry is None:
            return None
        if entry.is_expired:
            return None
        return entry

    def remove(self, knowledge_id: str) -> bool:
        """Remove a knowledge entry. Returns True if removed."""
        return self._entries.pop(knowledge_id, None) is not None

    # -- Query --

    def query(
        self,
        *,
        org_id: str,
        knowledge_type: str | None = None,
        agent_id: str | None = None,
        tags: list[str] | None = None,
        include_expired: bool = False,
    ) -> list[KnowledgeEntry]:
        """Query knowledge scoped to an org.

        Args:
            org_id: Required — enforces org isolation.
            knowledge_type: Filter by type.
            agent_id: Filter by agent.
            tags: Filter by tags (any match).
            include_expired: If True, include expired entries.

        Returns:
            List of matching KnowledgeEntry objects.
        """
        results = [
            e for e in self._entries.values()
            if e.org_id == org_id
        ]

        if not include_expired:
            results = [e for e in results if not e.is_expired]

        if knowledge_type is not None:
            results = [e for e in results if e.knowledge_type == knowledge_type]

        if agent_id is not None:
            results = [e for e in results if e.agent_id == agent_id]

        if tags is not None:
            tag_set = set(tags)
            results = [e for e in results if tag_set.intersection(e.tags)]

        # Sort by confidence descending, then created_at descending
        results.sort(key=lambda e: (-e.confidence, -e.created_at))
        return results

    def query_for_session(
        self,
        *,
        org_id: str,
        agent_id: str = "",
        top_k: int = DEFAULT_TOP_K,
    ) -> list[KnowledgeEntry]:
        """Get most relevant knowledge for a new session.

        Returns top-K non-expired knowledge entries for the org,
        optionally filtered by agent.
        """
        results = self.query(org_id=org_id, agent_id=agent_id or None)
        return results[:top_k]

    # -- Maintenance --

    def expire_stale(self) -> int:
        """Remove all expired entries. Returns count removed."""
        expired_ids = [
            eid for eid, e in self._entries.items()
            if e.is_expired
        ]
        for eid in expired_ids:
            del self._entries[eid]
        return len(expired_ids)

    def get_provenance(self, knowledge_id: str) -> dict[str, Any] | None:
        """Get provenance info for a knowledge entry."""
        entry = self._entries.get(knowledge_id)
        if entry is None:
            return None
        return {
            "knowledgeId": entry.knowledge_id,
            "sourceSessionId": entry.source_session_id,
            "orgId": entry.org_id,
            "createdAt": entry.created_at,
            "confidence": entry.confidence,
            "knowledgeType": entry.knowledge_type,
        }

    # -- Stats --

    def get_stats(self) -> dict[str, Any]:
        """Return knowledge store statistics."""
        by_type: dict[str, int] = {}
        by_org: dict[str, int] = {}
        expired = 0
        for e in self._entries.values():
            by_type[e.knowledge_type] = by_type.get(e.knowledge_type, 0) + 1
            by_org[e.org_id] = by_org.get(e.org_id, 0) + 1
            if e.is_expired:
                expired += 1

        return {
            "totalEntries": self.entry_count,
            "byType": by_type,
            "byOrg": by_org,
            "expiredCount": expired,
        }

    # -- Serialization --

    def to_dict(self) -> dict[str, Any]:
        return {
            "entryCount": self.entry_count,
            "defaultTtl": self._default_ttl,
            "entries": {eid: e.to_dict() for eid, e in self._entries.items()},
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, indent=2)
