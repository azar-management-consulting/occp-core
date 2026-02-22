"""EchoPlanner – demo Planner adapter that echoes the task description as a plan."""

from __future__ import annotations

from typing import Any

from orchestrator.models import Task


class EchoPlanner:
    """Implements the :class:`orchestrator.pipeline.Planner` protocol.

    Returns a simple plan derived from the task's own description.
    Useful for demos and integration tests.
    """

    async def create_plan(self, task: Task) -> dict[str, Any]:
        return {
            "strategy": "echo",
            "description": task.description,
            "steps": [
                f"Analyze: {task.name}",
                f"Execute: {task.description}",
                "Validate results",
                "Ship output",
            ],
        }
