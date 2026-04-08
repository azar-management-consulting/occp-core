"""Telegram Status Formatter — compact Brain status for Telegram messages.

Formats BrainStats overview data into a human-readable Telegram message
for Henry's status command ("staatusz", "status", "mi a helyzet").
"""

from __future__ import annotations

from typing import Any


# Agent status emoji mapping
_STATUS_EMOJI: dict[str, str] = {
    "idle": "\u2705",      # green checkmark
    "busy": "\U0001f504",  # counterclockwise arrows (spinning)
    "error": "\u26a0\ufe0f",  # warning sign
    "offline": "\u26ab",   # black circle
}


def format_telegram_status(overview: dict[str, Any]) -> str:
    """Format dashboard overview into a compact Telegram message.

    Args:
        overview: The dict returned by BrainStats.get_overview().

    Returns:
        Formatted Telegram message string (supports Telegram HTML/plain text).
    """
    brain = overview.get("brain", {})
    agents = overview.get("agents", [])
    projects = overview.get("projects", [])
    stats = overview.get("stats", {})

    total_today = brain.get("total_tasks_today", 0)
    completed = brain.get("total_tasks_completed", 0)
    in_progress = total_today - completed

    pass_rate = stats.get("quality_gate_pass_rate", 0.0)
    pass_pct = int(pass_rate * 100)

    lines: list[str] = []

    # Header
    lines.append("\U0001f9e0 Brian the Brain \u2014 St\u00e1tusz")
    lines.append("")

    # Summary
    lines.append(
        f"\U0001f4ca Ma: {total_today} feladat "
        f"({completed} k\u00e9sz, {in_progress} folyamatban)"
    )
    lines.append(f"\u2b50 Min\u0151s\u00e9g: {pass_pct}% \u00e1tment")
    lines.append("")

    # Agents
    lines.append("\U0001f916 Agentek:")
    for agent in agents:
        status = agent.get("status", "offline")
        emoji = _STATUS_EMOJI.get(status, "\u2753")
        agent_id = agent.get("id", "?")
        line = f"  {emoji} {agent_id} \u2014 {status}"
        current_task = agent.get("current_task", "")
        if status == "busy" and current_task:
            line += f" ({current_task})"
        lines.append(line)
    lines.append("")

    # Projects
    active_projects = [p for p in projects if p.get("status") == "active"]
    lines.append(f"\U0001f4c1 Akt\u00edv projektek: {len(active_projects)}")
    for proj in active_projects:
        tasks = proj.get("active_tasks", 0)
        name = proj.get("name", "?")
        lines.append(f"  \u2022 {name} ({tasks} feladat)")

    return "\n".join(lines)


def is_status_command(text: str) -> bool:
    """Check if the text is a status command from Henry.

    Recognized commands (case-insensitive):
    - "staatusz" / "st\u00e1tusz"
    - "status"
    - "mi a helyzet"
    - "brain status"
    - "dashboard"

    Args:
        text: The incoming message text.

    Returns:
        True if this is a status command.
    """
    normalized = text.strip().lower()
    status_triggers = {
        "st\u00e1tusz",
        "staatusz",
        "status",
        "mi a helyzet",
        "brain status",
        "dashboard",
    }
    return normalized in status_triggers
