"""Tests for JWT authentication – token lifecycle and endpoint protection."""

from __future__ import annotations

import time

import jwt
import pytest

from config.settings import Settings
from api.auth import create_access_token, decode_token


@pytest.fixture
def settings() -> Settings:
    return Settings(
        jwt_secret="test-secret-key-for-unit-tests!!",
        jwt_algorithm="HS256",
        jwt_expire_minutes=60,
        admin_user="admin",
        admin_password="pass",
    )


class TestTokenCreation:
    def test_creates_valid_jwt(self, settings: Settings) -> None:
        token = create_access_token("alice", settings)
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        assert payload["sub"] == "alice"
        assert "exp" in payload
        assert "iat" in payload

    def test_extra_claims(self, settings: Settings) -> None:
        token = create_access_token("bob", settings, extra={"role": "admin"})
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        assert payload["sub"] == "bob"
        assert payload["role"] == "admin"

    def test_expiry_matches_settings(self, settings: Settings) -> None:
        token = create_access_token("carol", settings)
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        ttl = payload["exp"] - payload["iat"]
        assert ttl == settings.jwt_expire_minutes * 60


class TestTokenDecoding:
    def test_decode_valid(self, settings: Settings) -> None:
        token = create_access_token("dave", settings)
        payload = decode_token(token, settings)
        assert payload["sub"] == "dave"

    def test_decode_expired(self, settings: Settings) -> None:
        expired_settings = Settings(
            jwt_secret=settings.jwt_secret,
            jwt_expire_minutes=0,  # immediate expiry
        )
        # Create token that's already expired
        token = jwt.encode(
            {"sub": "eve", "exp": int(time.time()) - 10, "iat": int(time.time()) - 70},
            settings.jwt_secret,
            algorithm="HS256",
        )
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            decode_token(token, settings)
        assert exc_info.value.status_code == 401
        assert "expired" in exc_info.value.detail.lower()

    def test_decode_invalid_signature(self, settings: Settings) -> None:
        token = jwt.encode({"sub": "frank"}, "wrong-secret-key-that-is-at-least-32-bytes-long!", algorithm="HS256")
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            decode_token(token, settings)
        assert exc_info.value.status_code == 401

    def test_decode_garbage(self, settings: Settings) -> None:
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            decode_token("not.a.jwt", settings)
        assert exc_info.value.status_code == 401
