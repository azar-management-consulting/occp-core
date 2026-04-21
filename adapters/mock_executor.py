"""MockExecutor – demo Executor adapter that simulates sandboxed execution.

Note: this executor performs NO real LLM calls — it simply returns a static
payload after a configurable delay. BudgetPolicy pre-flight check() and
post-flight record_spend() are therefore intentionally NOT wired here; doing
so would produce spurious spend accounting for a simulation. See
:mod:`policy_engine.budget_policy` and :mod:`adapters.openclaw_executor` for
the wired path.
"""

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
