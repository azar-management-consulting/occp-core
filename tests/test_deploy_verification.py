"""Tests for deploy verification logic.

These tests validate the verification checks used in scripts/verify_deploy.sh
by testing the actual API endpoints in a local test client context.
"""

from __future__ import annotations

import json
import os
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from api.app import create_app


@pytest.fixture
async def client(tmp_path):
    """Create an async test client with proper lifespan initialization."""
    db_path = tmp_path / "test_deploy.db"
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
# 1. Status endpoint
# ---------------------------------------------------------------------------


class TestStatusEndpoint:
    """Verify /api/v1/status returns correct structure."""

    @pytest.mark.asyncio
    async def test_status_returns_200(self, client: AsyncClient):
        resp = await client.get("/api/v1/status")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_status_contains_version(self, client: AsyncClient):
        resp = await client.get("/api/v1/status")
        data = resp.json()
        assert "version" in data
        assert data["version"] == "0.10.0"

    @pytest.mark.asyncio
    async def test_status_contains_environment(self, client: AsyncClient):
        resp = await client.get("/api/v1/status")
        data = resp.json()
        assert "environment" in data


# ---------------------------------------------------------------------------
# 2. Health endpoint
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    """Verify /api/v1/health returns correct structure."""

    @pytest.mark.asyncio
    async def test_health_returns_200(self, client: AsyncClient):
        resp = await client.get("/api/v1/health")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_health_contains_status(self, client: AsyncClient):
        resp = await client.get("/api/v1/health")
        data = resp.json()
        assert "status" in data


# ---------------------------------------------------------------------------
# 3. Brain endpoints exist
# ---------------------------------------------------------------------------


class TestBrainEndpointsExist:
    """Verify brain endpoints are registered and respond (auth-gated is OK)."""

    @pytest.mark.asyncio
    async def test_registry_endpoint_exists(self, client: AsyncClient):
        resp = await client.get("/api/v1/agents/registry")
        # 200 (public) or 401/403 (auth-gated) — NOT 404
        assert resp.status_code != 404, "Brain registry endpoint not found"

    @pytest.mark.asyncio
    async def test_dispatch_endpoint_exists(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/agents/eng-core/dispatch",
            json={"task_description": "test"},
        )
        assert resp.status_code != 404, "Brain dispatch endpoint not found"

    @pytest.mark.asyncio
    async def test_callback_endpoint_exists(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/agents/callback",
            json={"task_id": "test", "status": "completed", "result": {}},
        )
        assert resp.status_code != 404, "Brain callback endpoint not found"

    @pytest.mark.asyncio
    async def test_workflow_create_endpoint_exists(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/workflows",
            json={"name": "test", "nodes": []},
        )
        assert resp.status_code != 404, "Workflow create endpoint not found"


# ---------------------------------------------------------------------------
# 4. WebSocket endpoint
# ---------------------------------------------------------------------------


class TestWebSocketEndpoint:
    """Verify WebSocket endpoint is registered."""

    def test_ws_pipeline_endpoint_registered(self):
        """Verify the WebSocket route is registered in the app."""
        from api.app import create_app

        app = create_app()
        ws_routes = [
            r.path for r in app.routes
            if hasattr(r, "path") and "ws/pipeline" in r.path
        ]
        assert len(ws_routes) > 0, "WebSocket pipeline endpoint not registered"


# ---------------------------------------------------------------------------
# 5. Docker Compose configuration
# ---------------------------------------------------------------------------


class TestDockerComposeConfig:
    """Validate docker-compose.yml has required configuration."""

    def test_compose_file_parseable(self):
        """docker-compose.yml should be valid YAML."""
        import yaml
        from pathlib import Path

        compose_path = Path(__file__).parent.parent / "docker-compose.yml"
        with open(compose_path) as f:
            data = yaml.safe_load(f)

        assert "services" in data
        assert "api" in data["services"]
        assert "dash" in data["services"]

    def test_api_service_has_healthcheck(self):
        """API service must have a healthcheck."""
        import yaml
        from pathlib import Path

        compose_path = Path(__file__).parent.parent / "docker-compose.yml"
        with open(compose_path) as f:
            data = yaml.safe_load(f)

        api = data["services"]["api"]
        assert "healthcheck" in api, "API service must have a healthcheck"

    def test_api_service_has_brain_env_vars(self):
        """API service must have brain/OpenClaw environment variables."""
        import yaml
        from pathlib import Path

        compose_path = Path(__file__).parent.parent / "docker-compose.yml"
        with open(compose_path) as f:
            data = yaml.safe_load(f)

        api_env = data["services"]["api"]["environment"]
        env_keys = [e.split("=")[0].lstrip("- ") for e in api_env]

        assert "OCCP_WEBHOOK_SECRET" in env_keys, "Missing OCCP_WEBHOOK_SECRET"
        assert "OCCP_OPENCLAW_BASE_URL" in env_keys, "Missing OCCP_OPENCLAW_BASE_URL"
        assert "OCCP_CONFIRMATION_GATE_TIMEOUT" in env_keys, "Missing OCCP_CONFIRMATION_GATE_TIMEOUT"

    def test_api_binds_to_localhost(self):
        """API port must bind to 127.0.0.1 only (Apache proxy handles external)."""
        import yaml
        from pathlib import Path

        compose_path = Path(__file__).parent.parent / "docker-compose.yml"
        with open(compose_path) as f:
            data = yaml.safe_load(f)

        api_ports = data["services"]["api"]["ports"]
        for port in api_ports:
            assert "127.0.0.1" in str(port), f"Port {port} must bind to 127.0.0.1"

    def test_dash_depends_on_api_healthy(self):
        """Dash must depend on API being healthy."""
        import yaml
        from pathlib import Path

        compose_path = Path(__file__).parent.parent / "docker-compose.yml"
        with open(compose_path) as f:
            data = yaml.safe_load(f)

        dash = data["services"]["dash"]
        assert "depends_on" in dash
        assert "api" in dash["depends_on"]
        assert dash["depends_on"]["api"]["condition"] == "service_healthy"

    def test_security_opts_present(self):
        """Containers must have security_opt with no-new-privileges."""
        import yaml
        from pathlib import Path

        compose_path = Path(__file__).parent.parent / "docker-compose.yml"
        with open(compose_path) as f:
            data = yaml.safe_load(f)

        for svc_name in ["api", "dash"]:
            svc = data["services"][svc_name]
            assert "security_opt" in svc, f"{svc_name} missing security_opt"
            assert "no-new-privileges:true" in svc["security_opt"]


# ---------------------------------------------------------------------------
# 6. Dockerfile checks
# ---------------------------------------------------------------------------


class TestDockerfileApi:
    """Validate Dockerfile.api has required configuration."""

    def test_dockerfile_exists(self):
        from pathlib import Path

        dockerfile = Path(__file__).parent.parent / "Dockerfile.api"
        assert dockerfile.exists(), "Dockerfile.api not found"

    def test_dockerfile_has_healthcheck(self):
        from pathlib import Path

        dockerfile = Path(__file__).parent.parent / "Dockerfile.api"
        content = dockerfile.read_text()
        assert "HEALTHCHECK" in content, "Dockerfile.api must have HEALTHCHECK"

    def test_dockerfile_runs_as_nonroot(self):
        from pathlib import Path

        dockerfile = Path(__file__).parent.parent / "Dockerfile.api"
        content = dockerfile.read_text()
        assert "USER occp" in content, "Dockerfile.api must run as non-root user"

    def test_dockerfile_exposes_8000(self):
        from pathlib import Path

        dockerfile = Path(__file__).parent.parent / "Dockerfile.api"
        content = dockerfile.read_text()
        assert "EXPOSE 8000" in content

    def test_dockerfile_copies_brain_deps(self):
        """Dockerfile must COPY all required modules including security."""
        from pathlib import Path

        dockerfile = Path(__file__).parent.parent / "Dockerfile.api"
        content = dockerfile.read_text()
        for module in ["orchestrator", "policy_engine", "api", "config", "store", "security"]:
            assert f"COPY {module}/" in content, f"Dockerfile.api missing COPY for {module}"


# ---------------------------------------------------------------------------
# 7. .env.example completeness
# ---------------------------------------------------------------------------


class TestEnvExample:
    """Verify .env.example has all required variables."""

    def test_env_example_exists(self):
        from pathlib import Path

        env_example = Path(__file__).parent.parent / ".env.example"
        assert env_example.exists()

    def test_env_example_has_brain_vars(self):
        from pathlib import Path

        env_example = Path(__file__).parent.parent / ".env.example"
        content = env_example.read_text()

        required_vars = [
            "OCCP_WEBHOOK_SECRET",
            "OCCP_OPENCLAW_BASE_URL",
            "OCCP_CONFIRMATION_GATE_TIMEOUT",
        ]
        for var in required_vars:
            assert var in content, f".env.example missing {var}"

    def test_env_example_has_core_vars(self):
        from pathlib import Path

        env_example = Path(__file__).parent.parent / ".env.example"
        content = env_example.read_text()

        core_vars = [
            "OCCP_JWT_SECRET",
            "OCCP_ADMIN_USER",
            "OCCP_ADMIN_PASSWORD",
            "OCCP_DATABASE_URL",
            "OCCP_ANTHROPIC_API_KEY",
        ]
        for var in core_vars:
            assert var in content, f".env.example missing {var}"


# ---------------------------------------------------------------------------
# 8. Deploy script validation
# ---------------------------------------------------------------------------


class TestDeployScript:
    """Validate deploy script structure."""

    def test_deploy_script_exists(self):
        from pathlib import Path

        script = Path(__file__).parent.parent / "scripts" / "deploy_v090.sh"
        assert script.exists()

    def test_deploy_script_has_rollback(self):
        from pathlib import Path

        script = Path(__file__).parent.parent / "scripts" / "deploy_v090.sh"
        content = script.read_text()
        assert "rollback" in content.lower()

    def test_deploy_script_has_backup(self):
        from pathlib import Path

        script = Path(__file__).parent.parent / "scripts" / "deploy_v090.sh"
        content = script.read_text()
        assert "backup" in content.lower()

    def test_deploy_script_has_health_checks(self):
        from pathlib import Path

        script = Path(__file__).parent.parent / "scripts" / "deploy_v090.sh"
        content = script.read_text()
        assert "health" in content.lower()

    def test_deploy_script_uses_no_cache(self):
        from pathlib import Path

        script = Path(__file__).parent.parent / "scripts" / "deploy_v090.sh"
        content = script.read_text()
        assert "--no-cache" in content

    def test_deploy_script_target_server(self):
        from pathlib import Path

        script = Path(__file__).parent.parent / "scripts" / "deploy_v090.sh"
        content = script.read_text()
        assert "195.201.238.144" in content

    def test_verify_script_exists(self):
        from pathlib import Path

        script = Path(__file__).parent.parent / "scripts" / "verify_deploy.sh"
        assert script.exists()
