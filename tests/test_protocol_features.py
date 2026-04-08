"""Tests for P1/P2 protocol features: Brian prefix, EventEmitter, CloudCode formatter.

25+ tests covering:
- "Brian:" prefix filter on Telegram (Feature 1)
- PROGRESS event streaming (Feature 2)
- correlation_id on every event (Feature 3)
- CloudCode output formatting (Feature 4)
- Pipeline event integration (Feature 3)
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Feature 1: "Brian:" prefix filter on Telegram
# ---------------------------------------------------------------------------


def _make_bot(handler=None):
    from adapters.telegram_voice_bot import TelegramVoiceBot
    bot = TelegramVoiceBot(token="test", handler=handler)
    return bot


def _text_update(text: str, chat_id: int = 123) -> dict:
    return {"message": {"chat": {"id": chat_id}, "text": text}}


def _voice_update(chat_id: int = 123) -> dict:
    return {
        "message": {
            "chat": {"id": chat_id},
            "voice": {"file_id": "abc", "duration": 5},
            "_audio_bytes": b"fake-audio",
            "_file_name": "voice.ogg",
        }
    }


class TestBrianPrefixFilter:
    """Feature 1: Text messages must start with 'Brian:' to be processed."""

    @pytest.mark.asyncio
    async def test_text_with_brian_prefix_processed(self):
        handler = MagicMock()
        handler.handle_text = AsyncMock()
        handler.handle_voice = AsyncMock()
        bot = _make_bot(handler)

        result = await bot._handle_update(_text_update("Brian: deploy staging"))
        assert result is True
        handler.handle_text.assert_called_once_with(123, "deploy staging")

    @pytest.mark.asyncio
    async def test_text_without_prefix_ignored(self):
        handler = MagicMock()
        handler.handle_text = AsyncMock()
        handler.handle_voice = AsyncMock()
        bot = _make_bot(handler)

        result = await bot._handle_update(_text_update("deploy staging"))
        assert result is False
        handler.handle_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_voice_always_processed(self):
        handler = MagicMock()
        handler.handle_text = AsyncMock()
        handler.handle_voice = AsyncMock()
        bot = _make_bot(handler)

        result = await bot._handle_update(_voice_update())
        assert result is True
        handler.handle_voice.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_command_always_processed(self):
        handler = MagicMock()
        handler.handle_text = AsyncMock()
        handler.handle_voice = AsyncMock()
        bot = _make_bot(handler)

        result = await bot._handle_update(_text_update("/start"))
        assert result is True
        handler.handle_text.assert_called_once_with(123, "/start")

    @pytest.mark.asyncio
    async def test_help_command_always_processed(self):
        handler = MagicMock()
        handler.handle_text = AsyncMock()
        handler.handle_voice = AsyncMock()
        bot = _make_bot(handler)

        result = await bot._handle_update(_text_update("/help"))
        assert result is True
        handler.handle_text.assert_called_once_with(123, "/help")

    @pytest.mark.asyncio
    async def test_case_insensitive_brian_lowercase(self):
        handler = MagicMock()
        handler.handle_text = AsyncMock()
        handler.handle_voice = AsyncMock()
        bot = _make_bot(handler)

        result = await bot._handle_update(_text_update("brian: check status"))
        assert result is True
        handler.handle_text.assert_called_once_with(123, "check status")

    @pytest.mark.asyncio
    async def test_case_insensitive_brian_uppercase(self):
        handler = MagicMock()
        handler.handle_text = AsyncMock()
        handler.handle_voice = AsyncMock()
        bot = _make_bot(handler)

        result = await bot._handle_update(_text_update("BRIAN: check status"))
        assert result is True
        handler.handle_text.assert_called_once_with(123, "check status")

    @pytest.mark.asyncio
    async def test_case_insensitive_brian_mixed(self):
        handler = MagicMock()
        handler.handle_text = AsyncMock()
        handler.handle_voice = AsyncMock()
        bot = _make_bot(handler)

        result = await bot._handle_update(_text_update("BrIaN: mixed case"))
        assert result is True
        handler.handle_text.assert_called_once_with(123, "mixed case")

    @pytest.mark.asyncio
    async def test_brian_prefix_only_ignored(self):
        """'Brian:' with no content after it should be ignored."""
        handler = MagicMock()
        handler.handle_text = AsyncMock()
        handler.handle_voice = AsyncMock()
        bot = _make_bot(handler)

        result = await bot._handle_update(_text_update("Brian:"))
        assert result is False
        handler.handle_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_handler_returns_false(self):
        bot = _make_bot(handler=None)
        result = await bot._handle_update(_text_update("Brian: test"))
        assert result is False

    @pytest.mark.asyncio
    async def test_empty_message_returns_false(self):
        handler = MagicMock()
        handler.handle_text = AsyncMock()
        bot = _make_bot(handler)
        result = await bot._handle_update({"message": {}})
        assert result is False

    @pytest.mark.asyncio
    async def test_help_with_extra_text(self):
        """'/help something' should still be processed as a command."""
        handler = MagicMock()
        handler.handle_text = AsyncMock()
        handler.handle_voice = AsyncMock()
        bot = _make_bot(handler)

        result = await bot._handle_update(_text_update("/help something"))
        assert result is True


# ---------------------------------------------------------------------------
# Feature 2: PROGRESS event streaming (EventEmitter)
# ---------------------------------------------------------------------------


class TestEventEmitter:
    """Feature 2: Central event emitter with 6 event types."""

    def test_emit_and_subscribe(self):
        from orchestrator.event_emitter import EventEmitter, EventType
        emitter = EventEmitter()
        received = []
        emitter.on(lambda e: received.append(e))

        emitter.emit_status("t1", "c1", "started")
        assert len(received) == 1
        assert received[0].event_type == EventType.STATUS

    def test_all_six_event_types(self):
        from orchestrator.event_emitter import EventEmitter, EventType
        emitter = EventEmitter()
        events = []
        emitter.on(lambda e: events.append(e))

        emitter.emit_status("t1", "c1", "started")
        emitter.emit_progress("t1", "c1", "plan", "planning", 10)
        emitter.emit_completion("t1", "c1", "done")
        emitter.emit_question("t1", "c1", "Are you sure?")
        emitter.emit_approval("t1", "c1", "deploy")
        emitter.emit_error("t1", "c1", "something broke")

        types = {e.event_type for e in events}
        assert types == {
            EventType.STATUS,
            EventType.PROGRESS,
            EventType.COMPLETION,
            EventType.QUESTION,
            EventType.APPROVAL,
            EventType.ERROR,
        }

    def test_progress_with_stage_and_percent(self):
        from orchestrator.event_emitter import EventEmitter
        emitter = EventEmitter()
        events = []
        emitter.on(lambda e: events.append(e))

        emitter.emit_progress("t1", "c1", "execute", "running sandbox", 50)
        assert events[0].data["stage"] == "execute"
        assert events[0].data["percent"] == 50
        assert events[0].data["detail"] == "running sandbox"

    def test_correlation_id_present_on_every_event(self):
        from orchestrator.event_emitter import EventEmitter
        emitter = EventEmitter()
        events = []
        emitter.on(lambda e: events.append(e))

        emitter.emit_status("t1", "corr-123", "started")
        emitter.emit_progress("t1", "corr-123", "plan", "x", 0)
        emitter.emit_completion("t1", "corr-123")
        emitter.emit_error("t1", "corr-123", "err")

        for e in events:
            assert e.correlation_id == "corr-123"

    def test_ring_buffer_max_1000(self):
        from orchestrator.event_emitter import EventEmitter
        emitter = EventEmitter()

        for i in range(1100):
            emitter.emit_status(f"t-{i}", "c1", "x")

        assert len(emitter._event_log) == 1000

    def test_get_events_by_task_id(self):
        from orchestrator.event_emitter import EventEmitter
        emitter = EventEmitter()

        emitter.emit_status("task-a", "c1", "started")
        emitter.emit_status("task-b", "c2", "started")
        emitter.emit_progress("task-a", "c1", "plan", "planning", 10)

        events_a = emitter.get_events(task_id="task-a")
        assert len(events_a) == 2
        assert all(e["task_id"] == "task-a" for e in events_a)

    def test_get_events_limit(self):
        from orchestrator.event_emitter import EventEmitter
        emitter = EventEmitter()

        for i in range(10):
            emitter.emit_status("t1", "c1", f"status-{i}")

        events = emitter.get_events(task_id="t1", limit=3)
        assert len(events) == 3

    def test_brain_event_to_dict(self):
        from orchestrator.event_emitter import BrainEvent, EventType
        event = BrainEvent(
            event_type=EventType.PROGRESS,
            task_id="t1",
            correlation_id="c1",
            data={"stage": "plan"},
        )
        d = event.to_dict()
        assert d["event_type"] == "PROGRESS"
        assert d["task_id"] == "t1"
        assert d["correlation_id"] == "c1"
        assert "timestamp" in d

    def test_listener_error_does_not_crash(self):
        from orchestrator.event_emitter import EventEmitter
        emitter = EventEmitter()

        def bad_listener(event):
            raise RuntimeError("boom")

        good_events = []
        emitter.on(bad_listener)
        emitter.on(lambda e: good_events.append(e))

        # Should not raise
        emitter.emit_status("t1", "c1", "test")
        assert len(good_events) == 1


# ---------------------------------------------------------------------------
# Feature 3: Pipeline emits events with correlation_id
# ---------------------------------------------------------------------------


@dataclass
class _FakeGateResult:
    approved: bool = True
    reason: str = ""


class _FakePlanner:
    async def create_plan(self, task):
        return {"steps": ["step1"]}


class _FakePolicyEngine:
    async def evaluate(self, task):
        return _FakeGateResult(approved=True)


class _FakeExecutor:
    async def execute(self, task):
        return {"output": "done", "exit_code": 0}


class _FakeValidator:
    async def validate(self, task):
        return []  # no failures


class _FakeShipper:
    async def ship(self, task):
        return {"summary": "shipped"}


class _FailingExecutor:
    async def execute(self, task):
        from orchestrator.exceptions import ExecutionError
        raise ExecutionError(task.id, "sandbox crash")


class TestPipelineEventIntegration:
    """Feature 3: Pipeline emits PROGRESS at each stage, COMPLETION/ERROR at end."""

    def _make_pipeline(self, emitter, executor=None):
        from orchestrator.pipeline import Pipeline
        return Pipeline(
            planner=_FakePlanner(),
            policy_engine=_FakePolicyEngine(),
            executor=executor or _FakeExecutor(),
            validator=_FakeValidator(),
            shipper=_FakeShipper(),
            event_emitter=emitter,
        )

    @pytest.mark.asyncio
    async def test_pipeline_emits_progress_at_each_stage(self):
        from orchestrator.event_emitter import EventEmitter, EventType
        from orchestrator.models import Task

        emitter = EventEmitter()
        pipeline = self._make_pipeline(emitter)
        task = Task(name="test", description="test task", agent_type="general")

        result = await pipeline.run(task)
        assert result.success is True

        events = emitter.get_events(task_id=task.id)
        stages = [
            e["data"].get("stage")
            for e in events
            if e["event_type"] == "PROGRESS"
        ]
        assert "plan" in stages
        assert "gate" in stages
        assert "execute" in stages
        assert "validate" in stages
        assert "ship" in stages

    @pytest.mark.asyncio
    async def test_pipeline_emits_completion(self):
        from orchestrator.event_emitter import EventEmitter
        from orchestrator.models import Task

        emitter = EventEmitter()
        pipeline = self._make_pipeline(emitter)
        task = Task(name="test", description="test", agent_type="general")

        await pipeline.run(task)

        events = emitter.get_events(task_id=task.id)
        completions = [e for e in events if e["event_type"] == "COMPLETION"]
        assert len(completions) == 1

    @pytest.mark.asyncio
    async def test_pipeline_emits_error_on_failure(self):
        from orchestrator.event_emitter import EventEmitter
        from orchestrator.models import Task

        emitter = EventEmitter()
        pipeline = self._make_pipeline(emitter, executor=_FailingExecutor())
        task = Task(name="test", description="test", agent_type="general")

        result = await pipeline.run(task)
        assert result.success is False

        events = emitter.get_events(task_id=task.id)
        errors = [e for e in events if e["event_type"] == "ERROR"]
        assert len(errors) == 1
        assert "sandbox crash" in errors[0]["data"]["error"]

    @pytest.mark.asyncio
    async def test_correlation_id_stored_in_evidence(self):
        from orchestrator.event_emitter import EventEmitter
        from orchestrator.models import Task

        emitter = EventEmitter()
        pipeline = self._make_pipeline(emitter)
        task = Task(name="test", description="test", agent_type="general")

        result = await pipeline.run(task)
        assert "_correlation_id" in result.evidence
        assert result.evidence["_correlation_id"].startswith("pipe-")

    @pytest.mark.asyncio
    async def test_correlation_id_consistent_across_events(self):
        from orchestrator.event_emitter import EventEmitter
        from orchestrator.models import Task

        emitter = EventEmitter()
        pipeline = self._make_pipeline(emitter)
        task = Task(name="test", description="test", agent_type="general")

        result = await pipeline.run(task)
        events = emitter.get_events(task_id=task.id)
        corr_id = result.evidence["_correlation_id"]

        for event in events:
            assert event["correlation_id"] == corr_id


# ---------------------------------------------------------------------------
# Feature 4: CloudCode output formatting
# ---------------------------------------------------------------------------


class TestCloudCodeFormatter:
    """Feature 4: Structured report for CloudCode output."""

    def test_basic_report_formatting(self):
        from orchestrator.cloudcode_formatter import format_cloudcode_report

        result = {
            "status": "completed",
            "output": "Task finished successfully",
            "gate_approved": True,
            "validation_passed": True,
        }
        events = [
            {
                "timestamp": "2026-03-30T12:00:00.000Z",
                "event_type": "PROGRESS",
                "data": {"stage": "plan", "percent": 10},
            },
        ]

        report = format_cloudcode_report("task-123", result, events)
        assert "OCCP BRAIN REPORT" in report
        assert "task-123" in report
        assert "completed" in report
        assert "PASS" in report
        assert "END REPORT" in report

    def test_report_with_empty_events(self):
        from orchestrator.cloudcode_formatter import format_cloudcode_report

        result = {"status": "failed", "gate_approved": False}
        report = format_cloudcode_report("task-456", result, [])
        assert "task-456" in report
        assert "FAIL" in report

    def test_report_gate_fail(self):
        from orchestrator.cloudcode_formatter import format_cloudcode_report

        result = {
            "status": "rejected",
            "output": "Blocked by policy",
            "gate_approved": False,
            "validation_passed": False,
        }
        report = format_cloudcode_report("t1", result, [])
        assert "Gate: FAIL" in report

    def test_report_validation_na(self):
        from orchestrator.cloudcode_formatter import format_cloudcode_report

        result = {"status": "completed", "gate_approved": True}
        report = format_cloudcode_report("t1", result, [])
        assert "Validation: N/A" in report

    def test_report_timeline_shows_events(self):
        from orchestrator.cloudcode_formatter import format_cloudcode_report

        events = [
            {
                "timestamp": "2026-03-30T12:00:00.000Z",
                "event_type": "STATUS",
                "data": {"status": "started"},
            },
            {
                "timestamp": "2026-03-30T12:00:01.000Z",
                "event_type": "PROGRESS",
                "data": {"stage": "plan", "percent": 10},
            },
            {
                "timestamp": "2026-03-30T12:00:05.000Z",
                "event_type": "COMPLETION",
                "data": {"result": "done"},
            },
        ]
        report = format_cloudcode_report("t1", {"status": "ok"}, events)
        assert "STATUS" in report
        assert "PROGRESS" in report
        assert "COMPLETION" in report
