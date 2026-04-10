"""Merkle Root Audit Verification — REQ-SEC-06.

Audit trail entries hash-chained using SHA-256 Merkle tree.
Periodic Merkle root published to immutable store.
Tampering with historical entries detectable by root mismatch.

Acceptance Tests:
  (1) ``occp audit verify --from=... --to=...`` validates chain integrity.
  (2) Tampered entry detected: INTEGRITY_VIOLATION + affected range.
  (3) Merkle root published every 1,000 entries or 1 hour.
  (4) Verification completes in <5s for 100K entries.
  (5) Root publication survives network partition (local queue + retry).
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MERKLE_PUBLISH_ENTRY_THRESHOLD = 1000
MERKLE_PUBLISH_TIME_THRESHOLD = 3600  # 1 hour in seconds
HASH_ALGORITHM = "sha256"


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class VerificationStatus(str, Enum):
    """Audit verification result status."""
    VALID = "valid"
    INTEGRITY_VIOLATION = "integrity_violation"
    INCOMPLETE = "incomplete"
    ERROR = "error"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class MerkleError(Exception):
    """Base error for Merkle operations."""


class IntegrityViolationError(MerkleError):
    """Tampering detected in audit trail."""

    def __init__(self, message: str, affected_range: tuple[int, int] | None = None) -> None:
        self.affected_range = affected_range
        super().__init__(message)


# ---------------------------------------------------------------------------
# Core hashing
# ---------------------------------------------------------------------------

def hash_leaf(data: str) -> str:
    """Hash a single audit entry (leaf node)."""
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def hash_pair(left: str, right: str) -> str:
    """Hash two child nodes to form parent."""
    combined = left + right
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# MerkleTree
# ---------------------------------------------------------------------------

class MerkleTree:
    """SHA-256 Merkle tree for audit entry verification.

    Supports incremental construction and proof generation.
    """

    def __init__(self) -> None:
        self._leaves: list[str] = []  # leaf hashes

    @property
    def leaf_count(self) -> int:
        return len(self._leaves)

    @property
    def root(self) -> str:
        """Compute the Merkle root hash."""
        if not self._leaves:
            return hash_leaf("")
        return self._compute_root(self._leaves)

    def add_entry(self, data: str) -> str:
        """Add an audit entry and return its leaf hash."""
        leaf = hash_leaf(data)
        self._leaves.append(leaf)
        return leaf

    def add_entries(self, entries: list[str]) -> list[str]:
        """Add multiple entries. Returns list of leaf hashes."""
        return [self.add_entry(e) for e in entries]

    def get_proof(self, index: int) -> list[tuple[str, str]]:
        """Generate a Merkle proof for the entry at given index.

        Returns list of (hash, side) tuples where side is 'left' or 'right'.
        """
        if index < 0 or index >= len(self._leaves):
            raise IndexError(f"Index {index} out of range [0, {len(self._leaves)})")

        proof: list[tuple[str, str]] = []
        level = list(self._leaves)

        idx = index
        while len(level) > 1:
            if len(level) % 2 == 1:
                level.append(level[-1])  # duplicate last for odd

            if idx % 2 == 0:
                # Sibling is on the right
                if idx + 1 < len(level):
                    proof.append((level[idx + 1], "right"))
            else:
                # Sibling is on the left
                proof.append((level[idx - 1], "left"))

            # Move to next level
            new_level = []
            for i in range(0, len(level), 2):
                new_level.append(hash_pair(level[i], level[i + 1]))
            level = new_level
            idx = idx // 2

        return proof

    @staticmethod
    def verify_proof(leaf_hash: str, proof: list[tuple[str, str]], root: str) -> bool:
        """Verify a Merkle proof against a known root."""
        current = leaf_hash
        for sibling_hash, side in proof:
            if side == "left":
                current = hash_pair(sibling_hash, current)
            else:
                current = hash_pair(current, sibling_hash)
        return current == root

    def _compute_root(self, nodes: list[str]) -> str:
        """Recursively compute Merkle root from leaf hashes."""
        if len(nodes) == 1:
            return nodes[0]

        level = list(nodes)
        while len(level) > 1:
            if len(level) % 2 == 1:
                level.append(level[-1])  # duplicate last for odd count
            next_level = []
            for i in range(0, len(level), 2):
                next_level.append(hash_pair(level[i], level[i + 1]))
            level = next_level
        return level[0]


# ---------------------------------------------------------------------------
# PublishedRoot
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PublishedRoot:
    """A published Merkle root checkpoint."""

    root_hash: str
    entry_count: int
    first_entry_index: int
    last_entry_index: int
    published_at: float
    sequence_number: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "rootHash": self.root_hash,
            "entryCount": self.entry_count,
            "firstEntryIndex": self.first_entry_index,
            "lastEntryIndex": self.last_entry_index,
            "publishedAt": self.published_at,
            "sequenceNumber": self.sequence_number,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PublishedRoot:
        return cls(
            root_hash=data["rootHash"],
            entry_count=data["entryCount"],
            first_entry_index=data["firstEntryIndex"],
            last_entry_index=data["lastEntryIndex"],
            published_at=data["publishedAt"],
            sequence_number=data.get("sequenceNumber", 0),
        )


# ---------------------------------------------------------------------------
# VerificationResult
# ---------------------------------------------------------------------------

@dataclass
class VerificationResult:
    """Result of an audit chain verification."""

    status: str = VerificationStatus.VALID.value
    entries_verified: int = 0
    roots_verified: int = 0
    violations: list[dict[str, Any]] = field(default_factory=list)
    duration_ms: float = 0.0

    @property
    def is_valid(self) -> bool:
        return self.status == VerificationStatus.VALID.value

    def add_violation(
        self,
        entry_index: int,
        expected_hash: str,
        actual_hash: str,
    ) -> None:
        self.violations.append({
            "entryIndex": entry_index,
            "expectedHash": expected_hash,
            "actualHash": actual_hash,
        })
        self.status = VerificationStatus.INTEGRITY_VIOLATION.value

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "entriesVerified": self.entries_verified,
            "rootsVerified": self.roots_verified,
            "violations": self.violations,
            "durationMs": self.duration_ms,
        }


# ---------------------------------------------------------------------------
# MerkleAuditStore
# ---------------------------------------------------------------------------

class MerkleAuditStore:
    """Manages Merkle tree construction and root publication for audit trails.

    Publishes root every MERKLE_PUBLISH_ENTRY_THRESHOLD entries
    or MERKLE_PUBLISH_TIME_THRESHOLD seconds, whichever comes first.
    """

    def __init__(self) -> None:
        self._tree = MerkleTree()
        self._published_roots: list[PublishedRoot] = []
        self._entries_since_publish: int = 0
        self._last_publish_time: float = time.time()
        self._total_entries: int = 0
        self._pending_publish_queue: list[PublishedRoot] = []

    # -- Properties ----------------------------------------------------------

    @property
    def entry_count(self) -> int:
        return self._total_entries

    @property
    def published_root_count(self) -> int:
        return len(self._published_roots)

    @property
    def current_root(self) -> str:
        return self._tree.root

    @property
    def pending_publishes(self) -> int:
        return len(self._pending_publish_queue)

    # -- Entry ingestion -----------------------------------------------------

    def add_entry(self, entry_data: str) -> str:
        """Add an audit entry. Returns leaf hash.

        Automatically publishes root when threshold reached.
        """
        leaf_hash = self._tree.add_entry(entry_data)
        self._total_entries += 1
        self._entries_since_publish += 1

        if self._should_publish():
            self._publish_root()

        return leaf_hash

    def add_entries(self, entries: list[str]) -> list[str]:
        """Add multiple audit entries."""
        return [self.add_entry(e) for e in entries]

    # -- Root publication ----------------------------------------------------

    def _should_publish(self) -> bool:
        """Check if root should be published."""
        if self._entries_since_publish >= MERKLE_PUBLISH_ENTRY_THRESHOLD:
            return True
        elapsed = time.time() - self._last_publish_time
        if elapsed >= MERKLE_PUBLISH_TIME_THRESHOLD:
            return True
        return False

    def _publish_root(self) -> PublishedRoot:
        """Publish current Merkle root."""
        root = PublishedRoot(
            root_hash=self._tree.root,
            entry_count=self._total_entries,
            first_entry_index=self._total_entries - self._entries_since_publish,
            last_entry_index=self._total_entries - 1,
            published_at=time.time(),
            sequence_number=len(self._published_roots),
        )

        self._published_roots.append(root)
        self._entries_since_publish = 0
        self._last_publish_time = time.time()

        logger.info(
            "Merkle root published: seq=%d entries=%d root=%s",
            root.sequence_number, root.entry_count, root.root_hash[:16],
        )
        return root

    def force_publish(self) -> PublishedRoot:
        """Force publish current root (for testing or graceful shutdown)."""
        return self._publish_root()

    def get_published_roots(self) -> list[PublishedRoot]:
        """Return all published roots."""
        return list(self._published_roots)

    # -- Verification --------------------------------------------------------

    def verify_chain(
        self,
        entries: list[str],
        expected_root: str | None = None,
    ) -> VerificationResult:
        """Verify integrity of audit entries against Merkle root.

        Args:
            entries: Audit entry data to verify.
            expected_root: Expected Merkle root (if None, computes from entries).

        Returns:
            VerificationResult with status and any violations.
        """
        start = time.time()
        result = VerificationResult()

        # Build verification tree
        verify_tree = MerkleTree()
        for entry in entries:
            verify_tree.add_entry(entry)
        result.entries_verified = len(entries)

        computed_root = verify_tree.root

        if expected_root is not None and computed_root != expected_root:
            result.status = VerificationStatus.INTEGRITY_VIOLATION.value
            result.violations.append({
                "type": "root_mismatch",
                "expectedRoot": expected_root,
                "computedRoot": computed_root,
                "entryCount": len(entries),
            })

        result.duration_ms = (time.time() - start) * 1000
        return result

    def verify_entry(self, index: int, entry_data: str) -> bool:
        """Verify a single entry at given index matches the tree."""
        expected_leaf = hash_leaf(entry_data)
        if index < 0 or index >= self._tree.leaf_count:
            return False

        proof = self._tree.get_proof(index)
        return MerkleTree.verify_proof(expected_leaf, proof, self._tree.root)

    # -- Serialization -------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "entryCount": self._total_entries,
            "currentRoot": self._tree.root,
            "publishedRoots": [r.to_dict() for r in self._published_roots],
            "entriesSincePublish": self._entries_since_publish,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, indent=2)

    # -- Queue management (network partition resilience) ----------------------

    def queue_for_publish(self, root: PublishedRoot) -> None:
        """Add root to pending publish queue (for retry on network failure)."""
        self._pending_publish_queue.append(root)

    def drain_publish_queue(self) -> list[PublishedRoot]:
        """Get and clear pending publish queue."""
        queue = list(self._pending_publish_queue)
        self._pending_publish_queue.clear()
        return queue
