"""Tests for Agent Registry – Scheduler methods + API CRUD."""

from __future__ import annotations

import os

import pytest
from httpx import ASGITransport, AsyncClient

from orchestrator.models import AgentConfig
from orchestrator.scheduler import Scheduler

from api.app import create_app


# ---------------------------------------------------------------------------
# Scheduler unit tests
# ---------------------------------------------------------------------------


class TestSchedulerRegistry:
    def test_list_agents_empty(self) -> None:
        s = Scheduler()
        assert s.list_agents() == []

    def test_register_and_list(self) -> None:
        s = Scheduler()
        cfg = AgentConfig(agent_type="test", display_name="Test Agent")

        async def factory(_cfg, _task=None):
            return {}

        s.register(cfg, factory)
        agents = s.list_agents()
        assert len(agents) == 1
        assert agents[0].agent_type == "test"

    def test_get_agent(self) -> None:
        s = Scheduler()
        cfg = AgentConfig(agent_type="finder", display_name="Finder")

        async def factory(_cfg, _task=None):
            return {}

        s.register(cfg, factory)
        assert s.get_agent("finder") is not None
        assert s.get_agent("finder").display_name == "Finder"
        assert s.get_agent("missing") is None

    def test_unregister(self) -> None:
        s = Scheduler()
        cfg = AgentConfig(agent_type="temp", display_name="Temp")

        async def factory(_cfg, _task=None):
            return {}

        s.register(cfg, factory)
        assert len(s.list_agents()) == 1
        s.unregister("temp")
        assert len(s.list_agents()) == 0


# ---------------------------------------------------------------------------
# API integration tests
# ---------------------------------------------------------------------------


@pytest.fixture
async def client(tmp_path):
    db_path = tmp_path / "test_agents.db"
    os.environ["OCCP_DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"
    os.environ["OCCP_ADMIN_USER"] = "agentadmin"
    os.environ["OCCP_ADMIN_PASSWORD"] = "agentpass"
    try:
        app = create_app()
        async with app.router.lifespan_context(app):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                yield ac
    finally:
        os.environ.pop("OCCP_DATABASE_URL", None)
        os.environ.pop("OCCP_ADMIN_USER", None)
        os.environ.pop("OCCP_ADMIN_PASSWORD", None)


async def _get_token(client: AsyncClient) -> str:
    resp = await client.post("/api/v1/auth/login", json={
        "username": "agentadmin",
        "password": "agentpass",
    })
    return resp.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class TestAgentsAPI:
    @pytest.mark.asyncio
    async def test_list_seeded_defaults(self, client: AsyncClient) -> None:
        """Lifespan seeds 11 default agents (v0.9.0: +openclaw, +remote-agent for L4)."""
        token = await _get_token(client)
        resp = await client.get("/api/v1/agents", headers=_auth(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 11
        types = {a["agent_type"] for a in data["agents"]}
        assert types == {
            "general", "demo", "code-reviewer",
            "onboarding-wizard", "mcp-installer", "llm-setup",
            "skills-manager", "session-policy", "ux-copy",
            "openclaw", "remote-agent",
        }

    @pytest.mark.asyncio
    async def test_register_and_get(self, client: AsyncClient) -> None:
        token = await _get_token(client)
        resp = await client.post("/api/v1/agents", json={
            "agent_type": "coder",
            "display_name": "Code Agent",
            "capabilities": ["python", "js"],
            "max_concurrent": 3,
        }, headers=_auth(token))
        assert resp.status_code == 201
        data = resp.json()
        assert data["agent_type"] == "coder"
        assert data["max_concurrent"] == 3

        resp2 = await client.get("/api/v1/agents/coder", headers=_auth(token))
        assert resp2.status_code == 200
        assert resp2.json()["display_name"] == "Code Agent"

    @pytest.mark.asyncio
    async def test_register_requires_auth(self, client: AsyncClient) -> None:
        resp = await client.post("/api/v1/agents", json={
            "agent_type": "test",
            "display_name": "Test",
        })
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_get_missing_agent(self, client: AsyncClient) -> None:
        token = await _get_token(client)
        resp = await client.get("/api/v1/agents/nonexistent", headers=_auth(token))
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_agent(self, client: AsyncClient) -> None:
        token = await _get_token(client)
        await client.post("/api/v1/agents", json={
            "agent_type": "deleteme",
            "display_name": "Delete Me",
        }, headers=_auth(token))

        resp = await client.delete("/api/v1/agents/deleteme", headers=_auth(token))
        assert resp.status_code == 204

        resp2 = await client.get("/api/v1/agents/deleteme", headers=_auth(token))
        assert resp2.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_missing_agent(self, client: AsyncClient) -> None:
        token = await _get_token(client)
        resp = await client.delete("/api/v1/agents/ghost", headers=_auth(token))
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_list_after_registration(self, client: AsyncClient) -> None:
        token = await _get_token(client)
        await client.post("/api/v1/agents", json={
            "agent_type": "a1",
            "display_name": "Agent 1",
        }, headers=_auth(token))
        await client.post("/api/v1/agents", json={
            "agent_type": "a2",
            "display_name": "Agent 2",
        }, headers=_auth(token))

        resp = await client.get("/api/v1/agents", headers=_auth(token))
        # 11 seeded defaults + 2 newly registered = 13
        assert resp.json()["total"] == 13

    @pytest.mark.asyncio
    async def test_routing_info(self, client: AsyncClient) -> None:
        """GET /agents/{type}/routing returns adapter source per stage."""
        token = await _get_token(client)
        resp = await client.get("/api/v1/agents/general/routing", headers=_auth(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["planner"] == "default"
        assert data["executor"] == "default"

    @pytest.mark.asyncio
    async def test_routing_info_missing(self, client: AsyncClient) -> None:
        token = await _get_token(client)
        resp = await client.get("/api/v1/agents/nonexistent/routing", headers=_auth(token))
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Brain Webhook Gateway Tests
# ---------------------------------------------------------------------------

import hashlib
import hmac as hmac_mod
import json
from unittest.mock import AsyncMock, MagicMock

from api.routes.brain import (
    _OPENCLAW_AGENTS,
    _compute_hmac,
    _verify_hmac,
    clear_stores,
    get_dispatch_store,
    get_workflow_execution_store,
    get_workflow_store,
)


@pytest.fixture(autouse=False)
def clean_brain_stores():
    """Ensure brain stores are clean before and after each test."""
    clear_stores()
    yield
    clear_stores()


# ---------------------------------------------------------------------------
# HMAC helpers
# ---------------------------------------------------------------------------


class TestHMACHelpers:
    """Tests for _compute_hmac and _verify_hmac."""

    def test_compute_hmac_deterministic(self) -> None:
        payload = {"task_id": "abc123", "agent_id": "eng-core"}
        secret = "test-secret"
        sig1 = _compute_hmac(payload, secret)
        sig2 = _compute_hmac(payload, secret)
        assert sig1 == sig2
        assert len(sig1) == 64  # SHA-256 hex digest

    def test_compute_hmac_different_secret(self) -> None:
        payload = {"key": "value"}
        sig1 = _compute_hmac(payload, "secret-a")
        sig2 = _compute_hmac(payload, "secret-b")
        assert sig1 != sig2

    def test_compute_hmac_different_payload(self) -> None:
        secret = "shared"
        sig1 = _compute_hmac({"a": 1}, secret)
        sig2 = _compute_hmac({"a": 2}, secret)
        assert sig1 != sig2

    def test_verify_hmac_valid(self) -> None:
        payload = {"task_id": "t1"}
        secret = "my-secret"
        body = json.dumps(payload, sort_keys=True).encode()
        expected = hmac_mod.new(secret.encode(), body, hashlib.sha256).hexdigest()
        assert _verify_hmac(body, f"sha256={expected}", secret) is True

    def test_verify_hmac_invalid_signature(self) -> None:
        body = b'{"key":"value"}'
        assert _verify_hmac(body, "sha256=deadbeef", "secret") is False

    def test_verify_hmac_no_secret(self) -> None:
        body = b'{"key":"value"}'
        assert _verify_hmac(body, "sha256=anything", "") is False

    def test_verify_hmac_without_prefix(self) -> None:
        payload = {"x": 1}
        secret = "s"
        body = json.dumps(payload, sort_keys=True).encode()
        expected = hmac_mod.new(secret.encode(), body, hashlib.sha256).hexdigest()
        assert _verify_hmac(body, expected, secret) is True


# ---------------------------------------------------------------------------
# OpenClaw Agent Registry
# ---------------------------------------------------------------------------


class TestOpenClawRegistry:
    """Tests for the _OPENCLAW_AGENTS static registry."""

    def test_eight_agents_registered(self) -> None:
        assert len(_OPENCLAW_AGENTS) == 8

    def test_all_agents_have_required_fields(self) -> None:
        for agent in _OPENCLAW_AGENTS:
            assert "agent_id" in agent
            assert "name" in agent
            assert "model" in agent
            assert "sub_agents" in agent

    def test_agent_ids_unique(self) -> None:
        ids = [a["agent_id"] for a in _OPENCLAW_AGENTS]
        assert len(ids) == len(set(ids))

    def test_expected_agent_ids(self) -> None:
        ids = {a["agent_id"] for a in _OPENCLAW_AGENTS}
        expected = {
            "eng-core", "wp-web", "infra-ops", "design-lab",
            "content-forge", "social-growth", "intel-research", "biz-strategy",
        }
        assert ids == expected

    def test_sub_agents_have_skills(self) -> None:
        for agent in _OPENCLAW_AGENTS:
            for sub in agent["sub_agents"]:
                assert "id" in sub
                assert "name" in sub
                assert "skills" in sub
                assert len(sub["skills"]) >= 1

    def test_total_sub_agent_count(self) -> None:
        total = sum(len(a["sub_agents"]) for a in _OPENCLAW_AGENTS)
        assert total == 36  # 5+5+5+4+4+4+5+4 (spec rounds to 37)


# ---------------------------------------------------------------------------
# Pydantic model tests
# ---------------------------------------------------------------------------


class TestBrainPydanticModels:
    """Tests for brain-related Pydantic request/response models."""

    def test_task_dispatch_request_valid(self) -> None:
        from api.models import TaskDispatchRequest
        req = TaskDispatchRequest(
            task_name="Build landing page",
            description="Create an AI landing page",
            agent_type="wp-web",
            priority="high",
        )
        assert req.task_name == "Build landing page"
        assert req.priority == "high"

    def test_task_dispatch_request_defaults(self) -> None:
        from api.models import TaskDispatchRequest
        req = TaskDispatchRequest(task_name="Test", description="Desc")
        assert req.agent_type == "general"
        assert req.priority == "normal"
        assert req.metadata == {}

    def test_task_dispatch_request_invalid_priority(self) -> None:
        from api.models import TaskDispatchRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            TaskDispatchRequest(task_name="Test", description="Desc", priority="invalid")

    def test_task_dispatch_request_empty_name(self) -> None:
        from api.models import TaskDispatchRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            TaskDispatchRequest(task_name="", description="Desc")

    def test_agent_callback_request_valid(self) -> None:
        from api.models import AgentCallbackRequest
        req = AgentCallbackRequest(
            task_id="abc123", agent_id="eng-core",
            result={"output": "done"}, success=True,
        )
        assert req.task_id == "abc123"
        assert req.workflow_id is None

    def test_workflow_create_request_valid(self) -> None:
        from api.models import WorkflowCreateRequest, WorkflowTaskNode
        req = WorkflowCreateRequest(
            name="Landing page workflow",
            tasks=[
                WorkflowTaskNode(node_id="research", agent_type="intel-research"),
                WorkflowTaskNode(node_id="build", agent_type="wp-web", depends_on=["research"]),
            ],
        )
        assert len(req.tasks) == 2
        assert req.tasks[1].depends_on == ["research"]

    def test_workflow_create_request_empty_tasks(self) -> None:
        from api.models import WorkflowCreateRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            WorkflowCreateRequest(name="Empty", tasks=[])

    def test_workflow_status_response_model(self) -> None:
        from api.models import WorkflowNodeStatus, WorkflowStatusResponse
        resp = WorkflowStatusResponse(
            workflow_id="wf-1", name="Test WF", status="running",
            nodes=[
                WorkflowNodeStatus(node_id="n1", agent_type="eng-core", status="completed"),
                WorkflowNodeStatus(node_id="n2", agent_type="wp-web", status="pending"),
            ],
            waves=[["n1"], ["n2"]], wave_progress=1, total_waves=2,
        )
        assert resp.wave_progress == 1
        assert resp.total_waves == 2


# ---------------------------------------------------------------------------
# Dispatch endpoint unit tests
# ---------------------------------------------------------------------------


class TestBrainDispatchLogic:
    """Unit tests for dispatch_to_agent logic."""

    @pytest.mark.asyncio
    async def test_dispatch_stores_record(self, clean_brain_stores) -> None:
        from unittest.mock import patch
        from api.models import TaskDispatchRequest
        from api.routes.brain import dispatch_to_agent

        state = MagicMock()
        state.settings.webhook_secret = "test-secret"
        state.settings.openclaw_base_url = "https://claw.occp.ai"
        state.get_agent = AsyncMock(return_value=MagicMock())
        gate_result = MagicMock(approved=True)
        state.policy_engine = MagicMock()
        state.policy_engine.evaluate = AsyncMock(return_value=gate_result)
        state.policy_engine.audit = AsyncMock()

        body = TaskDispatchRequest(
            task_name="Build page", description="Build a landing page",
            agent_type="wp-web", priority="high",
        )

        mock_task = MagicMock()
        mock_task.status = "running"
        mock_task.session_key = "agent:wp-web:test123"
        mock_client = MagicMock()
        mock_client.dispatch_task = AsyncMock(return_value=mock_task)

        with patch("api.routes.brain._get_openclaw_client", return_value=mock_client):
            result = await dispatch_to_agent(agent_id="wp-web", body=body, state=state)
        assert result.status == "dispatched"
        assert result.agent_id == "wp-web"
        assert result.task_id in get_dispatch_store()
        record = get_dispatch_store()[result.task_id]
        assert record["signature"].startswith("sha256=")

    @pytest.mark.asyncio
    async def test_dispatch_unknown_agent_404(self, clean_brain_stores) -> None:
        from fastapi import HTTPException
        from api.models import TaskDispatchRequest
        from api.routes.brain import dispatch_to_agent

        state = MagicMock()
        state.settings.webhook_secret = ""
        state.get_agent = AsyncMock(return_value=None)
        state.policy_engine = None

        body = TaskDispatchRequest(task_name="Test", description="Test task")

        with pytest.raises(HTTPException) as exc_info:
            await dispatch_to_agent(agent_id="nonexistent-agent", body=body, state=state)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_dispatch_policy_rejected(self, clean_brain_stores) -> None:
        from fastapi import HTTPException
        from api.models import TaskDispatchRequest
        from api.routes.brain import dispatch_to_agent

        state = MagicMock()
        state.settings.webhook_secret = ""
        state.get_agent = AsyncMock(return_value=MagicMock())
        gate_result = MagicMock(approved=False, reason="PII detected")
        state.policy_engine = MagicMock()
        state.policy_engine.evaluate = AsyncMock(return_value=gate_result)

        body = TaskDispatchRequest(task_name="Expose SSN", description="SSN 123-45-6789")

        with pytest.raises(HTTPException) as exc_info:
            await dispatch_to_agent(agent_id="eng-core", body=body, state=state)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_dispatch_no_policy_engine(self, clean_brain_stores) -> None:
        from unittest.mock import patch
        from api.models import TaskDispatchRequest
        from api.routes.brain import dispatch_to_agent

        state = MagicMock()
        state.settings.webhook_secret = ""
        state.settings.openclaw_base_url = "https://claw.occp.ai"
        state.get_agent = AsyncMock(return_value=MagicMock())
        state.policy_engine = None

        mock_task = MagicMock()
        mock_task.status = "running"
        mock_task.session_key = "agent:eng-core:test456"
        mock_client = MagicMock()
        mock_client.dispatch_task = AsyncMock(return_value=mock_task)

        body = TaskDispatchRequest(task_name="Test", description="Test task")
        with patch("api.routes.brain._get_openclaw_client", return_value=mock_client):
            result = await dispatch_to_agent(agent_id="eng-core", body=body, state=state)
        assert result.status == "dispatched"


# ---------------------------------------------------------------------------
# Callback endpoint unit tests
# ---------------------------------------------------------------------------


class TestBrainCallbackLogic:
    """Unit tests for agent_callback logic."""

    @pytest.mark.asyncio
    async def test_callback_unknown_task_404(self, clean_brain_stores) -> None:
        from fastapi import HTTPException
        from api.models import AgentCallbackRequest
        from api.routes.brain import agent_callback

        state = MagicMock()
        state.settings.webhook_secret = ""
        state.policy_engine = None

        body = AgentCallbackRequest(task_id="nonexistent", agent_id="eng-core")
        with pytest.raises(HTTPException) as exc_info:
            await agent_callback(request=MagicMock(), body=body, state=state)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_callback_missing_hmac_401(self, clean_brain_stores) -> None:
        from fastapi import HTTPException
        from api.models import AgentCallbackRequest
        from api.routes.brain import agent_callback

        state = MagicMock()
        state.settings.webhook_secret = "secret"

        body = AgentCallbackRequest(task_id="t1", agent_id="eng-core")
        with pytest.raises(HTTPException) as exc_info:
            await agent_callback(
                request=MagicMock(), body=body,
                x_occp_signature=None, state=state,
            )
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_callback_invalid_hmac_401(self, clean_brain_stores) -> None:
        from fastapi import HTTPException
        from api.models import AgentCallbackRequest
        from api.routes.brain import agent_callback

        state = MagicMock()
        state.settings.webhook_secret = "secret"

        request = MagicMock()
        request.body = AsyncMock(return_value=b'{"task_id":"t1","agent_id":"eng-core"}')

        body = AgentCallbackRequest(task_id="t1", agent_id="eng-core")
        with pytest.raises(HTTPException) as exc_info:
            await agent_callback(
                request=request, body=body,
                x_occp_signature="sha256=invalid", state=state,
            )
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_callback_updates_dispatch_record(self, clean_brain_stores) -> None:
        from api.models import AgentCallbackRequest
        from api.routes.brain import agent_callback

        store = get_dispatch_store()
        store["task-1"] = {
            "task_id": "task-1", "agent_id": "eng-core",
            "status": "dispatched", "result": None,
        }

        state = MagicMock()
        state.settings.webhook_secret = ""
        state.policy_engine = MagicMock()
        state.policy_engine.evaluate = AsyncMock(return_value=MagicMock(approved=True))
        state.policy_engine.audit = AsyncMock()

        body = AgentCallbackRequest(
            task_id="task-1", agent_id="eng-core",
            result={"output": "page built"}, success=True,
        )

        result = await agent_callback(request=MagicMock(), body=body, state=state)
        assert result.status == "accepted"
        assert store["task-1"]["status"] == "completed"
        assert store["task-1"]["result"] == {"output": "page built"}

    @pytest.mark.asyncio
    async def test_callback_failed_task(self, clean_brain_stores) -> None:
        from api.models import AgentCallbackRequest
        from api.routes.brain import agent_callback

        store = get_dispatch_store()
        store["task-2"] = {
            "task_id": "task-2", "agent_id": "wp-web",
            "status": "dispatched", "result": None,
        }

        state = MagicMock()
        state.settings.webhook_secret = ""
        state.policy_engine = MagicMock()
        state.policy_engine.evaluate = AsyncMock(return_value=MagicMock(approved=True))
        state.policy_engine.audit = AsyncMock()

        body = AgentCallbackRequest(
            task_id="task-2", agent_id="wp-web",
            result={}, success=False, error="timeout",
        )

        result = await agent_callback(request=MagicMock(), body=body, state=state)
        assert result.status == "accepted"
        assert store["task-2"]["status"] == "failed"

    @pytest.mark.asyncio
    async def test_callback_updates_workflow_state(self, clean_brain_stores) -> None:
        from api.models import AgentCallbackRequest
        from api.routes.brain import agent_callback
        from orchestrator.multi_agent import AgentNode, WorkflowDefinition

        store = get_dispatch_store()
        store["task-wf"] = {
            "task_id": "task-wf", "agent_id": "eng-core",
            "status": "dispatched", "result": None,
        }

        wf = WorkflowDefinition(
            workflow_id="wf-test", name="Test WF",
            nodes=[AgentNode(node_id="n1", agent_type="eng-core", task_template={"name": "N1"})],
        )
        get_workflow_store()["wf-test"] = wf
        get_workflow_execution_store()["wf-test"] = {
            "workflow_id": "wf-test", "status": "running",
            "node_results": {}, "finished_at": None,
        }

        state = MagicMock()
        state.settings.webhook_secret = ""
        state.policy_engine = MagicMock()
        state.policy_engine.evaluate = AsyncMock(return_value=MagicMock(approved=True))
        state.policy_engine.audit = AsyncMock()

        body = AgentCallbackRequest(
            task_id="task-wf", agent_id="eng-core",
            result={"output": "done"}, success=True,
            workflow_id="wf-test", node_id="n1",
        )

        await agent_callback(request=MagicMock(), body=body, state=state)

        wf_exec = get_workflow_execution_store()["wf-test"]
        assert wf_exec["node_results"]["n1"]["status"] == "completed"
        assert wf_exec["status"] == "completed"
        assert wf_exec["finished_at"] is not None


# ---------------------------------------------------------------------------
# Registry endpoint unit tests
# ---------------------------------------------------------------------------


class TestBrainRegistryLogic:
    """Unit tests for list_agent_registry logic."""

    @pytest.mark.asyncio
    async def test_registry_returns_8_agents(self) -> None:
        from api.routes.brain import list_agent_registry
        state = MagicMock()
        state.list_agents = AsyncMock(return_value=[])
        result = await list_agent_registry(state=state)
        assert result.total == 8
        assert len(result.agents) == 8

    @pytest.mark.asyncio
    async def test_registry_includes_sub_agents(self) -> None:
        from api.routes.brain import list_agent_registry
        state = MagicMock()
        state.list_agents = AsyncMock(return_value=[])
        result = await list_agent_registry(state=state)
        eng = next(a for a in result.agents if a.agent_id == "eng-core")
        assert len(eng.sub_agents) == 5
        assert eng.sub_agents[0].id == "frontend-ui"

    @pytest.mark.asyncio
    async def test_registry_skill_count(self) -> None:
        from api.routes.brain import list_agent_registry
        state = MagicMock()
        state.list_agents = AsyncMock(return_value=[])
        result = await list_agent_registry(state=state)
        eng = next(a for a in result.agents if a.agent_id == "eng-core")
        assert eng.skill_count == 15  # 5 sub-agents * 3 skills

    @pytest.mark.asyncio
    async def test_registry_online_status(self) -> None:
        from api.routes.brain import list_agent_registry
        registered = AgentConfig(
            agent_type="eng-core", display_name="Engineering",
            capabilities=["planning", "execution"],
        )
        state = MagicMock()
        state.list_agents = AsyncMock(return_value=[registered])
        result = await list_agent_registry(state=state)
        eng = next(a for a in result.agents if a.agent_id == "eng-core")
        assert eng.status == "online"
        assert eng.capabilities == ["planning", "execution"]
        wp = next(a for a in result.agents if a.agent_id == "wp-web")
        assert wp.status == "offline"


# ---------------------------------------------------------------------------
# Workflow create unit tests
# ---------------------------------------------------------------------------


class TestBrainWorkflowCreateLogic:
    """Unit tests for create_workflow logic."""

    @pytest.mark.asyncio
    async def test_create_valid_workflow(self, clean_brain_stores) -> None:
        from api.models import WorkflowCreateRequest, WorkflowTaskNode
        from api.routes.brain import create_workflow

        state = MagicMock()
        state.policy_engine = MagicMock()
        state.policy_engine.audit = AsyncMock()

        body = WorkflowCreateRequest(
            name="AI Landing Page",
            tasks=[
                WorkflowTaskNode(node_id="research", agent_type="intel-research", task_name="Research", description="Research best practices"),
                WorkflowTaskNode(node_id="build", agent_type="wp-web", task_name="Build", description="Build the page", depends_on=["research"]),
                WorkflowTaskNode(node_id="deploy", agent_type="infra-ops", task_name="Deploy", description="Deploy to prod", depends_on=["build"]),
            ],
        )

        result = await create_workflow(body=body, state=state)
        assert result.name == "AI Landing Page"
        assert result.node_count == 3
        assert len(result.waves) == 3
        assert result.waves[0] == ["research"]
        assert result.workflow_id in get_workflow_store()

    @pytest.mark.asyncio
    async def test_create_workflow_with_cycle_422(self, clean_brain_stores) -> None:
        from fastapi import HTTPException
        from api.models import WorkflowCreateRequest, WorkflowTaskNode
        from api.routes.brain import create_workflow

        state = MagicMock()
        state.policy_engine = None

        body = WorkflowCreateRequest(
            name="Cyclic",
            tasks=[
                WorkflowTaskNode(node_id="a", agent_type="eng-core", depends_on=["c"]),
                WorkflowTaskNode(node_id="b", agent_type="wp-web", depends_on=["a"]),
                WorkflowTaskNode(node_id="c", agent_type="infra-ops", depends_on=["b"]),
            ],
        )

        with pytest.raises(HTTPException) as exc_info:
            await create_workflow(body=body, state=state)
        assert exc_info.value.status_code == 422
        assert "Cycle" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_create_workflow_parallel_waves(self, clean_brain_stores) -> None:
        from api.models import WorkflowCreateRequest, WorkflowTaskNode
        from api.routes.brain import create_workflow

        state = MagicMock()
        state.policy_engine = None

        body = WorkflowCreateRequest(
            name="Parallel",
            tasks=[
                WorkflowTaskNode(node_id="a", agent_type="intel-research"),
                WorkflowTaskNode(node_id="b", agent_type="content-forge"),
                WorkflowTaskNode(node_id="c", agent_type="design-lab"),
                WorkflowTaskNode(node_id="merge", agent_type="wp-web", depends_on=["a", "b", "c"]),
            ],
        )

        result = await create_workflow(body=body, state=state)
        assert result.node_count == 4
        assert len(result.waves) == 2
        assert sorted(result.waves[0]) == ["a", "b", "c"]
        assert result.waves[1] == ["merge"]


# ---------------------------------------------------------------------------
# Workflow status unit tests
# ---------------------------------------------------------------------------


class TestBrainWorkflowStatusLogic:
    """Unit tests for get_workflow_status logic."""

    @pytest.mark.asyncio
    async def test_status_not_found_404(self, clean_brain_stores) -> None:
        from fastapi import HTTPException
        from api.routes.brain import get_workflow_status

        state = MagicMock()
        with pytest.raises(HTTPException) as exc_info:
            await get_workflow_status(workflow_id="nonexistent", state=state)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_status_pending_workflow(self, clean_brain_stores) -> None:
        from orchestrator.multi_agent import AgentNode, WorkflowDefinition
        from api.routes.brain import get_workflow_status

        wf = WorkflowDefinition(
            workflow_id="wf-s1", name="Status Test",
            nodes=[
                AgentNode(node_id="n1", agent_type="eng-core", task_template={"name": "N1"}),
                AgentNode(node_id="n2", agent_type="wp-web", task_template={"name": "N2"}, depends_on=["n1"]),
            ],
        )
        get_workflow_store()["wf-s1"] = wf
        get_workflow_execution_store()["wf-s1"] = {
            "workflow_id": "wf-s1", "status": "pending",
            "node_results": {},
            "started_at": "2026-03-26T00:00:00", "finished_at": None,
            "waves": [["n1"], ["n2"]],
        }

        state = MagicMock()
        result = await get_workflow_status(workflow_id="wf-s1", state=state)
        assert result.status == "pending"
        assert result.total_waves == 2
        assert result.wave_progress == 0
        assert len(result.nodes) == 2
        assert result.nodes[0].status == "pending"

    @pytest.mark.asyncio
    async def test_status_partial_completion(self, clean_brain_stores) -> None:
        from orchestrator.multi_agent import AgentNode, WorkflowDefinition
        from api.routes.brain import get_workflow_status

        wf = WorkflowDefinition(
            workflow_id="wf-s2", name="Partial",
            nodes=[
                AgentNode(node_id="n1", agent_type="eng-core", task_template={"name": "N1"}),
                AgentNode(node_id="n2", agent_type="wp-web", task_template={"name": "N2"}, depends_on=["n1"]),
            ],
        )
        get_workflow_store()["wf-s2"] = wf
        get_workflow_execution_store()["wf-s2"] = {
            "workflow_id": "wf-s2", "status": "running",
            "node_results": {
                "n1": {"status": "completed", "result": {"done": True}, "error": None},
            },
            "started_at": "2026-03-26T00:00:00", "finished_at": None,
            "waves": [["n1"], ["n2"]],
        }

        state = MagicMock()
        result = await get_workflow_status(workflow_id="wf-s2", state=state)
        assert result.wave_progress == 1
        assert result.nodes[0].status == "completed"
        assert result.nodes[1].status == "pending"


# ---------------------------------------------------------------------------
# Brain API integration tests (full HTTP roundtrip)
# ---------------------------------------------------------------------------


class TestBrainAPI:
    """Integration tests for brain endpoints via HTTP client."""

    @pytest.mark.asyncio
    async def test_registry_endpoint(self, client: AsyncClient) -> None:
        """GET /agents/registry returns 8 OpenClaw agents."""
        token = await _get_token(client)
        resp = await client.get("/api/v1/agents/registry", headers=_auth(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 8
        ids = {a["agent_id"] for a in data["agents"]}
        assert "eng-core" in ids
        assert "wp-web" in ids

    @pytest.mark.asyncio
    async def test_registry_sub_agents_included(self, client: AsyncClient) -> None:
        token = await _get_token(client)
        resp = await client.get("/api/v1/agents/registry", headers=_auth(token))
        data = resp.json()
        eng = next(a for a in data["agents"] if a["agent_id"] == "eng-core")
        assert len(eng["sub_agents"]) == 5
        assert eng["skill_count"] == 15

    @pytest.mark.asyncio
    async def test_dispatch_endpoint(self, client: AsyncClient) -> None:
        """POST /agents/{agent_id}/dispatch dispatches a task."""
        from unittest.mock import patch, MagicMock, AsyncMock

        mock_task = MagicMock()
        mock_task.status = "running"
        mock_task.session_key = "agent:eng-core:test789"
        mock_client = MagicMock()
        mock_client.dispatch_task = AsyncMock(return_value=mock_task)

        token = await _get_token(client)
        with patch("api.routes.brain._get_openclaw_client", return_value=mock_client):
            resp = await client.post(
                "/api/v1/agents/eng-core/dispatch",
                json={
                    "task_name": "Build API",
                    "description": "Build a FastAPI endpoint",
                    "agent_type": "eng-core",
                    "priority": "high",
                },
                headers=_auth(token),
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "dispatched"
        assert data["agent_id"] == "eng-core"
        assert "task_id" in data

    @pytest.mark.asyncio
    async def test_dispatch_requires_auth(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/agents/eng-core/dispatch",
            json={"task_name": "Test", "description": "Test"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_workflow_create_endpoint(self, client: AsyncClient) -> None:
        """POST /workflows creates a valid DAG workflow."""
        token = await _get_token(client)
        resp = await client.post(
            "/api/v1/workflows",
            json={
                "name": "Test Workflow",
                "tasks": [
                    {"node_id": "a", "agent_type": "intel-research"},
                    {"node_id": "b", "agent_type": "wp-web", "depends_on": ["a"]},
                ],
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Test Workflow"
        assert data["node_count"] == 2
        assert len(data["waves"]) == 2

    @pytest.mark.asyncio
    async def test_workflow_create_cycle_rejected(self, client: AsyncClient) -> None:
        token = await _get_token(client)
        resp = await client.post(
            "/api/v1/workflows",
            json={
                "name": "Cyclic",
                "tasks": [
                    {"node_id": "a", "agent_type": "eng-core", "depends_on": ["c"]},
                    {"node_id": "b", "agent_type": "wp-web", "depends_on": ["a"]},
                    {"node_id": "c", "agent_type": "infra-ops", "depends_on": ["b"]},
                ],
            },
            headers=_auth(token),
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_workflow_status_endpoint(self, client: AsyncClient) -> None:
        """GET /workflows/{id}/status returns workflow progress."""
        token = await _get_token(client)
        # First create a workflow
        create_resp = await client.post(
            "/api/v1/workflows",
            json={
                "name": "Status Test",
                "tasks": [
                    {"node_id": "n1", "agent_type": "eng-core"},
                    {"node_id": "n2", "agent_type": "wp-web", "depends_on": ["n1"]},
                ],
            },
            headers=_auth(token),
        )
        wf_id = create_resp.json()["workflow_id"]

        resp = await client.get(
            f"/api/v1/workflows/{wf_id}/status",
            headers=_auth(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["workflow_id"] == wf_id
        assert data["status"] == "pending"
        assert data["total_waves"] == 2
        assert len(data["nodes"]) == 2

    @pytest.mark.asyncio
    async def test_workflow_status_not_found(self, client: AsyncClient) -> None:
        token = await _get_token(client)
        resp = await client.get(
            "/api/v1/workflows/nonexistent/status",
            headers=_auth(token),
        )
        assert resp.status_code == 404
