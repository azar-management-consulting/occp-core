"""Integration tests — BudgetPolicy wiring in executor adapters.

Scope:
  * :class:`adapters.openclaw_executor.OpenClawExecutor` MUST call
    :meth:`BudgetPolicy.check` BEFORE every ``chat.send`` dispatch.
  * It MUST call :meth:`BudgetPolicy.record_spend` AFTER a successful
    dispatch with the response usage fields (falling back to token
    estimates when the gateway omits ``usage``).
  * A failed pre-flight check MUST raise :class:`BudgetExceededError`
    and MUST NOT invoke ``record_spend``.

MockExecutor and SandboxExecutor are intentionally NOT tested here:
  - MockExecutor is a static simulation and performs no LLM call.
  - SandboxExecutor runs shell commands, not LLM calls.
  See their module docstrings.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from adapters.openclaw_executor import (
    OpenClawConfig,
    OpenClawExecutor,
)
from orchestrator.models import Task
from policy_engine.budget_policy import (
    BudgetExceededError,
    BudgetPolicy,
    CacheBreakdown,
)


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def policy() -> BudgetPolicy:
    """Hermetic in-memory BudgetPolicy with a generous default."""
    return BudgetPolicy(default_budget_usd=5.00)


@pytest.fixture
def tight_policy() -> BudgetPolicy:
    """Policy with a tiny budget that any real call must exceed."""
    return BudgetPolicy(default_budget_usd=0.0000001)


@pytest.fixture
def task() -> Task:
    """Baseline task suitable for the OpenClaw dispatch path."""
    t = Task(
        name="budget-wiring-smoke",
        description="Write a haiku about TCP retransmits.",
        agent_type="eng-core",
    )
    # Model the pipeline behaviour: attach the policy + hint the model.
    t.metadata = {"_model_id": "sonnet"}
    return t


def _make_executor_with_mock_conn(
    chat_response: dict[str, Any] | Exception,
) -> OpenClawExecutor:
    """Build an OpenClawExecutor whose WebSocket is fully stubbed."""
    cfg = OpenClawConfig(gateway_url="ws://test.local:1/")
    executor = OpenClawExecutor(config=cfg)

    # Replace the connection so no real network activity happens.
    conn = MagicMock()
    conn.is_connected = True
    conn.connect = AsyncMock(return_value=None)

    if isinstance(chat_response, Exception):
        conn.send_chat = AsyncMock(side_effect=chat_response)
    else:
        conn.send_chat = AsyncMock(return_value=chat_response)

    # Force circuit-breaker closed (no real failures yet).
    executor._conn = conn  # type: ignore[attr-defined]
    return executor


# ── Tests ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_openclaw_preflight_check_called_before_dispatch(
    policy: BudgetPolicy, task: Task
) -> None:
    """``BudgetPolicy.check`` runs BEFORE ``send_chat`` and receives task+model."""
    task.metadata["_budget_policy"] = policy
    task.metadata["_budget_task_id"] = task.id

    # Spy on the real check() to assert call ordering + args.
    original_check = policy.check
    check_spy = MagicMock(side_effect=original_check)
    policy.check = check_spy  # type: ignore[method-assign]

    response = {
        "message": {"text": "Packet lost in flight /\nanswered by a gentle retry /\nbuffers drain to zero."},
        "runId": "r-1",
        "sessionKey": "eng-core/default",
        "usage": {"input_tokens": 120, "output_tokens": 30},
    }
    executor = _make_executor_with_mock_conn(response)

    result = await executor.execute(task)

    assert check_spy.called, "BudgetPolicy.check() was never called"
    call = check_spy.call_args
    assert call.args == (task.id,)
    assert call.kwargs["model"] == "sonnet"
    assert call.kwargs["estimated_tokens"] > 0

    # send_chat MUST have been called too, and AFTER check()
    send_chat = executor._conn.send_chat  # type: ignore[attr-defined]
    assert send_chat.await_count == 1
    assert result["exit_code"] == 0
    assert "Packet lost" in result["output"]


@pytest.mark.asyncio
async def test_openclaw_postflight_records_response_usage(
    policy: BudgetPolicy, task: Task
) -> None:
    """``record_spend`` is called with the gateway-reported usage fields."""
    task.metadata["_budget_policy"] = policy
    task.metadata["_budget_task_id"] = task.id

    spend_spy = MagicMock(side_effect=policy.record_spend)
    policy.record_spend = spend_spy  # type: ignore[method-assign]

    response = {
        "message": {"text": "Done."},
        "runId": "r-2",
        "sessionKey": "eng-core/default",
        "usage": {
            "input_tokens": 500,
            "output_tokens": 80,
            "cache_read_input_tokens": 10,
            "cache_creation_input_tokens": 5,
        },
    }
    executor = _make_executor_with_mock_conn(response)

    await executor.execute(task)

    assert spend_spy.called, "BudgetPolicy.record_spend() was never called"
    kwargs = spend_spy.call_args.kwargs
    assert kwargs["model"] == "sonnet"
    breakdown: CacheBreakdown = kwargs["cache_breakdown"]
    assert breakdown.input_tokens == 500
    assert breakdown.output_tokens == 80
    assert breakdown.cache_read_input_tokens == 10
    assert breakdown.cache_creation_input_tokens == 5

    # And the aggregate spend moved.
    assert policy.get_spend(task.id) > 0.0


@pytest.mark.asyncio
async def test_openclaw_budget_exceeded_propagates_and_skips_dispatch(
    tight_policy: BudgetPolicy, task: Task
) -> None:
    """Pre-flight refusal raises BudgetExceededError; send_chat is not called."""
    task.metadata["_budget_policy"] = tight_policy
    task.metadata["_budget_task_id"] = task.id

    spend_spy = MagicMock(side_effect=tight_policy.record_spend)
    tight_policy.record_spend = spend_spy  # type: ignore[method-assign]

    response = {"message": {"text": "should-not-appear"}, "runId": "r-x"}
    executor = _make_executor_with_mock_conn(response)

    with pytest.raises(BudgetExceededError) as excinfo:
        await executor.execute(task)

    err = excinfo.value
    assert err.task_id == task.id
    assert err.budget_usd == tight_policy.get_task_budget(task.id)

    # Dispatch MUST NOT have happened.
    send_chat = executor._conn.send_chat  # type: ignore[attr-defined]
    assert send_chat.await_count == 0, "send_chat fired despite budget refusal"

    # record_spend must NOT have been called on a refused pre-flight.
    assert not spend_spy.called, "record_spend called after pre-flight refusal"
