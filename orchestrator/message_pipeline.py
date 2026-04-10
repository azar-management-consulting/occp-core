"""Message Pipeline — REQ-CORE-01: Channel-Agnostic Message Processing.

Normalizes messages from any channel (API, WebSocket, webhook, adapter)
into a unified format, routes them through the Verified Autonomy Pipeline,
and delivers responses back to the originating channel.

Usage::

    mp = MessagePipeline(pipeline=my_pipeline)
    mp.register_channel("api", api_handler)
    mp.register_channel("websocket", ws_handler)

    response = await mp.process(InboundMessage(
        channel="api",
        sender_id="user-1",
        content="Deploy staging",
        session_id="sess-abc",
    ))
"""

from __future__ import annotations

import enum
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol

from orchestrator.models import PipelineResult, RiskLevel, Task

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Channel types
# ---------------------------------------------------------------------------


class ChannelType(str, enum.Enum):
    """Supported inbound channel types."""

    API = "api"
    WEBSOCKET = "websocket"
    WEBHOOK = "webhook"
    ADAPTER = "adapter"


# ---------------------------------------------------------------------------
# Message models
# ---------------------------------------------------------------------------


@dataclass
class InboundMessage:
    """Normalized inbound message from any channel."""

    channel: str
    sender_id: str
    content: str
    session_id: str = ""
    message_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)
    agent_type: str = "default"
    risk_level: RiskLevel = RiskLevel.LOW

    def to_dict(self) -> dict[str, Any]:
        return {
            "message_id": self.message_id,
            "channel": self.channel,
            "sender_id": self.sender_id,
            "content": self.content,
            "session_id": self.session_id,
            "timestamp": self.timestamp.isoformat(),
            "agent_type": self.agent_type,
            "risk_level": self.risk_level.value,
            "metadata": self.metadata,
        }


@dataclass
class OutboundMessage:
    """Response message routed back to the originating channel."""

    channel: str
    recipient_id: str
    content: str
    session_id: str = ""
    message_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    in_reply_to: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    success: bool = True
    evidence: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "message_id": self.message_id,
            "channel": self.channel,
            "recipient_id": self.recipient_id,
            "content": self.content,
            "session_id": self.session_id,
            "in_reply_to": self.in_reply_to,
            "timestamp": self.timestamp.isoformat(),
            "success": self.success,
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------------------
# Middleware protocol
# ---------------------------------------------------------------------------


class Middleware(Protocol):
    """Pre/post processing hook for the message pipeline."""

    async def process_inbound(self, message: InboundMessage) -> InboundMessage:
        """Transform inbound message before VAP processing."""
        ...

    async def process_outbound(self, message: OutboundMessage) -> OutboundMessage:
        """Transform outbound message before delivery."""
        ...


# ---------------------------------------------------------------------------
# Channel handler protocol
# ---------------------------------------------------------------------------


class ChannelHandler(Protocol):
    """Delivers outbound messages to a specific channel."""

    async def deliver(self, message: OutboundMessage) -> bool:
        """Deliver *message* to the channel. Returns True on success."""
        ...


# ---------------------------------------------------------------------------
# Pipeline interface protocol (subset of Pipeline)
# ---------------------------------------------------------------------------


class PipelineRunner(Protocol):
    """Minimal pipeline interface needed by MessagePipeline."""

    async def run(self, task: Task) -> PipelineResult: ...


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class MessagePipelineError(Exception):
    """Message pipeline processing error."""


class UnknownChannelError(MessagePipelineError):
    """Raised when a message targets an unregistered channel."""

    def __init__(self, channel: str) -> None:
        self.channel = channel
        super().__init__(f"No handler registered for channel: {channel}")


class MessageValidationError(MessagePipelineError):
    """Raised when an inbound message fails validation."""


# ---------------------------------------------------------------------------
# Message Pipeline
# ---------------------------------------------------------------------------


class MessagePipeline:
    """Channel-agnostic message processing — REQ-CORE-01.

    Flow: Inbound → Middleware(in) → Normalize → VAP Pipeline → Middleware(out) → Deliver

    Features:
    - 4 channel types: api, websocket, webhook, adapter
    - Pluggable middleware stack (pre/post processing)
    - Message normalization into Task objects
    - Response routing back to originating channel
    - Per-message metrics (latency, status)
    """

    def __init__(
        self,
        *,
        pipeline: PipelineRunner,
        max_content_length: int = 100_000,
    ) -> None:
        self._pipeline = pipeline
        self._max_content_length = max_content_length
        self._channels: dict[str, ChannelHandler] = {}
        self._middleware: list[Middleware] = []
        self._processed_count: int = 0
        self._error_count: int = 0

    # -- Registration --

    def register_channel(self, name: str, handler: ChannelHandler) -> None:
        """Register a channel handler for delivering responses."""
        self._channels[name] = handler
        logger.info("MessagePipeline: registered channel=%s", name)

    def unregister_channel(self, name: str) -> None:
        """Remove a previously registered channel handler."""
        self._channels.pop(name, None)

    @property
    def registered_channels(self) -> list[str]:
        """List of registered channel names."""
        return list(self._channels)

    def add_middleware(self, mw: Middleware) -> None:
        """Append middleware to the processing stack."""
        self._middleware.append(mw)

    @property
    def processed_count(self) -> int:
        return self._processed_count

    @property
    def error_count(self) -> int:
        return self._error_count

    # -- Validation --

    def _validate_message(self, msg: InboundMessage) -> None:
        """Validate inbound message fields."""
        if not msg.content or not msg.content.strip():
            raise MessageValidationError("Message content must not be empty")
        if len(msg.content) > self._max_content_length:
            raise MessageValidationError(
                f"Message content exceeds max length "
                f"({len(msg.content)} > {self._max_content_length})"
            )
        if not msg.sender_id or not msg.sender_id.strip():
            raise MessageValidationError("sender_id must not be empty")
        if not msg.channel or not msg.channel.strip():
            raise MessageValidationError("channel must not be empty")

    # -- Normalization --

    @staticmethod
    def _to_task(msg: InboundMessage) -> Task:
        """Normalize an inbound message into a pipeline Task."""
        return Task(
            name=f"msg:{msg.message_id}",
            description=msg.content,
            agent_type=msg.agent_type,
            risk_level=msg.risk_level,
            metadata={
                "_source": "message_pipeline",
                "_channel": msg.channel,
                "_sender_id": msg.sender_id,
                "_session_id": msg.session_id,
                "_message_id": msg.message_id,
                **msg.metadata,
            },
        )

    @staticmethod
    def _to_outbound(
        msg: InboundMessage,
        result: PipelineResult,
    ) -> OutboundMessage:
        """Convert pipeline result to outbound message."""
        if result.success:
            content = result.evidence.get("ship", {}).get(
                "summary", "Task completed successfully."
            )
            if isinstance(content, dict):
                content = str(content)
        else:
            content = f"Task failed: {result.error or 'unknown error'}"

        return OutboundMessage(
            channel=msg.channel,
            recipient_id=msg.sender_id,
            content=str(content),
            session_id=msg.session_id,
            in_reply_to=msg.message_id,
            success=result.success,
            evidence=result.evidence,
        )

    # -- Core processing --

    async def process(self, message: InboundMessage) -> OutboundMessage:
        """Process an inbound message through the full pipeline.

        1. Validate → 2. Middleware(in) → 3. Normalize → 4. VAP run
        → 5. Build response → 6. Middleware(out) → 7. Deliver
        """
        t0 = time.monotonic()
        self._processed_count += 1

        try:
            # 1. Validate
            self._validate_message(message)

            # 2. Inbound middleware
            msg = message
            for mw in self._middleware:
                msg = await mw.process_inbound(msg)

            # 3. Normalize to Task
            task = self._to_task(msg)

            # 4. Run through VAP pipeline
            result = await self._pipeline.run(task)

            # 5. Build outbound
            outbound = self._to_outbound(msg, result)

            # 6. Outbound middleware
            for mw in self._middleware:
                outbound = await mw.process_outbound(outbound)

            # 7. Deliver (if handler registered)
            if msg.channel in self._channels:
                handler = self._channels[msg.channel]
                delivered = await handler.deliver(outbound)
                outbound.metadata["_delivered"] = delivered
            else:
                outbound.metadata["_delivered"] = False
                logger.warning(
                    "No channel handler for %s — response not delivered",
                    msg.channel,
                )

            latency = round(time.monotonic() - t0, 4)
            outbound.metadata["_latency_s"] = latency
            logger.info(
                "MessagePipeline: processed msg=%s channel=%s success=%s %.3fs",
                message.message_id,
                message.channel,
                outbound.success,
                latency,
            )
            return outbound

        except MessagePipelineError:
            self._error_count += 1
            raise

        except Exception as exc:
            self._error_count += 1
            logger.exception(
                "MessagePipeline: unexpected error for msg=%s",
                message.message_id,
            )
            return OutboundMessage(
                channel=message.channel,
                recipient_id=message.sender_id,
                content=f"Internal error: {exc}",
                session_id=message.session_id,
                in_reply_to=message.message_id,
                success=False,
            )

    async def process_batch(
        self, messages: list[InboundMessage]
    ) -> list[OutboundMessage]:
        """Process multiple messages sequentially, collecting results."""
        results: list[OutboundMessage] = []
        for msg in messages:
            try:
                result = await self.process(msg)
                results.append(result)
            except MessagePipelineError as exc:
                results.append(OutboundMessage(
                    channel=msg.channel,
                    recipient_id=msg.sender_id,
                    content=f"Error: {exc}",
                    session_id=msg.session_id,
                    in_reply_to=msg.message_id,
                    success=False,
                ))
        return results

    def get_stats(self) -> dict[str, Any]:
        """Return pipeline processing statistics."""
        return {
            "processed_count": self._processed_count,
            "error_count": self._error_count,
            "registered_channels": self.registered_channels,
            "middleware_count": len(self._middleware),
        }
