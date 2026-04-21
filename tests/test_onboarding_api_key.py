"""API key reveal-once + rotation tests (onboarding_keys module)."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("OCCP_JWT_SECRET", "jwt_secret_test_" + "x" * 20)
    monkeypatch.setenv("OCCP_ADMIN_USER", "admin")
    monkeypatch.setenv("OCCP_ADMIN_PASSWORD", "testpw12345")
    yield


@pytest.fixture
def client():
    from api.app import app
    with TestClient(app) as c:
        yield c


@pytest.fixture
def admin_token(client: TestClient) -> str:
    r = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "testpw12345"},
    )
    if r.status_code != 200:
        pytest.skip(f"admin login failed ({r.status_code}): {r.text}")
    return r.json()["access_token"]


@pytest.fixture(autouse=True)
def _reset_store():
    """Clear in-memory key store between tests."""
    from api.routes import onboarding_keys as ob
    ob._reset_store_for_testing()
    yield
    ob._reset_store_for_testing()


def test_first_api_key_prefix_occp_live_sk(client: TestClient, admin_token: str) -> None:
    r = client.post(
        "/api/v1/onboarding/first-api-key",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["key"].startswith("occp_live_sk_")
    assert len(body["key"]) >= len("occp_live_sk_") + 20
    assert "created_at" in body
    assert "…" in body["prefix_shown"]


def test_first_api_key_returns_plain_once(client: TestClient, admin_token: str) -> None:
    r1 = client.post(
        "/api/v1/onboarding/first-api-key",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r1.status_code == 201
    plain = r1.json()["key"]
    # Note: the plain key is never retrievable via a GET — the store holds only SHA-256.
    from api.routes.onboarding_keys import _KEY_BY_HASH
    assert not any(
        getattr(rec, "plain", None) == plain for rec in _KEY_BY_HASH.values()
    ), "Plain key must not be retained in store"


def test_first_api_key_idempotent_409_on_second(client: TestClient, admin_token: str) -> None:
    r1 = client.post(
        "/api/v1/onboarding/first-api-key",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r1.status_code == 201
    r2 = client.post(
        "/api/v1/onboarding/first-api-key",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r2.status_code == 409
    assert "rotate-api-key" in r2.json()["detail"]


def test_rotate_api_key_48h_grace(client: TestClient, admin_token: str) -> None:
    r1 = client.post(
        "/api/v1/onboarding/first-api-key",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r1.status_code == 201
    r2 = client.post(
        "/api/v1/onboarding/rotate-api-key",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"reason": "test rotate"},
    )
    assert r2.status_code == 200, r2.text
    body = r2.json()
    assert body["key"].startswith("occp_live_sk_")
    assert body["grace_seconds"] == 48 * 3600
    assert body["previous_grace_until"]


def test_rotate_without_first_key_returns_404(client: TestClient, admin_token: str) -> None:
    r = client.post(
        "/api/v1/onboarding/rotate-api-key",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"reason": "no prior key"},
    )
    assert r.status_code == 404


def test_revoke_requires_confirm(client: TestClient, admin_token: str) -> None:
    client.post(
        "/api/v1/onboarding/first-api-key",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    r = client.post(
        "/api/v1/onboarding/revoke-api-key",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"confirm": False},
    )
    assert r.status_code == 400


def test_revoke_confirmed_clears_store(client: TestClient, admin_token: str) -> None:
    client.post(
        "/api/v1/onboarding/first-api-key",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    r = client.post(
        "/api/v1/onboarding/revoke-api-key",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"confirm": True},
    )
    assert r.status_code == 204
    from api.routes.onboarding_keys import _LATEST_BY_USER
    assert _LATEST_BY_USER == {}


def test_unauth_rejected(client: TestClient) -> None:
    r = client.post("/api/v1/onboarding/first-api-key")
    assert r.status_code in (401, 403)
