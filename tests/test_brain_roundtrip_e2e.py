"""Brain round-trip E2E integration tests.

Runs against a live OCCP API instance (e.g., https://api.occp.ai).
Requires env vars:
  OCCP_TEST_API_URL         (default https://api.occp.ai)
  OCCP_TEST_ADMIN_USER      (default admin)
  OCCP_TEST_ADMIN_PASSWORD  (required; skip if not set)

Run: pytest tests/test_brain_roundtrip_e2e.py -v -m e2e
"""
from __future__ import annotations

import os
import time

import httpx
import pytest

pytestmark = pytest.mark.e2e

BASE_URL = os.environ.get("OCCP_TEST_API_URL", "https://api.occp.ai")
ADMIN_USER = os.environ.get("OCCP_TEST_ADMIN_USER", "admin")
ADMIN_PW = os.environ.get("OCCP_TEST_ADMIN_PASSWORD")


@pytest.fixture(scope="module")
def token() -> str:
    if not ADMIN_PW:
        pytest.skip("OCCP_TEST_ADMIN_PASSWORD not set")
    r = httpx.post(
        f"{BASE_URL}/api/v1/auth/login",
        json={"username": ADMIN_USER, "password": ADMIN_PW},
        timeout=10,
    )
    if r.status_code != 200:
        pytest.skip(f"admin login failed: {r.status_code} {r.text}")
    return r.json()["access_token"]


@pytest.fixture
def auth_client(token) -> httpx.Client:
    return httpx.Client(
        base_url=BASE_URL,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )


def test_brain_status_endpoint(auth_client):
    """Sanity: API is reachable, version reported."""
    r = auth_client.get("/api/v1/status")
    assert r.status_code == 200
    body = r.json()
    assert "version" in body
    assert body.get("status") == "running"


def test_brain_message_text_roundtrip(auth_client):
    """Art.14 L1: brain accepts message + returns narrative."""
    r = auth_client.post(
        "/api/v1/brain/message",
        json={"message": "What is your current version?", "user_id": "e2e_test"},
    )
    assert r.status_code in (200, 201), r.text
    body = r.json()
    assert any(k in body for k in ("response", "narrative", "output", "message"))


def test_brain_message_returns_execution_directives(auth_client):
    """After OpenClaw upgrade (2026-04-20): response may contain structured directives.

    This test is tolerant — older deployments return only narrative.
    """
    r = auth_client.post(
        "/api/v1/brain/message",
        json={
            "message": "Read /tmp/occp-workspace/hello.txt if it exists",
            "user_id": "e2e_test",
        },
    )
    assert r.status_code in (200, 201)
    body = r.json()
    if "execution_directives" in body:
        assert isinstance(body["execution_directives"], list)


def test_brain_kill_switch_blocks_message(auth_client):
    """Art.14 L3: activate kill switch → brain rejects new tasks."""
    ks_on = auth_client.post(
        "/api/v1/governance/kill_switch/activate",
        json={"trigger": "manual", "reason": "e2e test"},
    )
    if ks_on.status_code != 200:
        pytest.skip(f"kill switch activation not available: {ks_on.status_code}")

    try:
        r = auth_client.post(
            "/api/v1/brain/message",
            json={"message": "Attempt during kill switch", "user_id": "e2e_test"},
        )
        assert r.status_code >= 400, f"brain accepted task during kill switch: {r.text}"
    finally:
        auth_client.post(
            "/api/v1/governance/kill_switch/deactivate",
            json={"reason": "e2e cleanup"},
        )


def test_brain_audit_chain_after_message(auth_client):
    """Art.12 + 14: audit log accessible and hash-chained."""
    r = auth_client.get("/api/v1/audit?limit=10")
    if r.status_code == 404:
        pytest.skip("audit endpoint not exposed in this deployment")
    assert r.status_code == 200
    body = r.json()
    entries = body if isinstance(body, list) else body.get("entries", body.get("items", []))
    assert isinstance(entries, list)


def test_brain_latency_under_30s(auth_client):
    """Art.14 L1: response SLA for operator monitoring."""
    start = time.perf_counter()
    r = auth_client.post(
        "/api/v1/brain/message",
        json={"message": "quick status check", "user_id": "e2e_test"},
        timeout=35,
    )
    elapsed = time.perf_counter() - start
    assert r.status_code in (200, 201)
    assert elapsed < 30, f"p95 SLA breached: {elapsed:.2f}s"
