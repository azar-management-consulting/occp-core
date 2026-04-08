"""Tests for evaluation.feature_flags (L6 foundation)."""

from __future__ import annotations

import pytest

from evaluation import FeatureFlag, FeatureFlagStore, get_flag_store


class TestFeatureFlagStore:

    @pytest.fixture
    def store(self):
        return FeatureFlagStore()

    def test_defaults_seeded(self, store):
        flag = store.get("l6.observability.metrics_enabled")
        assert flag is not None
        assert flag.enabled is True

    def test_unsafe_defaults_off(self, store):
        # Self-modifier must default to log-only
        flag = store.get("l6.self_modifier.log_only")
        assert flag is not None
        assert flag.enabled is True
        # RFC auto-generation must default off
        rfc_flag = store.get("l6.rfc.auto_generation")
        assert rfc_flag is not None
        assert rfc_flag.enabled is False

    def test_set_new_flag(self, store):
        flag = store.set("test.new.flag", True, description="test flag")
        assert flag.enabled is True
        assert flag.description == "test flag"
        assert store.is_enabled("test.new.flag")

    def test_set_updates_existing(self, store):
        store.set("l6.canary.enabled", True)
        assert store.is_enabled("l6.canary.enabled") is True
        store.set("l6.canary.enabled", False)
        assert store.is_enabled("l6.canary.enabled") is False

    def test_is_enabled_unknown_returns_default(self, store):
        assert store.is_enabled("nonexistent.flag") is False
        assert store.is_enabled("nonexistent.flag", default=True) is True

    def test_delete(self, store):
        store.set("temp.flag", True)
        assert store.delete("temp.flag") is True
        assert store.get("temp.flag") is None
        assert store.delete("temp.flag") is False  # second delete

    def test_list_all_sorted(self, store):
        flags = store.list_all()
        keys = [f.key for f in flags]
        assert keys == sorted(keys)
        assert len(flags) >= 6  # at least the default seeds

    def test_rollout_percent_clamped(self, store):
        store.set("test.rollout", True, rollout_percent=150)
        assert store.get("test.rollout").rollout_percent == 100
        store.set("test.rollout", True, rollout_percent=-10)
        assert store.get("test.rollout").rollout_percent == 0

    def test_reset_restores_defaults(self, store):
        store.set("custom.flag", True)
        assert store.get("custom.flag") is not None
        store.reset()
        assert store.get("custom.flag") is None
        # defaults restored
        assert store.get("l6.observability.metrics_enabled") is not None

    def test_to_dict(self, store):
        flag = store.get("l6.observability.metrics_enabled")
        d = flag.to_dict()
        assert d["key"] == "l6.observability.metrics_enabled"
        assert "created_at" in d
        assert "updated_at" in d


class TestSingleton:

    def test_get_flag_store_returns_singleton(self):
        s1 = get_flag_store()
        s2 = get_flag_store()
        assert s1 is s2
