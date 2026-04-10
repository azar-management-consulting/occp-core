"""OpenClaw agent-to-workspace mapping.

Maps OCCP Brain agent IDs to OpenClaw workspace identifiers and
preferred model configuration.  Used by OpenClawClient when dispatching
tasks to determine the correct workspace on claw.occp.ai.
"""

from __future__ import annotations

from typing import Any

# Agent ID -> OpenClaw workspace + model configuration
AGENT_OPENCLAW_MAP: dict[str, dict[str, Any]] = {
    "eng-core": {
        "workspace": "eng-core",
        "model": "google/gemini-2.5-pro",
        "fallback": ["openai/gpt-4.1", "anthropic/claude-sonnet-4-6"],
    },
    "wp-web": {
        "workspace": "wp-web",
        "model": "google/gemini-2.5-pro",
        "fallback": ["openai/gpt-4.1", "anthropic/claude-sonnet-4-6"],
    },
    "infra-ops": {
        "workspace": "infra-ops",
        "model": "google/gemini-2.5-pro",
        "fallback": ["openai/gpt-4.1", "anthropic/claude-sonnet-4-6"],
    },
    "design-lab": {
        "workspace": "design-lab",
        "model": "google/gemini-2.5-pro",
        "fallback": ["openai/gpt-4.1", "anthropic/claude-sonnet-4-6"],
    },
    "content-forge": {
        "workspace": "content-forge",
        "model": "google/gemini-2.5-pro",
        "fallback": ["openai/gpt-4.1", "anthropic/claude-sonnet-4-6"],
    },
    "social-growth": {
        "workspace": "social-growth",
        "model": "google/gemini-2.5-pro",
        "fallback": ["openai/gpt-4.1", "anthropic/claude-sonnet-4-6"],
    },
    "intel-research": {
        "workspace": "intel-research",
        "model": "anthropic/claude-opus-4-6",
        "fallback": ["google/gemini-2.5-pro", "openai/gpt-4.1"],
    },
    "biz-strategy": {
        "workspace": "biz-strategy",
        "model": "anthropic/claude-opus-4-6",
        "fallback": ["google/gemini-2.5-pro", "openai/gpt-4.1"],
    },
}


def get_agent_workspace(agent_id: str) -> str | None:
    """Return the OpenClaw workspace name for an agent, or None if unknown."""
    entry = AGENT_OPENCLAW_MAP.get(agent_id)
    return entry["workspace"] if entry else None


def get_agent_model(agent_id: str) -> str | None:
    """Return the primary model for an agent, or None if unknown."""
    entry = AGENT_OPENCLAW_MAP.get(agent_id)
    return entry["model"] if entry else None


def get_all_agent_ids() -> list[str]:
    """Return all known OpenClaw agent IDs."""
    return list(AGENT_OPENCLAW_MAP.keys())
