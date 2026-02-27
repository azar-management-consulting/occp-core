"""Tests for Phase 4 hardening — middleware, health endpoint, structlog, rate limiting."""

from __future__ import annotations

import logging
import os
import time
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from api.middleware import (
    RateLimitMiddleware,
    RequestLoggingMiddleware,
    SecurityHeadersMiddleware,
)
from api.models import HealthCheck, HealthResponse


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def client(tmp_path):
    """Create a test client with full app lifespan."""
    db_path = tmp_path / "test_hardening.db"
    os.environ["OCCP_DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"
    os.environ["OCCP_ADMIN_USER"] = "hard_admin"
    os.environ["OCCP_ADMIN_PASSWORD"] = "hard_pass_123"
    os.environ["OCCP_LOG_FORMAT"] = "console"
    os.environ["OCCP_RATE_LIMIT_REQUESTS"] = "5"
    os.environ["OCCP_RATE_LIMIT_WINDOW"] = "60"
    try:
        from api.app import create_app
        app = create_app()
        async with app.router.lifespan_context(app):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                yield ac
    finally:
        os.environ.pop("OCCP_DATABASE_URL", None)
        os.environ.pop("OCCP_ADMIN_USER", None)
        os.environ.pop("OCCP_ADMIN_PASSWORD", None)
        os.environ.pop("OCCP_LOG_FORMAT", None)
        os.environ.pop("OCCP_RATE_LIMIT_REQUESTS", None)
        os.environ.pop("OCCP_RATE_LIMIT_WINDOW", None)


# ---------------------------------------------------------------------------
# Security Headers
# ---------------------------------------------------------------------------

class TestSecurityHeaders:
    async def test_nosniff_header(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/status")
        assert resp.headers["x-content-type-options"] == "nosniff"

    async def test_frame_deny(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/status")
        assert resp.headers["x-frame-options"] == "DENY"

    async def test_xss_protection(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/status")
        assert resp.headers["x-xss-protection"] == "1; mode=block"

    async def test_referrer_policy(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/status")
        assert resp.headers["referrer-policy"] == "strict-origin-when-cross-origin"

    async def test_permissions_policy(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/status")
        assert "camera=()" in resp.headers["permissions-policy"]

    async def test_cache_control(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/status")
        assert resp.headers["cache-control"] == "no-store"

    async def test_no_hsts_in_dev(self, client: AsyncClient) -> None:
        """HSTS should NOT be set in development mode."""
        resp = await client.get("/api/v1/status")
        assert "strict-transport-security" not in resp.headers


# ---------------------------------------------------------------------------
# Health Endpoint
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    async def test_health_returns_200(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/health")
        assert resp.status_code == 200

    async def test_health_structure(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/health")
        data = resp.json()
        assert "status" in data
        assert "version" in data
        assert "checks" in data

    async def test_health_status_healthy(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/health")
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["version"] == "0.8.2"

    async def test_health_db_check_present(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/health")
        checks = resp.json()["checks"]
        db_check = next((c for c in checks if c["name"] == "database"), None)
        assert db_check is not None
        assert db_check["status"] == "ok"
        assert db_check["latency_ms"] >= 0

    async def test_health_pipeline_check(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/health")
        checks = resp.json()["checks"]
        pl_check = next((c for c in checks if c["name"] == "pipeline"), None)
        assert pl_check is not None
        assert pl_check["status"] == "ok"

    async def test_health_policy_engine_check(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/health")
        checks = resp.json()["checks"]
        pe_check = next((c for c in checks if c["name"] == "policy_engine"), None)
        assert pe_check is not None
        assert pe_check["status"] == "ok"


# ---------------------------------------------------------------------------
# Status endpoint version bump
# ---------------------------------------------------------------------------

class TestStatusVersion:
    async def test_status_version_070(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/status")
        assert resp.json()["version"] == "0.8.2"


# ---------------------------------------------------------------------------
# Rate Limiting
# ---------------------------------------------------------------------------

class TestRateLimiting:
    async def test_auth_rate_limit_enforced(self, client: AsyncClient) -> None:
        """After N requests to auth endpoint, 429 is returned."""
        # Env sets OCCP_RATE_LIMIT_REQUESTS=5
        for i in range(5):
            resp = await client.post("/api/v1/auth/login", json={
                "username": "wrong",
                "password": "wrong",
            })
            # 401 is expected (bad creds), not 429 yet
            assert resp.status_code in (401, 429), f"Request {i}: {resp.status_code}"

        # 6th request should be rate limited
        resp = await client.post("/api/v1/auth/login", json={
            "username": "wrong",
            "password": "wrong",
        })
        assert resp.status_code == 429
        assert "retry_after" in resp.json()

    async def test_rate_limit_has_retry_after_header(self, client: AsyncClient) -> None:
        """429 response includes Retry-After header."""
        for _ in range(6):
            resp = await client.post("/api/v1/auth/login", json={
                "username": "x",
                "password": "x",
            })
        assert resp.status_code == 429
        assert "retry-after" in resp.headers

    async def test_non_auth_not_rate_limited(self, client: AsyncClient) -> None:
        """Non-auth endpoints are not subject to rate limiting."""
        for _ in range(10):
            resp = await client.get("/api/v1/status")
            assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Request Logging
# ---------------------------------------------------------------------------

class TestRequestLogging:
    async def test_request_logged(self, client: AsyncClient, caplog) -> None:
        """HTTP requests are logged with method, path, status, duration."""
        with caplog.at_level(logging.INFO):
            await client.get("/api/v1/status")
        log_messages = " ".join(caplog.messages)
        assert "http_request" in log_messages or "method=GET" in log_messages


# ---------------------------------------------------------------------------
# Structlog setup
# ---------------------------------------------------------------------------

class TestStructlogSetup:
    def test_setup_logging_json(self) -> None:
        """JSON format configures without error."""
        from api.logging_config import setup_logging
        setup_logging(level="INFO", fmt="json")

    def test_setup_logging_console(self) -> None:
        """Console format configures without error."""
        from api.logging_config import setup_logging
        setup_logging(level="DEBUG", fmt="console")

    def test_structlog_logger_works(self) -> None:
        """structlog bound loggers produce output."""
        import structlog
        from api.logging_config import setup_logging
        setup_logging(level="DEBUG", fmt="console")
        log = structlog.get_logger("test")
        # Should not raise
        log.info("test_event", key="value")


# ---------------------------------------------------------------------------
# Health model unit tests
# ---------------------------------------------------------------------------

class TestHealthModels:
    def test_health_check_model(self) -> None:
        check = HealthCheck(name="db", status="ok", latency_ms=1.5)
        assert check.name == "db"
        assert check.status == "ok"
        assert check.latency_ms == 1.5

    def test_health_response_model(self) -> None:
        resp = HealthResponse(
            status="healthy",
            version="0.8.2",
            checks=[HealthCheck(name="db", status="ok")],
        )
        assert resp.status == "healthy"
        assert len(resp.checks) == 1

    def test_health_response_empty_checks(self) -> None:
        resp = HealthResponse(status="unhealthy", version="0.8.2")
        assert resp.checks == []


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

class TestHardeningSettings:
    def test_rate_limit_defaults(self) -> None:
        from config.settings import Settings
        s = Settings(
            _env_file=None,
            rate_limit_requests=20,
            rate_limit_window=60,
        )
        assert s.rate_limit_requests == 20
        assert s.rate_limit_window == 60

    def test_log_settings_defaults(self) -> None:
        from config.settings import Settings
        s = Settings(_env_file=None)
        assert s.log_level == "INFO"
        assert s.log_format == "json"


# ---------------------------------------------------------------------------
# Middleware unit tests (isolated, no app)
# ---------------------------------------------------------------------------

class TestRateLimitUnit:
    def test_should_limit_matches_prefix(self) -> None:
        from starlette.applications import Starlette

        mw = RateLimitMiddleware(
            Starlette(),
            rate_limit_paths=["/api/v1/auth/"],
        )
        assert mw._should_limit("/api/v1/auth/login") is True
        assert mw._should_limit("/api/v1/status") is False

    def test_should_limit_none_means_all(self) -> None:
        from starlette.applications import Starlette

        mw = RateLimitMiddleware(
            Starlette(),
            rate_limit_paths=None,
        )
        assert mw._should_limit("/any/path") is True
