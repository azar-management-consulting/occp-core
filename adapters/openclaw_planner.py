"""OpenClawPlanner -- uses OpenClaw Gateway agents for plan generation.

Shares the WebSocket connection from OpenClawExecutor to send planning
prompts to OpenClaw agents and parse their responses into OCCP plan format.

Implements the ``Planner`` protocol from ``orchestrator.pipeline``.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from orchestrator.models import Task

logger = logging.getLogger(__name__)


class OpenClawPlanner:
    """Planner adapter that delegates plan creation to OpenClaw agents.

    Requires a connected OpenClawExecutor to share its WebSocket connection.

    Usage::

        from adapters.openclaw_executor import OpenClawExecutor

        executor = OpenClawExecutor()
        planner = OpenClawPlanner(executor)
        plan = await planner.create_plan(task)
    """

    def __init__(
        self,
        executor: Any,
        *,
        planning_agent: str = "general",
        timeout: float = 60.0,
    ) -> None:
        """Initialize with a reference to an OpenClawExecutor.

        Args:
            executor: An OpenClawExecutor instance (shares its WS connection).
            planning_agent: The OpenClaw agent name to use for planning.
            timeout: Maximum time for plan generation in seconds.
        """
        self._executor = executor
        self._planning_agent = planning_agent
        self._timeout = timeout

    async def create_plan(self, task: Task) -> dict[str, Any]:
        """Create an execution plan by prompting an OpenClaw agent.

        Sends a structured planning prompt to the configured OpenClaw agent
        and parses the response into OCCP's plan format.
        """
        t0 = time.monotonic()

        # Ensure the shared connection is alive
        conn = self._executor.connection
        if not conn.is_connected:
            await self._executor._ensure_connected()

        # Build planning prompt
        prompt = self._build_planning_prompt(task)

        try:
            result = await conn.send_chat(
                message=prompt,
                agent=self._planning_agent,
                session_id=f"plan-{task.id}",
                timeout=self._timeout,
            )

            latency = time.monotonic() - t0
            plan = self._parse_plan_response(task, result)

            plan["_provider"] = "openclaw"
            plan["_planning_agent"] = self._planning_agent
            plan["_latency_ms"] = round(latency * 1000, 1)

            logger.info(
                "OpenClawPlanner: task=%s plan created in %.1fs (%d steps)",
                task.id,
                latency,
                len(plan.get("steps", [])),
            )
            return plan

        except Exception as exc:
            latency = time.monotonic() - t0
            logger.warning(
                "OpenClawPlanner: task=%s failed after %.1fs: %s",
                task.id,
                latency,
                exc,
            )
            # Return error plan so MultiLLMPlanner can failover
            return {
                "strategy": "openclaw-failed",
                "description": task.description,
                "steps": [
                    f"Analyze: {task.name}",
                    f"Execute: {task.description}",
                    "Validate results",
                ],
                "_error": str(exc),
                "_provider": "openclaw",
                "_latency_ms": round(latency * 1000, 1),
            }

    def _build_planning_prompt(self, task: Task) -> str:
        """Build a structured planning prompt for the OpenClaw agent."""
        lines = [
            "Create an execution plan for the following task.",
            "Respond with a JSON object containing:",
            '  - "strategy": a brief name for the approach',
            '  - "description": one-sentence summary',
            '  - "steps": array of strings, each being a short action description',
            "",
            f"Task Name: {task.name}",
            f"Task Description: {task.description}",
            f"Agent Type: {task.agent_type}",
            f"Risk Level: {task.risk_level.value}",
        ]

        if task.metadata:
            for key in ("context", "constraints", "instructions"):
                val = task.metadata.get(key)
                if val:
                    lines.append(f"{key.capitalize()}: {val}")

        return "\n".join(lines)

    @staticmethod
    def _parse_plan_response(
        task: Task, result: dict[str, Any]
    ) -> dict[str, Any]:
        """Parse the OpenClaw agent response into OCCP plan format.

        Tries to extract a JSON plan from the response content.
        Falls back to a simple text-based plan if JSON parsing fails.
        """
        # Extract text content from the response
        content = ""
        if isinstance(result.get("content"), str):
            content = result["content"]
        elif isinstance(result.get("message"), str):
            content = result["message"]
        elif isinstance(result.get("text"), str):
            content = result["text"]
        elif isinstance(result.get("output"), str):
            content = result["output"]

        # Try to parse JSON from the response
        if content:
            # Look for JSON block in markdown code fences
            json_str = content
            if "```json" in content:
                start = content.index("```json") + 7
                end = content.index("```", start) if "```" in content[start:] else len(content)
                json_str = content[start:start + (end - start)]
            elif "```" in content:
                start = content.index("```") + 3
                end = content.index("```", start) if "```" in content[start:] else len(content)
                json_str = content[start:start + (end - start)]

            try:
                parsed = json.loads(json_str.strip())
                if isinstance(parsed, dict):
                    # Ensure required fields
                    raw_steps = parsed.get("steps", [])
                    # Normalize steps to plain strings
                    steps: list[str] = []
                    for s in raw_steps:
                        if isinstance(s, str):
                            steps.append(s)
                        elif isinstance(s, dict):
                            steps.append(
                                s.get("description", s.get("name", str(s)))
                            )
                        else:
                            steps.append(str(s))
                    plan: dict[str, Any] = {
                        "strategy": parsed.get("strategy", "openclaw-plan"),
                        "description": parsed.get(
                            "description", task.description
                        ),
                        "steps": steps,
                    }
                    # Preserve any extra fields
                    for k, v in parsed.items():
                        if k not in plan:
                            plan[k] = v
                    return plan
            except (json.JSONDecodeError, ValueError):
                pass

        # Fallback: create a simple plan from the text content
        steps = []
        if content:
            # Split content into lines and use non-empty ones as steps
            for line in content.strip().split("\n"):
                line = line.strip()
                if line and not line.startswith("#"):
                    # Remove common list prefixes
                    for prefix in ("- ", "* ", ". "):
                        if len(line) > 2 and line[1:3] == prefix[1:]:
                            line = line[2:].strip()
                            break
                    if line:
                        steps.append(line)

        if not steps:
            steps = [
                f"Analyze: {task.name}",
                f"Execute: {task.description}",
                "Validate results",
            ]

        return {
            "strategy": "openclaw-text-plan",
            "description": task.description,
            "steps": steps,
        }
