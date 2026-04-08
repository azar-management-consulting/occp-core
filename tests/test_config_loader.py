"""Tests for ConfigLoader — REQ-CORE-03: Config-First Agent Definitions.

Covers:
- AgentDefinition construction and to_dict / to_agent_config
- ConfigLoader.load_yaml() — valid definition
- Missing required fields (name, trust_level)
- Invalid trust_level string
- Invalid field types (capabilities not list, max_concurrent not int)
- Trust constraint validation: tool categories, LLM, network, spawn
- TrustViolationError details
- ConfigLoader.load_directory() with YAML files
- ConfigLoader.load_directory() missing directory
- get_definition() / get_agent_configs() / clear()
- TOOL_CATEGORIES mapping completeness
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import pytest

from orchestrator.config_loader import (
    AgentDefinition,
    AgentDefinitionError,
    ConfigLoader,
    ConfigLoaderError,
    TrustViolationError,
)
from orchestrator.models import AgentConfig
from policy_engine.trust_levels import TrustLevel


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _valid_yaml(
    name: str = "test-agent",
    trust: str = "L3_AUTONOMOUS",
    tools: list[str] | None = None,
    **overrides: Any,
) -> dict[str, Any]:
    d: dict[str, Any] = {
        "name": name,
        "display_name": f"Test {name}",
        "trust_level": trust,
        "capabilities": ["coding"],
        "tools": tools if tools is not None else ["file.read", "file.write"],
        "model": "claude-sonnet-4-6",
        "policy_profile": "default",
        "max_concurrent": 2,
        "timeout_seconds": 600,
        "metadata": {"team": "eng"},
    }
    d.update(overrides)
    return d


# ---------------------------------------------------------------------------
# AgentDefinition
# ---------------------------------------------------------------------------


class TestAgentDefinition:
    def test_construction(self) -> None:
        defn = AgentDefinition(
            name="coder",
            display_name="Coder",
            trust_level=TrustLevel.L3_AUTONOMOUS,
            capabilities=["coding"],
            tools=["file.read"],
        )
        assert defn.name == "coder"
        assert defn.trust_level == TrustLevel.L3_AUTONOMOUS

    def test_to_dict(self) -> None:
        defn = AgentDefinition(
            name="coder",
            display_name="Coder",
            trust_level=TrustLevel.L2_SUPERVISED,
        )
        d = defn.to_dict()
        assert d["name"] == "coder"
        assert d["trust_level"] == "L2_SUPERVISED"
        assert d["policy_profile"] == "default"

    def test_to_agent_config(self) -> None:
        defn = AgentDefinition(
            name="coder",
            display_name="Coder Agent",
            trust_level=TrustLevel.L3_AUTONOMOUS,
            capabilities=["coding", "testing"],
            tools=["file.read"],
            model="llama3.1:8b",
            max_concurrent=3,
            timeout_seconds=120,
        )
        cfg = defn.to_agent_config()
        assert isinstance(cfg, AgentConfig)
        assert cfg.agent_type == "coder"
        assert cfg.display_name == "Coder Agent"
        assert cfg.capabilities == ["coding", "testing"]
        assert cfg.max_concurrent == 3
        assert cfg.timeout_seconds == 120
        assert cfg.metadata["trust_level"] == "L3_AUTONOMOUS"
        assert cfg.metadata["model"] == "llama3.1:8b"


# ---------------------------------------------------------------------------
# load_yaml — valid
# ---------------------------------------------------------------------------


class TestLoadYamlValid:
    def test_basic_load(self) -> None:
        loader = ConfigLoader(validate_trust=False)
        defn = loader.load_yaml(_valid_yaml())
        assert defn.name == "test-agent"
        assert defn.trust_level == TrustLevel.L3_AUTONOMOUS
        assert defn.max_concurrent == 2

    def test_defaults(self) -> None:
        loader = ConfigLoader(validate_trust=False)
        defn = loader.load_yaml({
            "name": "minimal",
            "trust_level": "L0_DETERMINISTIC",
        })
        assert defn.display_name == "minimal"
        assert defn.capabilities == []
        assert defn.tools == []
        assert defn.model == ""
        assert defn.policy_profile == "default"
        assert defn.max_concurrent == 1
        assert defn.timeout_seconds == 300

    def test_stored_in_definitions(self) -> None:
        loader = ConfigLoader(validate_trust=False)
        loader.load_yaml(_valid_yaml(name="a1"))
        loader.load_yaml(_valid_yaml(name="a2"))
        assert len(loader.definitions) == 2
        assert "a1" in loader.definitions

    def test_get_definition(self) -> None:
        loader = ConfigLoader(validate_trust=False)
        loader.load_yaml(_valid_yaml(name="x"))
        assert loader.get_definition("x") is not None
        assert loader.get_definition("nope") is None


# ---------------------------------------------------------------------------
# load_yaml — validation errors
# ---------------------------------------------------------------------------


class TestLoadYamlErrors:
    def test_missing_name(self) -> None:
        loader = ConfigLoader(validate_trust=False)
        with pytest.raises(AgentDefinitionError, match="Missing required field: name"):
            loader.load_yaml({"trust_level": "L0_DETERMINISTIC"})

    def test_empty_name(self) -> None:
        loader = ConfigLoader(validate_trust=False)
        with pytest.raises(AgentDefinitionError, match="Missing required field: name"):
            loader.load_yaml({"name": "  ", "trust_level": "L0_DETERMINISTIC"})

    def test_missing_trust_level(self) -> None:
        loader = ConfigLoader(validate_trust=False)
        with pytest.raises(AgentDefinitionError, match="Missing required field: trust_level"):
            loader.load_yaml({"name": "agent"})

    def test_invalid_trust_level(self) -> None:
        loader = ConfigLoader(validate_trust=False)
        with pytest.raises(AgentDefinitionError, match="Invalid trust_level"):
            loader.load_yaml({"name": "agent", "trust_level": "L99_BOGUS"})

    def test_capabilities_not_list(self) -> None:
        loader = ConfigLoader(validate_trust=False)
        with pytest.raises(AgentDefinitionError, match="capabilities must be a list"):
            loader.load_yaml({
                "name": "agent",
                "trust_level": "L0_DETERMINISTIC",
                "capabilities": "string-not-list",
            })

    def test_tools_not_list(self) -> None:
        loader = ConfigLoader(validate_trust=False)
        with pytest.raises(AgentDefinitionError, match="tools must be a list"):
            loader.load_yaml({
                "name": "agent",
                "trust_level": "L0_DETERMINISTIC",
                "tools": "shell.exec",
            })

    def test_max_concurrent_not_positive(self) -> None:
        loader = ConfigLoader(validate_trust=False)
        with pytest.raises(AgentDefinitionError, match="max_concurrent must be a positive"):
            loader.load_yaml({
                "name": "agent",
                "trust_level": "L0_DETERMINISTIC",
                "max_concurrent": 0,
            })

    def test_timeout_not_positive(self) -> None:
        loader = ConfigLoader(validate_trust=False)
        with pytest.raises(AgentDefinitionError, match="timeout_seconds must be a positive"):
            loader.load_yaml({
                "name": "agent",
                "trust_level": "L0_DETERMINISTIC",
                "timeout_seconds": -1,
            })

    def test_metadata_not_dict(self) -> None:
        loader = ConfigLoader(validate_trust=False)
        with pytest.raises(AgentDefinitionError, match="metadata must be a dict"):
            loader.load_yaml({
                "name": "agent",
                "trust_level": "L0_DETERMINISTIC",
                "metadata": "string",
            })


# ---------------------------------------------------------------------------
# Trust constraint validation
# ---------------------------------------------------------------------------


class TestTrustValidation:
    def test_l0_no_write_tools(self) -> None:
        """L0_DETERMINISTIC cannot use write tools."""
        loader = ConfigLoader(validate_trust=True)
        with pytest.raises(TrustViolationError) as exc_info:
            loader.load_yaml({
                "name": "agent",
                "trust_level": "L0_DETERMINISTIC",
                "tools": ["file.write"],
            })
        assert "file.write" in str(exc_info.value)

    def test_l0_no_network(self) -> None:
        loader = ConfigLoader(validate_trust=True)
        with pytest.raises(TrustViolationError):
            loader.load_yaml({
                "name": "agent",
                "trust_level": "L0_DETERMINISTIC",
                "tools": ["http.request"],
            })

    def test_l0_no_llm(self) -> None:
        """L0_DETERMINISTIC cannot use LLM tools."""
        loader = ConfigLoader(validate_trust=True)
        with pytest.raises(TrustViolationError) as exc_info:
            loader.load_yaml({
                "name": "agent",
                "trust_level": "L0_DETERMINISTIC",
                "tools": ["llm.generate"],
            })
        assert "LLM tools not allowed" in str(exc_info.value)

    def test_l2_no_spawn(self) -> None:
        """L2_SUPERVISED cannot spawn agents."""
        loader = ConfigLoader(validate_trust=True)
        with pytest.raises(TrustViolationError) as exc_info:
            loader.load_yaml({
                "name": "agent",
                "trust_level": "L2_SUPERVISED",
                "tools": ["agent.spawn"],
            })
        assert "Agent spawn tools not allowed" in str(exc_info.value)

    def test_violation_error_details(self) -> None:
        loader = ConfigLoader(validate_trust=True)
        with pytest.raises(TrustViolationError) as exc_info:
            loader.load_yaml({
                "name": "bad-agent",
                "trust_level": "L0_DETERMINISTIC",
                "tools": ["file.write", "http.request"],
            })
        err = exc_info.value
        assert err.name == "bad-agent"
        assert len(err.violations) >= 2

    def test_high_trust_passes(self) -> None:
        """L5_ORCHESTRATOR should pass with all tool categories."""
        loader = ConfigLoader(validate_trust=True)
        defn = loader.load_yaml({
            "name": "orchestrator",
            "trust_level": "L5_ORCHESTRATOR",
            "tools": [
                "shell.exec",
                "file.write",
                "http.request",
                "llm.generate",
                "agent.spawn",
            ],
        })
        assert defn.name == "orchestrator"

    def test_unknown_tool_not_flagged(self) -> None:
        """Tools not in TOOL_CATEGORIES are ignored (no category to check)."""
        loader = ConfigLoader(validate_trust=True)
        defn = loader.load_yaml({
            "name": "agent",
            "trust_level": "L0_DETERMINISTIC",
            "tools": ["custom.unknown_tool"],
        })
        assert defn.name == "agent"

    def test_skip_trust_validation(self) -> None:
        loader = ConfigLoader(validate_trust=False)
        defn = loader.load_yaml({
            "name": "agent",
            "trust_level": "L0_DETERMINISTIC",
            "tools": ["shell.exec", "http.request", "llm.generate"],
        })
        assert defn.name == "agent"


# ---------------------------------------------------------------------------
# load_directory
# ---------------------------------------------------------------------------


class TestLoadDirectory:
    def test_load_from_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            # Write two YAML files
            (Path(tmpdir) / "agent1.yaml").write_text(
                "name: agent1\ntrust_level: L3_AUTONOMOUS\n"
            )
            (Path(tmpdir) / "agent2.yaml").write_text(
                "name: agent2\ntrust_level: L2_SUPERVISED\n"
            )
            # Non-YAML file should be ignored
            (Path(tmpdir) / "readme.txt").write_text("ignore me")

            loader = ConfigLoader(validate_trust=False)
            loaded = loader.load_directory(tmpdir)
            assert len(loaded) == 2
            assert {d.name for d in loaded} == {"agent1", "agent2"}

    def test_missing_directory_raises(self) -> None:
        loader = ConfigLoader(validate_trust=False)
        with pytest.raises(ConfigLoaderError, match="not found"):
            loader.load_directory("/nonexistent/path")


# ---------------------------------------------------------------------------
# get_agent_configs / clear
# ---------------------------------------------------------------------------


class TestUtilities:
    def test_get_agent_configs(self) -> None:
        loader = ConfigLoader(validate_trust=False)
        loader.load_yaml(_valid_yaml(name="a1"))
        loader.load_yaml(_valid_yaml(name="a2"))
        configs = loader.get_agent_configs()
        assert len(configs) == 2
        assert all(isinstance(c, AgentConfig) for c in configs)

    def test_clear(self) -> None:
        loader = ConfigLoader(validate_trust=False)
        loader.load_yaml(_valid_yaml())
        assert len(loader.definitions) == 1
        loader.clear()
        assert len(loader.definitions) == 0


# ---------------------------------------------------------------------------
# TOOL_CATEGORIES completeness
# ---------------------------------------------------------------------------


class TestToolCategories:
    def test_has_standard_tools(self) -> None:
        cats = ConfigLoader.TOOL_CATEGORIES
        assert cats["shell.exec"] == "execute"
        assert cats["file.read"] == "read"
        assert cats["git.push"] == "network"
        assert cats["llm.generate"] == "generate"
        assert cats["agent.spawn"] == "orchestrate"
        assert cats["deploy.production"] == "admin"

    def test_at_least_20_tools(self) -> None:
        assert len(ConfigLoader.TOOL_CATEGORIES) >= 20
