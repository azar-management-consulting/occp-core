"""Tests for ProjectManager — 10-project concurrent routing system.

Covers:
- CRUD operations
- 10 concurrent project creation
- Agent assignment/removal
- Project dispatch
- Status aggregation
- API endpoints
- Default projects initialization
"""

from __future__ import annotations

import asyncio
import os

import pytest
from httpx import ASGITransport, AsyncClient

from orchestrator.project_manager import (
    DEFAULT_PROJECTS,
    Project,
    ProjectLimitError,
    ProjectManager,
    ProjectManagerError,
    ProjectNotFoundError,
)


# ---------------------------------------------------------------------------
# Unit tests — ProjectManager core
# ---------------------------------------------------------------------------


class TestProjectManagerCRUD:
    """Test basic CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_project(self) -> None:
        pm = ProjectManager(max_projects=10)
        project = await pm.create_project(
            name="test-site.hu",
            description="Test project",
            agents=["wp-web", "design-lab"],
            priority=3,
            metadata={"domain": "test-site.hu"},
        )
        assert project.name == "test-site.hu"
        assert project.status == "active"
        assert project.priority == 3
        assert project.assigned_agents == ["wp-web", "design-lab"]
        assert project.metadata["domain"] == "test-site.hu"
        assert len(project.project_id) == 12

    @pytest.mark.asyncio
    async def test_get_project(self) -> None:
        pm = ProjectManager()
        created = await pm.create_project(name="get-test", description="", agents=[])
        fetched = await pm.get_project(created.project_id)
        assert fetched is not None
        assert fetched.project_id == created.project_id
        assert fetched.name == "get-test"

    @pytest.mark.asyncio
    async def test_get_project_not_found(self) -> None:
        pm = ProjectManager()
        result = await pm.get_project("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_projects_all(self) -> None:
        pm = ProjectManager()
        await pm.create_project(name="p1", description="", agents=[], priority=5)
        await pm.create_project(name="p2", description="", agents=[], priority=1)
        projects = await pm.list_projects()
        assert len(projects) == 2
        # Sorted by priority: p2 (1) before p1 (5)
        assert projects[0].name == "p2"
        assert projects[1].name == "p1"

    @pytest.mark.asyncio
    async def test_list_projects_filter_status(self) -> None:
        pm = ProjectManager()
        p1 = await pm.create_project(name="active-proj", description="", agents=[])
        p2 = await pm.create_project(name="paused-proj", description="", agents=[])
        await pm.update_project(p2.project_id, status="paused")

        active = await pm.list_projects(status="active")
        assert len(active) == 1
        assert active[0].name == "active-proj"

        paused = await pm.list_projects(status="paused")
        assert len(paused) == 1
        assert paused[0].name == "paused-proj"

    @pytest.mark.asyncio
    async def test_update_project(self) -> None:
        pm = ProjectManager()
        p = await pm.create_project(name="orig", description="d", agents=[])
        updated = await pm.update_project(p.project_id, name="renamed", priority=2)
        assert updated.name == "renamed"
        assert updated.priority == 2
        assert updated.updated_at > p.created_at

    @pytest.mark.asyncio
    async def test_update_project_invalid_field(self) -> None:
        pm = ProjectManager()
        p = await pm.create_project(name="x", description="", agents=[])
        with pytest.raises(ValueError, match="Cannot update field"):
            await pm.update_project(p.project_id, created_at="hack")

    @pytest.mark.asyncio
    async def test_update_project_invalid_status(self) -> None:
        pm = ProjectManager()
        p = await pm.create_project(name="x", description="", agents=[])
        with pytest.raises(ValueError, match="Invalid status"):
            await pm.update_project(p.project_id, status="invalid")

    @pytest.mark.asyncio
    async def test_update_project_not_found(self) -> None:
        pm = ProjectManager()
        with pytest.raises(ProjectNotFoundError):
            await pm.update_project("missing", name="x")

    @pytest.mark.asyncio
    async def test_archive_project(self) -> None:
        pm = ProjectManager()
        p = await pm.create_project(name="to-archive", description="", agents=[])
        await pm.archive_project(p.project_id)
        fetched = await pm.get_project(p.project_id)
        assert fetched is not None
        assert fetched.status == "archived"


class TestProjectManagerAgents:
    """Test agent assignment and removal."""

    @pytest.mark.asyncio
    async def test_assign_agent(self) -> None:
        pm = ProjectManager()
        p = await pm.create_project(name="p", description="", agents=["wp-web"])
        await pm.assign_agent(p.project_id, "design-lab")
        fetched = await pm.get_project(p.project_id)
        assert "design-lab" in fetched.assigned_agents
        assert "wp-web" in fetched.assigned_agents

    @pytest.mark.asyncio
    async def test_assign_agent_idempotent(self) -> None:
        pm = ProjectManager()
        p = await pm.create_project(name="p", description="", agents=["wp-web"])
        await pm.assign_agent(p.project_id, "wp-web")
        fetched = await pm.get_project(p.project_id)
        assert fetched.assigned_agents.count("wp-web") == 1

    @pytest.mark.asyncio
    async def test_remove_agent(self) -> None:
        pm = ProjectManager()
        p = await pm.create_project(name="p", description="", agents=["wp-web", "design-lab"])
        await pm.remove_agent(p.project_id, "wp-web")
        fetched = await pm.get_project(p.project_id)
        assert "wp-web" not in fetched.assigned_agents
        assert "design-lab" in fetched.assigned_agents

    @pytest.mark.asyncio
    async def test_remove_agent_not_assigned(self) -> None:
        pm = ProjectManager()
        p = await pm.create_project(name="p", description="", agents=[])
        with pytest.raises(ValueError, match="not assigned"):
            await pm.remove_agent(p.project_id, "unknown-agent")

    @pytest.mark.asyncio
    async def test_assign_agent_project_not_found(self) -> None:
        pm = ProjectManager()
        with pytest.raises(ProjectNotFoundError):
            await pm.assign_agent("missing", "wp-web")


class TestProjectManagerConcurrency:
    """Test concurrent project creation up to limit."""

    @pytest.mark.asyncio
    async def test_create_10_concurrent_projects(self) -> None:
        pm = ProjectManager(max_projects=10)
        tasks = [
            pm.create_project(
                name=f"project-{i}",
                description=f"Concurrent project {i}",
                agents=["eng-core"],
                priority=min(i + 1, 10),
            )
            for i in range(10)
        ]
        projects = await asyncio.gather(*tasks)
        assert len(projects) == 10
        assert pm.project_count == 10
        # All IDs unique
        ids = {p.project_id for p in projects}
        assert len(ids) == 10

    @pytest.mark.asyncio
    async def test_exceed_max_projects(self) -> None:
        pm = ProjectManager(max_projects=3)
        for i in range(3):
            await pm.create_project(name=f"p{i}", description="", agents=[])
        with pytest.raises(ProjectLimitError, match="Maximum 3"):
            await pm.create_project(name="overflow", description="", agents=[])

    @pytest.mark.asyncio
    async def test_archived_projects_dont_count_toward_limit(self) -> None:
        pm = ProjectManager(max_projects=2)
        p1 = await pm.create_project(name="p1", description="", agents=[])
        await pm.create_project(name="p2", description="", agents=[])
        assert pm.project_count == 2

        # Archive p1 — should free a slot
        await pm.archive_project(p1.project_id)
        assert pm.project_count == 1

        # Now we can create a new one
        p3 = await pm.create_project(name="p3", description="", agents=[])
        assert p3.name == "p3"
        assert pm.project_count == 2


class TestProjectManagerDispatch:
    """Test task dispatch within project context."""

    @pytest.mark.asyncio
    async def test_dispatch_to_project(self) -> None:
        pm = ProjectManager()
        p = await pm.create_project(name="d", description="", agents=["wp-web"])
        task_id = await pm.dispatch_to_project(p.project_id, "Build homepage")
        assert len(task_id) == 16
        # Task tracked in project
        status = await pm.get_project_status(p.project_id)
        assert task_id in status["task_ids"]
        assert status["task_count"] == 1

    @pytest.mark.asyncio
    async def test_dispatch_to_paused_project(self) -> None:
        pm = ProjectManager()
        p = await pm.create_project(name="d", description="", agents=["wp-web"])
        await pm.update_project(p.project_id, status="paused")
        with pytest.raises(ProjectManagerError, match="status 'paused'"):
            await pm.dispatch_to_project(p.project_id, "task")

    @pytest.mark.asyncio
    async def test_dispatch_to_project_no_agents(self) -> None:
        pm = ProjectManager()
        p = await pm.create_project(name="d", description="", agents=[])
        with pytest.raises(ProjectManagerError, match="no assigned agents"):
            await pm.dispatch_to_project(p.project_id, "task")

    @pytest.mark.asyncio
    async def test_dispatch_to_nonexistent_project(self) -> None:
        pm = ProjectManager()
        with pytest.raises(ProjectNotFoundError):
            await pm.dispatch_to_project("nope", "task")


class TestProjectManagerStatus:
    """Test project status aggregation."""

    @pytest.mark.asyncio
    async def test_get_project_status(self) -> None:
        pm = ProjectManager()
        p = await pm.create_project(
            name="s", description="desc", agents=["wp-web", "design-lab"]
        )
        await pm.add_workflow_to_project(p.project_id, "wf-001")
        await pm.dispatch_to_project(p.project_id, "task input")

        status = await pm.get_project_status(p.project_id)
        assert status["agent_count"] == 2
        assert status["workflow_count"] == 1
        assert status["task_count"] == 1
        assert status["project"]["name"] == "s"

    @pytest.mark.asyncio
    async def test_get_project_status_not_found(self) -> None:
        pm = ProjectManager()
        with pytest.raises(ProjectNotFoundError):
            await pm.get_project_status("missing")


class TestDefaultProjects:
    """Test default project seeding."""

    @pytest.mark.asyncio
    async def test_seed_defaults(self) -> None:
        pm = ProjectManager(max_projects=10)
        seeded = await pm.seed_defaults()
        assert len(seeded) == len(DEFAULT_PROJECTS)
        names = {p.name for p in seeded}
        assert "azar.hu" in names
        assert "felnottkepzes.hu" in names
        assert "magyarorszag.ai" in names
        assert "occp.ai" in names
        assert "tanfolyam.ai" in names

    @pytest.mark.asyncio
    async def test_seed_defaults_idempotent(self) -> None:
        pm = ProjectManager(max_projects=10)
        first = await pm.seed_defaults()
        second = await pm.seed_defaults()
        # Second call returns existing projects, doesn't create new ones
        assert len(second) == len(first)

    @pytest.mark.asyncio
    async def test_default_project_agents(self) -> None:
        pm = ProjectManager(max_projects=10)
        await pm.seed_defaults()
        projects = await pm.list_projects()
        azar = next(p for p in projects if p.name == "azar.hu")
        assert "wp-web" in azar.assigned_agents
        assert "design-lab" in azar.assigned_agents
        assert "seo-content" in azar.assigned_agents
        assert azar.metadata["hosting"] == "hetzner"

    @pytest.mark.asyncio
    async def test_default_project_priorities(self) -> None:
        pm = ProjectManager(max_projects=10)
        await pm.seed_defaults()
        projects = await pm.list_projects()
        azar = next(p for p in projects if p.name == "azar.hu")
        occp = next(p for p in projects if p.name == "occp.ai")
        assert azar.priority == 1
        assert occp.priority == 1


class TestProjectToDict:
    """Test Project serialization."""

    @pytest.mark.asyncio
    async def test_to_dict(self) -> None:
        pm = ProjectManager()
        p = await pm.create_project(
            name="dict-test", description="desc", agents=["a1"], metadata={"k": "v"}
        )
        d = p.to_dict()
        assert d["project_id"] == p.project_id
        assert d["name"] == "dict-test"
        assert d["assigned_agents"] == ["a1"]
        assert isinstance(d["created_at"], str)


class TestProjectPriorityValidation:
    """Test priority boundary validation."""

    @pytest.mark.asyncio
    async def test_invalid_priority_low(self) -> None:
        pm = ProjectManager()
        with pytest.raises(ValueError, match="Priority must be 1-10"):
            await pm.create_project(name="x", description="", agents=[], priority=0)

    @pytest.mark.asyncio
    async def test_invalid_priority_high(self) -> None:
        pm = ProjectManager()
        with pytest.raises(ValueError, match="Priority must be 1-10"):
            await pm.create_project(name="x", description="", agents=[], priority=11)


# ---------------------------------------------------------------------------
# API integration tests
# ---------------------------------------------------------------------------


@pytest.fixture
async def client(tmp_path):
    """Test client with full app lifespan (includes ProjectManager)."""
    from api.app import create_app

    db_path = tmp_path / "test_projects.db"
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


async def _get_token(client: AsyncClient) -> str:
    resp = await client.post("/api/v1/auth/login", json={
        "username": "testadmin",
        "password": "testpass123",
    })
    assert resp.status_code == 200
    return resp.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class TestProjectAPI:
    """Test REST API endpoints for projects."""

    @pytest.mark.asyncio
    async def test_list_projects_seeded(self, client: AsyncClient) -> None:
        token = await _get_token(client)
        resp = await client.get("/api/v1/projects", headers=_auth(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 5  # 5 default projects seeded
        names = {p["name"] for p in data["projects"]}
        assert "azar.hu" in names

    @pytest.mark.asyncio
    async def test_create_project_api(self, client: AsyncClient) -> None:
        token = await _get_token(client)
        resp = await client.post(
            "/api/v1/projects",
            headers=_auth(token),
            json={
                "name": "api-test.hu",
                "description": "API test project",
                "agents": ["eng-core"],
                "priority": 4,
                "metadata": {"domain": "api-test.hu"},
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "api-test.hu"
        assert data["status"] == "active"
        assert data["assigned_agents"] == ["eng-core"]
        assert data["priority"] == 4

    @pytest.mark.asyncio
    async def test_get_project_api(self, client: AsyncClient) -> None:
        token = await _get_token(client)
        # List to get a project_id
        resp = await client.get("/api/v1/projects", headers=_auth(token))
        project_id = resp.json()["projects"][0]["project_id"]

        resp = await client.get(f"/api/v1/projects/{project_id}", headers=_auth(token))
        assert resp.status_code == 200
        assert resp.json()["project_id"] == project_id

    @pytest.mark.asyncio
    async def test_get_project_not_found_api(self, client: AsyncClient) -> None:
        token = await _get_token(client)
        resp = await client.get("/api/v1/projects/nonexistent", headers=_auth(token))
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_update_project_api(self, client: AsyncClient) -> None:
        token = await _get_token(client)
        resp = await client.get("/api/v1/projects", headers=_auth(token))
        project_id = resp.json()["projects"][0]["project_id"]

        resp = await client.put(
            f"/api/v1/projects/{project_id}",
            headers=_auth(token),
            json={"name": "renamed-via-api", "priority": 2},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "renamed-via-api"
        assert resp.json()["priority"] == 2

    @pytest.mark.asyncio
    async def test_archive_project_api(self, client: AsyncClient) -> None:
        token = await _get_token(client)
        # Create a fresh project to archive
        resp = await client.post(
            "/api/v1/projects",
            headers=_auth(token),
            json={"name": "to-archive", "agents": []},
        )
        project_id = resp.json()["project_id"]

        resp = await client.delete(f"/api/v1/projects/{project_id}", headers=_auth(token))
        assert resp.status_code == 204

        # Verify archived
        resp = await client.get(f"/api/v1/projects/{project_id}", headers=_auth(token))
        assert resp.json()["status"] == "archived"

    @pytest.mark.asyncio
    async def test_project_status_api(self, client: AsyncClient) -> None:
        token = await _get_token(client)
        resp = await client.get("/api/v1/projects", headers=_auth(token))
        project_id = resp.json()["projects"][0]["project_id"]

        resp = await client.get(f"/api/v1/projects/{project_id}/status", headers=_auth(token))
        assert resp.status_code == 200
        data = resp.json()
        assert "project" in data
        assert "agents" in data
        assert "agent_count" in data
        assert "workflow_count" in data
        assert "task_count" in data

    @pytest.mark.asyncio
    async def test_assign_agent_api(self, client: AsyncClient) -> None:
        token = await _get_token(client)
        resp = await client.post(
            "/api/v1/projects",
            headers=_auth(token),
            json={"name": "agent-test", "agents": ["wp-web"]},
        )
        project_id = resp.json()["project_id"]

        resp = await client.post(
            f"/api/v1/projects/{project_id}/agents",
            headers=_auth(token),
            json={"agent_id": "design-lab"},
        )
        assert resp.status_code == 200
        assert "design-lab" in resp.json()["assigned_agents"]

    @pytest.mark.asyncio
    async def test_remove_agent_api(self, client: AsyncClient) -> None:
        token = await _get_token(client)
        resp = await client.post(
            "/api/v1/projects",
            headers=_auth(token),
            json={"name": "agent-rm-test", "agents": ["wp-web", "design-lab"]},
        )
        project_id = resp.json()["project_id"]

        resp = await client.delete(
            f"/api/v1/projects/{project_id}/agents/wp-web",
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert "wp-web" not in resp.json()["assigned_agents"]

    @pytest.mark.asyncio
    async def test_dispatch_to_project_api(self, client: AsyncClient) -> None:
        token = await _get_token(client)
        resp = await client.post(
            "/api/v1/projects",
            headers=_auth(token),
            json={"name": "dispatch-test", "agents": ["eng-core"]},
        )
        project_id = resp.json()["project_id"]

        resp = await client.post(
            f"/api/v1/projects/{project_id}/dispatch",
            headers=_auth(token),
            json={"task_input": "Build the landing page"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["project_id"] == project_id
        assert data["status"] == "dispatched"
        assert len(data["task_id"]) == 16

    @pytest.mark.asyncio
    async def test_filter_projects_by_status_api(self, client: AsyncClient) -> None:
        token = await _get_token(client)
        resp = await client.get(
            "/api/v1/projects?status=active",
            headers=_auth(token),
        )
        assert resp.status_code == 200
        for p in resp.json()["projects"]:
            assert p["status"] == "active"

    @pytest.mark.asyncio
    async def test_unauthorized_access(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/projects")
        assert resp.status_code in (401, 403)
