"""Project Manager — manages 10+ concurrent projects with isolated state.

Each project has its own agent assignments, workflows, and metadata.
Brain dispatches tasks scoped to a specific project context.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Project:
    """A managed project with agent assignments and metadata."""

    project_id: str
    name: str
    description: str
    status: str  # active | paused | completed | archived
    assigned_agents: list[str] = field(default_factory=list)
    priority: int = 5  # 1-10 (1=highest)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    _VALID_STATUSES = {"active", "paused", "completed", "archived"}

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for API responses."""
        return {
            "project_id": self.project_id,
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "assigned_agents": list(self.assigned_agents),
            "priority": self.priority,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": dict(self.metadata),
        }


# Pre-configured projects for Henry's real sites
DEFAULT_PROJECTS: list[dict[str, Any]] = [
    {
        "name": "azar.hu",
        "description": "Azar Management Consulting main site",
        "agents": ["wp-web", "design-lab", "seo-content"],
        "priority": 1,
        "metadata": {"domain": "azar.hu", "hosting": "hetzner", "tech_stack": "WordPress/Elementor"},
    },
    {
        "name": "felnottkepzes.hu",
        "description": "Adult education portal",
        "agents": ["wp-web", "content-forge", "seo-content"],
        "priority": 2,
        "metadata": {"domain": "felnottkepzes.hu", "hosting": "bestweb", "tech_stack": "WordPress"},
    },
    {
        "name": "magyarorszag.ai",
        "description": "Hungary AI news and intelligence portal",
        "agents": ["wp-web", "content-forge", "intel-research"],
        "priority": 2,
        "metadata": {"domain": "magyarorszag.ai", "hosting": "hostinger", "tech_stack": "WordPress"},
    },
    {
        "name": "occp.ai",
        "description": "OpenCloud Control Plane — the platform itself",
        "agents": ["eng-core", "infra-ops", "design-lab"],
        "priority": 1,
        "metadata": {"domain": "occp.ai", "hosting": "hetzner", "tech_stack": "Python/FastAPI/React"},
    },
    {
        "name": "tanfolyam.ai",
        "description": "AI course platform",
        "agents": ["wp-web", "content-forge", "social-growth"],
        "priority": 3,
        "metadata": {"domain": "tanfolyam.ai", "hosting": "hostinger", "tech_stack": "WordPress"},
    },
]


class ProjectManagerError(Exception):
    """Base exception for ProjectManager operations."""


class ProjectNotFoundError(ProjectManagerError):
    """Raised when a project_id is not found."""


class ProjectLimitError(ProjectManagerError):
    """Raised when max concurrent project limit reached."""


class ProjectManager:
    """Manages 10+ concurrent projects with isolated state.

    Thread-safe via asyncio.Lock for mutation operations.
    """

    def __init__(self, max_projects: int = 10) -> None:
        self.max_projects = max_projects
        self._projects: dict[str, Project] = {}
        self._project_workflows: dict[str, list[str]] = {}  # project_id -> workflow_ids
        self._project_tasks: dict[str, list[str]] = {}  # project_id -> task_ids
        self._lock = asyncio.Lock()

    @property
    def project_count(self) -> int:
        """Number of non-archived projects."""
        return sum(1 for p in self._projects.values() if p.status != "archived")

    async def create_project(
        self,
        name: str,
        description: str,
        agents: list[str],
        priority: int = 5,
        metadata: dict[str, Any] | None = None,
    ) -> Project:
        """Create a new project. Raises ProjectLimitError if at capacity."""
        async with self._lock:
            if self.project_count >= self.max_projects:
                raise ProjectLimitError(
                    f"Maximum {self.max_projects} active projects reached "
                    f"(current: {self.project_count})"
                )

            if not 1 <= priority <= 10:
                raise ValueError(f"Priority must be 1-10, got {priority}")

            project_id = uuid.uuid4().hex[:12]
            now = datetime.now(timezone.utc)
            project = Project(
                project_id=project_id,
                name=name,
                description=description,
                status="active",
                assigned_agents=list(agents),
                priority=priority,
                created_at=now,
                updated_at=now,
                metadata=metadata or {},
            )
            self._projects[project_id] = project
            self._project_workflows[project_id] = []
            self._project_tasks[project_id] = []

            logger.info("Project created: id=%s name=%s agents=%s", project_id, name, agents)
            return project

    async def get_project(self, project_id: str) -> Project | None:
        """Get a project by ID. Returns None if not found."""
        return self._projects.get(project_id)

    async def list_projects(self, status: str | None = None) -> list[Project]:
        """List projects, optionally filtered by status."""
        projects = list(self._projects.values())
        if status:
            projects = [p for p in projects if p.status == status]
        # Sort by priority (1=highest first), then name
        projects.sort(key=lambda p: (p.priority, p.name))
        return projects

    async def update_project(self, project_id: str, **kwargs: Any) -> Project:
        """Update project fields. Raises ProjectNotFoundError if not found."""
        async with self._lock:
            project = self._projects.get(project_id)
            if project is None:
                raise ProjectNotFoundError(f"Project '{project_id}' not found")

            allowed_fields = {"name", "description", "status", "priority", "metadata"}
            for key, value in kwargs.items():
                if key not in allowed_fields:
                    raise ValueError(f"Cannot update field: {key}")
                if key == "status" and value not in Project._VALID_STATUSES:
                    raise ValueError(f"Invalid status: {value}")
                if key == "priority" and not (1 <= value <= 10):
                    raise ValueError(f"Priority must be 1-10, got {value}")
                setattr(project, key, value)

            project.updated_at = datetime.now(timezone.utc)
            return project

    async def archive_project(self, project_id: str) -> None:
        """Archive a project (soft delete). Raises ProjectNotFoundError if not found."""
        await self.update_project(project_id, status="archived")
        logger.info("Project archived: id=%s", project_id)

    async def assign_agent(self, project_id: str, agent_id: str) -> None:
        """Assign an agent to a project."""
        async with self._lock:
            project = self._projects.get(project_id)
            if project is None:
                raise ProjectNotFoundError(f"Project '{project_id}' not found")
            if agent_id not in project.assigned_agents:
                project.assigned_agents.append(agent_id)
                project.updated_at = datetime.now(timezone.utc)
                logger.info("Agent %s assigned to project %s", agent_id, project_id)

    async def remove_agent(self, project_id: str, agent_id: str) -> None:
        """Remove an agent from a project."""
        async with self._lock:
            project = self._projects.get(project_id)
            if project is None:
                raise ProjectNotFoundError(f"Project '{project_id}' not found")
            if agent_id in project.assigned_agents:
                project.assigned_agents.remove(agent_id)
                project.updated_at = datetime.now(timezone.utc)
                logger.info("Agent %s removed from project %s", agent_id, project_id)
            else:
                raise ValueError(f"Agent '{agent_id}' not assigned to project '{project_id}'")

    async def get_project_status(self, project_id: str) -> dict[str, Any]:
        """Get full project status: agents, workflows, tasks summary."""
        project = self._projects.get(project_id)
        if project is None:
            raise ProjectNotFoundError(f"Project '{project_id}' not found")

        workflow_ids = self._project_workflows.get(project_id, [])
        task_ids = self._project_tasks.get(project_id, [])

        return {
            "project": project.to_dict(),
            "agents": list(project.assigned_agents),
            "agent_count": len(project.assigned_agents),
            "workflow_ids": list(workflow_ids),
            "workflow_count": len(workflow_ids),
            "task_ids": list(task_ids),
            "task_count": len(task_ids),
        }

    async def dispatch_to_project(self, project_id: str, task_input: str) -> str:
        """Dispatch a task within a project context. Returns task_id."""
        project = self._projects.get(project_id)
        if project is None:
            raise ProjectNotFoundError(f"Project '{project_id}' not found")

        if project.status != "active":
            raise ProjectManagerError(
                f"Cannot dispatch to project '{project_id}' with status '{project.status}'"
            )

        if not project.assigned_agents:
            raise ProjectManagerError(
                f"Project '{project_id}' has no assigned agents"
            )

        task_id = uuid.uuid4().hex[:16]
        async with self._lock:
            if project_id not in self._project_tasks:
                self._project_tasks[project_id] = []
            self._project_tasks[project_id].append(task_id)

        logger.info(
            "Task dispatched to project: task_id=%s project_id=%s input=%s",
            task_id,
            project_id,
            task_input[:100],
        )
        return task_id

    async def add_workflow_to_project(self, project_id: str, workflow_id: str) -> None:
        """Link a workflow to a project."""
        async with self._lock:
            project = self._projects.get(project_id)
            if project is None:
                raise ProjectNotFoundError(f"Project '{project_id}' not found")
            if project_id not in self._project_workflows:
                self._project_workflows[project_id] = []
            self._project_workflows[project_id].append(workflow_id)

    async def seed_defaults(self) -> list[Project]:
        """Seed default projects. Idempotent — skips if projects already exist."""
        if self._projects:
            return list(self._projects.values())

        seeded: list[Project] = []
        for proj_def in DEFAULT_PROJECTS:
            project = await self.create_project(
                name=proj_def["name"],
                description=proj_def["description"],
                agents=proj_def["agents"],
                priority=proj_def.get("priority", 5),
                metadata=proj_def.get("metadata", {}),
            )
            seeded.append(project)
        logger.info("Seeded %d default projects", len(seeded))
        return seeded
