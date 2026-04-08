"""Unified cross-channel authentication for OCCP Brain.

Maps channel-specific identities (Telegram chat_id, API JWT, CloudCode HMAC)
to a canonical ChannelIdentity used throughout the pipeline.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ChannelType(str, Enum):
    API = "api"
    TELEGRAM = "telegram"
    CLOUDCODE = "cloudcode"
    SLACK = "slack"
    WEBHOOK = "webhook"


@dataclass
class ChannelIdentity:
    user_id: str
    channel: ChannelType
    channel_user_id: str
    role: str = "viewer"
    display_name: str = ""
    verified: bool = False
    metadata: dict = field(default_factory=dict)


class ChannelAuthenticator:
    def __init__(self, jwt_secret: str = "", webhook_secret: str = "",
                 allowed_telegram_ids: set[int] | None = None,
                 owner_telegram_id: int = 0):
        self._jwt_secret = jwt_secret
        self._webhook_secret = webhook_secret
        self._allowed_telegram_ids = allowed_telegram_ids or set()
        self._owner_telegram_id = owner_telegram_id
        self._identity_map: dict[str, ChannelIdentity] = {}
        if owner_telegram_id:
            self._register("henry", ChannelType.TELEGRAM, str(owner_telegram_id),
                          "system_admin", "Henry", True)

    def authenticate_telegram(self, chat_id: int) -> Optional[ChannelIdentity]:
        key = f"telegram:{chat_id}"
        if key in self._identity_map:
            return self._identity_map[key]
        if self._allowed_telegram_ids and chat_id not in self._allowed_telegram_ids:
            logger.warning("Telegram rejected: chat_id=%d", chat_id)
            return None
        return self._register(f"tg_{chat_id}", ChannelType.TELEGRAM, str(chat_id), "viewer", "", True)

    def authenticate_api(self, jwt_payload: dict) -> Optional[ChannelIdentity]:
        username = jwt_payload.get("sub", "")
        if not username:
            return None
        key = f"api:{username}"
        if key in self._identity_map:
            return self._identity_map[key]
        return self._register(username, ChannelType.API, username,
                             jwt_payload.get("role", "viewer"),
                             jwt_payload.get("display_name", username), True)

    def authenticate_cloudcode(self, signature: str = "", payload: str = "",
                               timestamp: int = 0) -> Optional[ChannelIdentity]:
        if not self._webhook_secret:
            return ChannelIdentity(user_id="cloudcode_user", channel=ChannelType.CLOUDCODE,
                                  channel_user_id="hook", role="operator",
                                  display_name="Claude Code", verified=False)
        expected = hmac.new(self._webhook_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, f"sha256={expected}"):
            logger.warning("CloudCode HMAC failed")
            return None
        if timestamp and abs(time.time() - timestamp) > 300:
            logger.warning("CloudCode stale timestamp")
            return None
        return ChannelIdentity(user_id="cloudcode_user", channel=ChannelType.CLOUDCODE,
                              channel_user_id="hook", role="operator",
                              display_name="Claude Code", verified=True)

    def get_identity(self, channel: ChannelType, channel_user_id: str) -> Optional[ChannelIdentity]:
        return self._identity_map.get(f"{channel.value}:{channel_user_id}")

    def list_identities(self) -> list[ChannelIdentity]:
        return list(self._identity_map.values())

    def _register(self, user_id: str, channel: ChannelType, channel_user_id: str,
                  role: str, display_name: str, verified: bool) -> ChannelIdentity:
        identity = ChannelIdentity(user_id=user_id, channel=channel,
                                   channel_user_id=channel_user_id, role=role,
                                   display_name=display_name, verified=verified)
        self._identity_map[f"{channel.value}:{channel_user_id}"] = identity
        return identity
