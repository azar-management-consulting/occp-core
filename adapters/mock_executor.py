"""MockExecutor – demo Executor adapter that simulates sandboxed execution."""

from __future__ import annotations

import asyncio
from typing import Any

from orchestrator.models import Task


class MockExecutor:
    """Implements the :class:`orchestrator.pipeline.Executor` protocol.

    Simulates execution with a configurable delay.  Returns a mock
    output payload.  Useful for demos and integration tests.
    """

    def __init__(self, delay: float = 0.3) -> None:
        self._delay = delay

    async def execute(self, task: Task) -> dict[str, Any]:
        await asyncio.sleep(self._delay)
        return {
            "executor": "mock",
            "task_id": task.id,
            "output": f"Simulated execution of '{task.name}'",
            "exit_code": 0,
        }
