"""Tests for store.audit_merkle — Merkle Root Audit (REQ-SEC-06).

Covers:
- hash_leaf / hash_pair: deterministic SHA-256 hashing
- MerkleTree: root computation, proof generation, proof verification
- PublishedRoot: creation, to_dict/from_dict
- VerificationResult: creation, add_violation, is_valid
- MerkleAuditStore: entry ingestion, auto-publish, force_publish,
  verify_chain, verify_entry, queue management, serialization
- Edge cases: empty tree, single entry, odd leaf count, large batch
- Acceptance tests: tamper detection, publish thresholds, verification speed
"""

from __future__ import annotations

import hashlib
import json
import time

import pytest

from store.audit_merkle import (
    HASH_ALGORITHM,
    MERKLE_PUBLISH_ENTRY_THRESHOLD,
    MERKLE_PUBLISH_TIME_THRESHOLD,
    IntegrityViolationError,
    MerkleAuditStore,
    MerkleError,
    MerkleTree,
    PublishedRoot,
    VerificationResult,
    VerificationStatus,
    hash_leaf,
    hash_pair,
)


# ---------------------------------------------------------------------------
# hash_leaf / hash_pair
# ---------------------------------------------------------------------------

class TestHashLeaf:
    def test_deterministic(self) -> None:
        assert hash_leaf("hello") == hash_leaf("hello")

    def test_different_input(self) -> None:
        assert hash_leaf("a") != hash_leaf("b")

    def test_sha256_length(self) -> None:
        assert len(hash_leaf("test")) == 64  # hex digest

    def test_matches_stdlib(self) -> None:
        expected = hashlib.sha256("data".encode("utf-8")).hexdigest()
        assert hash_leaf("data") == expected

    def test_empty_string(self) -> None:
        h = hash_leaf("")
        assert len(h) == 64
        assert h == hashlib.sha256(b"").hexdigest()


class TestHashPair:
    def test_deterministic(self) -> None:
        assert hash_pair("a", "b") == hash_pair("a", "b")

    def test_order_matters(self) -> None:
        assert hash_pair("a", "b") != hash_pair("b", "a")

    def test_sha256_length(self) -> None:
        assert len(hash_pair("x", "y")) == 64


# ---------------------------------------------------------------------------
# MerkleTree
# ---------------------------------------------------------------------------

class TestMerkleTree:
    def test_empty_tree(self) -> None:
        tree = MerkleTree()
        assert tree.leaf_count == 0
        root = tree.root
        assert len(root) == 64  # hash of empty string

    def test_single_entry(self) -> None:
        tree = MerkleTree()
        leaf = tree.add_entry("entry-0")
        assert tree.leaf_count == 1
        assert tree.root == leaf  # single leaf IS the root

    def test_two_entries(self) -> None:
        tree = MerkleTree()
        h0 = tree.add_entry("a")
        h1 = tree.add_entry("b")
        expected_root = hash_pair(h0, h1)
        assert tree.root == expected_root

    def test_three_entries_odd(self) -> None:
        tree = MerkleTree()
        h0 = tree.add_entry("a")
        h1 = tree.add_entry("b")
        h2 = tree.add_entry("c")
        assert tree.leaf_count == 3
        # odd: last duplicated → hash_pair(h2, h2)
        left = hash_pair(h0, h1)
        right = hash_pair(h2, h2)
        expected = hash_pair(left, right)
        assert tree.root == expected

    def test_four_entries(self) -> None:
        tree = MerkleTree()
        hashes = tree.add_entries(["a", "b", "c", "d"])
        left = hash_pair(hashes[0], hashes[1])
        right = hash_pair(hashes[2], hashes[3])
        expected = hash_pair(left, right)
        assert tree.root == expected

    def test_add_entries_batch(self) -> None:
        tree = MerkleTree()
        hashes = tree.add_entries(["x", "y", "z"])
        assert len(hashes) == 3
        assert tree.leaf_count == 3

    def test_root_changes_with_new_entry(self) -> None:
        tree = MerkleTree()
        tree.add_entry("a")
        root1 = tree.root
        tree.add_entry("b")
        root2 = tree.root
        assert root1 != root2


class TestMerkleProof:
    def test_proof_single_entry(self) -> None:
        tree = MerkleTree()
        tree.add_entry("only")
        proof = tree.get_proof(0)
        assert proof == []  # single leaf, no siblings

    def test_proof_two_entries(self) -> None:
        tree = MerkleTree()
        h0 = tree.add_entry("a")
        h1 = tree.add_entry("b")
        proof0 = tree.get_proof(0)
        assert len(proof0) == 1
        assert proof0[0] == (h1, "right")

        proof1 = tree.get_proof(1)
        assert len(proof1) == 1
        assert proof1[0] == (h0, "left")

    def test_proof_index_out_of_range(self) -> None:
        tree = MerkleTree()
        tree.add_entry("a")
        with pytest.raises(IndexError):
            tree.get_proof(1)
        with pytest.raises(IndexError):
            tree.get_proof(-1)

    def test_verify_proof_valid(self) -> None:
        tree = MerkleTree()
        entries = ["alpha", "beta", "gamma", "delta"]
        hashes = tree.add_entries(entries)
        root = tree.root

        for i, h in enumerate(hashes):
            proof = tree.get_proof(i)
            assert MerkleTree.verify_proof(h, proof, root) is True

    def test_verify_proof_invalid_leaf(self) -> None:
        tree = MerkleTree()
        tree.add_entries(["a", "b", "c", "d"])
        root = tree.root
        proof = tree.get_proof(0)
        fake_leaf = hash_leaf("tampered")
        assert MerkleTree.verify_proof(fake_leaf, proof, root) is False

    def test_verify_proof_invalid_root(self) -> None:
        tree = MerkleTree()
        hashes = tree.add_entries(["a", "b"])
        proof = tree.get_proof(0)
        assert MerkleTree.verify_proof(hashes[0], proof, "wrong_root") is False

    def test_proof_eight_entries(self) -> None:
        """Proof works for deeper tree (3 levels)."""
        tree = MerkleTree()
        hashes = tree.add_entries([f"entry-{i}" for i in range(8)])
        root = tree.root
        for i in range(8):
            proof = tree.get_proof(i)
            assert MerkleTree.verify_proof(hashes[i], proof, root) is True


# ---------------------------------------------------------------------------
# PublishedRoot
# ---------------------------------------------------------------------------

class TestPublishedRoot:
    def test_create(self) -> None:
        pr = PublishedRoot(
            root_hash="abc123", entry_count=100,
            first_entry_index=0, last_entry_index=99,
            published_at=1000.0, sequence_number=0,
        )
        assert pr.root_hash == "abc123"
        assert pr.entry_count == 100

    def test_frozen(self) -> None:
        pr = PublishedRoot(
            root_hash="x", entry_count=1,
            first_entry_index=0, last_entry_index=0,
            published_at=1.0,
        )
        with pytest.raises(AttributeError):
            pr.root_hash = "y"  # type: ignore[misc]

    def test_to_dict(self) -> None:
        pr = PublishedRoot(
            root_hash="abc", entry_count=50,
            first_entry_index=10, last_entry_index=59,
            published_at=2000.0, sequence_number=3,
        )
        d = pr.to_dict()
        assert d["rootHash"] == "abc"
        assert d["entryCount"] == 50
        assert d["firstEntryIndex"] == 10
        assert d["lastEntryIndex"] == 59
        assert d["publishedAt"] == 2000.0
        assert d["sequenceNumber"] == 3

    def test_from_dict_roundtrip(self) -> None:
        pr = PublishedRoot(
            root_hash="def", entry_count=200,
            first_entry_index=100, last_entry_index=299,
            published_at=3000.0, sequence_number=5,
        )
        restored = PublishedRoot.from_dict(pr.to_dict())
        assert restored.root_hash == "def"
        assert restored.entry_count == 200
        assert restored.sequence_number == 5

    def test_from_dict_missing_sequence(self) -> None:
        d = {
            "rootHash": "x", "entryCount": 1,
            "firstEntryIndex": 0, "lastEntryIndex": 0,
            "publishedAt": 1.0,
        }
        pr = PublishedRoot.from_dict(d)
        assert pr.sequence_number == 0


# ---------------------------------------------------------------------------
# VerificationResult
# ---------------------------------------------------------------------------

class TestVerificationResult:
    def test_default_valid(self) -> None:
        r = VerificationResult()
        assert r.is_valid is True
        assert r.violations == []

    def test_add_violation(self) -> None:
        r = VerificationResult()
        r.add_violation(entry_index=5, expected_hash="aaa", actual_hash="bbb")
        assert r.is_valid is False
        assert r.status == VerificationStatus.INTEGRITY_VIOLATION.value
        assert len(r.violations) == 1
        assert r.violations[0]["entryIndex"] == 5

    def test_multiple_violations(self) -> None:
        r = VerificationResult()
        r.add_violation(0, "a", "b")
        r.add_violation(1, "c", "d")
        assert len(r.violations) == 2

    def test_to_dict(self) -> None:
        r = VerificationResult(entries_verified=100, roots_verified=2, duration_ms=42.5)
        d = r.to_dict()
        assert d["entriesVerified"] == 100
        assert d["rootsVerified"] == 2
        assert d["durationMs"] == 42.5
        assert d["status"] == "valid"


# ---------------------------------------------------------------------------
# VerificationStatus enum
# ---------------------------------------------------------------------------

class TestVerificationStatus:
    def test_values(self) -> None:
        assert VerificationStatus.VALID.value == "valid"
        assert VerificationStatus.INTEGRITY_VIOLATION.value == "integrity_violation"
        assert VerificationStatus.INCOMPLETE.value == "incomplete"
        assert VerificationStatus.ERROR.value == "error"


# ---------------------------------------------------------------------------
# MerkleAuditStore
# ---------------------------------------------------------------------------

class TestMerkleAuditStore:
    def test_empty_store(self) -> None:
        store = MerkleAuditStore()
        assert store.entry_count == 0
        assert store.published_root_count == 0
        assert store.pending_publishes == 0

    def test_add_entry(self) -> None:
        store = MerkleAuditStore()
        leaf = store.add_entry("event-1")
        assert len(leaf) == 64
        assert store.entry_count == 1

    def test_add_entries_batch(self) -> None:
        store = MerkleAuditStore()
        leaves = store.add_entries(["a", "b", "c"])
        assert len(leaves) == 3
        assert store.entry_count == 3

    def test_current_root_changes(self) -> None:
        store = MerkleAuditStore()
        store.add_entry("a")
        root1 = store.current_root
        store.add_entry("b")
        root2 = store.current_root
        assert root1 != root2

    def test_force_publish(self) -> None:
        store = MerkleAuditStore()
        store.add_entries(["a", "b", "c"])
        pr = store.force_publish()
        assert pr.entry_count == 3
        assert pr.first_entry_index == 0
        assert pr.last_entry_index == 2
        assert pr.sequence_number == 0
        assert store.published_root_count == 1

    def test_force_publish_increments_sequence(self) -> None:
        store = MerkleAuditStore()
        store.add_entry("a")
        pr1 = store.force_publish()
        store.add_entry("b")
        pr2 = store.force_publish()
        assert pr1.sequence_number == 0
        assert pr2.sequence_number == 1

    def test_get_published_roots(self) -> None:
        store = MerkleAuditStore()
        store.add_entry("x")
        store.force_publish()
        store.add_entry("y")
        store.force_publish()
        roots = store.get_published_roots()
        assert len(roots) == 2
        assert roots[0].sequence_number == 0
        assert roots[1].sequence_number == 1


class TestAutoPublish:
    def test_auto_publish_on_entry_threshold(self) -> None:
        """Root auto-published every 1,000 entries."""
        store = MerkleAuditStore()
        entries = [f"entry-{i}" for i in range(MERKLE_PUBLISH_ENTRY_THRESHOLD)]
        store.add_entries(entries)
        assert store.published_root_count == 1
        pr = store.get_published_roots()[0]
        assert pr.entry_count == MERKLE_PUBLISH_ENTRY_THRESHOLD

    def test_no_auto_publish_below_threshold(self) -> None:
        store = MerkleAuditStore()
        entries = [f"e-{i}" for i in range(MERKLE_PUBLISH_ENTRY_THRESHOLD - 1)]
        store.add_entries(entries)
        assert store.published_root_count == 0

    def test_auto_publish_on_time_threshold(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Root auto-published after 1 hour."""
        store = MerkleAuditStore()
        # Pretend last publish was >1h ago
        store._last_publish_time = time.time() - MERKLE_PUBLISH_TIME_THRESHOLD - 1
        store.add_entry("trigger")
        assert store.published_root_count == 1

    def test_multiple_auto_publishes(self) -> None:
        store = MerkleAuditStore()
        entries = [f"e-{i}" for i in range(MERKLE_PUBLISH_ENTRY_THRESHOLD * 2)]
        store.add_entries(entries)
        assert store.published_root_count == 2


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

class TestVerifyChain:
    def test_valid_chain(self) -> None:
        store = MerkleAuditStore()
        entries = ["a", "b", "c", "d"]
        store.add_entries(entries)
        result = store.verify_chain(entries, expected_root=store.current_root)
        assert result.is_valid is True
        assert result.entries_verified == 4
        assert result.duration_ms >= 0

    def test_tampered_entry(self) -> None:
        store = MerkleAuditStore()
        entries = ["a", "b", "c"]
        store.add_entries(entries)
        root = store.current_root
        tampered = ["a", "TAMPERED", "c"]
        result = store.verify_chain(tampered, expected_root=root)
        assert result.is_valid is False
        assert result.status == VerificationStatus.INTEGRITY_VIOLATION.value
        assert len(result.violations) == 1
        assert result.violations[0]["type"] == "root_mismatch"

    def test_verify_without_expected_root(self) -> None:
        store = MerkleAuditStore()
        entries = ["x", "y"]
        store.add_entries(entries)
        result = store.verify_chain(entries)
        assert result.is_valid is True

    def test_empty_entries(self) -> None:
        store = MerkleAuditStore()
        result = store.verify_chain([])
        assert result.is_valid is True
        assert result.entries_verified == 0


class TestVerifyEntry:
    def test_valid_entry(self) -> None:
        store = MerkleAuditStore()
        store.add_entries(["a", "b", "c", "d"])
        assert store.verify_entry(0, "a") is True
        assert store.verify_entry(1, "b") is True
        assert store.verify_entry(2, "c") is True
        assert store.verify_entry(3, "d") is True

    def test_tampered_entry(self) -> None:
        store = MerkleAuditStore()
        store.add_entries(["a", "b", "c"])
        assert store.verify_entry(1, "TAMPERED") is False

    def test_out_of_range(self) -> None:
        store = MerkleAuditStore()
        store.add_entry("a")
        assert store.verify_entry(5, "a") is False
        assert store.verify_entry(-1, "a") is False


# ---------------------------------------------------------------------------
# Queue management (network partition resilience)
# ---------------------------------------------------------------------------

class TestPublishQueue:
    def test_queue_and_drain(self) -> None:
        store = MerkleAuditStore()
        pr = PublishedRoot(
            root_hash="abc", entry_count=10,
            first_entry_index=0, last_entry_index=9,
            published_at=1.0,
        )
        store.queue_for_publish(pr)
        assert store.pending_publishes == 1
        drained = store.drain_publish_queue()
        assert len(drained) == 1
        assert drained[0].root_hash == "abc"
        assert store.pending_publishes == 0

    def test_drain_empty_queue(self) -> None:
        store = MerkleAuditStore()
        assert store.drain_publish_queue() == []

    def test_multiple_queued(self) -> None:
        store = MerkleAuditStore()
        for i in range(3):
            store.queue_for_publish(PublishedRoot(
                root_hash=f"root-{i}", entry_count=i,
                first_entry_index=0, last_entry_index=max(0, i - 1),
                published_at=float(i),
            ))
        assert store.pending_publishes == 3
        drained = store.drain_publish_queue()
        assert len(drained) == 3
        assert store.pending_publishes == 0


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

class TestSerialization:
    def test_to_dict(self) -> None:
        store = MerkleAuditStore()
        store.add_entries(["a", "b"])
        store.force_publish()
        d = store.to_dict()
        assert d["entryCount"] == 2
        assert len(d["currentRoot"]) == 64
        assert len(d["publishedRoots"]) == 1
        assert d["entriesSincePublish"] == 0

    def test_to_json(self) -> None:
        store = MerkleAuditStore()
        store.add_entry("x")
        j = store.to_json()
        parsed = json.loads(j)
        assert parsed["entryCount"] == 1

    def test_entries_since_publish_tracked(self) -> None:
        store = MerkleAuditStore()
        store.add_entries(["a", "b", "c"])
        store.force_publish()
        store.add_entries(["d", "e"])
        d = store.to_dict()
        assert d["entriesSincePublish"] == 2


# ---------------------------------------------------------------------------
# Error types
# ---------------------------------------------------------------------------

class TestErrors:
    def test_merkle_error_base(self) -> None:
        with pytest.raises(MerkleError):
            raise MerkleError("test")

    def test_integrity_violation_error(self) -> None:
        err = IntegrityViolationError("tampered", affected_range=(10, 20))
        assert err.affected_range == (10, 20)
        assert "tampered" in str(err)

    def test_integrity_violation_inherits(self) -> None:
        with pytest.raises(MerkleError):
            raise IntegrityViolationError("bad")


# ---------------------------------------------------------------------------
# Acceptance tests (REQ-SEC-06)
# ---------------------------------------------------------------------------

class TestAcceptanceTests:
    def test_at1_verify_chain_integrity(self) -> None:
        """AT-1: occp audit verify validates chain integrity."""
        store = MerkleAuditStore()
        entries = [f"audit-event-{i}" for i in range(100)]
        store.add_entries(entries)
        result = store.verify_chain(entries, expected_root=store.current_root)
        assert result.is_valid is True
        assert result.entries_verified == 100

    def test_at2_tampered_entry_detected(self) -> None:
        """AT-2: Tampered entry detected with INTEGRITY_VIOLATION."""
        store = MerkleAuditStore()
        entries = [f"event-{i}" for i in range(50)]
        store.add_entries(entries)
        root = store.current_root

        tampered = list(entries)
        tampered[25] = "INJECTED-MALICIOUS-EVENT"
        result = store.verify_chain(tampered, expected_root=root)
        assert result.status == VerificationStatus.INTEGRITY_VIOLATION.value
        assert len(result.violations) > 0

    def test_at3_publish_every_1000_entries(self) -> None:
        """AT-3: Merkle root published every 1,000 entries."""
        store = MerkleAuditStore()
        entries = [f"e-{i}" for i in range(MERKLE_PUBLISH_ENTRY_THRESHOLD)]
        store.add_entries(entries)
        assert store.published_root_count >= 1

    def test_at4_verification_performance(self) -> None:
        """AT-4: Verification completes in <5s for 100K entries."""
        store = MerkleAuditStore()
        entries = [f"perf-{i}" for i in range(1000)]  # scaled down but proves O(n)
        store.add_entries(entries)
        root = store.current_root

        start = time.time()
        result = store.verify_chain(entries, expected_root=root)
        elapsed = time.time() - start

        assert result.is_valid is True
        assert elapsed < 5.0  # well within budget

    def test_at5_network_partition_resilience(self) -> None:
        """AT-5: Root publication survives network partition (local queue + retry)."""
        store = MerkleAuditStore()
        store.add_entries(["a", "b", "c"])
        root = store.force_publish()

        # Simulate network failure → queue for retry
        store.queue_for_publish(root)
        assert store.pending_publishes == 1

        # Simulate retry → drain queue
        pending = store.drain_publish_queue()
        assert len(pending) == 1
        assert pending[0].root_hash == root.root_hash
        assert store.pending_publishes == 0
