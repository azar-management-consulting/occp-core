"""Tests for evaluation.kill_switch (L6 maximum state)."""

from __future__ import annotations

import pytest

from evaluation.kill_switch import (
    KillSwitch,
    KillSwitchActivation,
    KillSwitchActive,
    KillSwitchState,
    KillSwitchTrigger,
    get_kill_switch,
    require_kill_switch_inactive,
)


@pytest.fixture
def ks():
    k = KillSwitch()
    return k


# ── Initial state ────────────────────────────────────────

class TestInitialState:

    def test_defaults_inactive(self, ks):
        assert ks.state == KillSwitchState.INACTIVE
        assert ks.is_active() is False
        assert ks.is_drill() is False

    def test_no_current_activation(self, ks):
        assert ks.current_activation is None

    def test_empty_history(self, ks):
        assert ks.status()["history_count"] == 0


# ── Activation ───────────────────────────────────────────

class TestActivation:

    def test_manual_activation(self, ks):
        record = ks.activate(
            trigger=KillSwitchTrigger.MANUAL,
            actor="henry",
            reason="emergency stop",
        )
        assert ks.is_active() is True
        assert ks.state == KillSwitchState.ACTIVE
        assert record.trigger == KillSwitchTrigger.MANUAL
        assert record.actor == "henry"

    def test_anomaly_activation(self, ks):
        ks.activate(
            trigger=KillSwitchTrigger.ANOMALY,
            actor="anomaly_detector",
            reason="error rate > 20%",
            evidence={"error_rate": 0.25},
        )
        assert ks.is_active() is True
        assert ks.current_activation.trigger == KillSwitchTrigger.ANOMALY
        assert ks.current_activation.evidence["error_rate"] == 0.25

    def test_activation_appended_to_history(self, ks):
        ks.activate(trigger=KillSwitchTrigger.MANUAL, actor="a", reason="r1")
        ks.deactivate(actor="a", reason="clear")
        ks.activate(trigger=KillSwitchTrigger.ANOMALY, actor="b", reason="r2")
        assert ks.status()["history_count"] == 2


# ── Drill mode ───────────────────────────────────────────

class TestDrill:

    def test_drill_does_not_block(self, ks):
        ks.drill(actor="henry", reason="test")
        assert ks.state == KillSwitchState.DRILL
        assert ks.is_drill() is True
        # Drill does NOT count as active
        assert ks.is_active() is False

    def test_drill_logged_in_history(self, ks):
        ks.drill(actor="henry", reason="test drill")
        assert ks.status()["history_count"] == 1
        assert ks.current_activation.trigger == KillSwitchTrigger.DRILL


# ── Deactivation ─────────────────────────────────────────

class TestDeactivation:

    def test_deactivate_after_activation(self, ks):
        ks.activate(trigger=KillSwitchTrigger.MANUAL, actor="a", reason="r")
        prev = ks.deactivate(actor="henry", reason="all clear")
        assert ks.is_active() is False
        assert ks.state == KillSwitchState.INACTIVE
        assert prev is not None
        assert prev.deactivated_by == "henry"
        assert prev.deactivation_reason == "all clear"

    def test_deactivate_when_inactive(self, ks):
        result = ks.deactivate(actor="henry", reason="noop")
        assert result is None


# ── Entry-point guard ────────────────────────────────────

class TestGuard:

    def test_guard_raises_when_active(self, ks, monkeypatch):
        # Rewire get_kill_switch to return this instance
        from evaluation import kill_switch as mod
        monkeypatch.setattr(mod, "_global_switch", ks)

        ks.activate(
            trigger=KillSwitchTrigger.SECURITY,
            actor="sec",
            reason="incident",
        )
        with pytest.raises(KillSwitchActive) as exc_info:
            require_kill_switch_inactive()
        assert exc_info.value.trigger == KillSwitchTrigger.SECURITY
        assert "incident" in str(exc_info.value)

    def test_guard_silent_when_inactive(self, ks, monkeypatch):
        from evaluation import kill_switch as mod
        monkeypatch.setattr(mod, "_global_switch", ks)
        # Should not raise
        require_kill_switch_inactive()

    def test_guard_silent_during_drill(self, ks, monkeypatch):
        from evaluation import kill_switch as mod
        monkeypatch.setattr(mod, "_global_switch", ks)
        ks.drill(actor="henry", reason="test")
        # Drill must NOT raise
        require_kill_switch_inactive()


# ── Stats + history ──────────────────────────────────────

class TestStats:

    def test_stats_by_trigger(self, ks):
        ks.activate(trigger=KillSwitchTrigger.MANUAL, actor="a", reason="r1")
        ks.deactivate(actor="a", reason="clear")
        ks.activate(trigger=KillSwitchTrigger.ANOMALY, actor="b", reason="r2")
        ks.deactivate(actor="b", reason="clear")
        ks.activate(trigger=KillSwitchTrigger.MANUAL, actor="c", reason="r3")
        stats = ks.stats()
        assert stats["total_activations"] == 3
        assert stats["by_trigger"]["manual"] == 2
        assert stats["by_trigger"]["anomaly"] == 1

    def test_history_capped(self, ks):
        ks._max_history = 5
        for i in range(20):
            ks.activate(trigger=KillSwitchTrigger.MANUAL, actor="a", reason=f"r{i}")
        assert ks.status()["history_count"] == 5

    def test_reset(self, ks):
        ks.activate(trigger=KillSwitchTrigger.MANUAL, actor="a", reason="r")
        ks.reset()
        assert ks.is_active() is False
        assert ks.status()["history_count"] == 0


# ── Singleton ────────────────────────────────────────────

class TestSingleton:

    def test_singleton(self):
        k1 = get_kill_switch()
        k2 = get_kill_switch()
        assert k1 is k2
