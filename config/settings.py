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
    database_url: str = "sqlite+aiosqlite:///data/occp.db"  # PG trigger: migrate when concurrent_users > 5 or tasks > 10K

    # ── LLM providers ─────────────────────────────────────────────────
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"
    openai_api_key: str = ""

    # ── Encryption (AES-256-GCM for token storage) ─────────────────
    encryption_key: str = ""  # base64-encoded 32-byte key; auto-generates if empty

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

    # ── Audit retention (EU AI Act Art. 19 — minimum 180 days) ──────
    audit_retention_days: int = 180  # 0 = disable pruning (keep forever)

    # ── Logging ──────────────────────────────────────────────────────
    log_level: str = "INFO"
    log_format: str = "json"  # json | console

    # ── Brain Webhook Gateway ──────────────────────────────────────────
    webhook_secret: str = ""  # HMAC-SHA256 shared secret for agent webhooks
    openclaw_base_url: str = "http://localhost:8080"  # OpenClaw HTTP API URL
    openclaw_auth_user: str = ""  # Basic Auth username for OpenClaw gateway
    openclaw_auth_pass: str = ""  # Basic Auth password for OpenClaw gateway
    openclaw_callback_url: str = ""  # Callback URL for OpenClaw results
    openclaw_timeout: float = 30.0  # HTTP timeout for OpenClaw requests (seconds)
    # ── OpenClaw WebSocket Bridge ─────────────────────────────────────
    openclaw_gateway_url: str = ""  # WebSocket URL (ws:// or wss://)
    openclaw_gateway_token: str = ""
    openclaw_hmac_secret: str = ""
    openclaw_connect_timeout: float = 30.0
    openclaw_execute_timeout: float = 120.0
    # ── Voice Pipeline ────────────────────────────────────────────────
    voice_enabled: bool = False
    voice_telegram_bot_token: str = ""
    voice_telegram_owner_chat_id: int = 0  # Strict auth: only owner can send cmds
    voice_default_language: str = "hu"
    voice_allowed_chat_ids: str = ""  # comma-separated, empty = allow all
    voice_rate_limit: int = 5  # max commands per minute per chat

    # ── Brain Orchestration ──────────────────────────────────────────
    max_concurrent_agents: int = 12      # Max parallel agents in a workflow wave
    max_concurrent_pipelines: int = 10   # Max parallel pipeline executions
    brain_session_timeout: int = 3600    # Brain session idle timeout (seconds)

    # ── Parallel Dispatch ─────────────────────────────────────────────
    parallel_dispatch_max_concurrent: int = 12  # Max concurrent agent dispatches
    parallel_dispatch_default_timeout: int = 120  # Per-task timeout in seconds

    # ── Channels (future) ─────────────────────────────────────────────
    slack_bot_token: str = ""
    slack_signing_secret: str = ""
    telegram_bot_token: str = ""

    # ── Validators ────────────────────────────────────────────────────

    @model_validator(mode="after")
    def _reject_default_password_in_prod(self) -> "Settings":
        """Refuse to start with 'changeme' password in production."""
        if self.is_production and self.admin_password == "changeme":
            raise ValueError(
                "FATAL: OCCP_ADMIN_PASSWORD is 'changeme' in production. "
                "Set a strong password via OCCP_ADMIN_PASSWORD environment variable."
            )
        return self

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

    @property
    def has_openclaw(self) -> bool:
        return bool(self.openclaw_gateway_url)

    @property
    def has_voice(self) -> bool:
        return self.voice_enabled and bool(self.voice_telegram_bot_token)

    @property
    def voice_allowed_ids(self) -> list[int] | None:
        if not self.voice_allowed_chat_ids:
            return None
        return [int(x.strip()) for x in self.voice_allowed_chat_ids.split(",") if x.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached singleton – call this everywhere instead of constructing."""
    return Settings()
