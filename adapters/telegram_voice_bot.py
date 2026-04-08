"""Telegram Voice Bot — long-polling Telegram client with Brian: prefix filter.

Protocol requirement P1:
- Text messages: only process if starts with "Brian:" (case insensitive)
- Voice messages: always process (voice implies intent)
- /start and /help commands: always process
- Text without "Brian:" prefix: silently ignore

Runtime:
- httpx long-polling via getUpdates(timeout=30)
- Background asyncio task started by ``start()``, cancelled by ``stop()``
- Voice files downloaded via getFile + download URL
- Real send_message via sendMessage API
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Protocol

import httpx

logger = logging.getLogger(__name__)

_API_BASE = "https://api.telegram.org"
_POLL_TIMEOUT = 30  # long-poll seconds
_DOWNLOAD_TIMEOUT = 30.0
_SEND_TIMEOUT = 15.0

# Prefix that activates text message processing
_BRIAN_PREFIX = "brian:"

# Commands that bypass the prefix filter
_ALWAYS_COMMANDS = frozenset({"/start", "/help"})


class MessageHandler(Protocol):
    """Protocol for handling processed messages."""

    async def handle_text(self, chat_id: int, text: str) -> None: ...
    async def handle_voice(self, chat_id: int, audio_bytes: bytes, file_name: str) -> None: ...


class TelegramVoiceBot:
    """Telegram bot adapter with Brian: prefix filtering.

    Only processes text messages that start with "Brian:" (case insensitive).
    Voice messages and /start, /help commands are always processed.
    """

    def __init__(
        self,
        token: str = "",
        handler: MessageHandler | None = None,
        owner_chat_id: int = 0,
    ) -> None:
        self._token = token
        self._handler = handler
        self._owner_chat_id = owner_chat_id
        self._is_running = False
        self._poll_task: asyncio.Task[None] | None = None
        self._offset = 0
        self._client: httpx.AsyncClient | None = None
        self._updates_processed = 0
        self._updates_ignored = 0

    @property
    def is_running(self) -> bool:
        return self._is_running

    @property
    def stats(self) -> dict[str, Any]:
        return {
            "running": self._is_running,
            "owner_chat_id": self._owner_chat_id,
            "updates_processed": self._updates_processed,
            "updates_ignored": self._updates_ignored,
            "offset": self._offset,
        }

    def set_handler(self, handler: MessageHandler) -> None:
        self._handler = handler

    # ── Telegram HTTPS API ────────────────────────────────────────────

    def _api_url(self, method: str) -> str:
        return f"{_API_BASE}/bot{self._token}/{method}"

    def _file_url(self, file_path: str) -> str:
        return f"{_API_BASE}/file/bot{self._token}/{file_path}"

    async def send_message(self, chat_id: int, text: str) -> None:
        """Send a message to a Telegram chat via sendMessage API."""
        if not self._token:
            logger.warning("Telegram send skipped (no token) to %d", chat_id)
            return
        # If no background client, create a one-shot one (handles case where
        # send_message is called from code paths that run outside the polling
        # loop — e.g. pipeline result routing from voice_handler).
        client = self._client
        close_after = False
        if client is None:
            import httpx as _httpx
            client = _httpx.AsyncClient()
            close_after = True
        try:
            logger.info("Telegram send -> chat_id=%d len=%d", chat_id, len(text))
            r = await client.post(
                self._api_url("sendMessage"),
                json={"chat_id": chat_id, "text": text[:4096], "parse_mode": "Markdown"},
                timeout=_SEND_TIMEOUT,
            )
            if r.status_code != 200:
                body = r.text[:200]
                logger.warning(
                    "Telegram sendMessage HTTP=%s body=%s — retrying plain",
                    r.status_code,
                    body,
                )
                r2 = await client.post(
                    self._api_url("sendMessage"),
                    json={"chat_id": chat_id, "text": text[:4096]},
                    timeout=_SEND_TIMEOUT,
                )
                if r2.status_code != 200:
                    logger.error(
                        "Telegram sendMessage plain HTTP=%s body=%s",
                        r2.status_code,
                        r2.text[:200],
                    )
        except Exception as exc:
            logger.warning("Telegram send failed: %s", exc)
        finally:
            if close_after and client is not None:
                try:
                    await client.aclose()
                except Exception:
                    pass

    async def _download_voice(self, file_id: str) -> tuple[bytes, str]:
        """Download a Telegram voice file via getFile + file URL."""
        assert self._client is not None
        r = await self._client.get(
            self._api_url("getFile"),
            params={"file_id": file_id},
            timeout=_SEND_TIMEOUT,
        )
        r.raise_for_status()
        info = r.json()
        file_path = info.get("result", {}).get("file_path", "")
        if not file_path:
            return b"", "voice.ogg"
        file_name = file_path.rsplit("/", 1)[-1] or "voice.ogg"
        r2 = await self._client.get(self._file_url(file_path), timeout=_DOWNLOAD_TIMEOUT)
        r2.raise_for_status()
        return r2.content, file_name

    # ── Runtime loop ──────────────────────────────────────────────────

    async def _poll_loop(self) -> None:
        """Long-polling loop — runs until stop() is called."""
        assert self._client is not None
        logger.info(
            "Telegram polling started (owner_chat_id=%s)", self._owner_chat_id
        )
        while self._is_running:
            try:
                r = await self._client.get(
                    self._api_url("getUpdates"),
                    params={
                        "offset": self._offset,
                        "timeout": _POLL_TIMEOUT,
                        "allowed_updates": "message,edited_message",
                    },
                    timeout=_POLL_TIMEOUT + 10.0,
                )
                if r.status_code != 200:
                    logger.warning("Telegram getUpdates HTTP %s", r.status_code)
                    await asyncio.sleep(2)
                    continue
                data = r.json()
                if not data.get("ok"):
                    logger.warning("Telegram getUpdates not ok: %s", data)
                    await asyncio.sleep(2)
                    continue
                for update in data.get("result", []):
                    self._offset = update.get("update_id", 0) + 1
                    # Owner-only filter (strict auth)
                    msg = update.get("message") or update.get("edited_message") or {}
                    chat_id = msg.get("chat", {}).get("id", 0)
                    if self._owner_chat_id and chat_id != self._owner_chat_id:
                        logger.info(
                            "Telegram: ignored message from chat_id=%s (not owner)",
                            chat_id,
                        )
                        self._updates_ignored += 1
                        continue
                    # Hydrate voice bytes before handing off
                    voice = msg.get("voice")
                    if voice:
                        try:
                            audio_bytes, file_name = await self._download_voice(
                                voice.get("file_id", "")
                            )
                            msg["_audio_bytes"] = audio_bytes
                            msg["_file_name"] = file_name
                            update["message"] = msg
                        except Exception as exc:
                            logger.warning("Voice download failed: %s", exc)
                            continue
                    processed = await self._handle_update(update)
                    if processed:
                        self._updates_processed += 1
                    else:
                        self._updates_ignored += 1
            except asyncio.CancelledError:
                break
            except httpx.ReadTimeout:
                continue  # long-poll timeout is normal
            except Exception as exc:
                logger.warning("Telegram poll error: %s", exc)
                await asyncio.sleep(2)
        logger.info("Telegram polling stopped")

    async def start(self) -> None:
        if self._is_running:
            return
        if not self._token:
            logger.warning("Telegram bot start skipped: no token")
            return
        self._is_running = True
        self._client = httpx.AsyncClient()
        self._poll_task = asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:
        self._is_running = False
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
            try:
                await self._poll_task
            except (asyncio.CancelledError, Exception):
                pass
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _handle_update(self, update: dict[str, Any]) -> bool:
        """Process an incoming Telegram update.

        Returns True if the message was processed, False if ignored.

        Filtering rules:
        1. /start, /help commands -> always process
        2. Voice messages -> always process
        3. Text messages starting with "Brian:" (case insensitive) -> strip prefix, process
        4. All other text messages -> silently ignore
        """
        if not self._handler:
            logger.warning("No handler set — ignoring update")
            return False

        message = update.get("message", {})
        if not message:
            return False

        chat_id = message.get("chat", {}).get("id", 0)
        if not chat_id:
            return False

        # 1. Check for voice message — always process
        voice = message.get("voice")
        if voice:
            audio_bytes = message.get("_audio_bytes", b"")
            file_name = message.get("_file_name", "voice.ogg")
            await self._handler.handle_voice(chat_id, audio_bytes, file_name)
            return True

        # 2. Check for text
        text = message.get("text", "")
        if not text:
            return False

        # 3. Commands — always process
        stripped = text.strip()
        if stripped.split()[0].lower() in _ALWAYS_COMMANDS:
            await self._handler.handle_text(chat_id, stripped)
            return True

        # 4. Brian: prefix filter (case insensitive)
        if stripped.lower().startswith(_BRIAN_PREFIX):
            # Strip the prefix and leading whitespace after it
            content = stripped[len(_BRIAN_PREFIX):].lstrip()
            if content:
                await self._handler.handle_text(chat_id, content)
                return True
            return False  # "Brian:" with no content

        # 5. No prefix match — silently ignore
        return False
