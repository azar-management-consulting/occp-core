"""Agent Scheduler – manages concurrent agent execution slots."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Coroutine

from orchestrator.exceptions import AgentNotFoundError, SchedulerError
from orchestrator.models import AgentConfig, Task

logger = logging.getLogger(__name__)

AgentFactory = Callable[[AgentConfig], Coroutine[Any, Any, Any]]


class Scheduler:
    """Manages registered agents and dispatches tasks to them.

    Each :class:`AgentConfig` defines ``max_concurrent`` – the scheduler
    uses an :class:`asyncio.Semaphore` per agent type to enforce the limit.
    """

    def __init__(self) -> None:
        self._agents: dict[str, AgentConfig] = {}
        self._semaphores: dict[str, asyncio.Semaphore] = {}
        self._factories: dict[str, AgentFactory] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(
        self,
        config: AgentConfig,
        factory: AgentFactory,
    ) -> None:
        """Register an agent adapter with its factory coroutine."""
        self._agents[config.agent_type] = config
        self._semaphores[config.agent_type] = asyncio.Semaphore(
            config.max_concurrent
        )
        self._factories[config.agent_type] = factory
        logger.info(
            "Registered agent type=%s max_concurrent=%d",
            config.agent_type,
            config.max_concurrent,
        )

    def unregister(self, agent_type: str) -> None:
        """Remove a previously registered agent type."""
        self._agents.pop(agent_type, None)
        self._semaphores.pop(agent_type, None)
        self._factories.pop(agent_type, None)

    @property
    def registered_types(self) -> list[str]:
        return list(self._agents)

    def get_agent(self, agent_type: str) -> AgentConfig | None:
        """Return config for a single registered agent type, or None."""
        return self._agents.get(agent_type)

    def list_agents(self) -> list[AgentConfig]:
        """Return all registered agent configs."""
        return list(self._agents.values())

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    async def dispatch(self, task: Task) -> Any:
        """Dispatch *task* to the appropriate agent, respecting concurrency."""
        agent_type = task.agent_type
        if agent_type not in self._agents:
            raise AgentNotFoundError(agent_type)

        config = self._agents[agent_type]
        sem = self._semaphores[agent_type]
        factory = self._factories[agent_type]

        try:
            async with sem:
                logger.info(
                    "Dispatching task=%s to agent=%s", task.id, agent_type
                )
                return await asyncio.wait_for(
                    factory(config),
                    timeout=config.timeout_seconds,
                )
        except asyncio.TimeoutError as exc:
            raise SchedulerError(
                f"Agent {agent_type} timed out after {config.timeout_seconds}s "
                f"for task {task.id}"
            ) from exc

    async def dispatch_many(self, tasks: list[Task]) -> list[Any]:
        """Dispatch multiple tasks concurrently, return results in order."""
        return list(await asyncio.gather(
            *(self.dispatch(t) for t in tasks),
            return_exceptions=True,
        ))
