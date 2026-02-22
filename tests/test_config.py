"""Tests for config.settings – centralised Settings loader."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from config.settings import Settings


class TestSettingsDefaults:
    """Verify sane defaults when no env vars are set."""

    def test_default_env(self) -> None:
        s = Settings(_env_file=None)
        assert s.occp_env == "development"

    def test_default_database_url(self) -> None:
        s = Settings(_env_file=None)
        assert "sqlite" in s.database_url

    def test_default_cors(self) -> None:
        s = Settings(_env_file=None)
        assert "http://localhost:3000" in s.cors_origins

    def test_default_jwt_algorithm(self) -> None:
        s = Settings(_env_file=None)
        assert s.jwt_algorithm == "HS256"

    def test_jwt_secret_auto_generated(self) -> None:
        s = Settings(_env_file=None)
        assert len(s.jwt_secret) > 20

    def test_admin_defaults(self) -> None:
        s = Settings(_env_file=None)
        assert s.admin_user == "admin"
        assert s.admin_password == "changeme"


class TestSettingsOverride:
    """Env vars override defaults (OCCP_ prefix)."""

    def test_env_override(self) -> None:
        with patch.dict(os.environ, {"OCCP_OCCP_ENV": "production"}):
            s = Settings(_env_file=None)
            assert s.occp_env == "production"

    def test_cors_json_list(self) -> None:
        with patch.dict(os.environ, {"OCCP_CORS_ORIGINS": '["http://a.com","http://b.com"]'}):
            s = Settings(_env_file=None)
            assert s.cors_origins == ["http://a.com", "http://b.com"]

    def test_jwt_secret_from_env(self) -> None:
        with patch.dict(os.environ, {"OCCP_JWT_SECRET": "my-secret-key-123"}):
            s = Settings(_env_file=None)
            assert s.jwt_secret == "my-secret-key-123"


class TestSettingsHelpers:
    """Property helpers."""

    def test_is_production_false(self) -> None:
        s = Settings(_env_file=None)
        assert s.is_production is False

    def test_is_production_true(self) -> None:
        with patch.dict(os.environ, {"OCCP_OCCP_ENV": "production"}):
            s = Settings(_env_file=None)
            assert s.is_production is True

    def test_has_anthropic_false(self) -> None:
        s = Settings(_env_file=None)
        assert s.has_anthropic is False

    def test_has_anthropic_true(self) -> None:
        with patch.dict(os.environ, {"OCCP_ANTHROPIC_API_KEY": "sk-ant-test"}):
            s = Settings(_env_file=None)
            assert s.has_anthropic is True

    def test_has_openai_false(self) -> None:
        s = Settings(_env_file=None)
        assert s.has_openai is False
