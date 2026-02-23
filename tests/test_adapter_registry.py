"""Tests for AdapterRegistry — per-agent-type adapter routing."""

from __future__ import annotations

from typing import Any

import pytest

from orchestrator.adapter_registry import AdapterRegistry


# Minimal test adapters implementing the Protocol interfaces

class StubPlanner:
    def __init__(self, name: str = "stub") -> None:
        self.name = name

    async def create_plan(self, task: Any) -> dict[str, Any]:
        return {"planner": self.name}


class StubExecutor:
    def __init__(self, name: str = "stub") -> None:
        self.name = name

    async def execute(self, task: Any) -> dict[str, Any]:
        return {"executor": self.name}


class StubValidator:
    def __init__(self, name: str = "stub") -> None:
        self.name = name

    async def validate(self, task: Any) -> list[str]:
        return []


class StubShipper:
    def __init__(self, name: str = "stub") -> None:
        self.name = name

    async def ship(self, task: Any) -> dict[str, Any]:
        return {"shipper": self.name}


@pytest.fixture
def registry() -> AdapterRegistry:
    return AdapterRegistry(
        default_planner=StubPlanner("default"),
        default_executor=StubExecutor("default"),
        default_validator=StubValidator("default"),
        default_shipper=StubShipper("default"),
    )


class TestAdapterRegistry:
    def test_defaults_returned_for_unregistered_type(self, registry: AdapterRegistry) -> None:
        p = registry.get_planner("unknown")
        assert isinstance(p, StubPlanner) and p.name == "default"
        e = registry.get_executor("unknown")
        assert isinstance(e, StubExecutor) and e.name == "default"
        v = registry.get_validator("unknown")
        assert isinstance(v, StubValidator) and v.name == "default"
        s = registry.get_shipper("unknown")
        assert isinstance(s, StubShipper) and s.name == "default"

    def test_override_planner_only(self, registry: AdapterRegistry) -> None:
        custom_planner = StubPlanner("custom")
        registry.register("code-reviewer", planner=custom_planner)

        p = registry.get_planner("code-reviewer")
        assert isinstance(p, StubPlanner) and p.name == "custom"

        # Other stages still use default
        e = registry.get_executor("code-reviewer")
        assert isinstance(e, StubExecutor) and e.name == "default"
        v = registry.get_validator("code-reviewer")
        assert isinstance(v, StubValidator) and v.name == "default"
        s = registry.get_shipper("code-reviewer")
        assert isinstance(s, StubShipper) and s.name == "default"

    def test_full_override(self, registry: AdapterRegistry) -> None:
        registry.register(
            "full-custom",
            planner=StubPlanner("fc"),
            executor=StubExecutor("fc"),
            validator=StubValidator("fc"),
            shipper=StubShipper("fc"),
        )
        assert registry.get_planner("full-custom").name == "fc"  # type: ignore[union-attr]
        assert registry.get_executor("full-custom").name == "fc"  # type: ignore[union-attr]
        assert registry.get_validator("full-custom").name == "fc"  # type: ignore[union-attr]
        assert registry.get_shipper("full-custom").name == "fc"  # type: ignore[union-attr]

    def test_unregister(self, registry: AdapterRegistry) -> None:
        registry.register("temp", planner=StubPlanner("temp"))
        assert "temp" in registry.registered_types
        registry.unregister("temp")
        assert "temp" not in registry.registered_types
        # Falls back to default after unregister
        p = registry.get_planner("temp")
        assert isinstance(p, StubPlanner) and p.name == "default"

    def test_registered_types(self, registry: AdapterRegistry) -> None:
        assert registry.registered_types == []
        registry.register("a", planner=StubPlanner("a"))
        registry.register("b", executor=StubExecutor("b"))
        assert sorted(registry.registered_types) == ["a", "b"]

    def test_routing_info_default(self, registry: AdapterRegistry) -> None:
        info = registry.get_routing_info("unregistered")
        assert info == {
            "planner": "default",
            "executor": "default",
            "validator": "default",
            "shipper": "default",
        }

    def test_routing_info_partial_override(self, registry: AdapterRegistry) -> None:
        registry.register("partial", planner=StubPlanner("p"), shipper=StubShipper("s"))
        info = registry.get_routing_info("partial")
        assert info == {
            "planner": "override",
            "executor": "default",
            "validator": "default",
            "shipper": "override",
        }

    def test_unregister_nonexistent_is_noop(self, registry: AdapterRegistry) -> None:
        registry.unregister("does-not-exist")  # Should not raise
        assert registry.registered_types == []
