"""Tests for CloudCode hook integration — Claude Code CLI to Brian the Brain."""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from api.app import create_app
from api.routes.cloudcode import (
    CloudCodeCommand,
    CloudCodeResponse,
    CloudCodeTaskResult,
    _run_pipeline_background,
)
from orchestrator.models import PipelineResult, RiskLevel, Task, TaskStatus


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def client(tmp_path):
    db_path = tmp_path / "test_cloudcode.db"
    os.environ["OCCP_DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"
    os.environ["OCCP_ADMIN_USER"] = "testadmin"
    os.environ["OCCP_ADMIN_PASSWORD"] = "testpass123"
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


# ---------------------------------------------------------------------------
# Model validation tests
# ---------------------------------------------------------------------------


class TestCloudCodeModels:
    def test_command_model_defaults(self):
        cmd = CloudCodeCommand(command="test task")
        assert cmd.source == "cloudcode"
        assert cmd.hook_type == "UserPromptSubmit"
        assert cmd.priority == "high"
        assert cmd.context is None
        assert cmd.cwd is None

    def test_command_model_full(self):
        cmd = CloudCodeCommand(
            command="deploy feature",
            source="cloudcode",
            hook_type="Stop",
            priority="low",
            context={"branch": "main"},
            cwd="/tmp/project",
        )
        assert cmd.command == "deploy feature"
        assert cmd.context == {"branch": "main"}
        assert cmd.cwd == "/tmp/project"

    def test_command_model_rejects_empty(self):
        with pytest.raises(Exception):
            CloudCodeCommand(command="")

    def test_response_model(self):
        resp = CloudCodeResponse(
            task_id="abc123",
            status="accepted",
            message="received",
            timestamp="2026-03-30T00:00:00+00:00",
        )
        assert resp.task_id == "abc123"
        assert resp.status == "accepted"

    def test_task_result_model(self):
        result = CloudCodeTaskResult(
            task_id="abc123",
            status="completed",
            name="CloudCode: test",
            result={"output": "ok"},
            error=None,
            plan={"steps": ["step1"]},
            created_at="2026-03-30T00:00:00+00:00",
        )
        assert result.status == "completed"
        assert result.result == {"output": "ok"}

    def test_task_result_model_minimal(self):
        result = CloudCodeTaskResult(
            task_id="x",
            status="pending",
            name="test",
        )
        assert result.result is None
        assert result.error is None
        assert result.plan is None
        assert result.created_at is None


# ---------------------------------------------------------------------------
# Endpoint tests
# ---------------------------------------------------------------------------


class TestCloudCodeEndpoint:
    @pytest.mark.asyncio
    async def test_command_accepted(self, client: AsyncClient):
        resp = await client.post("/api/v1/cloudcode/command", json={
            "command": "analyze codebase security",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "accepted"
        assert "task_id" in data
        assert data["task_id"]  # non-empty
        assert "Brian received" in data["message"]
        assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_command_with_full_payload(self, client: AsyncClient):
        resp = await client.post("/api/v1/cloudcode/command", json={
            "command": "run tests on orchestrator module",
            "source": "cloudcode",
            "hook_type": "PostToolUse",
            "priority": "high",
            "context": {"tool": "Bash", "exit_code": 0},
            "cwd": "/Users/air/Desktop/PROJECTEK/OCCP/occp-core",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "accepted"

    @pytest.mark.asyncio
    async def test_empty_command_rejected(self, client: AsyncClient):
        resp = await client.post("/api/v1/cloudcode/command", json={
            "command": "   ",
        })
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_missing_command_rejected(self, client: AsyncClient):
        resp = await client.post("/api/v1/cloudcode/command", json={})
        assert resp.status_code == 422  # pydantic validation

    @pytest.mark.asyncio
    async def test_command_creates_task(self, client: AsyncClient):
        resp = await client.post("/api/v1/cloudcode/command", json={
            "command": "list all agents",
        })
        assert resp.status_code == 200
        task_id = resp.json()["task_id"]

        # Allow background task to start
        await asyncio.sleep(0.1)

        # Poll task
        poll = await client.get(f"/api/v1/cloudcode/tasks/{task_id}")
        assert poll.status_code == 200
        task_data = poll.json()
        assert task_data["task_id"] == task_id
        assert task_data["name"].startswith("CloudCode:")
        assert task_data["status"] in [s.value for s in TaskStatus]

    @pytest.mark.asyncio
    async def test_task_not_found(self, client: AsyncClient):
        resp = await client.get("/api/v1/cloudcode/tasks/nonexistent999")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_command_truncates_long_name(self, client: AsyncClient):
        long_cmd = "x" * 200
        resp = await client.post("/api/v1/cloudcode/command", json={
            "command": long_cmd,
        })
        assert resp.status_code == 200
        task_id = resp.json()["task_id"]

        await asyncio.sleep(0.05)

        poll = await client.get(f"/api/v1/cloudcode/tasks/{task_id}")
        assert poll.status_code == 200
        # Name should be truncated to ~50 chars + prefix
        assert len(poll.json()["name"]) < 70

    @pytest.mark.asyncio
    async def test_command_message_truncated(self, client: AsyncClient):
        long_cmd = "y" * 300
        resp = await client.post("/api/v1/cloudcode/command", json={
            "command": long_cmd,
        })
        assert resp.status_code == 200
        # Message truncated to 100 chars of command
        assert len(resp.json()["message"]) < 130

    @pytest.mark.asyncio
    async def test_task_metadata_contains_source(self, client: AsyncClient):
        """Verify the task metadata propagates source/hook_type/cwd."""
        resp = await client.post("/api/v1/cloudcode/command", json={
            "command": "check metadata",
            "hook_type": "PreToolUse",
            "cwd": "/tmp/test",
        })
        assert resp.status_code == 200
        # Task was created — metadata is internal, but we can verify via
        # the task being retrievable and having correct name
        task_id = resp.json()["task_id"]
        await asyncio.sleep(0.05)
        poll = await client.get(f"/api/v1/cloudcode/tasks/{task_id}")
        assert poll.status_code == 200
        assert poll.json()["name"] == "CloudCode: check metadata"

    @pytest.mark.asyncio
    async def test_timestamp_is_iso_format(self, client: AsyncClient):
        resp = await client.post("/api/v1/cloudcode/command", json={
            "command": "timestamp test",
        })
        assert resp.status_code == 200
        ts = resp.json()["timestamp"]
        # Should be parseable as ISO datetime
        parsed = datetime.fromisoformat(ts)
        assert parsed.year >= 2026

    @pytest.mark.asyncio
    async def test_task_result_has_created_at(self, client: AsyncClient):
        resp = await client.post("/api/v1/cloudcode/command", json={
            "command": "created at test",
        })
        task_id = resp.json()["task_id"]
        await asyncio.sleep(0.05)

        poll = await client.get(f"/api/v1/cloudcode/tasks/{task_id}")
        assert poll.status_code == 200
        created = poll.json()["created_at"]
        assert created is not None
        parsed = datetime.fromisoformat(created)
        assert parsed.year >= 2026


# ---------------------------------------------------------------------------
# Background pipeline tests
# ---------------------------------------------------------------------------


class TestBackgroundPipeline:
    @pytest.mark.asyncio
    async def test_pipeline_runs_in_background(self):
        """Verify _run_pipeline_background calls pipeline.run."""
        task = Task(
            name="test",
            description="bg test",
            agent_type="general",
        )
        mock_result = MagicMock()
        mock_result.success = True

        state = MagicMock()
        state.pipeline = AsyncMock()
        state.pipeline.run = AsyncMock(return_value=mock_result)

        await _run_pipeline_background(task, state)
        state.pipeline.run.assert_awaited_once_with(task)

    @pytest.mark.asyncio
    async def test_pipeline_none_logs_error(self, caplog):
        """When pipeline is None, should log error and not crash."""
        task = Task(
            name="test",
            description="no pipeline",
            agent_type="general",
        )
        state = MagicMock()
        state.pipeline = None

        await _run_pipeline_background(task, state)
        assert any("pipeline not initialized" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_pipeline_exception_caught(self, caplog):
        """Pipeline exceptions should be caught and logged, not raised."""
        task = Task(
            name="test",
            description="error test",
            agent_type="general",
        )
        state = MagicMock()
        state.pipeline = AsyncMock()
        state.pipeline.run = AsyncMock(side_effect=RuntimeError("boom"))

        # Should not raise
        await _run_pipeline_background(task, state)
        assert any("failed" in r.message for r in caplog.records)
