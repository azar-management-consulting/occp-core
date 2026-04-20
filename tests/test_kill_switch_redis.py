"""Tests for evaluation.kill_switch_redis.

Uses a hermetic MockRedis that implements GET/SET/DELETE/LPUSH/LTRIM/
LRANGE — enough surface to drive the RedisKillSwitch without requiring
a live Redis server or fakeredis.
"""

from __future__ import annotations

import json
import threading

import pytest

from evaluation import kill_switch as ks_mod
from evaluation.kill_switch import (
    KillSwitch,
    KillSwitchTrigger,
)
from evaluation.kill_switch_redis import (
    HALT_KEY,
    HISTORY_CAP,
    HISTORY_KEY,
    RedisKillSwitch,
    get_redis_kill_switch,
    kill_switch_backend,
    reset_redis_kill_switch,
)


# ── Hermetic Redis test double ───────────────────────────────


class MockRedis:
    """Implements the tiny subset of Redis used by RedisKillSwitch."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._strings: dict[str, str] = {}
        self._lists: dict[str, list[str]] = {}
        self.available: bool = True

    # --- strings
    def set(self, key: str, value: str, ex: int | None = None) -> bool:
        self._guard()
        with self._lock:
            self._strings[key] = value
        return True

    def get(self, key: str) -> str | None:
        self._guard()
        with self._lock:
            return self._strings.get(key)

    def delete(self, *keys: str) -> int:
        self._guard()
        removed = 0
        with self._lock:
            for k in keys:
                if k in self._strings:
                    del self._strings[k]
                    removed += 1
        return removed

    # --- lists
    def lpush(self, key: str, *values: str) -> int:
        self._guard()
        with self._lock:
            lst = self._lists.setdefault(key, [])
            for v in values:
                lst.insert(0, v)
            return len(lst)

    def ltrim(self, key: str, start: int, stop: int) -> bool:
        self._guard()
        with self._lock:
            lst = self._lists.get(key, [])
            # Redis LTRIM: inclusive stop; negative indices allowed. We
            # only need the simple 0..N case here.
            self._lists[key] = lst[start : stop + 1]
        return True

    def lrange(self, key: str, start: int, stop: int) -> list[str]:
        self._guard()
        with self._lock:
            lst = self._lists.get(key, [])
            return lst[start : stop + 1]

    def ping(self) -> bool:
        self._guard()
        return True

    # --- test controls
    def _guard(self) -> None:
        if not self.available:
            raise RuntimeError("simulated Redis outage")


class FailingRedis(MockRedis):
    """A Redis mock that fails on every call — simulates outage."""

    def __init__(self) -> None:
        super().__init__()
        self.available = False


# ── Fixtures ─────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_everything():
    # Ensure a clean in-memory singleton for each test.
    ks_mod._global_switch = None
    reset_redis_kill_switch()
    yield
    ks_mod._global_switch = None
    reset_redis_kill_switch()


@pytest.fixture
def mock_client():
    return MockRedis()


@pytest.fixture
def switch(mock_client):
    """RedisKillSwitch wired to our in-memory MockRedis."""
    # Also ensure memory fallback is pristine for mirror semantics.
    KillSwitch()  # warmup (no-op; isolates singleton)
    return RedisKillSwitch(redis_client=mock_client)


# ── activate / deactivate cycle ──────────────────────────────


class TestActivateDeactivateCycle:

    def test_initial_state_is_inactive(self, switch):
        assert switch.is_active() is False
        assert switch.status()["is_active"] is False

    def test_activate_sets_state(self, switch, mock_client):
        record = switch.activate(
            actor="henry",
            reason="runaway tokens",
            trigger=KillSwitchTrigger.MANUAL,
        )
        assert record["state"] == "active"
        assert record["actor"] == "henry"
        assert record["reason"] == "runaway tokens"
        assert record["trigger"] == "manual"
        assert switch.is_active() is True

        # Persisted JSON in the halt key
        raw = mock_client.get(HALT_KEY)
        assert raw is not None
        stored = json.loads(raw)
        assert stored["actor"] == "henry"
        assert stored["reason"] == "runaway tokens"

    def test_deactivate_clears_state(self, switch, mock_client):
        switch.activate(actor="henry", reason="test")
        assert switch.is_active() is True
        prev = switch.deactivate(actor="henry", reason="all clear")
        assert prev is not None
        assert prev["deactivated_by"] == "henry"
        assert prev["deactivation_reason"] == "all clear"
        assert switch.is_active() is False
        # Halt key should be cleared
        assert mock_client.get(HALT_KEY) is None

    def test_full_cycle_persists_history(self, switch, mock_client):
        switch.activate(actor="a", reason="r1")
        switch.deactivate(actor="a", reason="done")
        switch.activate(
            actor="b", reason="r2", trigger=KillSwitchTrigger.ANOMALY
        )
        history = mock_client.lrange(HISTORY_KEY, 0, 9)
        # Two activations + one deactivation record
        assert len(history) >= 2

    def test_history_capped_at_constant(self):
        assert HISTORY_CAP == 100


# ── idempotency ──────────────────────────────────────────────


class TestActivateIsIdempotent:

    def test_activate_twice_keeps_active(self, switch):
        switch.activate(actor="a", reason="first")
        switch.activate(actor="b", reason="second")
        assert switch.is_active() is True
        # Latest activation wins — evidence "current" is updated
        status = switch.status()
        assert status["current"]["actor"] == "b"
        assert status["current"]["reason"] == "second"

    def test_deactivate_when_inactive_is_noop(self, switch):
        result = switch.deactivate(actor="henry", reason="no-op")
        assert result is None
        assert switch.is_active() is False

    def test_deactivate_is_idempotent(self, switch):
        switch.activate(actor="a", reason="r")
        first = switch.deactivate(actor="henry", reason="done")
        second = switch.deactivate(actor="henry", reason="still done")
        assert first is not None
        assert second is None  # already inactive → no-op


# ── status ───────────────────────────────────────────────────


class TestStatusReturnsFullState:

    def test_status_when_inactive(self, switch):
        s = switch.status()
        assert s["backend"] == "redis"
        assert s["is_active"] is False
        assert s["current"] is None
        assert s["recent_history"] == []

    def test_status_when_active(self, switch):
        switch.activate(
            actor="henry",
            reason="emergency",
            trigger=KillSwitchTrigger.SECURITY,
            evidence={"error_rate": 0.42},
        )
        s = switch.status()
        assert s["is_active"] is True
        assert s["state"] == "active"
        assert s["current"] is not None
        assert s["current"]["actor"] == "henry"
        assert s["current"]["trigger"] == "security"
        assert s["current"]["evidence"]["error_rate"] == 0.42

    def test_status_includes_history_after_activations(self, switch):
        switch.activate(actor="a", reason="r1")
        switch.deactivate(actor="a", reason="d1")
        switch.activate(
            actor="b", reason="r2", trigger=KillSwitchTrigger.ANOMALY
        )
        s = switch.status()
        assert len(s["recent_history"]) >= 2


# ── fallback to memory ───────────────────────────────────────


class TestFallbackToMemoryWhenRedisDown:

    def test_failing_redis_falls_back_to_memory(self, monkeypatch):
        # Construct with a client that fails on every call.
        failing = FailingRedis()
        # Disable the ping that runs during __init__ for the path
        # that accepts an explicit client — FailingRedis starts in
        # "unavailable" state which would simulate a stale client.
        switch = RedisKillSwitch(redis_client=failing)

        # After a single failed operation, backend should flip to memory.
        assert switch.is_active() is False  # first call: may hit failure
        # After failure the switch must report the memory backend
        assert switch.backend == "memory"

    def test_activate_still_works_with_memory_fallback(self, monkeypatch):
        failing = FailingRedis()
        switch = RedisKillSwitch(redis_client=failing)
        # Even with Redis unavailable, activate must succeed via memory
        # so the operator can always stop the fleet.
        record = switch.activate(actor="henry", reason="redis down")
        assert record["state"] == "active"
        assert switch.is_active() is True

    def test_redis_unavailable_module_flag(self, monkeypatch):
        # Simulate the redis package being absent
        import evaluation.kill_switch_redis as mod

        monkeypatch.setattr(mod, "_REDIS_AVAILABLE", False)
        monkeypatch.setattr(mod, "_redis", None)
        reset_redis_kill_switch()

        switch = RedisKillSwitch()
        assert switch.backend == "memory"
        # Operations still succeed — they go through the memory singleton
        switch.activate(actor="henry", reason="no-redis")
        assert switch.is_active() is True


# ── multi-process shared state ───────────────────────────────


class TestMultipleProcessSharesState:

    def test_two_switches_share_halt_state(self, mock_client):
        """Two RedisKillSwitch instances against the same client must
        converge on the same state — this simulates two worker
        processes reading the same Redis."""
        # Reset the memory singleton so mirroring doesn't leak cross-instance
        ks_mod._global_switch = None
        s1 = RedisKillSwitch(redis_client=mock_client)
        ks_mod._global_switch = None  # fresh memory for s2
        s2 = RedisKillSwitch(redis_client=mock_client)

        assert s1.is_active() is False
        assert s2.is_active() is False

        s1.activate(actor="process-A", reason="budget blown")

        # The *Redis-backed* view from s2 must see ACTIVE even though
        # s2's in-memory fallback is a different object.
        assert s2.is_active() is True
        s2_status = s2.status()
        assert s2_status["current"]["actor"] == "process-A"
        assert s2_status["current"]["reason"] == "budget blown"

    def test_deactivation_propagates_across_instances(self, mock_client):
        ks_mod._global_switch = None
        s1 = RedisKillSwitch(redis_client=mock_client)
        ks_mod._global_switch = None
        s2 = RedisKillSwitch(redis_client=mock_client)

        s1.activate(actor="a", reason="r")
        assert s2.is_active() is True
        s1.deactivate(actor="b", reason="cleared")
        assert s2.is_active() is False


# ── env + singleton ──────────────────────────────────────────


class TestBackendSelection:

    def test_default_backend_is_memory(self, monkeypatch):
        monkeypatch.delenv("OCCP_KILL_SWITCH_BACKEND", raising=False)
        assert kill_switch_backend() == "memory"

    def test_backend_env_redis(self, monkeypatch):
        monkeypatch.setenv("OCCP_KILL_SWITCH_BACKEND", "redis")
        assert kill_switch_backend() == "redis"

    def test_backend_env_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("OCCP_KILL_SWITCH_BACKEND", "  REDIS ")
        assert kill_switch_backend() == "redis"


class TestSingleton:

    def test_singleton_returns_same_instance(self):
        s1 = get_redis_kill_switch()
        s2 = get_redis_kill_switch()
        assert s1 is s2

    def test_reset_returns_new_instance(self):
        s1 = get_redis_kill_switch()
        reset_redis_kill_switch()
        s2 = get_redis_kill_switch()
        assert s1 is not s2
