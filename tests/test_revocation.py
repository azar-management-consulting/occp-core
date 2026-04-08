"""Tests for security.revocation — Revocation Framework (REQ-CPC-04).

Covers:
- RevocationChecker: revoke, unrevoke, is_revoked, temporary revocations
- KillSwitch: activate, deactivate, core allowlist
- Serialization: to_dict/from_dict, to_json/from_json round-trip
- Sync: needs_sync, mark_synced, poll_interval
- RevocationEntry: expiry, frozen
"""

from __future__ import annotations

import json
import time
import pytest

from security.revocation import (
    RevocationChecker,
    RevocationEntry,
    RevocationError,
    KillSwitchState,
    DEFAULT_POLL_INTERVAL,
)


# ---------------------------------------------------------------------------
# RevocationEntry
# ---------------------------------------------------------------------------

class TestRevocationEntry:
    def test_create(self) -> None:
        e = RevocationEntry(
            artifact_id="skill-a",
            reason="CVE-2026-001",
            revoked_at=time.time(),
            revoked_by="admin",
            severity="critical",
        )
        assert e.artifact_id == "skill-a"
        assert e.severity == "critical"

    def test_permanent_not_expired(self) -> None:
        e = RevocationEntry(
            artifact_id="x", reason="r", revoked_at=time.time(), expires_at=0.0
        )
        assert e.is_expired is False

    def test_temporary_not_expired_yet(self) -> None:
        e = RevocationEntry(
            artifact_id="x",
            reason="r",
            revoked_at=time.time(),
            expires_at=time.time() + 3600,
        )
        assert e.is_expired is False

    def test_temporary_expired(self) -> None:
        e = RevocationEntry(
            artifact_id="x",
            reason="r",
            revoked_at=time.time() - 100,
            expires_at=time.time() - 1,
        )
        assert e.is_expired is True

    def test_to_dict_roundtrip(self) -> None:
        e = RevocationEntry(
            artifact_id="s",
            reason="test",
            revoked_at=1000.0,
            revoked_by="admin",
            severity="high",
            expires_at=2000.0,
        )
        d = e.to_dict()
        restored = RevocationEntry.from_dict(d)
        assert restored.artifact_id == "s"
        assert restored.reason == "test"
        assert restored.revoked_at == 1000.0
        assert restored.expires_at == 2000.0

    def test_frozen(self) -> None:
        e = RevocationEntry(artifact_id="x", reason="r", revoked_at=time.time())
        with pytest.raises(AttributeError):
            e.artifact_id = "y"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# RevocationChecker — basic operations
# ---------------------------------------------------------------------------

class TestRevocationCheckerBasic:
    def test_revoke_and_check(self) -> None:
        rc = RevocationChecker()
        rc.revoke("bad-skill", reason="malware")
        assert rc.is_revoked("bad-skill") is True
        assert rc.is_revoked("good-skill") is False

    def test_unrevoke(self) -> None:
        rc = RevocationChecker()
        rc.revoke("skill-a", reason="test")
        assert rc.unrevoke("skill-a") is True
        assert rc.is_revoked("skill-a") is False

    def test_unrevoke_nonexistent(self) -> None:
        rc = RevocationChecker()
        assert rc.unrevoke("nope") is False

    def test_revoked_artifacts_list(self) -> None:
        rc = RevocationChecker()
        rc.revoke("a", reason="r")
        rc.revoke("b", reason="r")
        assert set(rc.revoked_artifacts) == {"a", "b"}

    def test_revocation_count(self) -> None:
        rc = RevocationChecker()
        assert rc.revocation_count == 0
        rc.revoke("a", reason="r")
        rc.revoke("b", reason="r")
        assert rc.revocation_count == 2

    def test_get_revocation(self) -> None:
        rc = RevocationChecker()
        rc.revoke("s", reason="CVE-123", revoked_by="admin", severity="critical")
        entry = rc.get_revocation("s")
        assert entry is not None
        assert entry.reason == "CVE-123"
        assert entry.severity == "critical"

    def test_get_revocation_nonexistent(self) -> None:
        rc = RevocationChecker()
        assert rc.get_revocation("nope") is None

    def test_revoke_returns_entry(self) -> None:
        rc = RevocationChecker()
        entry = rc.revoke("x", reason="test", severity="medium")
        assert entry.artifact_id == "x"
        assert entry.severity == "medium"


# ---------------------------------------------------------------------------
# Temporary revocations
# ---------------------------------------------------------------------------

class TestTemporaryRevocations:
    def test_temporary_revocation_active(self) -> None:
        rc = RevocationChecker()
        rc.revoke("temp", reason="patch pending", ttl_seconds=3600)
        assert rc.is_revoked("temp") is True

    def test_temporary_revocation_expired(self) -> None:
        rc = RevocationChecker()
        rc.revoke("temp", reason="test", ttl_seconds=0.001)
        time.sleep(0.01)
        assert rc.is_revoked("temp") is False

    def test_expired_cleaned_from_list(self) -> None:
        rc = RevocationChecker()
        rc.revoke("temp", reason="test", ttl_seconds=0.001)
        time.sleep(0.01)
        assert "temp" not in rc.revoked_artifacts

    def test_get_revocation_expired_returns_none(self) -> None:
        rc = RevocationChecker()
        rc.revoke("temp", reason="test", ttl_seconds=0.001)
        time.sleep(0.01)
        assert rc.get_revocation("temp") is None


# ---------------------------------------------------------------------------
# Kill-switch
# ---------------------------------------------------------------------------

class TestKillSwitch:
    def test_activate(self) -> None:
        rc = RevocationChecker()
        rc.activate_kill_switch(reason="zero-day", activated_by="admin")
        assert rc.kill_switch_active is True
        assert rc.kill_switch_state.reason == "zero-day"

    def test_deactivate(self) -> None:
        rc = RevocationChecker()
        rc.activate_kill_switch()
        rc.deactivate_kill_switch()
        assert rc.kill_switch_active is False

    def test_kill_switch_blocks_non_core(self) -> None:
        rc = RevocationChecker(core_allowlist=["core-a"])
        rc.activate_kill_switch(reason="emergency")
        assert rc.is_revoked("random-skill") is True
        assert rc.is_revoked("core-a") is False

    def test_kill_switch_allows_default_core(self) -> None:
        rc = RevocationChecker()
        rc.activate_kill_switch()
        for core in RevocationChecker.DEFAULT_CORE:
            assert rc.is_revoked(core) is False

    def test_is_core_artifact(self) -> None:
        rc = RevocationChecker()
        assert rc.is_core_artifact("occp-core") is True
        assert rc.is_core_artifact("random") is False

    def test_kill_switch_with_revocation(self) -> None:
        """Kill-switch AND per-artifact revocation both active."""
        rc = RevocationChecker(core_allowlist=["safe"])
        rc.revoke("also-bad", reason="extra bad")
        rc.activate_kill_switch()
        assert rc.is_revoked("random") is True  # kill-switch
        assert rc.is_revoked("also-bad") is True  # revocation + kill-switch
        assert rc.is_revoked("safe") is False  # core allowlist


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

class TestSerialization:
    def test_to_dict_roundtrip(self) -> None:
        rc = RevocationChecker(core_allowlist=["core-1"])
        rc.revoke("a", reason="r1", severity="critical")
        rc.revoke("b", reason="r2", ttl_seconds=3600)
        rc.activate_kill_switch(reason="test")
        rc.mark_synced()

        d = rc.to_dict()
        rc2 = RevocationChecker.from_dict(d)
        assert rc2.is_revoked("a") is True
        assert rc2.is_revoked("b") is True
        assert rc2.kill_switch_active is True
        assert rc2.is_core_artifact("core-1") is True

    def test_to_json_roundtrip(self) -> None:
        rc = RevocationChecker()
        rc.revoke("x", reason="test")
        j = rc.to_json()
        rc2 = RevocationChecker.from_json(j)
        assert rc2.is_revoked("x") is True

    def test_expired_not_restored(self) -> None:
        rc = RevocationChecker()
        rc.revoke("temp", reason="test", ttl_seconds=0.001)
        time.sleep(0.01)
        d = rc.to_dict()
        rc2 = RevocationChecker.from_dict(d)
        assert rc2.is_revoked("temp") is False


# ---------------------------------------------------------------------------
# Sync
# ---------------------------------------------------------------------------

class TestSync:
    def test_needs_sync_initially(self) -> None:
        rc = RevocationChecker()
        assert rc.needs_sync() is True

    def test_mark_synced(self) -> None:
        rc = RevocationChecker(poll_interval=3600)
        rc.mark_synced()
        assert rc.needs_sync() is False
        assert rc.last_sync > 0

    def test_needs_sync_after_interval(self) -> None:
        rc = RevocationChecker(poll_interval=0.001)
        rc.mark_synced()
        time.sleep(0.01)
        assert rc.needs_sync() is True

    def test_poll_interval(self) -> None:
        rc = RevocationChecker(poll_interval=600)
        assert rc.poll_interval == 600


# ---------------------------------------------------------------------------
# KillSwitchState
# ---------------------------------------------------------------------------

class TestKillSwitchState:
    def test_to_dict_roundtrip(self) -> None:
        ks = KillSwitchState(
            active=True,
            reason="test",
            activated_at=1000.0,
            activated_by="admin",
            core_allowlist=["a", "b"],
        )
        d = ks.to_dict()
        restored = KillSwitchState.from_dict(d)
        assert restored.active is True
        assert restored.reason == "test"
        assert restored.core_allowlist == ["a", "b"]
