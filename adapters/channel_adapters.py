"""Channel Adapters — Messaging channel adapters for MessagePipeline.

Provides concrete adapter implementations for delivering and receiving messages
across different transport channels: Webhook, SSE, WebSocket.

NO external I/O dependencies — all network operations are stubbed.
Production implementations will use aiohttp / starlette SSE / websockets.

Usage::

    router = ChannelRouter()
    router.register(WebhookAdapter(url="https://example.com/hook"))
    router.register(SSEAdapter(endpoint="/events"))
    router.register(WebSocketAdapter(url="wss://example.com/ws"))

    msg = OutboundMessage(channel="webhook", ...)
    await router.route(msg)
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from abc import ABC, abstractmethod
from collections import deque, defaultdict
from dataclasses import dataclass, field
from typing import Any

from orchestrator.message_pipeline import InboundMessage, OutboundMessage


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ChannelAdapterError(Exception):
    """Base error for channel adapters."""


class ChannelNotFoundError(ChannelAdapterError):
    """Raised when routing to an unregistered channel."""

    def __init__(self, channel: str) -> None:
        self.channel = channel
        super().__init__(f"No adapter registered for channel: {channel}")


class ChannelDeliveryError(ChannelAdapterError):
    """Raised when message delivery fails."""

    def __init__(self, channel: str, reason: str = "") -> None:
        self.channel = channel
        self.reason = reason
        super().__init__(f"Delivery failed for channel '{channel}': {reason}")


# ---------------------------------------------------------------------------
# Base adapter
# ---------------------------------------------------------------------------


class BaseChannelAdapter(ABC):
    """Abstract base for all channel adapters."""

    def __init__(self) -> None:
        self._connected: bool = False
        self._delivered_count: int = 0
        self._receive_count: int = 0

    @property
    @abstractmethod
    def channel_name(self) -> str:
        """Unique name identifying this channel."""

    @abstractmethod
    async def deliver(self, message: OutboundMessage) -> bool:
        """Deliver an outbound message. Returns True on success."""

    async def receive(self) -> InboundMessage | None:
        """Poll for an inbound message. Returns None if none available."""
        return None

    async def connect(self) -> None:
        """Establish channel connection."""
        self._connected = True

    async def disconnect(self) -> None:
        """Tear down channel connection."""
        self._connected = False

    @property
    def is_connected(self) -> bool:
        """True if adapter is connected."""
        return self._connected

    def get_stats(self) -> dict[str, Any]:
        """Return per-adapter statistics."""
        return {
            "channel": self.channel_name,
            "connected": self._connected,
            "delivered": self._delivered_count,
            "received": self._receive_count,
        }


# ---------------------------------------------------------------------------
# Webhook adapter
# ---------------------------------------------------------------------------


@dataclass
class WebhookConfig:
    """Configuration for WebhookAdapter."""

    url: str
    secret: str = ""
    method: str = "POST"
    headers: dict[str, str] = field(default_factory=dict)


class WebhookAdapter(BaseChannelAdapter):
    """Adapter for outbound webhook delivery and inbound webhook receive.

    Delivery builds the HTTP payload (does NOT send — stub mode).
    Receive parses payloads from an internal queue (enqueue_webhook for testing).
    HMAC-SHA256 signature verification on incoming webhooks.
    """

    def __init__(
        self,
        url: str,
        secret: str = "",
        method: str = "POST",
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__()
        self._config = WebhookConfig(
            url=url,
            secret=secret,
            method=method,
            headers=headers or {},
        )
        self._outbound_log: list[dict[str, Any]] = []
        self._receive_queue: deque[dict[str, Any]] = deque()

    @property
    def channel_name(self) -> str:
        return "webhook"

    async def connect(self) -> None:
        """Webhook adapter does not maintain a persistent connection."""
        self._connected = True

    async def disconnect(self) -> None:
        self._connected = False

    async def deliver(self, message: OutboundMessage) -> bool:
        """Build HTTP webhook payload and record to outbound log (stub)."""
        payload = {
            "message_id": message.message_id,
            "channel": message.channel,
            "recipient_id": message.recipient_id,
            "content": message.content,
            "session_id": message.session_id,
            "in_reply_to": message.in_reply_to,
            "timestamp": message.timestamp.isoformat(),
            "success": message.success,
            "metadata": message.metadata,
        }

        request = {
            "url": self._config.url,
            "method": self._config.method,
            "headers": {**self._config.headers, "Content-Type": "application/json"},
            "payload": payload,
            "delivery_id": uuid.uuid4().hex[:16],
        }

        # Add HMAC signature if secret configured
        if self._config.secret:
            body = json.dumps(payload, sort_keys=True)
            sig = hmac.new(
                self._config.secret.encode(),
                body.encode(),
                hashlib.sha256,
            ).hexdigest()
            request["headers"]["X-OCCP-Signature"] = f"sha256={sig}"

        self._outbound_log.append(request)
        self._delivered_count += 1
        return True

    def enqueue_webhook(self, payload: dict[str, Any]) -> None:
        """Push a raw webhook payload into the receive queue (testing helper)."""
        self._receive_queue.append(payload)

    async def receive(self) -> InboundMessage | None:
        """Dequeue and parse the next webhook payload."""
        if not self._receive_queue:
            return None

        payload = self._receive_queue.popleft()
        self._receive_count += 1

        return InboundMessage(
            channel="webhook",
            sender_id=payload.get("sender_id", "webhook"),
            content=payload.get("content", ""),
            session_id=payload.get("session_id", ""),
            message_id=payload.get("message_id", uuid.uuid4().hex[:16]),
            metadata=payload.get("metadata", {}),
        )

    def verify_signature(self, body: str | bytes, signature: str) -> bool:
        """Verify HMAC-SHA256 signature on incoming webhook payload.

        Expects signature in format: 'sha256=<hexdigest>'
        Returns False if secret not configured or signature invalid.
        """
        if not self._config.secret:
            return False

        if isinstance(body, str):
            body = body.encode()

        expected = hmac.new(
            self._config.secret.encode(),
            body,
            hashlib.sha256,
        ).hexdigest()

        # Strip prefix
        received = signature
        if received.startswith("sha256="):
            received = received[7:]

        return hmac.compare_digest(expected, received)

    @property
    def outbound_log(self) -> list[dict[str, Any]]:
        """Recorded outbound deliveries (stub mode)."""
        return list(self._outbound_log)


# ---------------------------------------------------------------------------
# SSE adapter
# ---------------------------------------------------------------------------


@dataclass
class SSEConfig:
    """Configuration for SSEAdapter."""

    endpoint: str
    max_connections: int = 100


class SSEAdapter(BaseChannelAdapter):
    """Adapter for Server-Sent Events delivery.

    Formats messages as SSE events and pushes to a virtual connection pool.
    No real HTTP server — stubs record dispatched events.
    """

    def __init__(self, endpoint: str, max_connections: int = 100) -> None:
        super().__init__()
        self._config = SSEConfig(endpoint=endpoint, max_connections=max_connections)
        self._connections: dict[str, list[str]] = {}  # connection_id -> event log
        self._event_log: list[dict[str, Any]] = []

    @property
    def channel_name(self) -> str:
        return "sse"

    async def deliver(self, message: OutboundMessage) -> bool:
        """Format as SSE event and push to all active connections."""
        event_id = uuid.uuid4().hex[:16]
        event_data = json.dumps({
            "message_id": message.message_id,
            "content": message.content,
            "recipient_id": message.recipient_id,
            "success": message.success,
            "timestamp": message.timestamp.isoformat(),
        })

        # SSE wire format
        sse_event = (
            f"id: {event_id}\n"
            f"event: message\n"
            f"data: {event_data}\n\n"
        )

        # Push to all connections
        for conn_id, log in self._connections.items():
            log.append(sse_event)

        self._event_log.append({
            "event_id": event_id,
            "message_id": message.message_id,
            "sse": sse_event,
            "connection_count": len(self._connections),
        })

        self._delivered_count += 1
        return True

    def add_connection(self, connection_id: str) -> None:
        """Register a new SSE connection."""
        if len(self._connections) >= self._config.max_connections:
            raise ChannelAdapterError(
                f"SSE max connections reached ({self._config.max_connections})"
            )
        self._connections[connection_id] = []

    def remove_connection(self, connection_id: str) -> None:
        """Remove an SSE connection."""
        self._connections.pop(connection_id, None)

    def get_connection_count(self) -> int:
        """Return number of active SSE connections."""
        return len(self._connections)

    def get_connection_events(self, connection_id: str) -> list[str]:
        """Return events dispatched to a specific connection (stub)."""
        return list(self._connections.get(connection_id, []))

    @property
    def event_log(self) -> list[dict[str, Any]]:
        """All events dispatched (stub mode)."""
        return list(self._event_log)


# ---------------------------------------------------------------------------
# WebSocket adapter
# ---------------------------------------------------------------------------


@dataclass
class WebSocketConfig:
    """Configuration for WebSocketAdapter."""

    url: str
    max_connections: int = 100
    heartbeat_interval: float = 30.0


class WebSocketAdapter(BaseChannelAdapter):
    """Adapter for WebSocket delivery and broadcasting.

    Maintains a virtual pool of connections and delivers messages to clients.
    No real WebSocket — stubs record dispatched messages.
    """

    def __init__(
        self,
        url: str,
        max_connections: int = 100,
        heartbeat_interval: float = 30.0,
    ) -> None:
        super().__init__()
        self._config = WebSocketConfig(
            url=url,
            max_connections=max_connections,
            heartbeat_interval=heartbeat_interval,
        )
        self._connections: dict[str, list[str]] = {}  # connection_id -> message log
        self._broadcast_log: list[str] = []

    @property
    def channel_name(self) -> str:
        return "websocket"

    async def deliver(self, message: OutboundMessage) -> bool:
        """Format and push message to all connected clients."""
        payload = json.dumps({
            "message_id": message.message_id,
            "content": message.content,
            "recipient_id": message.recipient_id,
            "success": message.success,
            "timestamp": message.timestamp.isoformat(),
        })

        for conn_id, log in self._connections.items():
            log.append(payload)

        self._delivered_count += 1
        return True

    def add_connection(self, connection_id: str) -> None:
        """Register a new WebSocket connection."""
        if len(self._connections) >= self._config.max_connections:
            raise ChannelAdapterError(
                f"WebSocket max connections reached ({self._config.max_connections})"
            )
        self._connections[connection_id] = []

    def remove_connection(self, connection_id: str) -> None:
        """Remove a WebSocket connection."""
        self._connections.pop(connection_id, None)

    async def broadcast(self, message: str) -> None:
        """Send a raw text message to all connected clients."""
        for conn_id, log in self._connections.items():
            log.append(message)
        self._broadcast_log.append(message)

    def get_connection_messages(self, connection_id: str) -> list[str]:
        """Return messages delivered to a specific connection (stub)."""
        return list(self._connections.get(connection_id, []))

    @property
    def broadcast_log(self) -> list[str]:
        """All broadcast messages (stub mode)."""
        return list(self._broadcast_log)

    @property
    def heartbeat_interval(self) -> float:
        return self._config.heartbeat_interval


# ---------------------------------------------------------------------------
# Channel Router
# ---------------------------------------------------------------------------


class ChannelRouter:
    """Routes OutboundMessages to the appropriate channel adapter.

    Adapters are keyed by channel_name. ChannelRouter is the single
    dispatch point for multi-channel delivery.
    """

    def __init__(self) -> None:
        self._adapters: dict[str, BaseChannelAdapter] = {}
        self._message_counts: dict[str, int] = defaultdict(int)

    def register(self, adapter: BaseChannelAdapter) -> None:
        """Register an adapter by its channel_name."""
        self._adapters[adapter.channel_name] = adapter

    async def route(self, message: OutboundMessage) -> bool:
        """Deliver message via the adapter matching message.channel.

        Raises ChannelNotFoundError if no adapter is registered.
        """
        adapter = self._adapters.get(message.channel)
        if adapter is None:
            raise ChannelNotFoundError(message.channel)

        result = await adapter.deliver(message)
        if result:
            self._message_counts[message.channel] += 1
        return result

    def get_adapter(self, name: str) -> BaseChannelAdapter | None:
        """Return the adapter registered under *name*, or None."""
        return self._adapters.get(name)

    def list_channels(self) -> list[str]:
        """Return list of registered channel names."""
        return list(self._adapters.keys())

    def get_stats(self) -> dict[str, Any]:
        """Return per-channel message delivery counts."""
        return {
            "channels": list(self._adapters.keys()),
            "message_counts": dict(self._message_counts),
            "total_delivered": sum(self._message_counts.values()),
        }
