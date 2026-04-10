"""Tests for unified cross-channel authentication module."""

from __future__ import annotations

import hashlib
import hmac as hmac_mod
import time

import pytest

from security.channel_auth import ChannelAuthenticator, ChannelIdentity, ChannelType


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

OWNER_TG_ID = 123456789
WEBHOOK_SECRET = "test-webhook-secret-key"


@pytest.fixture
def auth_basic() -> ChannelAuthenticator:
    """Authenticator with no restrictions."""
    return ChannelAuthenticator()


@pytest.fixture
def auth_owner() -> ChannelAuthenticator:
    """Authenticator with owner telegram id."""
    return ChannelAuthenticator(owner_telegram_id=OWNER_TG_ID)


@pytest.fixture
def auth_allowlist() -> ChannelAuthenticator:
    """Authenticator with telegram allowlist."""
    return ChannelAuthenticator(
        allowed_telegram_ids={OWNER_TG_ID, 999},
        owner_telegram_id=OWNER_TG_ID,
    )


@pytest.fixture
def auth_hmac() -> ChannelAuthenticator:
    """Authenticator with webhook secret for HMAC verification."""
    return ChannelAuthenticator(webhook_secret=WEBHOOK_SECRET)


def _make_signature(secret: str, payload: str) -> str:
    digest = hmac_mod.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"sha256={digest}"


# ---------------------------------------------------------------------------
# Telegram tests
# ---------------------------------------------------------------------------

class TestTelegramAuth:
    def test_owner_gets_system_admin(self, auth_owner: ChannelAuthenticator):
        identity = auth_owner.authenticate_telegram(OWNER_TG_ID)
        assert identity is not None
        assert identity.role == "system_admin"
        assert identity.user_id == "henry"
        assert identity.display_name == "Henry"
        assert identity.verified is True
        assert identity.channel == ChannelType.TELEGRAM

    def test_owner_channel_user_id(self, auth_owner: ChannelAuthenticator):
        identity = auth_owner.authenticate_telegram(OWNER_TG_ID)
        assert identity is not None
        assert identity.channel_user_id == str(OWNER_TG_ID)

    def test_unknown_with_allowlist_rejected(self, auth_allowlist: ChannelAuthenticator):
        result = auth_allowlist.authenticate_telegram(777)
        assert result is None

    def test_allowed_non_owner_gets_viewer(self, auth_allowlist: ChannelAuthenticator):
        identity = auth_allowlist.authenticate_telegram(999)
        assert identity is not None
        assert identity.role == "viewer"
        assert identity.verified is True

    def test_unknown_no_allowlist_gets_viewer(self, auth_basic: ChannelAuthenticator):
        identity = auth_basic.authenticate_telegram(55555)
        assert identity is not None
        assert identity.role == "viewer"
        assert identity.user_id == "tg_55555"

    def test_repeat_auth_returns_cached(self, auth_basic: ChannelAuthenticator):
        first = auth_basic.authenticate_telegram(100)
        second = auth_basic.authenticate_telegram(100)
        assert first is second


# ---------------------------------------------------------------------------
# API / JWT tests
# ---------------------------------------------------------------------------

class TestApiAuth:
    def test_valid_jwt_payload(self, auth_basic: ChannelAuthenticator):
        payload = {"sub": "alice", "role": "admin", "display_name": "Alice"}
        identity = auth_basic.authenticate_api(payload)
        assert identity is not None
        assert identity.user_id == "alice"
        assert identity.role == "admin"
        assert identity.display_name == "Alice"
        assert identity.channel == ChannelType.API
        assert identity.verified is True

    def test_empty_sub_returns_none(self, auth_basic: ChannelAuthenticator):
        assert auth_basic.authenticate_api({"sub": ""}) is None

    def test_missing_sub_returns_none(self, auth_basic: ChannelAuthenticator):
        assert auth_basic.authenticate_api({"role": "admin"}) is None

    def test_default_role_is_viewer(self, auth_basic: ChannelAuthenticator):
        identity = auth_basic.authenticate_api({"sub": "bob"})
        assert identity is not None
        assert identity.role == "viewer"

    def test_display_name_defaults_to_username(self, auth_basic: ChannelAuthenticator):
        identity = auth_basic.authenticate_api({"sub": "charlie"})
        assert identity is not None
        assert identity.display_name == "charlie"

    def test_repeat_api_auth_cached(self, auth_basic: ChannelAuthenticator):
        payload = {"sub": "dave"}
        first = auth_basic.authenticate_api(payload)
        second = auth_basic.authenticate_api(payload)
        assert first is second


# ---------------------------------------------------------------------------
# CloudCode HMAC tests
# ---------------------------------------------------------------------------

class TestCloudCodeAuth:
    def test_no_secret_returns_unverified(self, auth_basic: ChannelAuthenticator):
        identity = auth_basic.authenticate_cloudcode()
        assert identity is not None
        assert identity.verified is False
        assert identity.role == "operator"
        assert identity.channel == ChannelType.CLOUDCODE

    def test_valid_hmac_returns_verified(self, auth_hmac: ChannelAuthenticator):
        payload = '{"action":"deploy"}'
        sig = _make_signature(WEBHOOK_SECRET, payload)
        ts = int(time.time())
        identity = auth_hmac.authenticate_cloudcode(signature=sig, payload=payload, timestamp=ts)
        assert identity is not None
        assert identity.verified is True
        assert identity.display_name == "Claude Code"

    def test_invalid_hmac_returns_none(self, auth_hmac: ChannelAuthenticator):
        result = auth_hmac.authenticate_cloudcode(signature="sha256=bad", payload="data", timestamp=int(time.time()))
        assert result is None

    def test_stale_timestamp_returns_none(self, auth_hmac: ChannelAuthenticator):
        payload = '{"old":true}'
        sig = _make_signature(WEBHOOK_SECRET, payload)
        stale = int(time.time()) - 600
        result = auth_hmac.authenticate_cloudcode(signature=sig, payload=payload, timestamp=stale)
        assert result is None

    def test_zero_timestamp_skips_check(self, auth_hmac: ChannelAuthenticator):
        payload = '{"no_ts":1}'
        sig = _make_signature(WEBHOOK_SECRET, payload)
        identity = auth_hmac.authenticate_cloudcode(signature=sig, payload=payload, timestamp=0)
        assert identity is not None
        assert identity.verified is True


# ---------------------------------------------------------------------------
# Identity management tests
# ---------------------------------------------------------------------------

class TestIdentityManagement:
    def test_get_identity_found(self, auth_owner: ChannelAuthenticator):
        result = auth_owner.get_identity(ChannelType.TELEGRAM, str(OWNER_TG_ID))
        assert result is not None
        assert result.user_id == "henry"

    def test_get_identity_not_found(self, auth_basic: ChannelAuthenticator):
        assert auth_basic.get_identity(ChannelType.API, "ghost") is None

    def test_list_identities_empty(self, auth_basic: ChannelAuthenticator):
        assert auth_basic.list_identities() == []

    def test_list_identities_multiple(self, auth_basic: ChannelAuthenticator):
        auth_basic.authenticate_telegram(1)
        auth_basic.authenticate_api({"sub": "x"})
        identities = auth_basic.list_identities()
        assert len(identities) == 2

    def test_multiple_channels_separate_identities(self, auth_basic: ChannelAuthenticator):
        tg = auth_basic.authenticate_telegram(42)
        api = auth_basic.authenticate_api({"sub": "tg_42"})
        assert tg is not None and api is not None
        assert tg.channel == ChannelType.TELEGRAM
        assert api.channel == ChannelType.API
        assert tg is not api

    def test_owner_preregistered_in_list(self, auth_owner: ChannelAuthenticator):
        identities = auth_owner.list_identities()
        assert len(identities) == 1
        assert identities[0].role == "system_admin"


# ---------------------------------------------------------------------------
# ChannelType enum tests
# ---------------------------------------------------------------------------

class TestChannelType:
    def test_string_values(self):
        assert ChannelType.API.value == "api"
        assert ChannelType.TELEGRAM.value == "telegram"
        assert ChannelType.CLOUDCODE.value == "cloudcode"
        assert ChannelType.SLACK.value == "slack"
        assert ChannelType.WEBHOOK.value == "webhook"
