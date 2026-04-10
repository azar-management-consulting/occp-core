"""Tests for Channel Adapters — Messaging channel adapters for MessagePipeline.

Covers:
- BaseChannelAdapter: ABC enforcement, interface
- WebhookAdapter: deliver, receive, enqueue, HMAC, connect/disconnect, stats
- SSEAdapter: deliver, connections, max connections, disconnect
- WebSocketAdapter: deliver, broadcast, connections, heartbeat config
- ChannelRouter: register, route, missing channel, list, stats
- ChannelErrors: error types
- Acceptance tests: ACC-CH-01 through ACC-CH-05
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone
from typing import Any

import pytest

from adapters.channel_adapters import (
    BaseChannelAdapter,
    ChannelAdapterError,
    ChannelDeliveryError,
    ChannelNotFoundError,
    ChannelRouter,
    SSEAdapter,
    WebSocketAdapter,
    WebhookAdapter,
)
from orchestrator.message_pipeline import InboundMessage, OutboundMessage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_outbound(
    channel: str = "webhook",
    content: str = "Hello",
    recipient_id: str = "user-1",
    session_id: str = "sess-abc",
    success: bool = True,
) -> OutboundMessage:
    return OutboundMessage(
        channel=channel,
        recipient_id=recipient_id,
        content=content,
        session_id=session_id,
        success=success,
    )


# ---------------------------------------------------------------------------
# TestBaseChannelAdapter
# ---------------------------------------------------------------------------


class TestBaseChannelAdapter:
    def test_cannot_instantiate_abc(self):
        with pytest.raises(TypeError):
            BaseChannelAdapter()  # type: ignore[abstract]

    def test_missing_channel_name_enforced(self):
        """Subclass without channel_name and deliver should fail."""
        class IncompleteAdapter(BaseChannelAdapter):
            pass  # missing channel_name and deliver

        with pytest.raises(TypeError):
            IncompleteAdapter()  # type: ignore[abstract]

    def test_concrete_subclass_must_implement_interface(self):
        class GoodAdapter(BaseChannelAdapter):
            @property
            def channel_name(self) -> str:
                return "test"

            async def deliver(self, message: OutboundMessage) -> bool:
                return True

        adapter = GoodAdapter()
        assert adapter.channel_name == "test"
        assert adapter.is_connected is False


# ---------------------------------------------------------------------------
# TestWebhookAdapter
# ---------------------------------------------------------------------------


class TestWebhookAdapter:
    @pytest.mark.asyncio
    async def test_deliver_records_to_log(self):
        adapter = WebhookAdapter(url="https://example.com/hook")
        msg = _make_outbound(channel="webhook")
        result = await adapter.deliver(msg)
        assert result is True
        assert len(adapter.outbound_log) == 1

    @pytest.mark.asyncio
    async def test_deliver_payload_structure(self):
        adapter = WebhookAdapter(url="https://example.com/hook")
        msg = _make_outbound(content="Test payload")
        await adapter.deliver(msg)
        entry = adapter.outbound_log[0]
        assert entry["url"] == "https://example.com/hook"
        assert entry["method"] == "POST"
        assert entry["payload"]["content"] == "Test payload"

    @pytest.mark.asyncio
    async def test_receive_empty_queue(self):
        adapter = WebhookAdapter(url="https://example.com/hook")
        result = await adapter.receive()
        assert result is None

    @pytest.mark.asyncio
    async def test_enqueue_and_receive(self):
        adapter = WebhookAdapter(url="https://example.com/hook")
        adapter.enqueue_webhook({
            "sender_id": "user-123",
            "content": "Incoming event",
            "session_id": "sess-001",
        })
        msg = await adapter.receive()
        assert msg is not None
        assert msg.sender_id == "user-123"
        assert msg.content == "Incoming event"
        assert msg.channel == "webhook"

    @pytest.mark.asyncio
    async def test_hmac_signature_on_delivery(self):
        adapter = WebhookAdapter(url="https://example.com/hook", secret="my-secret")
        msg = _make_outbound()
        await adapter.deliver(msg)
        entry = adapter.outbound_log[0]
        assert "X-OCCP-Signature" in entry["headers"]
        sig = entry["headers"]["X-OCCP-Signature"]
        assert sig.startswith("sha256=")

    def test_verify_signature_valid(self):
        secret = "test-secret"
        adapter = WebhookAdapter(url="https://example.com/hook", secret=secret)
        body = '{"key": "value"}'
        expected_sig = hmac.new(
            secret.encode(), body.encode(), hashlib.sha256
        ).hexdigest()
        assert adapter.verify_signature(body, f"sha256={expected_sig}") is True

    def test_verify_signature_invalid(self):
        adapter = WebhookAdapter(url="https://example.com/hook", secret="secret")
        assert adapter.verify_signature("body", "sha256=badhex") is False

    def test_verify_signature_no_secret(self):
        adapter = WebhookAdapter(url="https://example.com/hook")
        assert adapter.verify_signature("body", "sha256=anything") is False

    @pytest.mark.asyncio
    async def test_connect_disconnect(self):
        adapter = WebhookAdapter(url="https://example.com/hook")
        assert adapter.is_connected is False
        await adapter.connect()
        assert adapter.is_connected is True
        await adapter.disconnect()
        assert adapter.is_connected is False

    @pytest.mark.asyncio
    async def test_stats(self):
        adapter = WebhookAdapter(url="https://example.com/hook")
        await adapter.connect()
        msg = _make_outbound()
        await adapter.deliver(msg)
        stats = adapter.get_stats()
        assert stats["delivered"] == 1
        assert stats["channel"] == "webhook"
        assert stats["connected"] is True


# ---------------------------------------------------------------------------
# TestSSEAdapter
# ---------------------------------------------------------------------------


class TestSSEAdapter:
    @pytest.mark.asyncio
    async def test_deliver_no_connections(self):
        adapter = SSEAdapter(endpoint="/events")
        msg = _make_outbound(channel="sse")
        result = await adapter.deliver(msg)
        assert result is True
        assert len(adapter.event_log) == 1

    @pytest.mark.asyncio
    async def test_deliver_to_connections(self):
        adapter = SSEAdapter(endpoint="/events")
        adapter.add_connection("conn-1")
        adapter.add_connection("conn-2")
        msg = _make_outbound(channel="sse", content="Event data")
        await adapter.deliver(msg)
        events_1 = adapter.get_connection_events("conn-1")
        events_2 = adapter.get_connection_events("conn-2")
        assert len(events_1) == 1
        assert len(events_2) == 1
        assert "Event data" in events_1[0]

    def test_add_remove_connection(self):
        adapter = SSEAdapter(endpoint="/events")
        adapter.add_connection("conn-a")
        assert adapter.get_connection_count() == 1
        adapter.remove_connection("conn-a")
        assert adapter.get_connection_count() == 0

    def test_max_connections_enforced(self):
        adapter = SSEAdapter(endpoint="/events", max_connections=2)
        adapter.add_connection("conn-1")
        adapter.add_connection("conn-2")
        with pytest.raises(ChannelAdapterError):
            adapter.add_connection("conn-3")

    @pytest.mark.asyncio
    async def test_disconnect_clears_connected(self):
        adapter = SSEAdapter(endpoint="/events")
        await adapter.connect()
        assert adapter.is_connected is True
        await adapter.disconnect()
        assert adapter.is_connected is False

    @pytest.mark.asyncio
    async def test_sse_event_format(self):
        adapter = SSEAdapter(endpoint="/events")
        adapter.add_connection("conn-1")
        msg = _make_outbound(channel="sse", content="Test SSE")
        await adapter.deliver(msg)
        events = adapter.get_connection_events("conn-1")
        assert len(events) == 1
        sse = events[0]
        assert "id: " in sse
        assert "event: message" in sse
        assert "data: " in sse
        assert "Test SSE" in sse


# ---------------------------------------------------------------------------
# TestWebSocketAdapter
# ---------------------------------------------------------------------------


class TestWebSocketAdapter:
    @pytest.mark.asyncio
    async def test_deliver_to_connections(self):
        adapter = WebSocketAdapter(url="wss://example.com/ws")
        adapter.add_connection("ws-1")
        adapter.add_connection("ws-2")
        msg = _make_outbound(channel="websocket", content="WS message")
        result = await adapter.deliver(msg)
        assert result is True
        msgs_1 = adapter.get_connection_messages("ws-1")
        msgs_2 = adapter.get_connection_messages("ws-2")
        assert len(msgs_1) == 1
        assert len(msgs_2) == 1
        data = json.loads(msgs_1[0])
        assert data["content"] == "WS message"

    @pytest.mark.asyncio
    async def test_broadcast(self):
        adapter = WebSocketAdapter(url="wss://example.com/ws")
        adapter.add_connection("ws-a")
        adapter.add_connection("ws-b")
        await adapter.broadcast("ping")
        assert adapter.get_connection_messages("ws-a") == ["ping"]
        assert adapter.get_connection_messages("ws-b") == ["ping"]
        assert adapter.broadcast_log == ["ping"]

    def test_add_remove_connections(self):
        adapter = WebSocketAdapter(url="wss://example.com/ws")
        adapter.add_connection("ws-1")
        assert len(adapter._connections) == 1
        adapter.remove_connection("ws-1")
        assert len(adapter._connections) == 0

    def test_max_connections_enforced(self):
        adapter = WebSocketAdapter(url="wss://example.com/ws", max_connections=2)
        adapter.add_connection("ws-1")
        adapter.add_connection("ws-2")
        with pytest.raises(ChannelAdapterError):
            adapter.add_connection("ws-3")

    def test_heartbeat_interval_config(self):
        adapter = WebSocketAdapter(
            url="wss://example.com/ws", heartbeat_interval=15.0
        )
        assert adapter.heartbeat_interval == 15.0

    @pytest.mark.asyncio
    async def test_deliver_no_connections(self):
        adapter = WebSocketAdapter(url="wss://example.com/ws")
        msg = _make_outbound(channel="websocket")
        result = await adapter.deliver(msg)
        assert result is True
        assert adapter._delivered_count == 1


# ---------------------------------------------------------------------------
# TestChannelRouter
# ---------------------------------------------------------------------------


class TestChannelRouter:
    @pytest.mark.asyncio
    async def test_register_and_route(self):
        router = ChannelRouter()
        adapter = WebhookAdapter(url="https://example.com/hook")
        router.register(adapter)
        msg = _make_outbound(channel="webhook")
        result = await router.route(msg)
        assert result is True

    @pytest.mark.asyncio
    async def test_route_missing_channel_raises(self):
        router = ChannelRouter()
        msg = _make_outbound(channel="unknown")
        with pytest.raises(ChannelNotFoundError) as exc_info:
            await router.route(msg)
        assert "unknown" in str(exc_info.value)

    def test_list_channels(self):
        router = ChannelRouter()
        router.register(WebhookAdapter(url="https://example.com"))
        router.register(SSEAdapter(endpoint="/events"))
        channels = router.list_channels()
        assert "webhook" in channels
        assert "sse" in channels

    def test_get_adapter(self):
        router = ChannelRouter()
        adapter = SSEAdapter(endpoint="/events")
        router.register(adapter)
        found = router.get_adapter("sse")
        assert found is adapter

    def test_get_adapter_missing(self):
        router = ChannelRouter()
        assert router.get_adapter("nonexistent") is None

    @pytest.mark.asyncio
    async def test_stats_counts(self):
        router = ChannelRouter()
        router.register(WebhookAdapter(url="https://example.com"))
        msg = _make_outbound(channel="webhook")
        await router.route(msg)
        await router.route(msg)
        stats = router.get_stats()
        assert stats["message_counts"]["webhook"] == 2
        assert stats["total_delivered"] == 2

    @pytest.mark.asyncio
    async def test_router_delivers_to_correct_adapter(self):
        router = ChannelRouter()
        wh = WebhookAdapter(url="https://example.com/hook")
        sse = SSEAdapter(endpoint="/events")
        router.register(wh)
        router.register(sse)

        await router.route(_make_outbound(channel="webhook"))
        await router.route(_make_outbound(channel="sse"))

        assert len(wh.outbound_log) == 1
        assert len(sse.event_log) == 1


# ---------------------------------------------------------------------------
# TestChannelErrors
# ---------------------------------------------------------------------------


class TestChannelErrors:
    def test_channel_not_found_error(self):
        err = ChannelNotFoundError("my-channel")
        assert "my-channel" in str(err)
        assert err.channel == "my-channel"

    def test_delivery_error(self):
        err = ChannelDeliveryError("webhook", "Connection refused")
        assert "webhook" in str(err)
        assert "Connection refused" in str(err)
        assert err.channel == "webhook"
        assert err.reason == "Connection refused"

    def test_error_hierarchy(self):
        assert issubclass(ChannelNotFoundError, ChannelAdapterError)
        assert issubclass(ChannelDeliveryError, ChannelAdapterError)


# ---------------------------------------------------------------------------
# Acceptance Tests
# ---------------------------------------------------------------------------


class TestAcceptanceChannel:
    @pytest.mark.asyncio
    async def test_acc_ch_01_webhook_roundtrip(self):
        """ACC-CH-01: Webhook deliver + receive roundtrip."""
        adapter = WebhookAdapter(url="https://example.com/hook")
        await adapter.connect()

        # Deliver outbound
        msg = _make_outbound(channel="webhook", content="Outbound payload")
        delivered = await adapter.deliver(msg)
        assert delivered is True
        assert len(adapter.outbound_log) == 1

        # Receive inbound via queue
        adapter.enqueue_webhook({
            "sender_id": "remote-service",
            "content": "Acknowledgement",
            "session_id": "sess-roundtrip",
        })
        inbound = await adapter.receive()
        assert inbound is not None
        assert inbound.content == "Acknowledgement"
        assert inbound.sender_id == "remote-service"

        # Queue now empty
        empty = await adapter.receive()
        assert empty is None

    @pytest.mark.asyncio
    async def test_acc_ch_02_sse_connections_and_delivery(self):
        """ACC-CH-02: SSE adapter manages connections and delivers events."""
        adapter = SSEAdapter(endpoint="/stream", max_connections=50)
        await adapter.connect()

        adapter.add_connection("browser-1")
        adapter.add_connection("browser-2")
        assert adapter.get_connection_count() == 2

        msg = _make_outbound(channel="sse", content="Live update")
        await adapter.deliver(msg)

        for conn_id in ("browser-1", "browser-2"):
            events = adapter.get_connection_events(conn_id)
            assert len(events) == 1
            assert "Live update" in events[0]
            assert "event: message" in events[0]

        # Remove one connection
        adapter.remove_connection("browser-1")
        assert adapter.get_connection_count() == 1

        # Next delivery only goes to browser-2
        msg2 = _make_outbound(channel="sse", content="Update 2")
        await adapter.deliver(msg2)
        assert len(adapter.get_connection_events("browser-2")) == 2

    @pytest.mark.asyncio
    async def test_acc_ch_03_websocket_broadcast(self):
        """ACC-CH-03: WebSocket adapter broadcasts to all connected clients."""
        adapter = WebSocketAdapter(url="wss://example.com/ws", max_connections=100)

        for i in range(5):
            adapter.add_connection(f"client-{i}")

        await adapter.broadcast("system-broadcast")

        for i in range(5):
            msgs = adapter.get_connection_messages(f"client-{i}")
            assert "system-broadcast" in msgs

        assert len(adapter.broadcast_log) == 1

    @pytest.mark.asyncio
    async def test_acc_ch_04_router_correct_channel(self):
        """ACC-CH-04: Router delivers to correct channel adapter."""
        router = ChannelRouter()
        wh = WebhookAdapter(url="https://example.com/hook")
        sse = SSEAdapter(endpoint="/events")
        ws = WebSocketAdapter(url="wss://example.com/ws")
        router.register(wh)
        router.register(sse)
        router.register(ws)

        # Route 3 messages to 3 channels
        await router.route(_make_outbound(channel="webhook", content="WH msg"))
        await router.route(_make_outbound(channel="sse", content="SSE msg"))
        await router.route(_make_outbound(channel="websocket", content="WS msg"))

        # Each adapter received exactly 1 message
        assert len(wh.outbound_log) == 1
        assert len(sse.event_log) == 1
        assert ws._delivered_count == 1

        stats = router.get_stats()
        assert stats["total_delivered"] == 3
        assert stats["message_counts"]["webhook"] == 1
        assert stats["message_counts"]["sse"] == 1
        assert stats["message_counts"]["websocket"] == 1

    @pytest.mark.asyncio
    async def test_acc_ch_05_hmac_signature_verification(self):
        """ACC-CH-05: HMAC signature verification on webhook."""
        secret = "super-secret-key"
        adapter = WebhookAdapter(url="https://example.com/hook", secret=secret)

        # Deliver a message — should include signature
        msg = _make_outbound(channel="webhook", content="Signed payload")
        await adapter.deliver(msg)

        entry = adapter.outbound_log[0]
        assert "X-OCCP-Signature" in entry["headers"]
        sig_header = entry["headers"]["X-OCCP-Signature"]
        assert sig_header.startswith("sha256=")

        # Verify that the signature is correct for the payload body
        payload_json = json.dumps(entry["payload"], sort_keys=True)
        expected_digest = hmac.new(
            secret.encode(), payload_json.encode(), hashlib.sha256
        ).hexdigest()
        assert sig_header == f"sha256={expected_digest}"

        # Verify using adapter method
        assert adapter.verify_signature(payload_json, sig_header) is True

        # Tampered body should fail
        assert adapter.verify_signature("tampered body", sig_header) is False
