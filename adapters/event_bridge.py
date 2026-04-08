"""EventBridge — Event processing layer between OpenClaw Gateway and OCCP Brain.

Listens for WebSocket events from OpenClaw Gateway, processes them,
and routes actionable intents to the OCCP pipeline.

Event types handled:
- chat (state=final) → extract conversation context, detect commands
- agent (stream=lifecycle) → log agent activity
- agent (stream=tool) → audit tool usage
- * (wildcard) → buffer all events for API exposure
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# Maximum events to keep in the ring buffer
MAX_EVENT_BUFFER = 200


@dataclass
class EventRecord:
    """A single recorded event from the Gateway."""

    event: str
    payload: dict[str, Any]
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event": self.event,
            "payload": self.payload,
            "timestamp": self.timestamp,
        }


class EventBridge:
    """Processes OpenClaw Gateway events and routes to OCCP Brain logic.

    Usage::

        bridge = EventBridge(executor=openclaw_executor)
        bridge.start()  # registers callbacks on executor
    """

    def __init__(self, executor: Any) -> None:
        self._executor = executor
        self._pipeline: Any = None  # Set via set_pipeline() after Pipeline init
        self._task_store: Any = None
        self._event_buffer: deque[EventRecord] = deque(maxlen=MAX_EVENT_BUFFER)
        self._chat_finals: int = 0
        self._agent_lifecycles: int = 0
        self._tool_events: int = 0
        self._routed_to_brain: int = 0
        self._errors: int = 0
        self._started = False
        self._owner_chat_id = "8400869598"  # Telegram owner ID
        self._error_sessions: dict[str, float] = {}  # circuit breaker: session -> last_error_ts
        self._error_cooldown = 120.0  # suppress repeated errors for 2 min per session
        self._seen_runs: dict[str, int] = {}  # run_id -> retry count (suppress agent retry spam)

    def start(self) -> None:
        """Register event callbacks on the OpenClaw executor."""
        if self._started:
            return

        self._executor.on_event("*", self._on_any_event)
        self._executor.on_event("chat", self._on_chat_event)
        self._executor.on_event("agent", self._on_agent_event)
        self._started = True
        logger.info("EventBridge: started (listening for chat, agent, * events)")

    def set_pipeline(self, pipeline: Any, task_store: Any = None) -> None:
        """Set the OCCP pipeline reference (called after Pipeline init)."""
        self._pipeline = pipeline
        self._task_store = task_store
        logger.info("EventBridge: pipeline connected (routing enabled)")

    async def _on_any_event(self, event_name: str, payload: dict[str, Any]) -> None:
        """Buffer all events for API exposure."""
        record = EventRecord(event=event_name, payload=payload)
        self._event_buffer.append(record)

    # Session prefixes that indicate Telegram user conversations
    _TELEGRAM_SESSION_PREFIXES = (
        "agent:main:telegram:direct:",   # DMs
        "agent:main:telegram:group:",    # Group chats
        "agent:main:telegram:channel:",  # Channels
    )

    # Session prefixes for Brain's own pipeline tasks (must NOT be re-routed)
    _BRAIN_SESSION_PREFIXES = (
        "agent:main:openclaw/",   # Brain pipeline executor sessions
        "agent:main:general/",    # Brain pipeline planner sessions
    )

    async def _on_chat_event(self, event_name: str, payload: dict[str, Any]) -> None:
        """Process chat events — detect final responses and extract context."""
        state = payload.get("state", "")

        if state == "final":
            self._chat_finals += 1
            session_key = payload.get("sessionKey", "")
            run_id = payload.get("runId", "")
            message = payload.get("message", {})

            logger.info(
                "EventBridge: chat.final session=%s run=%s",
                session_key,
                run_id[:12] if run_id else "?",
            )

            # FILTER: Only process Telegram conversations, skip Brain pipeline echoes
            if any(session_key.startswith(p) for p in self._BRAIN_SESSION_PREFIXES):
                logger.info(
                    "EventBridge: skipping Brain pipeline session=%s (no re-route)",
                    session_key,
                )
                return

            is_telegram = any(
                session_key.startswith(p) for p in self._TELEGRAM_SESSION_PREFIXES
            )
            if not is_telegram:
                logger.info(
                    "EventBridge: skipping non-Telegram session=%s",
                    session_key,
                )
                return

            # Process only Telegram user conversations
            if session_key:
                asyncio.create_task(
                    self._process_chat_final(session_key, run_id, message)
                )

        elif state == "error":
            self._errors += 1
            session_key = payload.get("sessionKey", "?")
            error_msg = payload.get("errorMessage", "unknown")

            # Circuit breaker: suppress repeated errors from same session
            now = time.time()
            last_err = self._error_sessions.get(session_key, 0.0)
            if now - last_err < self._error_cooldown:
                return  # suppress — already logged recently
            self._error_sessions[session_key] = now

            logger.warning(
                "EventBridge: chat.error session=%s error=%s (suppressing repeats for %ds)",
                session_key,
                error_msg[:120],
                int(self._error_cooldown),
            )

    async def _on_agent_event(self, event_name: str, payload: dict[str, Any]) -> None:
        """Process agent lifecycle and tool events."""
        stream = payload.get("stream", "")

        if stream == "lifecycle":
            self._agent_lifecycles += 1
            phase = payload.get("data", {}).get("phase", "")
            run_id = payload.get("runId", "")

            # Suppress retry spam: only log first start + final phase per run
            run_short = run_id[:12] if run_id else "?"
            count = self._seen_runs.get(run_short, 0)
            self._seen_runs[run_short] = count + 1
            if phase == "start" and count > 0:
                return  # suppress retry start
            if phase == "error" and count > 1:
                return  # suppress retry errors
            # Cleanup old runs (keep last 50)
            if len(self._seen_runs) > 100:
                keys = sorted(self._seen_runs, key=self._seen_runs.get)
                for k in keys[:50]:
                    del self._seen_runs[k]

            logger.info(
                "EventBridge: agent.lifecycle phase=%s run=%s",
                phase,
                run_short,
            )

        elif stream == "tool":
            self._tool_events += 1
            data = payload.get("data", {})
            tool_name = data.get("name", data.get("toolName", "?"))
            logger.debug(
                "EventBridge: agent.tool name=%s run=%s",
                tool_name,
                payload.get("runId", "?")[:12],
            )

        elif stream == "error":
            self._errors += 1
            data = payload.get("data", {})
            logger.warning(
                "EventBridge: agent.error reason=%s",
                data.get("reason", "unknown"),
            )

    async def _process_chat_final(
        self,
        session_key: str,
        run_id: str,
        message: dict[str, Any],
    ) -> None:
        """Process a completed chat — attempt to extract user intent.

        This calls chat.history to get the user's original message,
        then checks if it contains a command the Brain should handle.
        """
        try:
            logger.info(
                "EventBridge: _process_chat_final START session=%s run=%s",
                session_key,
                run_id[:12] if run_id else "?",
            )

            history = await self._executor.chat_history(
                session_key=session_key,
                limit=10,
            )

            logger.info(
                "EventBridge: chat.history returned keys=%s error=%s msg_count=%d",
                list(history.keys()) if isinstance(history, dict) else "NOT_DICT",
                history.get("error", "none"),
                len(history.get("messages", [])),
            )

            if history.get("error"):
                logger.warning(
                    "EventBridge: chat.history ERROR: %s (session=%s)",
                    history.get("error"),
                    session_key,
                )
                return

            # Extract last user message from history
            messages = history.get("messages", [])
            user_messages = [
                m for m in messages
                if m.get("role") == "user"
            ]

            logger.info(
                "EventBridge: history has %d messages, %d from user",
                len(messages),
                len(user_messages),
            )

            if not user_messages:
                logger.info("EventBridge: no user messages in history, skipping")
                # Log what roles we DID see
                roles = [m.get("role", "?") for m in messages[:5]]
                logger.info("EventBridge: message roles seen: %s", roles)
                return

            last_user_msg = user_messages[-1]
            user_text = ""
            content = last_user_msg.get("content", "")
            if isinstance(content, str):
                user_text = content
            elif isinstance(content, list):
                # Extract text from content blocks
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        user_text += block.get("text", "")

            # Clean Gateway metadata from user text
            raw_text = user_text
            user_text = self._clean_gateway_text(user_text)

            logger.info(
                "EventBridge: raw='%s' cleaned='%s' (len=%d)",
                raw_text[:80],
                user_text[:80],
                len(user_text),
            )

            if user_text:
                # Filter out Brain/Agent protocol messages to avoid loops
                _skip_prefixes = ("[BRAIN", "[AGENT", "✅ *BRAIN*", "❌ *BRAIN*", "✅ BRAIN", "❌ BRAIN")
                if any(user_text.startswith(p) for p in _skip_prefixes):
                    logger.info("EventBridge: skipping Brain/Agent echo='%s'", user_text[:40])
                    return

                intent = self._extract_intent(user_text)
                logger.info(
                    "EventBridge: intent extraction result: %s (text='%s')",
                    intent,
                    user_text[:60],
                )
                if intent:
                    logger.info(
                        "EventBridge: detected intent '%s' from user message",
                        intent.get("action", "?"),
                    )
                    await self._route_to_brain(
                        intent=intent,
                        session_key=session_key,
                        user_text=user_text,
                        run_id=run_id,
                    )
                else:
                    logger.info(
                        "EventBridge: no intent matched for text='%s'",
                        user_text[:80],
                    )

        except Exception as exc:
            logger.error(
                "EventBridge: process_chat_final error: %s", exc, exc_info=True
            )

    async def _route_to_brain(
        self,
        intent: dict[str, Any],
        session_key: str,
        user_text: str,
        run_id: str = "",
    ) -> None:
        """Route detected command to OCCP pipeline for execution.

        Creates a Task from the user's Telegram message and runs it
        through the full PLAN→GATE→EXECUTE→VALIDATE→SHIP pipeline.
        """
        if not self._pipeline:
            logger.warning(
                "EventBridge: pipeline not connected, cannot route intent '%s'",
                intent.get("action", "?"),
            )
            return

        try:
            from orchestrator.models import Task

            action = intent.get("action", "unknown")
            # For direct Brain addressing, use the instruction text as description
            task_description = intent.get("instruction", user_text)
            task = Task(
                name=f"telegram-{action}",
                description=task_description,
                agent_type="openclaw",
                metadata={
                    "source": "telegram",
                    "intent": intent,
                    "routed_at": datetime.now(timezone.utc).isoformat(),
                },
            )

            # Persist task if store available
            if self._task_store:
                await self._task_store.add(task)

            self._routed_to_brain += 1
            logger.info(
                "EventBridge: routing to Brain pipeline task=%s action=%s text='%s'",
                task.id,
                action,
                user_text[:80],
            )

            # Run through full pipeline (async, non-blocking)
            result = await self._pipeline.run(task)

            if result.success:
                logger.info(
                    "EventBridge: Brain pipeline SUCCESS task=%s",
                    task.id,
                )
                # Send result back to Telegram via chat.send
                await self._send_result_to_telegram(
                    session_key=session_key,
                    task_id=task.id,
                    result=result,
                )
            else:
                logger.warning(
                    "EventBridge: Brain pipeline FAILED task=%s error=%s",
                    task.id,
                    result.error[:200] if result.error else "unknown",
                )
                # Notify user about failure
                await self._send_result_to_telegram(
                    session_key=session_key,
                    task_id=task.id,
                    result=result,
                )

        except Exception as exc:
            self._errors += 1
            logger.error(
                "EventBridge: route_to_brain error: %s", exc, exc_info=True
            )

    async def _send_result_to_telegram(
        self,
        session_key: str,
        task_id: str,
        result: Any,
    ) -> None:
        """Send pipeline result back to Telegram conversation via chat.send."""
        try:
            evidence = getattr(result, "evidence", {}) or {}
            execution = evidence.get("execution", {})
            output = execution.get("output", "")
            task_name = getattr(result, "task_name", "") or evidence.get("task_name", "")

            # Format a clean, human-readable response
            response_text = self._format_brain_response(
                task_id=task_id,
                success=result.success,
                output=output,
                task_name=task_name,
                evidence=evidence,
            )

            import uuid as _uuid
            await self._executor.connection.send_request(
                "chat.send",
                {
                    "sessionKey": session_key,
                    "message": response_text,
                    "idempotencyKey": str(_uuid.uuid4()),
                    "deliver": True,
                },
                timeout=30.0,
            )
            logger.info(
                "EventBridge: result sent to Telegram session=%s",
                session_key,
            )
        except Exception as exc:
            logger.error(
                "EventBridge: failed to send result to Telegram: %s", exc
            )

    @staticmethod
    def _format_brain_response(
        task_id: str,
        success: bool,
        output: str,
        task_name: str = "",
        evidence: dict[str, Any] | None = None,
    ) -> str:
        """Format pipeline result as clean Telegram message."""
        evidence = evidence or {}
        status_icon = "✅" if success else "❌"
        short_id = task_id[:8]

        # Try to extract meaningful text from output
        clean_output = output.strip() if output else ""

        # If output is JSON-like, try to extract just the message
        if clean_output.startswith("{") or clean_output.startswith("["):
            try:
                import json
                parsed = json.loads(clean_output)
                if isinstance(parsed, dict):
                    # Try common response fields
                    for key in ("message", "result", "output", "response", "text", "answer"):
                        if key in parsed and isinstance(parsed[key], str):
                            clean_output = parsed[key]
                            break
                    else:
                        # Build summary from known fields
                        status = parsed.get("status", "")
                        run_id = parsed.get("runId", "")
                        if status:
                            clean_output = f"Státusz: {status}"
                            if run_id:
                                clean_output += f" (run: {run_id[:8]})"
                        elif isinstance(clean_output, dict):
                            clean_output = json.dumps(clean_output, ensure_ascii=False, indent=2)
            except (json.JSONDecodeError, TypeError):
                pass

        if not clean_output:
            clean_output = "Végrehajtva." if success else "Sikertelen."

        # Build response
        parts = [f"{status_icon} *BRAIN* [{short_id}]"]

        if task_name:
            parts[0] += f" — {task_name}"

        # Truncate output for Telegram (max ~800 chars)
        if len(clean_output) > 800:
            clean_output = clean_output[:800] + "…"
        parts.append(clean_output)

        # Add timing info if available
        execution = evidence.get("execution", {})
        duration = execution.get("duration_s")
        if duration is not None:
            parts.append(f"⏱ {duration:.1f}s")

        return "\n".join(parts)

    @staticmethod
    def _clean_gateway_text(raw_text: str) -> str:
        """Extract actual user message from Gateway-formatted text.

        Gateway wraps Telegram messages with metadata like:
          [Audio]\nUser text:\n[Telegram F H id:123 ...] <media:audio>\nTranscription: actual text
          [Telegram F H id:123 +9m Wed ...] actual text
          [Image]\nUser text:\n[Telegram F H id:123 ...] <media:image>\nCaption: actual text

        This strips all metadata and returns just the user's message.
        """
        import re

        text = raw_text.strip()
        if not text:
            return ""

        # Remove leading [Audio], [Image], [Video], [Document] etc.
        text = re.sub(r'^\[(Audio|Image|Video|Document|Sticker|Voice|File)\]\s*', '', text, flags=re.IGNORECASE)

        # Remove "User text:" prefix
        text = re.sub(r'^User text:\s*', '', text, flags=re.IGNORECASE)

        # Remove [Telegram ... id:NNNN ... UTC] metadata block
        text = re.sub(r'\[Telegram[^\]]*\]\s*', '', text)

        # Remove <media:XXX> tags
        text = re.sub(r'<media:\w+>\s*', '', text)

        # Strip whitespace between steps
        text = text.strip()

        # Remove Transcription:/Caption: prefix
        text = re.sub(r'^(Transcription|Transcript|Caption|Text):\s*', '', text, flags=re.IGNORECASE)

        return text.strip()

    def _extract_intent(self, user_text: str) -> dict[str, Any] | None:
        """Extract actionable intent from user message text.

        Returns None if no Brain-level action is needed.

        Routing modes:
        1. Direct prefix: /brain <instruction> or brain: <instruction> or @brain <instruction>
           -> Routes the full instruction text to Brain as a freeform task.
        2. Keyword matching: known commands like status, deploy, backup, etc.
        3. (Future) LLM-based intent classification.
        """
        text_lower = user_text.lower().strip()

        # --- Direct Brain addressing ---
        # /brain <instruction>, brain: <instruction>, @brain <instruction>
        direct_prefixes = ["/brain ", "brain ", "brain: ", "brain:", "@brain ", "agy ", "agy:", "/agy "]
        for prefix in direct_prefixes:
            if text_lower.startswith(prefix):
                instruction = user_text[len(prefix):].strip()
                if instruction:
                    return {
                        "action": "direct",
                        "keyword": prefix.strip(),
                        "original_text": user_text,
                        "instruction": instruction,
                    }

        # Known command patterns (Hungarian + English)
        command_patterns: dict[str, list[str]] = {
            "backup": ["backup", "mentés", "biztonsági mentés", "back up", "mentes"],
            "deploy": ["deploy", "telepítés", "kitelepítés", "publish", "release", "telepites"],
            "scan": ["scan", "vizsgálat", "security scan", "biztonsági", "audit", "vizsgalat"],
            "status": ["status", "státusz", "állapot", "health check", "health", "info", "statusz", "allapot", "státuszod", "statuszod"],
            "update": ["frissítés", "update", "upgrade", "patch", "frissites"],
            "help": ["help", "segítség", "parancsok", "commands", "segitseg"],
        }

        # Exact substring match first
        for action, keywords in command_patterns.items():
            for kw in keywords:
                if kw in text_lower:
                    return {
                        "action": action,
                        "keyword": kw,
                        "original_text": user_text,
                    }

        # Fuzzy match: strip accents + check similarity for transcription errors
        text_normalized = self._strip_accents(text_lower)
        for action, keywords in command_patterns.items():
            for kw in keywords:
                kw_norm = self._strip_accents(kw)
                # Check normalized substring
                if kw_norm in text_normalized:
                    return {
                        "action": action,
                        "keyword": kw,
                        "original_text": user_text,
                        "fuzzy": True,
                    }
                # Check word-level Levenshtein (max distance 2) for short words
                if len(kw_norm) >= 4:
                    for word in text_normalized.split():
                        if self._levenshtein(word.rstrip("?!.,"), kw_norm) <= 2:
                            return {
                                "action": action,
                                "keyword": kw,
                                "original_text": user_text,
                                "fuzzy": True,
                            }

        return None

    @staticmethod
    def _strip_accents(text: str) -> str:
        """Remove diacritical marks from text for fuzzy comparison."""
        import unicodedata
        nfkd = unicodedata.normalize("NFKD", text)
        return "".join(c for c in nfkd if not unicodedata.combining(c))

    @staticmethod
    def _levenshtein(s1: str, s2: str) -> int:
        """Compute Levenshtein distance between two strings."""
        if len(s1) < len(s2):
            return EventBridge._levenshtein(s2, s1)
        if len(s2) == 0:
            return len(s1)
        prev_row = list(range(len(s2) + 1))
        for i, c1 in enumerate(s1):
            curr_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = prev_row[j + 1] + 1
                deletions = curr_row[j] + 1
                substitutions = prev_row[j] + (c1 != c2)
                curr_row.append(min(insertions, deletions, substitutions))
            prev_row = curr_row
        return prev_row[-1]

    def get_recent_events(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return the most recent events from the buffer."""
        events = list(self._event_buffer)
        # Return most recent first
        events.reverse()
        return [e.to_dict() for e in events[:limit]]

    def get_stats(self) -> dict[str, Any]:
        """Return event processing statistics."""
        return {
            "started": self._started,
            "events_buffered": len(self._event_buffer),
            "chat_finals_processed": self._chat_finals,
            "agent_lifecycle_events": self._agent_lifecycles,
            "tool_events": self._tool_events,
            "routed_to_brain": self._routed_to_brain,
            "errors": self._errors,
        }
