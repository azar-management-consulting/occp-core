"""Centralised application settings loaded from environment / .env file.

Uses ``pydantic-settings`` so that every field can be overridden via an
environment variable with the ``OCCP_`` prefix (e.g. ``OCCP_JWT_SECRET``).
"""

from __future__ import annotations

import secrets
from functools import lru_cache
from typing import Any

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All OCCP runtime settings.  Defaults are safe for local development."""

    model_config = SettingsConfigDict(
        env_prefix="OCCP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Core ──────────────────────────────────────────────────────────
    occp_env: str = "development"
    debug: bool = False
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # ── Database ──────────────────────────────────────────────────────
    database_url: str = "sqlite+aiosqlite:///data/occp.db"

    # ── LLM providers ─────────────────────────────────────────────────
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"
    openai_api_key: str = ""

    # ── JWT auth ──────────────────────────────────────────────────────
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440  # 24 hours

    # ── Admin bootstrap credentials ───────────────────────────────────
    admin_user: str = "admin"
    admin_password: str = "changeme"

    # ── CORS ──────────────────────────────────────────────────────────
    cors_origins: list[str] = [
        "http://localhost:3000",
        "https://dash.occp.ai",
    ]

    # ── Sandbox executor ───────────────────────────────────────────────
    sandbox_backend: str = ""  # nsjail | bwrap | process | mock | "" (auto-detect)
    sandbox_time_limit: int = 30  # seconds
    sandbox_memory_limit: int = 256  # MB
    sandbox_enable_network: bool = False
    sandbox_nsjail_bin: str = "nsjail"
    sandbox_bwrap_bin: str = "bwrap"
    sandbox_nsjail_config: str = ""

    # ── Rate limiting ────────────────────────────────────────────────
    rate_limit_requests: int = 20  # per window
    rate_limit_window: int = 60  # seconds
    rate_limit_paths: str = "/api/v1/auth/"  # comma-separated prefixes

    # ── Logging ──────────────────────────────────────────────────────
    log_level: str = "INFO"
    log_format: str = "json"  # json | console

    # ── Channels (future) ─────────────────────────────────────────────
    slack_bot_token: str = ""
    slack_signing_secret: str = ""
    telegram_bot_token: str = ""

    # ── Validators ────────────────────────────────────────────────────

    @model_validator(mode="after")
    def _auto_generate_jwt_secret(self) -> "Settings":
        """Generate a random JWT secret if none was provided."""
        if not self.jwt_secret:
            object.__setattr__(self, "jwt_secret", secrets.token_urlsafe(48))
        return self

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, v: Any) -> list[str]:
        """Accept both comma-separated string and list."""
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v

    # ── Helpers ───────────────────────────────────────────────────────

    @property
    def is_production(self) -> bool:
        return self.occp_env == "production"

    @property
    def has_anthropic(self) -> bool:
        return bool(self.anthropic_api_key)

    @property
    def has_openai(self) -> bool:
        return bool(self.openai_api_key)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached singleton – call this everywhere instead of constructing."""
    return Settings()
