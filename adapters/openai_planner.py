"""OpenAIPlanner – LLM-backed Planner using OpenAI Chat Completions API."""

from __future__ import annotations

import json
import logging
from typing import Any

from observability.gen_ai_tracer import record_llm_call, record_response
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


class OpenAIPlanner:
    """Implements the :class:`orchestrator.pipeline.Planner` protocol
    using the OpenAI Chat Completions API.

    Falls back to a minimal echo plan if the API call fails.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o",
        max_tokens: int = 1024,
        base_url: str | None = None,
    ) -> None:
        try:
            import openai
        except ImportError as exc:
            raise ImportError(
                "openai package is required for OpenAIPlanner. "
                "Install with: pip install 'occp[openai]'"
            ) from exc

        kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url

        self._client = openai.AsyncOpenAI(**kwargs)
        self._model = model
        self._max_tokens = max_tokens
        logger.info("OpenAIPlanner initialized (model=%s)", model)

    async def create_plan(self, task: Task) -> dict[str, Any]:
        """Call OpenAI to generate an execution plan for *task*."""
        user_message = (
            f"Task: {task.name}\n"
            f"Description: {task.description}\n"
            f"Agent Type: {task.agent_type}\n"
            f"Risk Level: {task.risk_level.value}\n"
        )
        if task.metadata:
            user_message += f"Metadata: {json.dumps(task.metadata)}\n"

        try:
            with record_llm_call(
                "chat",
                model=self._model,
                system="openai",
                request_kwargs={
                    "max_tokens": self._max_tokens,
                    "temperature": 0.2,
                },
            ) as span:
                response = await self._client.chat.completions.create(
                    model=self._model,
                    max_tokens=self._max_tokens,
                    messages=[
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": user_message},
                    ],
                    temperature=0.2,
                    response_format={"type": "json_object"},
                )
                record_response(
                    span,
                    response=response,
                    usage=getattr(response, "usage", None),
                )

            raw = response.choices[0].message.content or ""
            raw = raw.strip()

            # Strip markdown code fence if present
            if raw.startswith("```"):
                lines = raw.split("\n")
                lines = [ln for ln in lines if not ln.strip().startswith("```")]
                raw = "\n".join(lines)

            plan = json.loads(raw)

            if "strategy" not in plan:
                plan["strategy"] = "llm"
            if "steps" not in plan or not isinstance(plan["steps"], list):
                plan["steps"] = [plan.get("description", task.description)]

            plan["_model"] = self._model
            plan["_provider"] = "openai"
            plan["_tokens"] = {
                "input": response.usage.prompt_tokens if response.usage else 0,
                "output": response.usage.completion_tokens if response.usage else 0,
            }

            logger.info(
                "OpenAIPlanner generated plan for task=%s (%d steps)",
                task.id,
                len(plan["steps"]),
            )
            return plan

        except json.JSONDecodeError:
            logger.warning("OpenAI response was not valid JSON, falling back")
            return {
                "strategy": "llm-raw",
                "description": raw if "raw" in dir() else task.description,
                "steps": [f"Execute: {task.description}"],
                "_model": self._model,
                "_provider": "openai",
                "_parse_error": True,
            }

        except Exception as exc:
            logger.error("OpenAIPlanner API call failed: %s", exc)
            return {
                "strategy": "fallback",
                "description": task.description,
                "steps": [
                    f"Analyze: {task.name}",
                    f"Execute: {task.description}",
                    "Validate results",
                ],
                "_provider": "openai",
                "_error": str(exc),
            }
