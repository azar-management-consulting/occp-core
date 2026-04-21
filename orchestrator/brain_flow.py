"""Brain conversation flow engine — the 7-phase orchestrator.

Manages the full conversation lifecycle between Henry and Brian:
    INTAKE -> UNDERSTAND -> PLAN -> CONFIRM -> DISPATCH -> MONITOR -> DELIVER -> COMPLETED

Brian NEVER executes directly. He plans, confirms with Henry, dispatches to
OpenClaw agents, monitors progress, and delivers results.

Each conversation is tracked as a BrainConversation with isolated state.
Conversations auto-expire after 30 minutes of inactivity.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

from store.conversation_store import ConversationStore

# L6 kill switch — process-global hard-stop (import-safe)
try:
    from evaluation.kill_switch import require_kill_switch_inactive as _require_ks_inactive
except Exception:  # noqa: BLE001
    _require_ks_inactive = None  # type: ignore[assignment]

if TYPE_CHECKING:
    from adapters.confirmation_gate import ConfirmationGate
    from orchestrator.project_manager import ProjectManager
    from orchestrator.quality_gate import QualityGate
    from orchestrator.task_router import RouteDecision, TaskRouter

logger = logging.getLogger(__name__)

# Conversation expiry (seconds)
CONVERSATION_EXPIRY_SECONDS = 1800  # 30 minutes
MAX_CONVERSATIONS_PER_USER = 10


class FlowPhase(str, Enum):
    """Phases of the Brain conversation flow."""

    INTAKE = "intake"
    UNDERSTAND = "understand"
    PLAN = "plan"
    CONFIRM = "confirm"
    DISPATCH = "dispatch"
    MONITOR = "monitor"
    DELIVER = "deliver"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass
class BrainConversation:
    """Tracks a full conversation flow between Henry and Brian."""

    conversation_id: str
    user_id: str
    phase: FlowPhase = FlowPhase.INTAKE
    original_message: str = ""
    clarifying_questions: list[str] = field(default_factory=list)
    clarifying_answers: list[str] = field(default_factory=list)
    execution_plan: Optional[dict[str, Any]] = None
    plan_approved: bool = False
    dispatched_tasks: list[str] = field(default_factory=list)
    results: list[dict[str, Any]] = field(default_factory=list)
    feedback_score: Optional[int] = None
    project_id: Optional[str] = None
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def touch(self) -> None:
        """Update the last activity timestamp."""
        self.updated_at = datetime.now(timezone.utc)

    def is_expired(self) -> bool:
        """Check if this conversation has expired due to inactivity."""
        elapsed = (datetime.now(timezone.utc) - self.updated_at).total_seconds()
        return elapsed > CONVERSATION_EXPIRY_SECONDS

    def is_terminal(self) -> bool:
        """Check if this conversation is in a terminal state."""
        return self.phase in (FlowPhase.COMPLETED, FlowPhase.CANCELLED)


class BrainFlowEngine:
    """The core engine managing conversations between Henry and Brian.

    Brian NEVER executes directly. He plans, confirms, dispatches, monitors.

    Args:
        task_router: Routes tasks to the correct agent(s).
        quality_gate: Quality assurance for agent outputs.
        project_manager: Manages project contexts.
        confirmation_gate: Human approval gate.
    """

    __kill_switch_guarded__ = True

    def __init__(
        self,
        task_router: TaskRouter,
        quality_gate: QualityGate,
        project_manager: ProjectManager,
        confirmation_gate: ConfirmationGate,
        conversation_store: ConversationStore | None = None,
        approval_store: Any = None,
        pipeline: Any = None,
        task_store: Any = None,
    ) -> None:
        self._conversations: dict[str, BrainConversation] = {}
        # user_id -> list of conversation_ids (most recent last)
        self._user_conversations: dict[str, list[str]] = {}
        self._task_router = task_router
        self._quality_gate = quality_gate
        self._project_manager = project_manager
        self._confirmation_gate = confirmation_gate
        self._conversation_store = conversation_store
        self._approval_store = approval_store
        self._pipeline = pipeline
        self._task_store = task_store

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def process_message(
        self,
        user_id: str,
        message: str,
        conversation_id: str | None = None,
    ) -> dict[str, Any]:
        """Main entry point for processing a message from Henry.

        Returns a response dict:
            - text: str (what Brian says)
            - phase: str (current phase name)
            - actions: list[str] (suggested actions/buttons)
            - conversation_id: str
            - metadata: dict
        """
        # EU AI Act Art.14(4)(e): kill-switch guard at entry point
        if _require_ks_inactive is not None:
            _require_ks_inactive()

        # Expire stale conversations
        self._expire_conversations(user_id)

        # Get or create conversation
        conv = self._get_or_create_conversation(user_id, message, conversation_id)
        conv.touch()
        await self._persist_conversation(conv)

        # Route based on current phase
        handler = self._phase_handlers().get(conv.phase)
        if handler is None:
            # Terminal or unknown phase — start new conversation
            conv = self._create_conversation(user_id, message)
            handler = self._phase_handlers()[FlowPhase.INTAKE]

        result = await handler(conv, message)
        # Persist after phase handler (captures all state changes)
        await self._persist_conversation(conv)
        # Only set conversation_id if handler didn't already set it
        if "conversation_id" not in result:
            result["conversation_id"] = conv.conversation_id
        return result

    def get_conversation(self, conversation_id: str) -> BrainConversation | None:
        """Get a conversation by ID."""
        return self._conversations.get(conversation_id)

    def get_active_conversations(self, user_id: str) -> list[BrainConversation]:
        """Get all active (non-terminal, non-expired) conversations for a user."""
        self._expire_conversations(user_id)
        conv_ids = self._user_conversations.get(user_id, [])
        result = []
        for cid in conv_ids:
            conv = self._conversations.get(cid)
            if conv and not conv.is_terminal() and not conv.is_expired():
                result.append(conv)
        return result

    @property
    def conversation_count(self) -> int:
        """Total number of tracked conversations."""
        return len(self._conversations)

    # ------------------------------------------------------------------
    # Phase handlers
    # ------------------------------------------------------------------

    def _phase_handlers(self) -> dict:
        """Map phases to their handler methods."""
        return {
            FlowPhase.INTAKE: self._handle_intake,
            FlowPhase.UNDERSTAND: self._handle_understand,
            FlowPhase.CONFIRM: self._handle_confirm,
            FlowPhase.DISPATCH: self._handle_dispatch_phase,
            FlowPhase.MONITOR: self._handle_monitor,
            FlowPhase.DELIVER: self._handle_deliver,
        }

    async def _handle_intake(
        self, conv: BrainConversation, message: str
    ) -> dict[str, Any]:
        """Phase 1: Analyze the incoming message."""
        conv.original_message = message

        # Use TaskRouter to classify
        route = self._task_router.route(message)

        # Check if we need clarification
        if self._needs_clarification(message, route):
            conv.phase = FlowPhase.UNDERSTAND
            questions = self._generate_clarifying_questions(message, route)
            conv.clarifying_questions = questions
            questions_text = "\n".join(
                f"{i + 1}. {q}" for i, q in enumerate(questions)
            )
            return {
                "text": (
                    "\U0001f9e0 Brian the Brain\n\n"
                    "Ertem a feladatot! Mielott nekiallok, par kerdes:\n\n"
                    f"{questions_text}"
                ),
                "phase": "understand",
                "actions": ["valaszolj", "ugorjuk at"],
                "metadata": {"route": route.to_dict()},
            }

        # Skip to plan
        return await self._create_plan(conv, route)

    async def _handle_understand(
        self, conv: BrainConversation, message: str
    ) -> dict[str, Any]:
        """Phase 2: Process clarifying answers."""
        normalized = message.lower().strip()

        # Check for skip
        if any(
            k in normalized
            for k in ["ugorjuk", "skip", "hagyd", "mindegy", "ugorjuk at"]
        ):
            route = self._task_router.route(conv.original_message)
            return await self._create_plan(conv, route)

        conv.clarifying_answers.append(message)

        if len(conv.clarifying_answers) >= len(conv.clarifying_questions):
            # All questions answered, create plan
            combined = (
                conv.original_message + " " + " ".join(conv.clarifying_answers)
            )
            route = self._task_router.route(combined)
            return await self._create_plan(conv, route)

        # Next question
        idx = len(conv.clarifying_answers)
        return {
            "text": (
                "\U0001f9e0 Brian the Brain\n\n"
                f"Koszi! Kovetkezo kerdes:\n\n{conv.clarifying_questions[idx]}"
            ),
            "phase": "understand",
            "actions": ["valaszolj"],
            "metadata": {},
        }

    async def _create_plan(
        self, conv: BrainConversation, route: RouteDecision
    ) -> dict[str, Any]:
        """Phase 3: Create and present execution plan."""
        steps = self._break_down_steps(conv.original_message, route)
        plan = {
            "primary_agent": route.primary_agent,
            "support_agents": route.support_agents,
            "risk_level": route.risk_level,
            "estimated_duration": route.estimated_duration,
            "steps": steps,
            "confidence": route.confidence,
            "matched_workflow": route.matched_workflow,
        }
        conv.execution_plan = plan
        conv.phase = FlowPhase.CONFIRM

        # Persist pending approval for MEDIUM/HIGH/CRITICAL risk
        if self._approval_store and route.risk_level in ("medium", "high", "critical"):
            try:
                plan_summary = f"{route.primary_agent} + {', '.join(route.support_agents)}: {conv.original_message[:200]}"
                await self._approval_store.save(
                    task_id=conv.conversation_id,
                    chat_id=0,  # API path, not Telegram
                    plan_summary=plan_summary,
                    risk_level=route.risk_level,
                    agent_type=route.primary_agent,
                    timeout_seconds=300,
                )
                logger.info(
                    "Pending approval saved: conv=%s risk=%s",
                    conv.conversation_id, route.risk_level,
                )
            except Exception as exc:
                logger.warning("Failed to persist pending approval: %s", exc)

        # Format plan for Henry
        agents_str = f"**{route.primary_agent}**"
        if route.support_agents:
            agents_str += " + " + ", ".join(route.support_agents)

        steps_str = "\n".join(
            f"  {i + 1}. {s['description']}" for i, s in enumerate(steps)
        )

        risk_emoji = {
            "low": "\u2705",
            "medium": "\u26a0\ufe0f",
            "high": "\U0001f6a8",
            "critical": "\U0001f6d1",
        }
        risk_display = risk_emoji.get(route.risk_level, "\u2753")

        text = (
            "\U0001f9e0 Brian the Brain\n\n"
            "\U0001f4cb **Terv kesz!**\n\n"
            f"\U0001f916 Agentek: {agents_str}\n"
            f"\u26a1 Kockazat: {risk_display} {route.risk_level}\n"
            f"\u23f1 Becsult ido: {route.estimated_duration}\n\n"
            f"\U0001f4dd Lepesek:\n{steps_str}\n\n"
            "Indithatom?"
        )

        return {
            "text": text,
            "phase": "confirm",
            "actions": ["igen", "modositsd", "megsem"],
            "metadata": {"plan": plan},
        }

    async def _handle_confirm(
        self, conv: BrainConversation, message: str
    ) -> dict[str, Any]:
        """Phase 4: Handle Henry's approval/modification/cancel."""
        normalized = message.lower().strip()

        approve_keywords = {
            "igen", "ok", "oke", "go", "rajta", "inditsd", "csinald",
            "mehet", "jo", "yes", "start", "approve", "rendben",
            "jovahagyom", "proceed",
        }
        cancel_keywords = {
            "nem", "megsem", "cancel", "stop", "hagyd", "ne", "megse",
        }
        modify_keywords = {"modosit", "valtoztat", "mas", "inkabb", "cserel"}

        # Use word-boundary matching to avoid false positives
        words = set(normalized.split())

        if words & approve_keywords or normalized in approve_keywords:
            conv.plan_approved = True
            conv.phase = FlowPhase.DISPATCH
            # Update approval store if MEDIUM+ risk
            if self._approval_store:
                try:
                    await self._approval_store.update_status(conv.conversation_id, "approved")
                except Exception as exc:
                    logger.warning("Failed to update approval status: %s", exc)
            return await self._dispatch_tasks(conv)

        if words & cancel_keywords or normalized in cancel_keywords:
            conv.phase = FlowPhase.CANCELLED
            return {
                "text": (
                    "\U0001f9e0 Brian the Brain\n\n"
                    "\u274c Rendben, leallitva. Szolj ha mast szeretnel!"
                ),
                "phase": "cancelled",
                "actions": [],
                "metadata": {},
            }

        if any(k in normalized for k in modify_keywords):
            return {
                "text": (
                    "\U0001f9e0 Brian the Brain\n\n"
                    "Mit valtoztassak a tervben? (agent, lepesek, prioritas)"
                ),
                "phase": "confirm",
                "actions": ["valaszolj"],
                "metadata": {},
            }

        # Treat as modification — re-route with additional context
        route = self._task_router.route(conv.original_message + " " + message)
        return await self._create_plan(conv, route)

    async def _dispatch_tasks(
        self, conv: BrainConversation
    ) -> dict[str, Any]:
        """Phase 5: Dispatch tasks to agents via Pipeline.run().

        ISS-001 FIX: Previously this method only generated task_ids and
        returned a text message. Now it actually creates Task objects and
        runs them through the Verified Autonomy Pipeline (Plan→Gate→
        Execute→Validate→Ship), collecting real results.

        If no pipeline is wired, falls back to the old text-only behavior.
        """
        from orchestrator.models import Task, RiskLevel

        plan = conv.execution_plan
        if not plan:
            conv.phase = FlowPhase.CANCELLED
            return {
                "text": (
                    "\U0001f9e0 Brian the Brain\n\n"
                    "Nincs vegrehajtasi terv. Szolj ha ujra probalnad!"
                ),
                "phase": "cancelled",
                "actions": [],
                "metadata": {},
            }

        agents_working = plan["primary_agent"]
        support = plan.get("support_agents", [])
        if support:
            agents_working += ", " + ", ".join(support)

        # If no pipeline wired, fall back to text-only (old behavior)
        if self._pipeline is None:
            task_ids = [self._generate_task_id() for _ in plan.get("steps", [])]
            conv.dispatched_tasks = task_ids
            conv.phase = FlowPhase.MONITOR
            return {
                "text": (
                    "\U0001f9e0 Brian the Brain\n\n"
                    "\U0001f680 **Elinditva!**\n\n"
                    f"\U0001f916 Dolgoznak: {agents_working}\n"
                    f"\U0001f4cb Feladatok: {len(task_ids)}\n"
                    f"\u23f1 Becsult ido: {plan['estimated_duration']}\n\n"
                    "Szolok ha kesz, vagy kerdezz ra barmikor!"
                ),
                "phase": "dispatch",
                "actions": ["statusz", "leallitas"],
                "metadata": {"task_ids": task_ids},
            }

        # ── REAL DISPATCH via Pipeline.run() ──────────────────────
        task_ids = []
        results = []
        risk_map = {"low": RiskLevel.LOW, "medium": RiskLevel.MEDIUM,
                     "high": RiskLevel.HIGH, "critical": RiskLevel.CRITICAL}
        risk_level = risk_map.get(plan.get("risk_level", "low"), RiskLevel.LOW)

        # ── PRE-EXECUTION: gather live data via MCP bridge tools ──
        # For wp-web tasks, automatically call wordpress.* tools and embed
        # results so agents get REAL DATA, not just a text directive.
        tool_context = ""
        try:
            tool_context = await self._gather_tool_context(conv.original_message)
        except Exception as exc:
            logger.warning("Tool context gathering failed: %s", exc)

        for step in plan.get("steps", []):
            task_id = self._generate_task_id()
            task_ids.append(task_id)
            agent_type = step.get("agent", plan["primary_agent"])
            step_desc = step.get("description", "")

            # PERMANENT FIX: The guard scans task.name AND task.description
            # for injection patterns. Brain-dispatched tasks were ALREADY
            # sanitized at INTAKE. The full directive + live data goes into
            # metadata["full_context"] which the guard NEVER scans (it's in
            # _PLAN_FIELDS). The OpenClaw executor reads full_context.
            #
            # name + description = ONLY clean step text. NO original message.
            clean_name = step_desc[:80] if step_desc else f"{agent_type} feladat"
            description = step_desc or f"{agent_type} agent feladat vegrehajtasa"

            # Build rich context for the executor (goes into metadata,
            # which the guard's _PLAN_FIELDS skips). The executor sends
            # this as the actual prompt to OpenClaw Claude.
            full_context = (
                f"Te a(z) {agent_type} agent vagy az OCCP rendszerben.\n"
                f"Feladat: {step_desc}\n\n"
                f"--- EREDETI DIREKTÍVA ---\n"
                f"{conv.original_message[:2000]}\n"
            )
            if tool_context:
                full_context += (
                    f"\n--- ÉLŐ WORDPRESS ADATOK ---\n"
                    f"{tool_context}\n"
                )

            task = Task(
                id=task_id,
                name=clean_name,
                description=description,
                agent_type=agent_type,
                risk_level=risk_level,
                metadata={
                    "conversation_id": conv.conversation_id,
                    "chat_id": int(conv.user_id) if conv.user_id.isdigit() else 0,
                    "brain_dispatched": True,
                    "full_context": full_context,
                },
            )

            if self._task_store:
                try:
                    await self._task_store.add(task)
                except Exception as exc:
                    logger.warning("Failed to persist task %s: %s", task_id, exc)

            try:
                result = await self._pipeline.run(task)
                results.append({
                    "task_id": task_id,
                    "agent": agent_type,
                    "success": result.success,
                    "output": str(result.evidence.get("execution", ""))[:500] if result.evidence else "",
                })
            except Exception as exc:
                logger.error("Pipeline run failed for task %s: %s", task_id, exc)
                results.append({
                    "task_id": task_id,
                    "agent": agent_type,
                    "success": False,
                    "output": f"error: {exc}",
                })

        conv.dispatched_tasks = task_ids
        conv.phase = FlowPhase.DELIVER

        # Build result summary
        succeeded = sum(1 for r in results if r["success"])
        total = len(results)

        result_lines = []
        for r in results:
            icon = "\u2705" if r["success"] else "\u274c"
            output_preview = r["output"][:200] if r["output"] else ""
            result_lines.append(f"{icon} {r['agent']}: {output_preview}")

        conv.phase = FlowPhase.COMPLETED

        return {
            "text": (
                "\U0001f9e0 Brian the Brain\n\n"
                f"\U0001f3c1 **Kesz!** {succeeded}/{total} feladat sikeres.\n\n"
                + "\n".join(result_lines[:10])
            ),
            "phase": "completed",
            "actions": ["uj feladat", "reszletek"],
            "metadata": {
                "task_ids": task_ids,
                "results": results,
                "succeeded": succeeded,
                "total": total,
            },
        }

    async def _gather_tool_context(self, message: str) -> str:
        """Pre-execution: gather FULL system context via MCP bridge tools.

        Brain always knows:
        1. INFRASTRUCTURE — which nodes are reachable (node.list + node.status)
        2. WORDPRESS — site info + pages + posts for mentioned domains
        3. BRAIN STATUS — self health check

        This makes Brain the CENTRAL CONTROLLER that understands the entire
        system structure before dispatching any work.
        """
        from adapters.mcp_bridge import ToolCall, build_default_bridge

        lines: list[str] = []
        lowered = message.lower()
        bridge = build_default_bridge()

        # ── 1. ALWAYS: Infrastructure status ──────────────────────
        lines.append("=== INFRASTRUCTURE STATUS ===")

        # Node list
        try:
            r = await bridge.dispatch(ToolCall(
                tool="node.list", params={}, agent_id="brain",
            ))
            if r.status == "ok" and r.result:
                for node in r.result.get("nodes", []):
                    lines.append(
                        f"  node: {node['id']} | host={node['host']} | "
                        f"user={node['user']} | role={node['role']}"
                    )
        except Exception as exc:
            lines.append(f"  node.list error: {exc}")

        # Node status (check which are reachable)
        for node_id in ("hetzner-brain", "hetzner-openclaw", "imac", "mbp"):
            try:
                r = await bridge.dispatch(ToolCall(
                    tool="node.status",
                    params={"node_id": node_id},
                    agent_id="brain",
                ))
                if r.status == "ok" and r.result:
                    reach = r.result.get("reachable", False)
                    out = r.result.get("output", "")[:60]
                    icon = "ONLINE" if reach else "OFFLINE"
                    lines.append(f"  {node_id}: {icon} {out}")
            except Exception:
                lines.append(f"  {node_id}: CHECK FAILED")

        # Docker on brain server
        try:
            r = await bridge.dispatch(ToolCall(
                tool="node.exec",
                params={"node_id": "hetzner-brain", "command": "docker ps --format {{.Names}}:{{.Status}}"},
                agent_id="brain",
            ))
            if r.status == "ok" and r.result and r.result.get("exit_code") == 0:
                lines.append("  docker containers:")
                for line in r.result["stdout"].strip().split("\n")[:10]:
                    lines.append(f"    {line}")
        except Exception:
            pass

        # ── 2. WordPress data for mentioned domains ───────────────
        wp_sites: list[str] = []
        if "magyarorszag.ai" in lowered:
            wp_sites.append("https://magyarorszag.ai")
        if "azar.hu" in lowered:
            wp_sites.append("https://azar.hu")
        if "felnottkepzes.hu" in lowered:
            wp_sites.append("https://felnottkepzes.hu")

        for site in wp_sites:
            lines.append(f"\n=== WORDPRESS: {site} ===")
            try:
                r = await bridge.dispatch(ToolCall(
                    tool="wordpress.get_site_info",
                    params={"site_url": site},
                    agent_id="brain",
                ))
                if r.status == "ok" and r.result:
                    lines.append(f"  name={r.result.get('name')}, "
                                 f"routes={r.result.get('routes_count')}, "
                                 f"namespaces={r.result.get('namespaces', [])[:5]}")
            except Exception as exc:
                lines.append(f"  site_info error: {exc}")

            try:
                r = await bridge.dispatch(ToolCall(
                    tool="wordpress.get_pages",
                    params={"site_url": site, "per_page": 20},
                    agent_id="brain",
                ))
                if r.status == "ok" and r.result:
                    pages = r.result.get("pages", [])
                    lines.append(f"  pages ({len(pages)}):")
                    for p in pages[:15]:
                        lines.append(f"    id={p['id']} title=\"{p['title']}\" slug={p['slug']} link={p['link']}")
            except Exception as exc:
                lines.append(f"  pages error: {exc}")

            try:
                r = await bridge.dispatch(ToolCall(
                    tool="wordpress.get_posts",
                    params={"site_url": site, "per_page": 10},
                    agent_id="brain",
                ))
                if r.status == "ok" and r.result:
                    posts = r.result.get("posts", [])
                    lines.append(f"  posts ({len(posts)}):")
                    for p in posts[:10]:
                        lines.append(f"    id={p['id']} title=\"{p['title']}\" slug={p['slug']}")
            except Exception as exc:
                lines.append(f"  posts error: {exc}")

        # ── 3. Brain self-status ──────────────────────────────────
        lines.append("\n=== BRAIN STATUS ===")
        try:
            r = await bridge.dispatch(ToolCall(
                tool="brain.status", params={}, agent_id="brain",
            ))
            if r.status == "ok" and r.result:
                lines.append(f"  platform={r.result.get('platform')} "
                             f"version={r.result.get('version')} "
                             f"bridge={r.result.get('bridge')}")
        except Exception:
            lines.append("  brain.status: error")

        # Available tools
        lines.append(f"  tools_available: {len(bridge.list_tools())}")
        lines.append(f"  tools: {', '.join(bridge.list_tools())}")

        context = "\n".join(lines)
        logger.info(
            "brain_flow: gathered %d lines of system context (nodes + wp + brain)",
            len(lines),
        )
        return context

    async def _handle_dispatch_phase(
        self, conv: BrainConversation, message: str
    ) -> dict[str, Any]:
        """Handle messages during dispatch — route to monitor."""
        conv.phase = FlowPhase.MONITOR
        return await self._handle_monitor(conv, message)

    async def _handle_monitor(
        self, conv: BrainConversation, message: str
    ) -> dict[str, Any]:
        """Phase 6: Report progress."""
        normalized = message.lower().strip()

        status_keywords = {
            "statusz", "status", "hol tart", "mi a helyzet",
            "progress", "hogyan all",
        }
        stop_keywords = {"leallitas", "leallitsd", "stop", "cancel", "megse"}

        if any(k in normalized for k in stop_keywords):
            conv.phase = FlowPhase.CANCELLED
            return {
                "text": (
                    "\U0001f9e0 Brian the Brain\n\n"
                    "\u23f9 Leallitva. A mar elkeszult reszeket megorzom."
                ),
                "phase": "cancelled",
                "actions": [],
                "metadata": {},
            }

        if any(k in normalized for k in status_keywords):
            completed = sum(
                1 for r in conv.results if r.get("status") == "completed"
            )
            total = len(conv.dispatched_tasks)
            return {
                "text": (
                    "\U0001f9e0 Brian the Brain\n\n"
                    f"\U0001f4ca **Statusz:** {completed}/{total} kesz\n"
                    f"\U0001f504 Folyamatban: {total - completed}\n"
                ),
                "phase": "monitor",
                "actions": ["statusz", "leallitas"],
                "metadata": {
                    "completed": completed,
                    "total": total,
                },
            }

        # Unrelated message during monitoring — start new conversation
        new_conv = self._create_conversation(conv.user_id, message)
        result = await self._handle_intake(new_conv, message)
        result["conversation_id"] = new_conv.conversation_id
        return result

    async def _handle_deliver(
        self, conv: BrainConversation, message: str
    ) -> dict[str, Any]:
        """Phase 7: Present results and ask for feedback."""
        # Check if this is feedback (1-5 rating)
        stripped = message.strip()
        if stripped.isdigit() and 1 <= int(stripped) <= 5:
            conv.feedback_score = int(stripped)
            conv.phase = FlowPhase.COMPLETED
            stars = "\u2b50" * int(stripped)
            return {
                "text": (
                    "\U0001f9e0 Brian the Brain\n\n"
                    f"{stars} Koszi a visszajelzest! Szolj ha kell valami mas."
                ),
                "phase": "completed",
                "actions": [],
                "metadata": {"feedback_score": conv.feedback_score},
            }

        # New message — start new conversation
        new_conv = self._create_conversation(conv.user_id, message)
        result = await self._handle_intake(new_conv, message)
        result["conversation_id"] = new_conv.conversation_id
        return result

    # ------------------------------------------------------------------
    # Task completion callback (called by external monitor/webhook)
    # ------------------------------------------------------------------

    async def complete_task(
        self,
        conversation_id: str,
        task_id: str,
        result: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Mark a task as completed and check if all tasks are done.

        Called externally when an OpenClaw agent finishes a task.
        Returns a delivery response if all tasks are done, None otherwise.
        """
        conv = self._conversations.get(conversation_id)
        if not conv:
            return None

        conv.results.append({"task_id": task_id, "status": "completed", **result})
        conv.touch()

        completed = sum(
            1 for r in conv.results if r.get("status") == "completed"
        )
        total = len(conv.dispatched_tasks)

        if completed >= total:
            conv.phase = FlowPhase.DELIVER
            results_summary = "\n".join(
                f"  - {r.get('task_id', '?')}: {r.get('summary', 'kesz')}"
                for r in conv.results
            )
            return {
                "text": (
                    "\U0001f9e0 Brian the Brain\n\n"
                    "\u2705 **Minden kesz!**\n\n"
                    f"{results_summary}\n\n"
                    "Ertekelned 1-5 skalan?"
                ),
                "phase": "deliver",
                "actions": ["1", "2", "3", "4", "5"],
                "conversation_id": conv.conversation_id,
                "metadata": {"results": conv.results},
            }

        return None

    # ------------------------------------------------------------------
    # Conversation management
    # ------------------------------------------------------------------

    def _get_or_create_conversation(
        self,
        user_id: str,
        message: str,
        conversation_id: str | None,
    ) -> BrainConversation:
        """Get existing conversation or create a new one."""
        if conversation_id:
            conv = self._conversations.get(conversation_id)
            if conv and not conv.is_expired() and not conv.is_terminal():
                return conv

        # Find active non-terminal conversation for user
        active = self.get_active_conversations(user_id)
        if active:
            return active[-1]  # Most recent

        return self._create_conversation(user_id, message)

    def _create_conversation(
        self, user_id: str, message: str
    ) -> BrainConversation:
        """Create a new conversation."""
        # Enforce per-user limit
        self._enforce_user_limit(user_id)

        conv_id = uuid.uuid4().hex[:16]
        conv = BrainConversation(
            conversation_id=conv_id,
            user_id=user_id,
        )
        self._conversations[conv_id] = conv

        if user_id not in self._user_conversations:
            self._user_conversations[user_id] = []
        self._user_conversations[user_id].append(conv_id)

        logger.info(
            "New conversation: id=%s user=%s",
            conv_id,
            user_id,
        )
        return conv

    async def _persist_conversation(self, conv: BrainConversation) -> None:
        """Persist full conversation state to DB (if store configured)."""
        if not self._conversation_store:
            return
        try:
            await self._conversation_store.save(
                conv_id=conv.conversation_id,
                user_id=conv.user_id,
                phase=conv.phase.value,
                original_message=conv.original_message,
                clarifying_questions=conv.clarifying_questions,
                clarifying_answers=conv.clarifying_answers,
                execution_plan=conv.execution_plan,
                plan_approved=conv.plan_approved,
                dispatched_tasks=conv.dispatched_tasks,
                results=conv.results,
                feedback_score=conv.feedback_score,
                project_id=conv.project_id,
            )
        except Exception as exc:
            logger.warning("Failed to persist conversation %s: %s", conv.conversation_id, exc)

    async def load_active_conversations(self) -> int:
        """Load active conversations from DB on startup. Returns count loaded."""
        if not self._conversation_store:
            return 0
        try:
            # Cleanup expired first
            cleaned = await self._conversation_store.cleanup_expired()
            if cleaned:
                logger.info("Cleaned %d expired conversations from DB", cleaned)

            # Load all active conversations (grouped by user)
            # We need all non-terminal conversations
            loaded = 0
            # Get all users with active conversations
            # ConversationStore.get_active_by_user requires a user_id,
            # so we iterate known users from the DB
            # For now, use a direct query if available
            if hasattr(self._conversation_store, '_session_factory'):
                from sqlalchemy import select
                from store.conversation_store import BrainConversationRow
                async with self._conversation_store._session_factory() as session:
                    result = await session.execute(
                        select(BrainConversationRow)
                        .where(BrainConversationRow.phase.notin_(["completed", "cancelled"]))
                    )
                    rows = result.scalars().all()
                    for row in rows:
                        conv = BrainConversation(
                            conversation_id=row.conversation_id,
                            user_id=row.user_id,
                        )
                        try:
                            conv.phase = FlowPhase(row.phase)
                        except ValueError:
                            conv.phase = FlowPhase.INTAKE
                        conv.original_message = row.original_message or ""
                        conv.clarifying_questions = row.clarifying_questions or []
                        conv.clarifying_answers = row.clarifying_answers or []
                        conv.execution_plan = row.execution_plan
                        conv.plan_approved = row.plan_approved or False
                        conv.dispatched_tasks = row.dispatched_tasks or []
                        conv.results = row.results or []
                        conv.feedback_score = row.feedback_score
                        conv.project_id = row.project_id

                        self._conversations[conv.conversation_id] = conv
                        if conv.user_id not in self._user_conversations:
                            self._user_conversations[conv.user_id] = []
                        self._user_conversations[conv.user_id].append(conv.conversation_id)
                        loaded += 1

            logger.info("Loaded %d active conversations from DB", loaded)
            return loaded
        except Exception as exc:
            logger.warning("Failed to load conversations: %s", exc)
            return 0

    def _expire_conversations(self, user_id: str) -> None:
        """Remove expired conversations for a user."""
        conv_ids = self._user_conversations.get(user_id, [])
        active_ids = []
        for cid in conv_ids:
            conv = self._conversations.get(cid)
            if conv and not conv.is_expired():
                active_ids.append(cid)
            elif conv:
                del self._conversations[cid]
                logger.debug("Expired conversation: id=%s user=%s", cid, user_id)

        self._user_conversations[user_id] = active_ids

    def _enforce_user_limit(self, user_id: str) -> None:
        """Enforce max conversations per user. Removes oldest if over limit."""
        conv_ids = self._user_conversations.get(user_id, [])
        while len(conv_ids) >= MAX_CONVERSATIONS_PER_USER:
            oldest_id = conv_ids.pop(0)
            self._conversations.pop(oldest_id, None)
            logger.debug(
                "Evicted oldest conversation: id=%s user=%s",
                oldest_id,
                user_id,
            )
        self._user_conversations[user_id] = conv_ids

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _needs_clarification(self, message: str, route: RouteDecision) -> bool:
        """Determine if we need to ask clarifying questions."""
        # Very short messages — just do it, not enough to ask about
        if len(message.split()) < 5:
            return False

        # Low confidence needs clarification
        if route.confidence < 0.6:
            return True

        # High risk tasks always get clarification
        if route.risk_level in ("high", "critical"):
            return True

        return False

    def _generate_clarifying_questions(
        self, message: str, route: RouteDecision
    ) -> list[str]:
        """Generate smart clarifying questions based on context."""
        questions: list[str] = []

        if route.risk_level in ("high", "critical"):
            questions.append("Ez production kornyezetet erint?")

        if route.confidence < 0.6:
            questions.append(
                f"Jol ertem, hogy a fo feladat: {route.primary_agent} teruletre vonatkozik?"
            )

        if len(route.support_agents) > 2:
            questions.append("Melyik reszfeladatot priorizaljam?")

        if not questions:
            questions.append("Van-e hatarido vagy prioritas?")

        return questions

    def _break_down_steps(
        self, message: str, route: RouteDecision
    ) -> list[dict[str, str]]:
        """Break task into concrete steps."""
        steps: list[dict[str, str]] = []

        # Primary agent main task
        steps.append({
            "agent": route.primary_agent,
            "description": f"{route.primary_agent}: fo feladat vegrehajtasa",
            "type": "execute",
        })

        # Support agent tasks
        for agent in route.support_agents:
            steps.append({
                "agent": agent,
                "description": f"{agent}: tamogato feladat",
                "type": "support",
            })

        # Quality check
        steps.append({
            "agent": "brain",
            "description": "Brian: minoseg-ellenorzes es osszesites",
            "type": "quality",
        })

        return steps

    @staticmethod
    def _generate_task_id() -> str:
        """Generate a unique task ID."""
        return uuid.uuid4().hex[:16]


# Module-level alias so `from orchestrator.brain_flow import BrainFlow` works
# (EU AI Act Art.14 test expects this name).
BrainFlow = BrainFlowEngine
