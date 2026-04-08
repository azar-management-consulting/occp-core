"""AnthropicPlanner – real LLM-backed Planner using Anthropic Claude API."""

from __future__ import annotations

import json
import logging
from typing import Any

from orchestrator.models import Task

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are the Planning Agent for OCCP (OpenCloud Control Plane).
Given a task, produce a structured execution plan as JSON with these keys:
- "strategy": a short label for the approach (e.g., "sequential", "parallel", "analysis")
- "description": one-sentence summary of what you'll do
- "steps": list of 3-8 concrete action strings
- "risk_notes": optional list of risk considerations
- "estimated_duration": optional human-readable estimate

Respond with ONLY valid JSON. No markdown, no explanation."""


class ClaudePlanner:
    """Implements the :class:`orchestrator.pipeline.Planner` protocol
    using the Anthropic Messages API.

    Falls back to a minimal echo plan if the API call fails.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-6",
        max_tokens: int = 1024,
    ) -> None:
        try:
            import anthropic
        except ImportError as exc:
            raise ImportError(
                "anthropic package is required for ClaudePlanner. "
                "Install with: pip install 'occp[llm]'"
            ) from exc

        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens
        logger.info("ClaudePlanner initialized (model=%s)", model)

    async def create_plan(self, task: Task) -> dict[str, Any]:
        """Call Claude to generate an execution plan for *task*."""
        user_message = (
            f"Task: {task.name}\n"
            f"Description: {task.description}\n"
            f"Agent Type: {task.agent_type}\n"
            f"Risk Level: {task.risk_level.value}\n"
        )
        if task.metadata:
            user_message += f"Metadata: {json.dumps(task.metadata)}\n"

        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )

            raw = response.content[0].text.strip()

            # Strip markdown code fence if present
            if raw.startswith("```"):
                lines = raw.split("\n")
                # Remove first and last lines (``` markers)
                lines = [l for l in lines if not l.strip().startswith("```")]
                raw = "\n".join(lines)

            plan = json.loads(raw)

            # Ensure required keys
            if "strategy" not in plan:
                plan["strategy"] = "llm"
            if "steps" not in plan or not isinstance(plan["steps"], list):
                plan["steps"] = [plan.get("description", task.description)]

            plan["_model"] = self._model
            plan["_tokens"] = {
                "input": response.usage.input_tokens,
                "output": response.usage.output_tokens,
            }

            logger.info(
                "ClaudePlanner generated plan for task=%s (%d steps, %d tokens)",
                task.id,
                len(plan["steps"]),
                response.usage.input_tokens + response.usage.output_tokens,
            )
            return plan

        except json.JSONDecodeError:
            logger.warning("Claude response was not valid JSON, falling back to raw plan")
            return {
                "strategy": "llm-raw",
                "description": raw if "raw" in dir() else task.description,
                "steps": [f"Execute: {task.description}"],
                "_model": self._model,
                "_parse_error": True,
            }

        except Exception as exc:
            logger.error("ClaudePlanner API call failed: %s", exc)
            # Fallback to echo-style plan
            return {
                "strategy": "fallback",
                "description": task.description,
                "steps": [
                    f"Analyze: {task.name}",
                    f"Execute: {task.description}",
                    "Validate results",
                ],
                "_error": str(exc),
            }
