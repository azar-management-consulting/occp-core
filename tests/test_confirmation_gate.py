"""Tests for the ConfirmationGate — human approval gate.

Covers:
- Auto-approve for LOW risk tasks
- Approval via known keywords (ok, igen, go, jovahagyom, etc.)
- Rejection via unknown response
- Timeout handling
- Pending state tracking
- Chat-to-task routing
- Plan summary formatting
- Message formatting
- Stats tracking
- Pipeline integration with confirmation gate
- Voice handler confirmation routing
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from adapters.confirmation_gate import (
    ConfirmationGate,
    ConfirmationStatus,
    ConfirmationTimeoutError,
    HumanRejectedError,
    PendingConfirmation,
    _APPROVE_KEYWORDS,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class FakeSender:
    """Test double for ConfirmationSender."""

    def __init__(self) -> None:
        self.requests: list[tuple[int, str]] = []
        self.results: list[tuple[int, str]] = []

    async def send_confirmation_request(self, chat_id: int, message: str) -> None:
        self.requests.append((chat_id, message))

    async def send_confirmation_result(self, chat_id: int, message: str) -> None:
        self.results.append((chat_id, message))


def _make_gate(**kw: Any) -> ConfirmationGate:
    defaults: dict[str, Any] = {
        "sender": FakeSender(),
        "timeout": 5,
    }
    defaults.update(kw)
    return ConfirmationGate(**defaults)


# ---------------------------------------------------------------------------
# Auto-approve for LOW risk
# ---------------------------------------------------------------------------


class TestAutoApprove:
    @pytest.mark.asyncio
    async def test_low_risk_auto_approves(self) -> None:
        gate = _make_gate()
        result = await gate.request_confirmation(
            task_id="t1",
            chat_id=123,
            plan_summary="Test plan",
            risk_level="low",
            agent_type="eng-core",
        )
        assert result == ConfirmationStatus.AUTO_APPROVED

    @pytest.mark.asyncio
    async def test_low_risk_no_message_sent(self) -> None:
        sender = FakeSender()
        gate = _make_gate(sender=sender)
        await gate.request_confirmation(
            task_id="t1",
            chat_id=123,
            plan_summary="Test",
            risk_level="low",
            agent_type="default",
        )
        assert len(sender.requests) == 0

    @pytest.mark.asyncio
    async def test_low_risk_stats(self) -> None:
        gate = _make_gate()
        await gate.request_confirmation(
            task_id="t1", chat_id=1, plan_summary="x",
            risk_level="low", agent_type="a",
        )
        stats = gate.get_stats()
        assert stats["total_auto_approved"] == 1
        assert stats["total_requests"] == 1

    @pytest.mark.asyncio
    async def test_custom_auto_approve_levels(self) -> None:
        gate = _make_gate(
            auto_approve_risk_levels=frozenset({"low", "medium"})
        )
        result = await gate.request_confirmation(
            task_id="t1", chat_id=1, plan_summary="x",
            risk_level="medium", agent_type="a",
        )
        assert result == ConfirmationStatus.AUTO_APPROVED


# ---------------------------------------------------------------------------
# Approval keywords
# ---------------------------------------------------------------------------


class TestApprovalKeywords:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("keyword", [
        "ok", "igen", "go", "yes", "jovahagyom",
        "approve", "proceed", "mehet", "rendben",
    ])
    async def test_approval_keywords(self, keyword: str) -> None:
        gate = _make_gate(timeout=10)
        chat_id = 100

        async def _simulate_approval() -> ConfirmationStatus:
            return await gate.request_confirmation(
                task_id="t1", chat_id=chat_id, plan_summary="Plan",
                risk_level="high", agent_type="eng-core",
            )

        async def _respond() -> None:
            await asyncio.sleep(0.01)
            gate.handle_response(chat_id, keyword)

        result, _ = await asyncio.gather(
            _simulate_approval(), _respond()
        )
        assert result == ConfirmationStatus.APPROVED

    @pytest.mark.asyncio
    async def test_approval_case_insensitive(self) -> None:
        gate = _make_gate(timeout=10)

        async def _req() -> ConfirmationStatus:
            return await gate.request_confirmation(
                task_id="t1", chat_id=1, plan_summary="x",
                risk_level="high", agent_type="a",
            )

        async def _resp() -> None:
            await asyncio.sleep(0.01)
            gate.handle_response(1, "  OK  ")

        result, _ = await asyncio.gather(_req(), _resp())
        assert result == ConfirmationStatus.APPROVED

    @pytest.mark.asyncio
    async def test_approval_with_accents(self) -> None:
        """'j\u00f3v\u00e1hagyom' with accents should normalize to 'jovahagyom'."""
        gate = _make_gate(timeout=10)

        async def _req() -> ConfirmationStatus:
            return await gate.request_confirmation(
                task_id="t1", chat_id=1, plan_summary="x",
                risk_level="high", agent_type="a",
            )

        async def _resp() -> None:
            await asyncio.sleep(0.01)
            gate.handle_response(1, "j\u00f3v\u00e1hagyom")

        result, _ = await asyncio.gather(_req(), _resp())
        assert result == ConfirmationStatus.APPROVED


# ---------------------------------------------------------------------------
# Rejection
# ---------------------------------------------------------------------------


class TestRejection:
    @pytest.mark.asyncio
    async def test_rejection_with_arbitrary_text(self) -> None:
        gate = _make_gate(timeout=10)

        async def _req() -> ConfirmationStatus:
            return await gate.request_confirmation(
                task_id="t1", chat_id=1, plan_summary="x",
                risk_level="high", agent_type="a",
            )

        async def _resp() -> None:
            await asyncio.sleep(0.01)
            gate.handle_response(1, "nem, inkabb ne")

        result, _ = await asyncio.gather(_req(), _resp())
        assert result == ConfirmationStatus.REJECTED

    @pytest.mark.asyncio
    async def test_rejection_stats(self) -> None:
        gate = _make_gate(timeout=10)

        async def _req() -> ConfirmationStatus:
            return await gate.request_confirmation(
                task_id="t1", chat_id=1, plan_summary="x",
                risk_level="high", agent_type="a",
            )

        async def _resp() -> None:
            await asyncio.sleep(0.01)
            gate.handle_response(1, "nem")

        await asyncio.gather(_req(), _resp())
        assert gate.get_stats()["total_rejected"] == 1


# ---------------------------------------------------------------------------
# Timeout
# ---------------------------------------------------------------------------


class TestTimeout:
    @pytest.mark.asyncio
    async def test_timeout_returns_timeout_status(self) -> None:
        gate = _make_gate(timeout=0.05)  # 50ms timeout
        result = await gate.request_confirmation(
            task_id="t1", chat_id=1, plan_summary="x",
            risk_level="high", agent_type="a",
        )
        assert result == ConfirmationStatus.TIMEOUT

    @pytest.mark.asyncio
    async def test_timeout_sends_message(self) -> None:
        sender = FakeSender()
        gate = _make_gate(sender=sender, timeout=0.05)
        await gate.request_confirmation(
            task_id="t1", chat_id=1, plan_summary="x",
            risk_level="high", agent_type="a",
        )
        assert len(sender.results) == 1
        assert "Lejart" in sender.results[0][1]

    @pytest.mark.asyncio
    async def test_timeout_cleanup(self) -> None:
        gate = _make_gate(timeout=0.05)
        await gate.request_confirmation(
            task_id="t1", chat_id=1, plan_summary="x",
            risk_level="high", agent_type="a",
        )
        assert gate.pending_count == 0
        assert not gate.has_pending(1)


# ---------------------------------------------------------------------------
# Pending state
# ---------------------------------------------------------------------------


class TestPendingState:
    @pytest.mark.asyncio
    async def test_has_pending_during_wait(self) -> None:
        gate = _make_gate(timeout=10)

        async def _req() -> ConfirmationStatus:
            return await gate.request_confirmation(
                task_id="t1", chat_id=42, plan_summary="x",
                risk_level="high", agent_type="a",
            )

        async def _check_and_respond() -> None:
            await asyncio.sleep(0.01)
            assert gate.has_pending(42)
            assert gate.pending_count == 1
            pending = gate.get_pending("t1")
            assert pending is not None
            assert pending.task_id == "t1"
            assert pending.chat_id == 42
            gate.handle_response(42, "ok")

        await asyncio.gather(_req(), _check_and_respond())

    def test_no_pending_initially(self) -> None:
        gate = _make_gate()
        assert gate.pending_count == 0
        assert not gate.has_pending(1)
        assert gate.get_pending("x") is None

    def test_handle_response_no_pending_returns_false(self) -> None:
        gate = _make_gate()
        assert gate.handle_response(999, "ok") is False


# ---------------------------------------------------------------------------
# Message formatting
# ---------------------------------------------------------------------------


class TestMessageFormatting:
    def test_confirmation_message_format(self) -> None:
        msg = ConfirmationGate._format_confirmation_message(
            plan_summary="1. Do X\n2. Do Y",
            risk_level="high",
            agent_type="infra-ops",
        )
        assert "Brian the Brain" in msg
        assert "Henry" in msg
        assert "HIGH" in msg
        assert "infra-ops" in msg
        assert "igen/nem" in msg

    def test_plan_summary_with_steps(self) -> None:
        plan = {"steps": ["Step A", "Step B", "Step C"]}
        summary = ConfirmationGate.format_plan_summary(plan)
        assert "Step A" in summary
        assert "Step B" in summary
        assert "Step C" in summary

    def test_plan_summary_with_summary_field(self) -> None:
        plan = {"summary": "Do something important"}
        summary = ConfirmationGate.format_plan_summary(plan)
        assert "Do something important" in summary

    def test_plan_summary_with_description(self) -> None:
        plan = {"description": "Build landing page"}
        summary = ConfirmationGate.format_plan_summary(plan)
        assert "Build landing page" in summary

    def test_plan_summary_with_dict_steps(self) -> None:
        plan = {"steps": [
            {"name": "research", "description": "Research competitors"},
            {"name": "build", "description": "Build the page"},
        ]}
        summary = ConfirmationGate.format_plan_summary(plan)
        assert "Research competitors" in summary

    def test_plan_summary_fallback(self) -> None:
        plan = {"key1": "val1", "key2": "val2"}
        summary = ConfirmationGate.format_plan_summary(plan)
        assert "key1" in summary

    def test_plan_summary_non_dict(self) -> None:
        summary = ConfirmationGate.format_plan_summary("raw string")  # type: ignore[arg-type]
        assert "raw string" in summary


# ---------------------------------------------------------------------------
# Exception classes
# ---------------------------------------------------------------------------


class TestExceptions:
    def test_human_rejected_error(self) -> None:
        err = HumanRejectedError("t1", "user said no")
        assert err.task_id == "t1"
        assert err.reason == "user said no"
        assert "t1" in str(err)

    def test_confirmation_timeout_error(self) -> None:
        err = ConfirmationTimeoutError("t2")
        assert err.task_id == "t2"
        assert "timeout" in str(err).lower()


# ---------------------------------------------------------------------------
# Pipeline integration
# ---------------------------------------------------------------------------


class TestPipelineIntegration:
    """Test confirmation gate integrated into the VAP pipeline."""

    @pytest.mark.asyncio
    async def test_pipeline_with_confirmation_auto_approve(self) -> None:
        """LOW risk task auto-approves, pipeline runs normally."""
        from orchestrator.models import RiskLevel, Task, TaskStatus
        from orchestrator.pipeline import Pipeline
        from policy_engine.engine import GateResult

        planner = MagicMock()
        planner.create_plan = AsyncMock(return_value={"steps": ["a"]})
        engine = MagicMock()
        engine.evaluate = AsyncMock(return_value=GateResult(approved=True, reason=""))
        executor = MagicMock()
        executor.execute = AsyncMock(return_value={"result": "ok"})
        validator = MagicMock()
        validator.validate = AsyncMock(return_value=[])
        shipper = MagicMock()
        shipper.ship = AsyncMock(return_value={"shipped": True})

        gate = ConfirmationGate(sender=FakeSender(), timeout=5)

        pipeline = Pipeline(
            planner=planner,
            policy_engine=engine,
            executor=executor,
            validator=validator,
            shipper=shipper,
            confirmation_gate=gate,
        )

        task = Task(
            name="test", description="test", agent_type="default",
            risk_level=RiskLevel.LOW,
            metadata={"chat_id": 1},
        )
        result = await pipeline.run(task)
        assert result.success is True
        assert result.evidence.get("confirmation", {}).get("status") == "auto_approved"

    @pytest.mark.asyncio
    async def test_pipeline_with_confirmation_approved(self) -> None:
        """MEDIUM risk task approved by human, pipeline continues."""
        from orchestrator.models import RiskLevel, Task, TaskStatus
        from orchestrator.pipeline import Pipeline
        from policy_engine.engine import GateResult

        planner = MagicMock()
        planner.create_plan = AsyncMock(return_value={"steps": ["a"]})
        engine = MagicMock()
        engine.evaluate = AsyncMock(return_value=GateResult(approved=True, reason=""))
        executor = MagicMock()
        executor.execute = AsyncMock(return_value={"result": "ok"})
        validator = MagicMock()
        validator.validate = AsyncMock(return_value=[])
        shipper = MagicMock()
        shipper.ship = AsyncMock(return_value={"shipped": True})

        gate = ConfirmationGate(sender=FakeSender(), timeout=10)

        pipeline = Pipeline(
            planner=planner,
            policy_engine=engine,
            executor=executor,
            validator=validator,
            shipper=shipper,
            confirmation_gate=gate,
        )

        task = Task(
            name="test", description="test", agent_type="default",
            risk_level=RiskLevel.MEDIUM,
            metadata={"chat_id": 42},
        )

        async def _approve_later() -> None:
            await asyncio.sleep(0.05)
            gate.handle_response(42, "ok")

        result, _ = await asyncio.gather(
            pipeline.run(task), _approve_later()
        )
        assert result.success is True
        assert result.evidence["confirmation"]["status"] == "approved"

    @pytest.mark.asyncio
    async def test_pipeline_with_confirmation_rejected(self) -> None:
        """MEDIUM risk task rejected by human, pipeline stops."""
        from orchestrator.models import RiskLevel, Task, TaskStatus
        from orchestrator.pipeline import Pipeline
        from policy_engine.engine import GateResult

        planner = MagicMock()
        planner.create_plan = AsyncMock(return_value={"steps": ["a"]})
        engine = MagicMock()
        engine.evaluate = AsyncMock(return_value=GateResult(approved=True, reason=""))
        executor = MagicMock()
        executor.execute = AsyncMock(return_value={"result": "ok"})
        validator = MagicMock()
        validator.validate = AsyncMock(return_value=[])
        shipper = MagicMock()
        shipper.ship = AsyncMock(return_value={"shipped": True})

        gate = ConfirmationGate(sender=FakeSender(), timeout=10)

        pipeline = Pipeline(
            planner=planner,
            policy_engine=engine,
            executor=executor,
            validator=validator,
            shipper=shipper,
            confirmation_gate=gate,
        )

        task = Task(
            name="test", description="test", agent_type="default",
            risk_level=RiskLevel.HIGH,
            metadata={"chat_id": 42},
        )

        async def _reject_later() -> None:
            await asyncio.sleep(0.05)
            gate.handle_response(42, "nem, ne csinald")

        with pytest.raises(HumanRejectedError):
            await asyncio.gather(
                pipeline.run(task), _reject_later()
            )

        # Executor should NOT have been called
        executor.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_pipeline_with_confirmation_timeout(self) -> None:
        """MEDIUM risk task times out, pipeline stops."""
        from orchestrator.models import RiskLevel, Task
        from orchestrator.pipeline import Pipeline
        from policy_engine.engine import GateResult

        planner = MagicMock()
        planner.create_plan = AsyncMock(return_value={"steps": ["a"]})
        engine = MagicMock()
        engine.evaluate = AsyncMock(return_value=GateResult(approved=True, reason=""))
        executor = MagicMock()
        executor.execute = AsyncMock(return_value={"result": "ok"})
        validator = MagicMock()
        validator.validate = AsyncMock(return_value=[])
        shipper = MagicMock()
        shipper.ship = AsyncMock(return_value={"shipped": True})

        gate = ConfirmationGate(sender=FakeSender(), timeout=0.05)

        pipeline = Pipeline(
            planner=planner,
            policy_engine=engine,
            executor=executor,
            validator=validator,
            shipper=shipper,
            confirmation_gate=gate,
        )

        task = Task(
            name="test", description="test", agent_type="default",
            risk_level=RiskLevel.HIGH,
            metadata={"chat_id": 42},
        )

        with pytest.raises(ConfirmationTimeoutError):
            await pipeline.run(task)

        executor.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_pipeline_without_confirmation_gate(self) -> None:
        """Pipeline without confirmation gate works as before."""
        from orchestrator.models import Task, TaskStatus
        from orchestrator.pipeline import Pipeline
        from policy_engine.engine import GateResult

        planner = MagicMock()
        planner.create_plan = AsyncMock(return_value={"steps": ["a"]})
        engine = MagicMock()
        engine.evaluate = AsyncMock(return_value=GateResult(approved=True, reason=""))
        executor = MagicMock()
        executor.execute = AsyncMock(return_value={"result": "ok"})
        validator = MagicMock()
        validator.validate = AsyncMock(return_value=[])
        shipper = MagicMock()
        shipper.ship = AsyncMock(return_value={"shipped": True})

        pipeline = Pipeline(
            planner=planner,
            policy_engine=engine,
            executor=executor,
            validator=validator,
            shipper=shipper,
            # No confirmation_gate
        )

        task = Task(name="test", description="test", agent_type="default")
        result = await pipeline.run(task)
        assert result.success is True
        assert "confirmation" not in result.evidence


# ---------------------------------------------------------------------------
# Voice handler confirmation routing
# ---------------------------------------------------------------------------


class TestVoiceHandlerConfirmation:
    def test_is_confirmation_response_no_gate(self) -> None:
        from adapters.voice_handler import VoiceCommandHandler

        handler = VoiceCommandHandler(
            whisper=MagicMock(),
            intent_router=MagicMock(),
            pipeline=MagicMock(),
            task_store=MagicMock(),
            audit_store=MagicMock(),
        )
        assert handler.is_confirmation_response(123) is False

    def test_handle_confirmation_no_gate(self) -> None:
        from adapters.voice_handler import VoiceCommandHandler

        handler = VoiceCommandHandler(
            whisper=MagicMock(),
            intent_router=MagicMock(),
            pipeline=MagicMock(),
            task_store=MagicMock(),
            audit_store=MagicMock(),
        )
        assert handler.handle_confirmation_response(123, "ok") is False

    def test_set_confirmation_gate(self) -> None:
        from adapters.voice_handler import VoiceCommandHandler

        handler = VoiceCommandHandler(
            whisper=MagicMock(),
            intent_router=MagicMock(),
            pipeline=MagicMock(),
            task_store=MagicMock(),
            audit_store=MagicMock(),
        )
        gate = ConfirmationGate()
        handler.set_confirmation_gate(gate)
        assert handler._confirmation_gate is gate
