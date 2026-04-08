"""Voice command orchestrator: transcribe -> classify -> pipeline -> respond.

Connects the Whisper transcription, intent classification, and VAP
pipeline to process voice commands end-to-end and send results
back to the user on Telegram.

Integrates the ConfirmationGate for human approval of MEDIUM/HIGH risk tasks.
"""

from __future__ import annotations

import logging
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from security.channel_auth import ChannelAuthenticator, ChannelIdentity
from security.input_sanitizer import InputSanitizer

if TYPE_CHECKING:
    from adapters.confirmation_gate import ConfirmationGate
    from adapters.intent_router import IntentRouter
    from adapters.telegram_voice_bot import TelegramVoiceBot
    from adapters.whisper_client import WhisperClient
    from orchestrator.brain_flow import BrainFlowEngine
    from orchestrator.models import RiskLevel
    from orchestrator.task_router import TaskRouter

logger = logging.getLogger(__name__)

# Keep last N commands in memory for /voice/history
MAX_HISTORY = 100


@dataclass
class VoiceCommandLog:
    """In-memory log entry for a voice command."""

    id: str
    chat_id: int
    transcription: str
    intent: str
    agent_type: str
    task_id: str | None = None
    status: str = "received"  # received | transcribed | routing | confirming | executing | completed | failed
    error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    duration_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "chat_id": self.chat_id,
            "transcription": self.transcription,
            "intent": self.intent,
            "agent_type": self.agent_type,
            "task_id": self.task_id,
            "status": self.status,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.duration_ms,
        }


class TelegramConfirmationSender:
    """Adapts TelegramVoiceBot to the ConfirmationSender protocol."""

    def __init__(self, bot: TelegramVoiceBot) -> None:
        self._bot = bot

    async def send_confirmation_request(self, chat_id: int, message: str) -> None:
        await self._bot.send_message(chat_id, message)

    async def send_confirmation_result(self, chat_id: int, message: str) -> None:
        await self._bot.send_message(chat_id, message)


class VoiceCommandHandler:
    """Orchestrates voice command -> pipeline -> response flow.

    Flow:
        1. Receive voice/text from Telegram
        2. Transcribe voice via WhisperClient (skip for text)
        3. Classify intent via IntentRouter
        4. Create Task and run through VAP Pipeline
        5. (NEW) If MEDIUM/HIGH risk: ask Henry for confirmation
        6. Send result back to user on Telegram
        7. Log to audit trail
    """

    def __init__(
        self,
        whisper: WhisperClient,
        intent_router: IntentRouter,
        pipeline: Any,  # orchestrator.pipeline.Pipeline
        task_store: Any,  # store.task_store.TaskStore
        audit_store: Any,  # store.audit_store.AuditStore
        bot: TelegramVoiceBot | None = None,
        confirmation_gate: ConfirmationGate | None = None,
        task_router: TaskRouter | None = None,
        brain_flow: BrainFlowEngine | None = None,
        channel_auth: ChannelAuthenticator | None = None,
        input_sanitizer: InputSanitizer | None = None,
    ) -> None:
        self._whisper = whisper
        self._intent_router = intent_router
        self._pipeline = pipeline
        self._task_store = task_store
        self._audit_store = audit_store
        self._bot: TelegramVoiceBot | None = bot
        self._confirmation_gate = confirmation_gate
        self._task_router: TaskRouter | None = task_router
        self._brain_flow: BrainFlowEngine | None = brain_flow
        self._channel_auth: ChannelAuthenticator | None = channel_auth
        self._input_sanitizer: InputSanitizer = input_sanitizer or InputSanitizer()
        # Track conversation_id per chat_id for BrainFlowEngine
        self._chat_conversations: dict[int, str] = {}

        # In-memory command history
        self._history: deque[VoiceCommandLog] = deque(maxlen=MAX_HISTORY)
        self._total_commands: int = 0
        self._last_command_at: datetime | None = None

    def set_bot(self, bot: TelegramVoiceBot) -> None:
        """Set the Telegram bot reference (circular dependency resolution)."""
        self._bot = bot
        # Wire up the confirmation gate sender
        if self._confirmation_gate and bot:
            sender = TelegramConfirmationSender(bot)
            self._confirmation_gate.set_sender(sender)

    def set_confirmation_gate(self, gate: ConfirmationGate) -> None:
        """Set the confirmation gate (can be done after init)."""
        self._confirmation_gate = gate
        if self._bot:
            sender = TelegramConfirmationSender(self._bot)
            gate.set_sender(sender)

    def set_brain_flow(self, brain_flow: BrainFlowEngine) -> None:
        """Set the BrainFlowEngine (can be done after init)."""
        self._brain_flow = brain_flow

    # ------------------------------------------------------------------
    # Incoming message routing (confirmation vs new command)
    # ------------------------------------------------------------------

    def is_confirmation_response(self, chat_id: int) -> bool:
        """Check if there's a pending confirmation for this chat."""
        if self._confirmation_gate:
            return self._confirmation_gate.has_pending(chat_id)
        return False

    def handle_confirmation_response(self, chat_id: int, text: str) -> bool:
        """Route a text message to the confirmation gate if applicable.

        Returns True if handled as a confirmation response.
        """
        if not self._confirmation_gate:
            return False
        return self._confirmation_gate.handle_response(chat_id, text)

    # ------------------------------------------------------------------
    # Public handlers (called from TelegramVoiceBot callbacks)
    # ------------------------------------------------------------------

    def _authenticate_telegram(self, chat_id: int) -> ChannelIdentity | None:
        """Authenticate Telegram user. Returns None if rejected.

        Strict mode: if no ChannelAuthenticator configured, reject ALL.
        This prevents unauthenticated access when auth is expected but missing.
        """
        if not self._channel_auth:
            logger.warning("No ChannelAuthenticator configured — rejecting chat_id=%d", chat_id)
            return None
        return self._channel_auth.authenticate_telegram(chat_id)

    async def handle_voice(
        self, chat_id: int, audio_bytes: bytes, file_name: str
    ) -> None:
        """Full pipeline: transcribe -> classify -> execute -> respond."""
        identity = self._authenticate_telegram(chat_id)
        if identity is None:
            logger.warning("Telegram auth rejected: chat_id=%d", chat_id)
            await self._send(chat_id, "🧠 Nem vagy jogosult, sajnálom.")
            return

        start = time.monotonic()
        cmd_id = uuid.uuid4().hex[:12]

        log_entry = VoiceCommandLog(
            id=cmd_id,
            chat_id=chat_id,
            transcription="",
            intent="",
            agent_type="",
        )
        self._history.append(log_entry)
        self._total_commands += 1
        self._last_command_at = datetime.now(timezone.utc)

        try:
            # 1. Transcribe
            log_entry.status = "transcribed"
            text = await self._whisper.transcribe(
                audio_bytes, filename=file_name
            )
            log_entry.transcription = text

            if not text.strip():
                await self._send(chat_id, "\U0001f9e0 Nem ertettem, Henry. Probald ujra.")
                log_entry.status = "failed"
                log_entry.error = "empty_transcription"
                return

            # 1.5 Sanitize transcribed text (OWASP ASI01)
            san_result = self._input_sanitizer.sanitize(text, channel="telegram")
            if not san_result.safe:
                logger.warning("Voice input BLOCKED chat_id=%d threats=%s", chat_id, san_result.threats_detected)
                await self._send(chat_id, "🧠 A hangparancsot biztonsági okokból nem tudom feldolgozni.")
                log_entry.status = "failed"
                log_entry.error = f"sanitization_blocked:{san_result.threats_detected}"
                return
            text = san_result.sanitized

            # 2. Send interim message with transcription
            await self._send(
                chat_id,
                f"\U0001f3a4 _{text}_\n\n\u23f3 Dolgozom rajta, Henry...",
            )

            # 3. Classify intent
            log_entry.status = "routing"
            intent_result = await self._intent_router.classify(text)
            log_entry.intent = intent_result.intent
            log_entry.agent_type = intent_result.agent_type

            # 4. Create task and run pipeline
            await self._execute_pipeline(chat_id, intent_result, log_entry)

        except Exception as exc:
            logger.error("Voice command failed: %s", exc, exc_info=True)
            log_entry.status = "failed"
            log_entry.error = str(exc)[:300]
            await self._send(
                chat_id,
                f"\U0001f9e0 Nem sikerult feldolgozni, Henry. `{str(exc)[:150]}`",
            )
        finally:
            elapsed = int((time.monotonic() - start) * 1000)
            log_entry.duration_ms = elapsed
            if log_entry.status not in ("completed", "failed"):
                log_entry.status = "completed"
            log_entry.completed_at = datetime.now(timezone.utc)

    async def handle_text(self, chat_id: int, text: str) -> None:
        """Text commands bypass transcription, go straight to intent routing.

        When BrainFlowEngine is configured, routes ALL messages through the
        7-phase conversation flow. Otherwise falls back to legacy pipeline.
        """
        # Auth check
        identity = self._authenticate_telegram(chat_id)
        if identity is None:
            logger.warning("Telegram auth rejected (text): chat_id=%d", chat_id)
            await self._send(chat_id, "🧠 Nem vagy jogosult, sajnálom.")
            return

        # Input sanitization (OWASP ASI01)
        san_result = self._input_sanitizer.sanitize(text, channel="telegram")
        if not san_result.safe:
            logger.warning("Input BLOCKED chat_id=%d threats=%s", chat_id, san_result.threats_detected)
            await self._send(chat_id, "🧠 A kérést biztonsági okokból nem tudom feldolgozni.")
            return
        text = san_result.sanitized

        # Check if this is a response to a pending confirmation (legacy gate)
        if not self._brain_flow and self.is_confirmation_response(chat_id):
            handled = self.handle_confirmation_response(chat_id, text)
            if handled:
                await self._send_confirmation_feedback(chat_id, text)
                return

        start = time.monotonic()
        cmd_id = uuid.uuid4().hex[:12]

        log_entry = VoiceCommandLog(
            id=cmd_id,
            chat_id=chat_id,
            transcription=text,
            intent="",
            agent_type="",
            status="routing",
        )
        self._history.append(log_entry)
        self._total_commands += 1
        self._last_command_at = datetime.now(timezone.utc)

        try:
            # BrainFlowEngine path — the new 7-phase conversation flow
            if self._brain_flow:
                await self._handle_brain_flow(chat_id, text, log_entry)
                return

            # Legacy path — direct intent routing + pipeline
            intent_result = await self._intent_router.classify(text)
            log_entry.intent = intent_result.intent
            log_entry.agent_type = intent_result.agent_type

            await self._send(chat_id, "\u23f3 Dolgozom rajta, Henry...")
            await self._execute_pipeline(chat_id, intent_result, log_entry)

        except Exception as exc:
            logger.error("Text command failed: %s", exc, exc_info=True)
            log_entry.status = "failed"
            log_entry.error = str(exc)[:300]
            await self._send(
                chat_id,
                f"\U0001f9e0 Hiba, Henry. `{str(exc)[:150]}`",
            )
        finally:
            elapsed = int((time.monotonic() - start) * 1000)
            log_entry.duration_ms = elapsed
            if log_entry.status not in ("completed", "failed"):
                log_entry.status = "completed"
            log_entry.completed_at = datetime.now(timezone.utc)

    async def _handle_brain_flow(
        self, chat_id: int, text: str, log_entry: VoiceCommandLog
    ) -> None:
        """Route message through BrainFlowEngine and send response."""
        assert self._brain_flow is not None

        user_id = str(chat_id)
        conversation_id = self._chat_conversations.get(chat_id)

        try:
            response = await self._brain_flow.process_message(
                user_id=user_id,
                message=text,
                conversation_id=conversation_id,
            )

            # Track conversation_id for this chat
            new_conv_id = response.get("conversation_id")
            if new_conv_id:
                self._chat_conversations[chat_id] = new_conv_id

            # Send Brian's response text to Telegram
            response_text = response.get("text", "")
            if response_text:
                await self._send(chat_id, response_text)

            log_entry.status = "completed"
            log_entry.intent = f"brain_flow:{response.get('phase', 'unknown')}"
            log_entry.agent_type = "brain"

        except Exception as exc:
            logger.error("BrainFlowEngine failed: %s", exc, exc_info=True)
            log_entry.status = "failed"
            log_entry.error = str(exc)[:300]
            await self._send(
                chat_id,
                f"\U0001f9e0 Hiba, Henry. `{str(exc)[:150]}`",
            )

    # ------------------------------------------------------------------
    # Pipeline execution
    # ------------------------------------------------------------------

    async def _execute_pipeline(
        self,
        chat_id: int,
        intent_result: Any,
        log_entry: VoiceCommandLog,
    ) -> None:
        """Create a Task, run it through the VAP pipeline, and respond."""
        from adapters.confirmation_gate import (
            ConfirmationTimeoutError,
            HumanRejectedError,
        )
        from orchestrator.models import RiskLevel, Task

        # --- TaskRouter: intelligent agent routing ---
        route_decision = None
        if self._task_router:
            route_decision = self._task_router.route(
                log_entry.transcription,
                context={"chat_id": chat_id},
            )
            logger.info(
                "TaskRouter decision: primary=%s support=%s confidence=%.3f",
                route_decision.primary_agent,
                route_decision.support_agents,
                route_decision.confidence,
            )

        # Map risk_level string to enum
        risk_map = {
            "low": RiskLevel.LOW,
            "medium": RiskLevel.MEDIUM,
            "high": RiskLevel.HIGH,
            "critical": RiskLevel.CRITICAL,
        }

        # Use TaskRouter risk if available, otherwise fall back to intent_result
        risk_str = route_decision.risk_level if route_decision else intent_result.risk_level
        risk = risk_map.get(risk_str, RiskLevel.LOW)

        # Use TaskRouter agent if available and confident enough
        agent_type = intent_result.agent_type
        if route_decision and route_decision.confidence >= 0.15:
            agent_type = route_decision.primary_agent

        # Create Task
        task_metadata: dict[str, Any] = {
            "source": "voice",
            "chat_id": chat_id,
            "intent": intent_result.intent,
            "confidence": intent_result.confidence,
            "voice_command_id": log_entry.id,
        }
        if route_decision:
            task_metadata["route_decision"] = route_decision.to_dict()

        task = Task(
            name=intent_result.task_name,
            description=intent_result.task_description,
            agent_type=agent_type,
            risk_level=risk,
            metadata=task_metadata,
        )

        log_entry.task_id = task.id
        log_entry.status = "executing"

        # Persist task
        try:
            await self._task_store.add(task)
        except Exception as exc:
            logger.warning("Failed to persist task: %s", exc)

        # Run pipeline
        try:
            result = await self._pipeline.run(task)

            if result.success:
                log_entry.status = "completed"
                output = await self._format_result(result)

                # Build header with routing info if available
                if route_decision and self._task_router:
                    header = self._task_router.format_brain_header(route_decision)
                    await self._send(
                        chat_id,
                        f"{header}\n\n{output}",
                    )
                else:
                    await self._send(
                        chat_id,
                        f"\U0001f9e0 *Brian the Brain*\n\n"
                        f"{output}",
                    )
            else:
                log_entry.status = "failed"
                error_msg = result.error or "Ismeretlen hiba"
                log_entry.error = error_msg[:300]
                # User-friendly error messages
                if "timeout" in error_msg.lower() or "chat completion timeout" in error_msg.lower():
                    friendly = "Az AI modell tulterheltseg miatt nem valaszolt idoeben. Probald ujra par perc mulva."
                elif "connection" in error_msg.lower() or "ssl" in error_msg.lower():
                    friendly = "Nem tudtam elerni az agent szervert. Ellenorzom es probald ujra."
                elif "429" in error_msg or "quota" in error_msg.lower():
                    friendly = "Az AI szolgaltatas kvotaja atlegesre kerult. Probald kesobb."
                else:
                    friendly = error_msg[:200]
                await self._send(
                    chat_id,
                    f"\U0001f9e0 *Brian the Brain*\n\n"
                    f"\u26a0\ufe0f {friendly}\n\n"
                    f"\U0001f4a1 _Probald ujra vagy fogalmazd at._",
                )

        except HumanRejectedError:
            log_entry.status = "failed"
            log_entry.error = "human_rejected"
            # Feedback already sent via confirmation gate
            await self._send(
                chat_id,
                "\U0001f9e0 *Brian the Brain*\n\n"
                "Rendben, Henry. Leallitottam a feladatot.",
            )

        except ConfirmationTimeoutError:
            log_entry.status = "failed"
            log_entry.error = "confirmation_timeout"
            # Timeout message already sent by gate

        except Exception as exc:
            log_entry.status = "failed"
            log_entry.error = str(exc)[:300]
            await self._send(
                chat_id,
                f"\U0001f9e0 *Brian the Brain*\n\n"
                f"Hiba tortent, Henry: `{str(exc)[:200]}`\n\n"
                f"\U0001f4a1 _Probald ujra vagy fogalmazd at._",
            )

        # Audit log — route through policy_engine so hash chain is linked
        try:
            from store.audit_store import AuditEntry

            entry = AuditEntry(
                actor="voice_pipeline",
                action="voice_command",
                task_id=log_entry.task_id or "",
                detail={
                    "command_id": log_entry.id,
                    "chat_id": chat_id,
                    "transcription": log_entry.transcription[:500],
                    "intent": log_entry.intent,
                    "agent_type": log_entry.agent_type,
                    "status": log_entry.status,
                    "duration_ms": log_entry.duration_ms,
                },
            )
            # Link hash chain: fetch last entry and compute hash
            last = await self._audit_store.get_last()
            prev_hash = last.hash if last else ""
            entry.prev_hash = prev_hash
            entry.hash = entry.compute_hash(prev_hash)
            await self._audit_store.append(entry)
        except Exception as exc:
            logger.warning("Failed to write audit log: %s", exc)

    # ------------------------------------------------------------------
    # Confirmation feedback
    # ------------------------------------------------------------------

    async def _send_confirmation_feedback(self, chat_id: int, text: str) -> None:
        """Send appropriate feedback after a confirmation response."""
        from adapters.confirmation_gate import _APPROVE_KEYWORDS

        normalized = (
            text.strip()
            .lower()
            .replace("\u00e1", "a")
            .replace("\u00e9", "e")
            .replace("\u00f3", "o")
        )

        if normalized in _APPROVE_KEYWORDS:
            await self._send(
                chat_id,
                "\U0001f9e0 Jovahagyva! Dolgozom rajta, Henry...",
            )
        else:
            await self._send(
                chat_id,
                "\U0001f9e0 Leallitva. Ha maskepp szeretned, szolj!",
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _format_result(self, result: Any) -> str:
        """Format pipeline result for Telegram message.

        PipelineResult stores output in evidence dict:
          result.evidence["execution"]["output"] -- main executor output
          result.evidence["execution"]["gateway_response"] -- raw response
          result.evidence["validation"] -- validation info

        Handles OpenClaw gateway responses where the execution dict contains
        only metadata (runId, sessionKey, seq, state) and the actual text
        must be extracted from nested fields or fetched via session history.
        """
        import json

        # Primary: PipelineResult.evidence (VAP pipeline)
        evidence = getattr(result, "evidence", None)
        if isinstance(evidence, dict):
            execution = evidence.get("execution", {})
            if isinstance(execution, dict):
                # Try direct text extraction first
                text = self._extract_text_from_execution(execution)

                if text.strip():
                    text = self._escape_md(text)
                    if len(text) > 3500:
                        text = text[:3500] + "\n\n_(csonkolva)_"
                    return text

                # Detect OpenClaw gateway response: has runId/sessionKey/state
                # but no usable text — fetch from session history API
                if self._is_openclaw_gateway_response(execution):
                    session_key = execution.get("sessionKey", "")
                    fetched = await self._fetch_openclaw_session_text(session_key)
                    if fetched.strip():
                        fetched = self._escape_md(fetched)
                        if len(fetched) > 3500:
                            fetched = fetched[:3500] + "\n\n_(csonkolva)_"
                        return fetched
                    # Gateway returned final state but no text retrievable
                    logger.warning(
                        "OpenClaw gateway response with no extractable text: %s",
                        json.dumps(execution, default=str)[:300],
                    )
                    return "Feldolgoztam a kerest, de nem kaptam szoveges valaszt az agenttol."

            # Fallback: stringify non-empty evidence keys
            parts = []
            for key in ("plan", "validation", "ship"):
                val = evidence.get(key)
                if val and val != {"passed": True}:
                    parts.append(f"**{key}:** {json.dumps(val, ensure_ascii=False)[:500]}")
            if parts:
                return "\n".join(parts)

        # Legacy fallback: direct output/result attributes
        output = getattr(result, "output", None) or getattr(result, "result", None)
        if output:
            if isinstance(output, dict) and self._is_openclaw_gateway_response(output):
                session_key = output.get("sessionKey", "")
                fetched = await self._fetch_openclaw_session_text(session_key)
                if fetched.strip():
                    fetched = self._escape_md(fetched)
                    if len(fetched) > 3500:
                        fetched = fetched[:3500] + "\n\n_(csonkolva)_"
                    return fetched
                return "Feldolgoztam a kerest, de nem kaptam szoveges valaszt az agenttol."
            text = json.dumps(output, ensure_ascii=False, indent=2) if isinstance(output, dict) else str(output)
            if len(text) > 3500:
                text = text[:3500] + "\n\n_(csonkolva)_"
            return text

        return "_(Nincs reszletes kimenet)_"

    @staticmethod
    def _is_openclaw_gateway_response(data: dict[str, Any]) -> bool:
        """Detect if a dict is an OpenClaw gateway metadata response.

        OpenClaw gateway returns: {runId, sessionKey, seq, state}
        These contain no usable text content for the user.
        """
        gateway_keys = {"runId", "sessionKey", "state"}
        return gateway_keys.issubset(data.keys())

    @staticmethod
    def _extract_text_from_execution(execution: dict[str, Any]) -> str:
        """Extract human-readable text from an execution result dict.

        Checks multiple known locations where text content may live:
        - execution["output"] (string or dict with text/content keys)
        - execution["gateway_response"]["text"|"content"|"message"]
        - execution["messages"][-1]["content"] (chat-style responses)
        - execution["result"]["text"|"content"]
        - execution["response"]["text"|"content"]
        """
        import json

        # 1. Direct output field
        text = execution.get("output", "")
        if isinstance(text, dict):
            text = (
                text.get("text", "")
                or text.get("content", "")
                or text.get("message", "")
                or text.get("response", "")
            )
            if isinstance(text, dict):
                text = json.dumps(text, ensure_ascii=False, indent=2)
        elif not isinstance(text, str):
            text = str(text) if text else ""

        if text.strip():
            return text

        # 2. gateway_response field
        gw = execution.get("gateway_response", "")
        if isinstance(gw, dict):
            gw_text = (
                gw.get("text", "")
                or gw.get("content", "")
                or gw.get("message", "")
                or gw.get("response", "")
            )
            if isinstance(gw_text, str) and gw_text.strip():
                return gw_text

        # 3. messages array (chat-style: last assistant message)
        messages = execution.get("messages", [])
        if isinstance(messages, list) and messages:
            for msg in reversed(messages):
                if isinstance(msg, dict):
                    role = msg.get("role", "")
                    content = msg.get("content", "")
                    if role in ("assistant", "agent") and isinstance(content, str) and content.strip():
                        return content

        # 4. result sub-dict
        res = execution.get("result", "")
        if isinstance(res, dict):
            res_text = res.get("text", "") or res.get("content", "") or res.get("message", "")
            if isinstance(res_text, str) and res_text.strip():
                return res_text

        # 5. response sub-dict
        resp = execution.get("response", "")
        if isinstance(resp, dict):
            resp_text = resp.get("text", "") or resp.get("content", "") or resp.get("message", "")
            if isinstance(resp_text, str) and resp_text.strip():
                return resp_text

        return ""

    async def _fetch_openclaw_session_text(self, session_key: str) -> str:
        """Fetch the last assistant message from OpenClaw session history.

        Calls GET {openclaw_base_url}/sessions/{session_key}/history
        and extracts the last assistant/agent message content.

        Returns empty string on any failure (network, auth, parsing).
        """
        if not session_key:
            return ""

        try:
            import os
            import httpx

            base_url = os.environ.get("OCCP_OPENCLAW_BASE_URL", "").rstrip("/")
            if not base_url:
                # Try settings if available via pipeline
                try:
                    from config.settings import get_settings
                    base_url = get_settings().openclaw_base_url.rstrip("/")
                except Exception:
                    base_url = "https://claw.occp.ai"

            url = f"{base_url}/sessions/{session_key}/history"
            auth_user = os.environ.get("OPENCLAW_AUTH_USER", "")
            auth_pass = os.environ.get("OPENCLAW_AUTH_PASS", "")

            auth = None
            if auth_user and auth_pass:
                auth = httpx.BasicAuth(auth_user, auth_pass)

            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, auth=auth)
                if resp.status_code != 200:
                    logger.warning(
                        "OpenClaw session history fetch failed: status=%d url=%s",
                        resp.status_code,
                        url,
                    )
                    return ""

                data = resp.json()

                # Extract last assistant message from history
                # Expected formats:
                #   {"messages": [{"role": "assistant", "content": "..."}]}
                #   {"history": [{"role": "agent", "content": "..."}]}
                #   [{"role": "assistant", "content": "..."}]
                messages = data
                if isinstance(data, dict):
                    messages = (
                        data.get("messages", [])
                        or data.get("history", [])
                        or data.get("events", [])
                    )

                if isinstance(messages, list):
                    for msg in reversed(messages):
                        if isinstance(msg, dict):
                            role = msg.get("role", "") or msg.get("type", "")
                            content = (
                                msg.get("content", "")
                                or msg.get("text", "")
                                or msg.get("data", "")
                            )
                            if role in ("assistant", "agent", "model") and isinstance(content, str) and content.strip():
                                return content

                # If data itself has a text/content field
                if isinstance(data, dict):
                    direct = data.get("text", "") or data.get("content", "") or data.get("response", "")
                    if isinstance(direct, str) and direct.strip():
                        return direct

        except ImportError:
            logger.warning("httpx not available — cannot fetch OpenClaw session history")
        except Exception as exc:
            logger.warning("Failed to fetch OpenClaw session history: %s", exc)

        return ""

    @staticmethod
    def _escape_md(text: str) -> str:
        for ch in ("*", "_", "`", "[", "]"):
            text = text.replace(ch, "\\" + ch)
        return text

    async def _send(self, chat_id: int, text: str) -> None:
        """Send message via Telegram bot."""
        if self._bot:
            await self._bot.send_message(chat_id, text)
        else:
            logger.warning("No bot reference -- cannot send message to %d", chat_id)

    # ------------------------------------------------------------------
    # Status / History API
    # ------------------------------------------------------------------

    def get_status(self) -> dict[str, Any]:
        """Return voice pipeline status for API endpoint."""
        status = {
            "enabled": True,
            "bot_connected": self._bot is not None and self._bot.is_running,
            "total_commands": self._total_commands,
            "last_command_at": (
                self._last_command_at.isoformat() if self._last_command_at else ""
            ),
            "confirmation_gate_active": self._confirmation_gate is not None,
        }
        if self._confirmation_gate:
            status["confirmation_stats"] = self._confirmation_gate.get_stats()
        return status

    def get_history(self, limit: int = 20) -> list[dict[str, Any]]:
        """Return recent voice commands."""
        entries = list(self._history)
        entries.reverse()  # Most recent first
        return [e.to_dict() for e in entries[:limit]]
