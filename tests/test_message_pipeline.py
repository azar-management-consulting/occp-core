"""Tests for MessagePipeline — REQ-CORE-01: Channel-Agnostic Message Processing.

Covers:
- InboundMessage / OutboundMessage dataclass construction + to_dict
- ChannelType enum values
- MessagePipeline.register_channel / unregister_channel
- MessagePipeline.add_middleware
- Validation: empty content, empty sender, empty channel, oversized content
- Full process() happy path: validate → middleware(in) → VAP → middleware(out) → deliver
- process() with unregistered channel (no delivery)
- process() with pipeline failure
- process() unexpected exception → OutboundMessage(success=False)
- Inbound/outbound middleware ordering
- process_batch() collects results
- process_batch() with validation errors
- get_stats() counters
- _to_task normalization
- _to_outbound success/failure mapping
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from orchestrator.message_pipeline import (
    ChannelType,
    InboundMessage,
    MessagePipeline,
    MessagePipelineError,
    MessageValidationError,
    OutboundMessage,
    UnknownChannelError,
)
from orchestrator.models import PipelineResult, RiskLevel, Task, TaskStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pipeline_runner(success: bool = True, error: str = "") -> MagicMock:
    runner = MagicMock()
    result = PipelineResult(
        task_id="t-1",
        success=success,
        status=TaskStatus.COMPLETED if success else TaskStatus.FAILED,
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
        evidence={"ship": {"summary": "Done."}} if success else {},
        error=error if not success else "",
    )
    runner.run = AsyncMock(return_value=result)
    return runner


def _make_channel_handler(success: bool = True) -> MagicMock:
    h = MagicMock()
    h.deliver = AsyncMock(return_value=success)
    return h


def _make_middleware() -> MagicMock:
    mw = MagicMock()
    mw.process_inbound = AsyncMock(side_effect=lambda m: m)
    mw.process_outbound = AsyncMock(side_effect=lambda m: m)
    return mw


def _msg(
    channel: str = "api",
    sender_id: str = "user-1",
    content: str = "Hello",
    **kwargs: Any,
) -> InboundMessage:
    return InboundMessage(
        channel=channel, sender_id=sender_id, content=content, **kwargs
    )


# ---------------------------------------------------------------------------
# ChannelType enum
# ---------------------------------------------------------------------------


class TestChannelType:
    def test_values(self) -> None:
        assert ChannelType.API == "api"
        assert ChannelType.WEBSOCKET == "websocket"
        assert ChannelType.WEBHOOK == "webhook"
        assert ChannelType.ADAPTER == "adapter"

    def test_all_four(self) -> None:
        assert len(ChannelType) == 4


# ---------------------------------------------------------------------------
# InboundMessage / OutboundMessage
# ---------------------------------------------------------------------------


class TestMessageModels:
    def test_inbound_defaults(self) -> None:
        m = InboundMessage(channel="api", sender_id="u1", content="hi")
        assert m.channel == "api"
        assert m.sender_id == "u1"
        assert m.content == "hi"
        assert m.agent_type == "default"
        assert m.risk_level == RiskLevel.LOW
        assert len(m.message_id) == 16
        assert isinstance(m.timestamp, datetime)

    def test_inbound_to_dict(self) -> None:
        m = _msg()
        d = m.to_dict()
        assert d["channel"] == "api"
        assert d["sender_id"] == "user-1"
        assert d["content"] == "Hello"
        assert "timestamp" in d

    def test_outbound_defaults(self) -> None:
        o = OutboundMessage(channel="api", recipient_id="u1", content="ok")
        assert o.success is True
        assert o.in_reply_to == ""
        assert len(o.message_id) == 16

    def test_outbound_to_dict(self) -> None:
        o = OutboundMessage(
            channel="ws", recipient_id="u2", content="resp", in_reply_to="msg-1"
        )
        d = o.to_dict()
        assert d["in_reply_to"] == "msg-1"
        assert d["success"] is True


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


class TestRegistration:
    def test_register_and_list(self) -> None:
        mp = MessagePipeline(pipeline=_make_pipeline_runner())
        h = _make_channel_handler()
        mp.register_channel("api", h)
        mp.register_channel("ws", h)
        assert sorted(mp.registered_channels) == ["api", "ws"]

    def test_unregister(self) -> None:
        mp = MessagePipeline(pipeline=_make_pipeline_runner())
        mp.register_channel("api", _make_channel_handler())
        mp.unregister_channel("api")
        assert "api" not in mp.registered_channels

    def test_unregister_missing_no_error(self) -> None:
        mp = MessagePipeline(pipeline=_make_pipeline_runner())
        mp.unregister_channel("nonexistent")  # Should not raise

    def test_add_middleware(self) -> None:
        mp = MessagePipeline(pipeline=_make_pipeline_runner())
        mw = _make_middleware()
        mp.add_middleware(mw)
        stats = mp.get_stats()
        assert stats["middleware_count"] == 1


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestValidation:
    @pytest.mark.asyncio
    async def test_empty_content(self) -> None:
        mp = MessagePipeline(pipeline=_make_pipeline_runner())
        with pytest.raises(MessageValidationError, match="content must not be empty"):
            await mp.process(_msg(content=""))

    @pytest.mark.asyncio
    async def test_whitespace_content(self) -> None:
        mp = MessagePipeline(pipeline=_make_pipeline_runner())
        with pytest.raises(MessageValidationError, match="content must not be empty"):
            await mp.process(_msg(content="   "))

    @pytest.mark.asyncio
    async def test_oversized_content(self) -> None:
        mp = MessagePipeline(pipeline=_make_pipeline_runner(), max_content_length=10)
        with pytest.raises(MessageValidationError, match="exceeds max length"):
            await mp.process(_msg(content="x" * 11))

    @pytest.mark.asyncio
    async def test_empty_sender(self) -> None:
        mp = MessagePipeline(pipeline=_make_pipeline_runner())
        with pytest.raises(MessageValidationError, match="sender_id must not be empty"):
            await mp.process(_msg(sender_id=""))

    @pytest.mark.asyncio
    async def test_empty_channel(self) -> None:
        mp = MessagePipeline(pipeline=_make_pipeline_runner())
        with pytest.raises(MessageValidationError, match="channel must not be empty"):
            await mp.process(_msg(channel=""))


# ---------------------------------------------------------------------------
# Processing — happy path
# ---------------------------------------------------------------------------


class TestProcessing:
    @pytest.mark.asyncio
    async def test_full_success(self) -> None:
        runner = _make_pipeline_runner(success=True)
        handler = _make_channel_handler()
        mp = MessagePipeline(pipeline=runner)
        mp.register_channel("api", handler)

        out = await mp.process(_msg())

        assert out.success is True
        assert out.channel == "api"
        assert out.recipient_id == "user-1"
        assert out.content == "Done."
        handler.deliver.assert_awaited_once()
        assert out.metadata.get("_delivered") is True
        assert "_latency_s" in out.metadata
        runner.run.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_pipeline_failure(self) -> None:
        runner = _make_pipeline_runner(success=False, error="boom")
        mp = MessagePipeline(pipeline=runner)
        mp.register_channel("api", _make_channel_handler())

        out = await mp.process(_msg())

        assert out.success is False
        assert "boom" in out.content

    @pytest.mark.asyncio
    async def test_no_handler_still_returns(self) -> None:
        """Process succeeds even without registered channel handler."""
        runner = _make_pipeline_runner()
        mp = MessagePipeline(pipeline=runner)

        out = await mp.process(_msg())

        assert out.success is True
        assert out.metadata.get("_delivered") is False

    @pytest.mark.asyncio
    async def test_unexpected_exception(self) -> None:
        runner = MagicMock()
        runner.run = AsyncMock(side_effect=RuntimeError("crash"))
        mp = MessagePipeline(pipeline=runner)

        out = await mp.process(_msg())

        assert out.success is False
        assert "crash" in out.content

    @pytest.mark.asyncio
    async def test_error_count_increments(self) -> None:
        mp = MessagePipeline(pipeline=_make_pipeline_runner())
        assert mp.error_count == 0
        with pytest.raises(MessageValidationError):
            await mp.process(_msg(content=""))
        assert mp.error_count == 1

    @pytest.mark.asyncio
    async def test_processed_count_increments(self) -> None:
        mp = MessagePipeline(pipeline=_make_pipeline_runner())
        mp.register_channel("api", _make_channel_handler())
        await mp.process(_msg())
        await mp.process(_msg())
        assert mp.processed_count == 2


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------


class TestMiddleware:
    @pytest.mark.asyncio
    async def test_inbound_middleware_called(self) -> None:
        mw = _make_middleware()
        mp = MessagePipeline(pipeline=_make_pipeline_runner())
        mp.add_middleware(mw)
        mp.register_channel("api", _make_channel_handler())

        await mp.process(_msg())

        mw.process_inbound.assert_awaited_once()
        mw.process_outbound.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_middleware_ordering(self) -> None:
        order: list[str] = []

        class MW1:
            async def process_inbound(self, m: Any) -> Any:
                order.append("in-1")
                return m

            async def process_outbound(self, m: Any) -> Any:
                order.append("out-1")
                return m

        class MW2:
            async def process_inbound(self, m: Any) -> Any:
                order.append("in-2")
                return m

            async def process_outbound(self, m: Any) -> Any:
                order.append("out-2")
                return m

        mp = MessagePipeline(pipeline=_make_pipeline_runner())
        mp.add_middleware(MW1())
        mp.add_middleware(MW2())
        mp.register_channel("api", _make_channel_handler())

        await mp.process(_msg())

        assert order == ["in-1", "in-2", "out-1", "out-2"]


# ---------------------------------------------------------------------------
# Batch processing
# ---------------------------------------------------------------------------


class TestBatchProcessing:
    @pytest.mark.asyncio
    async def test_process_batch(self) -> None:
        mp = MessagePipeline(pipeline=_make_pipeline_runner())
        mp.register_channel("api", _make_channel_handler())

        results = await mp.process_batch([_msg(), _msg(content="World")])

        assert len(results) == 2
        assert all(r.success for r in results)

    @pytest.mark.asyncio
    async def test_batch_with_validation_error(self) -> None:
        mp = MessagePipeline(pipeline=_make_pipeline_runner())

        results = await mp.process_batch([
            _msg(content=""),  # invalid
            _msg(content="Valid"),  # valid
        ])

        assert len(results) == 2
        assert results[0].success is False
        assert results[1].success is True


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------


class TestNormalization:
    def test_to_task(self) -> None:
        m = _msg(agent_type="coder", session_id="s-1")
        task = MessagePipeline._to_task(m)
        assert isinstance(task, Task)
        assert task.agent_type == "coder"
        assert task.metadata["_channel"] == "api"
        assert task.metadata["_sender_id"] == "user-1"
        assert task.metadata["_session_id"] == "s-1"
        assert task.name.startswith("msg:")

    def test_to_outbound_success(self) -> None:
        m = _msg(message_id="m-1")
        result = PipelineResult(
            task_id="t-1",
            success=True,
            status=TaskStatus.COMPLETED,
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
            evidence={"ship": {"summary": "Deployed OK"}},
        )
        out = MessagePipeline._to_outbound(m, result)
        assert out.success is True
        assert out.content == "Deployed OK"
        assert out.in_reply_to == "m-1"

    def test_to_outbound_failure(self) -> None:
        m = _msg()
        result = PipelineResult(
            task_id="t-1",
            success=False,
            status=TaskStatus.FAILED,
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
            evidence={},
            error="timeout",
        )
        out = MessagePipeline._to_outbound(m, result)
        assert out.success is False
        assert "timeout" in out.content


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


class TestStats:
    @pytest.mark.asyncio
    async def test_get_stats(self) -> None:
        mp = MessagePipeline(pipeline=_make_pipeline_runner())
        mp.register_channel("api", _make_channel_handler())
        mp.add_middleware(_make_middleware())

        await mp.process(_msg())

        stats = mp.get_stats()
        assert stats["processed_count"] == 1
        assert stats["error_count"] == 0
        assert stats["registered_channels"] == ["api"]
        assert stats["middleware_count"] == 1
