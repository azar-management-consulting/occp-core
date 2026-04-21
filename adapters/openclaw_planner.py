"""OpenClawPlanner -- uses OpenClaw Gateway agents for plan generation.

Shares the WebSocket connection from OpenClawExecutor to send planning
prompts to OpenClaw agents and parse their responses into OCCP plan format.

Implements the ``Planner`` protocol from ``orchestrator.pipeline``.
"""

from __future__ import annotations

import json
import logging
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from orchestrator.models import Task

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt version — bump this string whenever the system prompt changes.
# The version is embedded in the prompt header so it surfaces in planner
# logs and in OpenClaw session JSONL dumps for traceability.
# History:
#   (unset)                     → original prose-leaning prompt (pre-2026-04)
#   "2026-04-21-strict-json"    → strict JSON-only directive output (this file)
# ---------------------------------------------------------------------------
OPENCLAW_PROMPT_VERSION: str = "2026-04-21-strict-json"


# Structured tool schema injected into agent prompts so that agents can
# emit execution directives (MCP tools/call-style) rather than prose.
# The shape mirrors OCCP_SYSTEM_MANUAL.md §6 (14 MCP Bridge tools).
# This block is cache-friendly (stable JSON) and is prepended to the
# planning prompt as an agent system message.
AVAILABLE_TOOLS_SCHEMA: dict[str, Any] = {
    "available_tools": [
        {"name": "brain.status", "args_schema": {}, "risk": "low"},
        {"name": "brain.health", "args_schema": {}, "risk": "low"},
        {
            "name": "filesystem.read",
            "args_schema": {"path": "string (within /tmp/occp-workspace)"},
            "risk": "low",
        },
        {
            "name": "filesystem.write",
            "args_schema": {
                "path": "string (within /tmp/occp-workspace)",
                "content": "string",
            },
            "risk": "medium",
        },
        {
            "name": "filesystem.list",
            "args_schema": {"path": "string (within /tmp/occp-workspace)"},
            "risk": "low",
        },
        {
            "name": "http.get",
            "args_schema": {"url": "string (https:// URL)"},
            "risk": "low",
        },
        {
            "name": "http.post",
            "args_schema": {
                "url": "string (https:// URL)",
                "body": "object | string",
            },
            "risk": "medium",
        },
        {
            "name": "wordpress.get_site_info",
            "args_schema": {"site": "string (e.g. magyarorszag.ai)"},
            "risk": "low",
        },
        {
            "name": "wordpress.get_posts",
            "args_schema": {"site": "string", "per_page": "int (<=100)"},
            "risk": "low",
        },
        {
            "name": "wordpress.get_pages",
            "args_schema": {"site": "string", "per_page": "int (<=100)"},
            "risk": "low",
        },
        {
            "name": "wordpress.update_post",
            "args_schema": {
                "site": "string",
                "post_id": "int",
                "fields": "object (title/content/status)",
            },
            "risk": "high",
        },
        {"name": "node.list", "args_schema": {}, "risk": "low"},
        {
            "name": "node.status",
            "args_schema": {"node_id": "string"},
            "risk": "low",
        },
        {
            "name": "node.exec",
            "args_schema": {
                "node_id": "string",
                "command": "string (allowlisted only — see §6.1)",
            },
            "risk": "medium",
        },
    ],
    "response_format": {
        "narrative": (
            "string — human-readable explanation of the plan and outcome"
        ),
        "directives": (
            "array — structured execution_directives to execute AFTER policy "
            "approval. Each item: {tool, args, risk}. Omit or use [] if the "
            "task is purely analytical and requires no side effects."
        ),
    },
    "directive_example": {
        "directives": [
            {
                "tool": "wordpress.get_site_info",
                "args": {"site": "magyarorszag.ai"},
                "risk": "low",
            }
        ]
    },
}


# ---------------------------------------------------------------------------
# Response schema — MUST match the keys consumed by
# ``OpenClawExecutor._parse_execution_directives``:
#   * top-level key:  "directives"  (array)
#   * directive keys: "tool", "args", "risk"
#   * alt directive:  "exec_type" (accepted by executor as a tool alias)
# The executor's fenced-JSON regex requires the block to contain either
# "directives" or "exec_type" — keep at least one of those keys present.
# ---------------------------------------------------------------------------
RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["strategy", "description", "steps"],
    "properties": {
        "strategy": {"type": "string", "description": "Brief name of the approach"},
        "description": {"type": "string", "description": "One-sentence summary"},
        "steps": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Ordered action strings",
        },
        "directives": {
            "type": "array",
            "description": (
                "OPTIONAL structured MCP tool-calls executed by the Brain "
                "after policy approval. Omit or use [] if the task is "
                "purely analytical."
            ),
            "items": {
                "type": "object",
                "required": ["tool", "args"],
                "properties": {
                    "tool": {
                        "type": "string",
                        "description": (
                            "Whitelisted tool name from available_tools "
                            "(e.g. 'wordpress.get_site_info'). Alias: "
                            "'exec_type' — same semantics."
                        ),
                    },
                    "args": {"type": "object"},
                    "risk": {
                        "type": "string",
                        "enum": ["low", "medium", "high"],
                    },
                },
            },
        },
    },
}


# ---------------------------------------------------------------------------
# Few-shot examples — wire-format identical to what the executor parser
# expects (fenced ```json``` block containing the object). Keep them short
# to stay cache-friendly.
# ---------------------------------------------------------------------------
POSITIVE_EXAMPLE_1: dict[str, Any] = {
    "strategy": "wp-site-inspect",
    "description": "Fetch magyarorszag.ai site info via MCP Bridge.",
    "steps": [
        "Call wordpress.get_site_info for magyarorszag.ai",
        "Return summary fields to user",
    ],
    "directives": [
        {
            "tool": "wordpress.get_site_info",
            "args": {"site": "magyarorszag.ai"},
            "risk": "low",
        }
    ],
}

POSITIVE_EXAMPLE_2: dict[str, Any] = {
    "strategy": "analyze-only",
    "description": "Explain caching strategy; no side effects required.",
    "steps": [
        "Summarize cache layers",
        "Recommend TTL values",
    ],
    "directives": [],
}

# Negative: prose + markdown fence with language tag 'text' + missing keys.
NEGATIVE_EXAMPLE_BAD_OUTPUT: str = (
    "Sure! Here is the plan:\n"
    "1. Check site\n"
    "2. Update post\n"
    "```text\n{strategy: wp}\n```"
)
NEGATIVE_EXAMPLE_REASON: str = (
    "FAILS because: (a) conversational prose before/after JSON, "
    "(b) not a valid JSON object (unquoted keys), "
    "(c) fence language is 'text' not 'json', "
    "(d) missing required keys: description, steps, "
    "(e) executor's _FENCED_JSON_RE will NOT match — parser falls through "
    "to chat-text branch and directives are lost."
)


def _render_tools_schema_block() -> str:
    """Render the stable tool-schema + strict-JSON system block.

    Cache-friendly: all contents are deterministic JSON (stable key order)
    and a fixed prompt-version header.
    """
    header = (
        f"[SYSTEM: OpenClaw Planner v{OPENCLAW_PROMPT_VERSION}]\n"
        "HARD CONSTRAINT — JSON-ONLY OUTPUT\n"
        "You MUST respond with a single JSON object conforming to the schema\n"
        "below, wrapped in a fenced ```json``` block. NO markdown outside the\n"
        "fence, NO prose, NO explanation, NO apology, NO preface. The first\n"
        "three characters of your response MUST be the backtick sequence\n"
        "that opens the fence. The last three MUST close it.\n"
        "The object MUST contain the key \"directives\" (array, may be empty)\n"
        "so that the executor's JSON parser matches the fenced block.\n"
    )

    tools_block = (
        "\n[SYSTEM: available tools]\n"
        "Tool names in 'directives[].tool' MUST come from this whitelist.\n"
        "Do NOT invent tool names. Unknown tools are silently dropped by the\n"
        "executor (audit-logged).\n\n"
        + json.dumps(AVAILABLE_TOOLS_SCHEMA, indent=2, ensure_ascii=False)
    )

    schema_block = (
        "\n\n[SYSTEM: response schema — JSONSchema draft-07]\n"
        + json.dumps(RESPONSE_SCHEMA, indent=2, ensure_ascii=False)
    )

    examples_block = (
        "\n\n[SYSTEM: one-shot examples — COPY THIS WIRE FORMAT EXACTLY]\n\n"
        "# POSITIVE EXAMPLE 1 — action task with one directive\n"
        "User: Get site info for magyarorszag.ai.\n"
        "Assistant:\n"
        "```json\n"
        + json.dumps(POSITIVE_EXAMPLE_1, indent=2, ensure_ascii=False)
        + "\n```\n\n"
        "# POSITIVE EXAMPLE 2 — analytical task, empty directives\n"
        "User: Explain our caching strategy.\n"
        "Assistant:\n"
        "```json\n"
        + json.dumps(POSITIVE_EXAMPLE_2, indent=2, ensure_ascii=False)
        + "\n```\n\n"
        "# NEGATIVE EXAMPLE — DO NOT EMIT THIS\n"
        "Assistant:\n"
        + NEGATIVE_EXAMPLE_BAD_OUTPUT
        + "\n"
        "# " + NEGATIVE_EXAMPLE_REASON + "\n"
    )

    return header + tools_block + schema_block + examples_block


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

        # NOTE on structured-output flags:
        #   OpenClaw Gateway's chat.send RPC does NOT expose an OpenAI-style
        #   ``response_format={"type": "json_object"}`` nor an Anthropic-style
        #   ``tools`` + forced ``tool_choice`` argument — the upstream agent
        #   picks its own LLM backend. We therefore rely on the strict system
        #   prompt (_render_tools_schema_block) + fenced-JSON examples that
        #   match ``OpenClawExecutor._FENCED_JSON_RE`` exactly. If OpenClaw
        #   later exposes a JSON-mode knob in ``params``, wire it in here.
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
        """Build a structured planning prompt for the OpenClaw agent.

        The prompt starts with a stable, cache-friendly system block that
        enforces JSON-only output (schema + positive/negative one-shots),
        then appends task context, and closes with a reminder that the
        response MUST be a single fenced ```json``` block and nothing else.
        """
        lines = [
            _render_tools_schema_block(),
            "",
            "[TASK CONTEXT]",
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

        # Final reminder — the model tends to drift into prose without this.
        lines.extend([
            "",
            "[OUTPUT DIRECTIVE]",
            "Emit EXACTLY ONE fenced ```json``` block and nothing else.",
            "The JSON object MUST include the key \"directives\" (even if []).",
            "No prose. No apology. No trailing explanation.",
        ])

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
