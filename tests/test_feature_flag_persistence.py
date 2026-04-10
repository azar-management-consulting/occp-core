"""Tests for feature flag JSON persistence (L6 maximum state)."""

from __future__ import annotations

import json
import pathlib

import pytest

from evaluation.feature_flags import FeatureFlagStore


@pytest.fixture
def store_path(tmp_path):
    return tmp_path / "flags.json"


class TestPersistence:

    def test_persist_on_set(self, store_path):
        store = FeatureFlagStore(store_path=store_path, load=False)
        store.set("test.flag", True, description="test")
        assert store_path.exists()
        data = json.loads(store_path.read_text())
        assert "test.flag" in data
        assert data["test.flag"]["enabled"] is True

    def test_persist_on_delete(self, store_path):
        store = FeatureFlagStore(store_path=store_path, load=False)
        store.set("temp.flag", True)
        store.delete("temp.flag")
        data = json.loads(store_path.read_text())
        assert "temp.flag" not in data

    def test_load_from_disk(self, store_path):
        # Pre-seed a disk state
        store_path.write_text(json.dumps({
            "disk.flag": {
                "enabled": True,
                "rollout_percent": 50,
                "description": "loaded from disk",
                "updated_at": "2026-04-08T00:00:00+00:00",
            }
        }))
        store = FeatureFlagStore(store_path=store_path, load=True)
        flag = store.get("disk.flag")
        assert flag is not None
        assert flag.enabled is True
        assert flag.rollout_percent == 50

    def test_load_merges_with_defaults(self, store_path):
        store_path.write_text(json.dumps({
            "l6.rfc.auto_generation": {"enabled": True, "rollout_percent": 0}
        }))
        store = FeatureFlagStore(store_path=store_path, load=True)
        # Default RFC auto-generation is OFF; disk state should override
        assert store.is_enabled("l6.rfc.auto_generation") is True
        # Other defaults still present
        assert store.get("l6.self_modifier.log_only") is not None

    def test_survives_recreation(self, store_path):
        # Write via first instance
        s1 = FeatureFlagStore(store_path=store_path, load=False)
        s1.set("persistent.flag", True, description="persist me")
        # Read via second instance
        s2 = FeatureFlagStore(store_path=store_path, load=True)
        flag = s2.get("persistent.flag")
        assert flag is not None
        assert flag.enabled is True
        assert flag.description == "persist me"

    def test_corrupt_file_fallback_to_defaults(self, store_path):
        store_path.write_text("not valid json {")
        # Must NOT raise — must fall back to defaults
        store = FeatureFlagStore(store_path=store_path, load=True)
        assert store.get("l6.observability.metrics_enabled") is not None

    def test_missing_file_uses_defaults(self, store_path):
        # File does not exist
        store = FeatureFlagStore(store_path=store_path, load=True)
        assert store.get("l6.observability.metrics_enabled") is not None
        assert not store_path.exists()  # No write yet

    def test_explicit_persist(self, store_path):
        store = FeatureFlagStore(store_path=store_path, load=False)
        store.set("manual.persist", True)
        assert store.persist() is True
        assert store_path.exists()

    def test_persist_creates_parent_dir(self, tmp_path):
        nested = tmp_path / "deep" / "nested" / "flags.json"
        store = FeatureFlagStore(store_path=nested, load=False)
        store.set("x", True)
        assert nested.exists()
