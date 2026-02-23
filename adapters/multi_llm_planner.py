"""MultiLLMPlanner – cascading failover across multiple LLM providers.

Routes planning requests through a prioritized chain of LLM planners.
If the primary fails, automatically falls over to the next provider.
Tracks per-provider health metrics for intelligent routing.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from orchestrator.models import Task

logger = logging.getLogger(__name__)


@dataclass
class ProviderHealth:
    """Tracks health metrics for a single LLM provider."""

    name: str
    total_calls: int = 0
    failures: int = 0
    total_latency: float = 0.0
    last_failure: float | None = None
    consecutive_failures: int = 0

    # Circuit breaker: disable provider after N consecutive failures
    max_consecutive_failures: int = 3
    cooldown_seconds: float = 300.0  # 5 minutes

    @property
    def is_healthy(self) -> bool:
        """Provider is healthy if not in circuit-breaker cooldown."""
        if self.consecutive_failures < self.max_consecutive_failures:
            return True
        if self.last_failure is None:
            return True
        elapsed = time.monotonic() - self.last_failure
        return elapsed >= self.cooldown_seconds

    @property
    def avg_latency(self) -> float:
        """Average response latency in seconds."""
        successful = self.total_calls - self.failures
        if successful <= 0:
            return 0.0
        return self.total_latency / successful

    @property
    def success_rate(self) -> float:
        """Success rate as a percentage."""
        if self.total_calls == 0:
            return 100.0
        return ((self.total_calls - self.failures) / self.total_calls) * 100

    def record_success(self, latency: float) -> None:
        """Record a successful call."""
        self.total_calls += 1
        self.total_latency += latency
        self.consecutive_failures = 0

    def record_failure(self) -> None:
        """Record a failed call."""
        self.total_calls += 1
        self.failures += 1
        self.consecutive_failures += 1
        self.last_failure = time.monotonic()


class MultiLLMPlanner:
    """Cascading multi-provider LLM planner with automatic failover.

    Features:
    - Priority-ordered provider chain (Anthropic → OpenAI → Echo)
    - Circuit breaker per provider (auto-disable after N failures)
    - Per-provider health metrics (latency, success rate)
    - Transparent failover with full audit trail in plan metadata

    Usage::

        planner = MultiLLMPlanner()
        planner.add_provider("anthropic", claude_planner, priority=1)
        planner.add_provider("openai", openai_planner, priority=2)
        planner.add_provider("echo", echo_planner, priority=99)

        plan = await planner.create_plan(task)
        # plan["_provider_chain"] shows which providers were tried
    """

    def __init__(self) -> None:
        self._providers: list[tuple[int, str, Any]] = []  # (priority, name, planner)
        self._health: dict[str, ProviderHealth] = {}

    def add_provider(
        self,
        name: str,
        planner: Any,
        priority: int = 50,
        *,
        max_failures: int = 3,
        cooldown: float = 300.0,
    ) -> None:
        """Register a planner provider with given priority (lower = higher priority)."""
        self._providers.append((priority, name, planner))
        self._providers.sort(key=lambda x: x[0])
        self._health[name] = ProviderHealth(
            name=name,
            max_consecutive_failures=max_failures,
            cooldown_seconds=cooldown,
        )
        logger.info(
            "MultiLLMPlanner: registered provider=%s priority=%d",
            name, priority,
        )

    def get_health(self) -> dict[str, dict[str, Any]]:
        """Return health metrics for all registered providers."""
        return {
            name: {
                "healthy": h.is_healthy,
                "total_calls": h.total_calls,
                "failures": h.failures,
                "success_rate": round(h.success_rate, 1),
                "avg_latency_ms": round(h.avg_latency * 1000, 1),
                "consecutive_failures": h.consecutive_failures,
            }
            for name, h in self._health.items()
        }

    async def create_plan(self, task: Task) -> dict[str, Any]:
        """Route planning to highest-priority healthy provider, with failover."""
        chain: list[dict[str, Any]] = []
        last_error: str | None = None

        for _priority, name, planner in self._providers:
            health = self._health[name]

            if not health.is_healthy:
                chain.append({
                    "provider": name,
                    "status": "circuit_open",
                    "consecutive_failures": health.consecutive_failures,
                })
                logger.info(
                    "MultiLLMPlanner: skipping %s (circuit breaker open)", name
                )
                continue

            try:
                t0 = time.monotonic()
                plan = await planner.create_plan(task)
                latency = time.monotonic() - t0

                # Check if the planner returned a fallback/error plan
                if plan.get("_error"):
                    raise RuntimeError(plan["_error"])

                health.record_success(latency)
                chain.append({
                    "provider": name,
                    "status": "success",
                    "latency_ms": round(latency * 1000, 1),
                })
                plan["_provider"] = name
                plan["_provider_chain"] = chain
                plan["_failover"] = len(chain) > 1

                logger.info(
                    "MultiLLMPlanner: task=%s routed to %s (%.0fms)",
                    task.id, name, latency * 1000,
                )
                return plan

            except Exception as exc:
                health.record_failure()
                last_error = str(exc)
                chain.append({
                    "provider": name,
                    "status": "failed",
                    "error": last_error,
                })
                logger.warning(
                    "MultiLLMPlanner: %s failed for task=%s: %s",
                    name, task.id, exc,
                )
                continue

        # All providers exhausted — return emergency fallback
        logger.error(
            "MultiLLMPlanner: all providers exhausted for task=%s", task.id,
        )
        return {
            "strategy": "emergency-fallback",
            "description": task.description,
            "steps": [
                f"Analyze: {task.name}",
                f"Execute: {task.description}",
                "Validate results",
            ],
            "_provider": "none",
            "_provider_chain": chain,
            "_failover": True,
            "_all_providers_exhausted": True,
            "_last_error": last_error,
        }
