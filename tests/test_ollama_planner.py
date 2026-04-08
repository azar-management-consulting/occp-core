"""Tests for OllamaPlanner — REQ-CORE-04: Local Model Support via Ollama HTTP API.

Covers:
- OllamaPlanner construction (defaults, custom params)
- Properties: model, base_url
- is_available() — success and failure
- list_models() — success, failure, import error
- create_plan() — successful JSON response
- create_plan() — JSON with code fence stripping
- create_plan() — missing strategy/steps defaults
- create_plan() — non-JSON fallback (JSONDecodeError)
- create_plan() — API error (non-200 status)
- create_plan() — network failure (fallback plan)
- create_plan() — aiohttp ImportError
- Token tracking from Ollama response metadata
"""

from __future__ import annotations

import json
import sys
import types
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from orchestrator.models import RiskLevel, Task


# ---------------------------------------------------------------------------
# Install a fake aiohttp module so patch("aiohttp.ClientSession") works
# even when aiohttp is not installed.
# ---------------------------------------------------------------------------

_fake_aiohttp = types.ModuleType("aiohttp")
_fake_aiohttp.ClientSession = MagicMock  # placeholder — tests override via patch
_fake_aiohttp.ClientTimeout = lambda **kw: MagicMock()
if "aiohttp" not in sys.modules:
    sys.modules["aiohttp"] = _fake_aiohttp


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_aiohttp_response(
    status: int = 200,
    json_data: dict | None = None,
    text: str = "",
) -> MagicMock:
    resp = MagicMock()
    resp.status = status
    resp.json = AsyncMock(return_value=json_data or {})
    resp.text = AsyncMock(return_value=text)
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=None)
    return resp


def _mock_session(response: MagicMock) -> MagicMock:
    session = MagicMock()
    session.get = MagicMock(return_value=response)
    session.post = MagicMock(return_value=response)
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    return session


def _task(name: str = "test-task", desc: str = "Do something") -> Task:
    return Task(
        name=name,
        description=desc,
        agent_type="test",
        risk_level=RiskLevel.LOW,
    )


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestConstruction:
    def test_defaults(self) -> None:
        from adapters.ollama_planner import OllamaPlanner

        p = OllamaPlanner()
        assert p.model == "llama3.1:8b"
        assert p.base_url == "http://localhost:11434"

    def test_custom_params(self) -> None:
        from adapters.ollama_planner import OllamaPlanner

        p = OllamaPlanner(
            model="mistral:7b",
            base_url="http://gpu-box:11434/",
            timeout=60.0,
            temperature=0.5,
        )
        assert p.model == "mistral:7b"
        assert p.base_url == "http://gpu-box:11434"  # trailing / stripped


# ---------------------------------------------------------------------------
# is_available
# ---------------------------------------------------------------------------


class TestIsAvailable:
    @pytest.mark.asyncio
    async def test_available(self) -> None:
        from adapters.ollama_planner import OllamaPlanner

        resp = _mock_aiohttp_response(status=200)
        session = _mock_session(resp)

        with patch("aiohttp.ClientSession", return_value=session):
            p = OllamaPlanner()
            result = await p.is_available()
            assert result is True

    @pytest.mark.asyncio
    async def test_unavailable(self) -> None:
        from adapters.ollama_planner import OllamaPlanner

        resp = _mock_aiohttp_response(status=500)
        session = _mock_session(resp)

        with patch("aiohttp.ClientSession", return_value=session):
            p = OllamaPlanner()
            result = await p.is_available()
            assert result is False

    @pytest.mark.asyncio
    async def test_connection_error(self) -> None:
        from adapters.ollama_planner import OllamaPlanner

        session = MagicMock()
        session.get = MagicMock(side_effect=ConnectionError("refused"))
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=session):
            p = OllamaPlanner()
            result = await p.is_available()
            assert result is False


# ---------------------------------------------------------------------------
# list_models
# ---------------------------------------------------------------------------


class TestListModels:
    @pytest.mark.asyncio
    async def test_list_success(self) -> None:
        from adapters.ollama_planner import OllamaPlanner

        resp = _mock_aiohttp_response(
            status=200,
            json_data={"models": [{"name": "llama3.1:8b"}, {"name": "mistral:7b"}]},
        )
        session = _mock_session(resp)

        with patch("aiohttp.ClientSession", return_value=session):
            p = OllamaPlanner()
            models = await p.list_models()
            assert models == ["llama3.1:8b", "mistral:7b"]

    @pytest.mark.asyncio
    async def test_list_failure(self) -> None:
        from adapters.ollama_planner import OllamaPlanner

        resp = _mock_aiohttp_response(status=500)
        session = _mock_session(resp)

        with patch("aiohttp.ClientSession", return_value=session):
            p = OllamaPlanner()
            models = await p.list_models()
            assert models == []


# ---------------------------------------------------------------------------
# create_plan — success
# ---------------------------------------------------------------------------


class TestCreatePlan:
    @pytest.mark.asyncio
    async def test_valid_json_response(self) -> None:
        from adapters.ollama_planner import OllamaPlanner

        plan_json = {
            "strategy": "sequential",
            "description": "Execute step by step",
            "steps": ["step-1", "step-2", "step-3"],
        }
        resp = _mock_aiohttp_response(
            status=200,
            json_data={
                "message": {"content": json.dumps(plan_json)},
                "eval_count": 150,
                "prompt_eval_count": 50,
            },
        )
        session = _mock_session(resp)

        with patch("aiohttp.ClientSession", return_value=session):
            p = OllamaPlanner()
            plan = await p.create_plan(_task())

            assert plan["strategy"] == "sequential"
            assert len(plan["steps"]) == 3
            assert plan["_model"] == "llama3.1:8b"
            assert plan["_provider"] == "ollama"
            assert "_latency_ms" in plan
            assert plan["_tokens"]["completion"] == 150
            assert plan["_tokens"]["prompt"] == 50

    @pytest.mark.asyncio
    async def test_code_fence_stripping(self) -> None:
        from adapters.ollama_planner import OllamaPlanner

        plan_json = {"strategy": "analysis", "steps": ["analyze"]}
        raw = f"```json\n{json.dumps(plan_json)}\n```"
        resp = _mock_aiohttp_response(
            status=200,
            json_data={"message": {"content": raw}},
        )
        session = _mock_session(resp)

        with patch("aiohttp.ClientSession", return_value=session):
            p = OllamaPlanner()
            plan = await p.create_plan(_task())
            assert plan["strategy"] == "analysis"

    @pytest.mark.asyncio
    async def test_missing_strategy_defaults(self) -> None:
        from adapters.ollama_planner import OllamaPlanner

        resp = _mock_aiohttp_response(
            status=200,
            json_data={
                "message": {"content": json.dumps({"description": "do stuff"})},
            },
        )
        session = _mock_session(resp)

        with patch("aiohttp.ClientSession", return_value=session):
            p = OllamaPlanner()
            plan = await p.create_plan(_task())
            assert plan["strategy"] == "llm"
            assert isinstance(plan["steps"], list)


# ---------------------------------------------------------------------------
# create_plan — errors
# ---------------------------------------------------------------------------


class TestCreatePlanErrors:
    @pytest.mark.asyncio
    async def test_non_json_fallback(self) -> None:
        from adapters.ollama_planner import OllamaPlanner

        resp = _mock_aiohttp_response(
            status=200,
            json_data={"message": {"content": "This is not JSON at all."}},
        )
        session = _mock_session(resp)

        with patch("aiohttp.ClientSession", return_value=session):
            p = OllamaPlanner()
            plan = await p.create_plan(_task())
            assert plan["strategy"] == "llm-raw"
            assert plan["_parse_error"] is True

    @pytest.mark.asyncio
    async def test_api_error_status(self) -> None:
        from adapters.ollama_planner import OllamaPlanner, OllamaPlannerError

        resp = _mock_aiohttp_response(status=500, text="Internal Server Error")
        session = _mock_session(resp)

        with patch("aiohttp.ClientSession", return_value=session):
            p = OllamaPlanner()
            with pytest.raises(OllamaPlannerError, match="500"):
                await p.create_plan(_task())

    @pytest.mark.asyncio
    async def test_network_failure_fallback(self) -> None:
        from adapters.ollama_planner import OllamaPlanner

        session = MagicMock()
        session.post = MagicMock(side_effect=ConnectionError("refused"))
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=session):
            p = OllamaPlanner()
            plan = await p.create_plan(_task())
            assert plan["strategy"] == "fallback"
            assert "_error" in plan

    @pytest.mark.asyncio
    async def test_aiohttp_import_error(self) -> None:
        from adapters.ollama_planner import OllamaPlanner, OllamaPlannerError

        # Remove fake aiohttp temporarily so the import inside create_plan fails
        saved = sys.modules.pop("aiohttp", None)
        try:
            p = OllamaPlanner()
            with pytest.raises(OllamaPlannerError, match="aiohttp"):
                await p.create_plan(_task())
        finally:
            # Restore it
            if saved is not None:
                sys.modules["aiohttp"] = saved


# ---------------------------------------------------------------------------
# Token tracking
# ---------------------------------------------------------------------------


class TestTokenTracking:
    @pytest.mark.asyncio
    async def test_no_tokens_when_absent(self) -> None:
        from adapters.ollama_planner import OllamaPlanner

        resp = _mock_aiohttp_response(
            status=200,
            json_data={
                "message": {"content": json.dumps({"strategy": "x", "steps": ["a"]})},
            },
        )
        session = _mock_session(resp)

        with patch("aiohttp.ClientSession", return_value=session):
            p = OllamaPlanner()
            plan = await p.create_plan(_task())
            assert "_tokens" not in plan
