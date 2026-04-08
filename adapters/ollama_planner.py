"""OllamaPlanner — REQ-CORE-04: Local Model Support via Ollama HTTP API.

Implements the Planner protocol using the Ollama REST API for local LLM
inference. Supports model selection, timeout configuration, and automatic
fallback when Ollama is unavailable.

Usage::

    planner = OllamaPlanner(model="llama3.1:8b")
    plan = await planner.create_plan(task)
"""

from __future__ import annotations

import json
import logging
import time
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


class OllamaPlannerError(Exception):
    """Ollama planner-specific errors."""


class OllamaPlanner:
    """Implements the :class:`orchestrator.pipeline.Planner` protocol
    using the Ollama HTTP API (``/api/chat``).

    Features:
    - Local model inference (no cloud dependency)
    - Configurable model, temperature, and timeout
    - JSON response parsing with fallback
    - Latency and token tracking in plan metadata
    - Graceful degradation when Ollama is unavailable
    """

    def __init__(
        self,
        model: str = "llama3.1:8b",
        base_url: str = "http://localhost:11434",
        timeout: float = 120.0,
        temperature: float = 0.2,
    ) -> None:
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._temperature = temperature
        logger.info(
            "OllamaPlanner initialized (model=%s base_url=%s)",
            model,
            base_url,
        )

    @property
    def model(self) -> str:
        return self._model

    @property
    def base_url(self) -> str:
        return self._base_url

    async def is_available(self) -> bool:
        """Check if Ollama server is reachable."""
        try:
            import aiohttp
        except ImportError:
            return False

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self._base_url}/api/tags",
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    return resp.status == 200
        except Exception:
            return False

    async def list_models(self) -> list[str]:
        """List available models from Ollama server."""
        try:
            import aiohttp
        except ImportError:
            raise OllamaPlannerError(
                "aiohttp package is required for OllamaPlanner. "
                "Install with: pip install aiohttp"
            )

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self._base_url}/api/tags",
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status != 200:
                        return []
                    data = await resp.json()
                    return [m["name"] for m in data.get("models", [])]
        except Exception as exc:
            logger.warning("OllamaPlanner: failed to list models: %s", exc)
            return []

    async def create_plan(self, task: Task) -> dict[str, Any]:
        """Call Ollama to generate an execution plan for *task*."""
        try:
            import aiohttp
        except ImportError:
            raise OllamaPlannerError(
                "aiohttp package is required for OllamaPlanner. "
                "Install with: pip install aiohttp"
            )

        user_message = (
            f"Task: {task.name}\n"
            f"Description: {task.description}\n"
            f"Agent Type: {task.agent_type}\n"
            f"Risk Level: {task.risk_level.value}\n"
        )
        if task.metadata:
            user_message += f"Metadata: {json.dumps(task.metadata)}\n"

        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            "stream": False,
            "format": "json",
            "options": {
                "temperature": self._temperature,
            },
        }

        try:
            t0 = time.monotonic()
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self._base_url}/api/chat",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self._timeout),
                ) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        raise OllamaPlannerError(
                            f"Ollama API returned {resp.status}: {body[:200]}"
                        )
                    data = await resp.json()

            latency = time.monotonic() - t0
            raw = data.get("message", {}).get("content", "")
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
            plan["_provider"] = "ollama"
            plan["_latency_ms"] = round(latency * 1000, 1)

            # Extract token counts if available
            if "eval_count" in data:
                plan["_tokens"] = {
                    "prompt": data.get("prompt_eval_count", 0),
                    "completion": data.get("eval_count", 0),
                }

            logger.info(
                "OllamaPlanner generated plan for task=%s (%d steps, %.0fms)",
                task.id,
                len(plan["steps"]),
                latency * 1000,
            )
            return plan

        except json.JSONDecodeError:
            logger.warning("Ollama response was not valid JSON, falling back")
            return {
                "strategy": "llm-raw",
                "description": raw if "raw" in dir() else task.description,
                "steps": [f"Execute: {task.description}"],
                "_model": self._model,
                "_provider": "ollama",
                "_parse_error": True,
            }

        except OllamaPlannerError:
            raise

        except Exception as exc:
            logger.error("OllamaPlanner API call failed: %s", exc)
            return {
                "strategy": "fallback",
                "description": task.description,
                "steps": [
                    f"Analyze: {task.name}",
                    f"Execute: {task.description}",
                    "Validate results",
                ],
                "_model": self._model,
                "_provider": "ollama",
                "_error": str(exc),
            }
