"""BasicValidator – demo Validator that checks plan and execution result exist."""

from __future__ import annotations

from orchestrator.models import Task


class BasicValidator:
    """Implements the :class:`orchestrator.pipeline.Validator` protocol.

    Performs basic sanity checks:
    - Task must have a plan (non-empty dict).
    - Task description must not be empty.

    Returns an empty list (no failures) if all checks pass.
    """

    async def validate(self, task: Task) -> list[str]:
        failures: list[str] = []

        if not task.plan:
            failures.append("No plan attached to task")

        if not task.description.strip():
            failures.append("Task description is empty")

        return failures
