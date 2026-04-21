"""Anthropic Managed Agents client (2026-Q2 beta).

Thin wrapper around the Managed Agents REST surface (header
``managed-agents-2026-04-01``). Retries 5xx (3x, exponential backoff),
raises :class:`ManagedAgentsAPIError` on 4xx, :class:`NotConfigured`
when the API key is missing. Never logs the API key in full.

FELT: the JSON shape of Managed Agents endpoints is still evolving —
this client assumes ``POST /v1/managed_agents/sessions`` returns
``{id, created_at}`` and messages stream as SSE ``text_delta`` events.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# ── Constants (single source of truth) ───────────────────────────

DEFAULT_BETA_HEADER: str = "managed-agents-2026-04-01"
DEFAULT_BASE_URL: str = "https://api.anthropic.com"
_SESSIONS_PATH: str = "/v1/managed_agents/sessions"
_ANTHROPIC_VERSION: str = "2023-06-01"

_CONNECT_TIMEOUT_S: float = 30.0
_READ_TIMEOUT_S: float = 300.0
_MAX_RETRIES: int = 3
_BACKOFF_SCHEDULE_S: tuple[float, ...] = (1.0, 2.0, 4.0)


# ── Errors ───────────────────────────────────────────────────────


class NotConfigured(RuntimeError):
    """Raised when the client cannot be built because the API key is missing."""


class ManagedAgentsAPIError(RuntimeError):
    """Raised on non-retryable HTTP errors (4xx) from the Managed Agents API."""

    def __init__(self, status_code: int, body: str, message: str | None = None) -> None:
        self.status_code = status_code
        self.body = body
        super().__init__(
            message or f"Managed Agents API {status_code}: {body[:500]}"
        )


# ── Data types ───────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class SessionHandle:
    """Opaque handle returned from :meth:`AnthropicManagedAgentsClient.create_session`."""

    session_id: str
    agent_name: str
    created_at: str
    raw: dict[str, Any]


# ── Client ───────────────────────────────────────────────────────


class AnthropicManagedAgentsClient:
    """Async client for the Anthropic Managed Agents beta."""

    def __init__(
        self,
        api_key: str | None = None,
        beta_header: str = DEFAULT_BETA_HEADER,
        base_url: str | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        key = (
            api_key
            or os.environ.get("OCCP_ANTHROPIC_API_KEY")
            or os.environ.get("ANTHROPIC_API_KEY")
        )
        if not key:
            raise NotConfigured(
                "Managed Agents client requires OCCP_ANTHROPIC_API_KEY "
                "(or ANTHROPIC_API_KEY) to be set."
            )
        self._api_key = key
        self._beta_header = beta_header
        self._base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self._owns_client = http_client is None
        self._http = http_client or httpx.AsyncClient(
            timeout=httpx.Timeout(
                _READ_TIMEOUT_S,
                connect=_CONNECT_TIMEOUT_S,
                read=_READ_TIMEOUT_S,
            ),
        )
        logger.info(
            "AnthropicManagedAgentsClient initialised (beta=%s, base=%s, key=***REDACTED***)",
            self._beta_header,
            self._base_url,
        )

    # ── lifecycle ─────────────────────────────────────────────

    async def aclose(self) -> None:
        if self._owns_client:
            await self._http.aclose()

    # ── private helpers ───────────────────────────────────────

    def _headers(self, *, stream: bool = False) -> dict[str, str]:
        h = {
            "x-api-key": self._api_key,
            "anthropic-version": _ANTHROPIC_VERSION,
            "anthropic-beta": self._beta_header,
            "content-type": "application/json",
        }
        if stream:
            h["accept"] = "text/event-stream"
        return h

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Issue a request expecting a JSON response, with retry on 5xx."""
        url = f"{self._base_url}{path}"
        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                response = await self._http.request(
                    method,
                    url,
                    headers=self._headers(),
                    json=json_body,
                )
            except httpx.HTTPError as exc:  # network-level failure
                last_exc = exc
                if attempt >= _MAX_RETRIES:
                    raise ManagedAgentsAPIError(
                        0, f"network error: {exc!s}"
                    ) from exc
                await asyncio.sleep(_BACKOFF_SCHEDULE_S[attempt])
                continue

            if 200 <= response.status_code < 300:
                if not response.content:
                    return {}
                return response.json()
            if 400 <= response.status_code < 500:
                raise ManagedAgentsAPIError(response.status_code, response.text)
            # 5xx → retry
            last_exc = ManagedAgentsAPIError(response.status_code, response.text)
            if attempt >= _MAX_RETRIES:
                raise last_exc
            await asyncio.sleep(_BACKOFF_SCHEDULE_S[attempt])

        # Should be unreachable
        raise ManagedAgentsAPIError(0, f"exhausted retries: {last_exc!s}")

    # ── public API ────────────────────────────────────────────

    async def create_session(self, agent_config: dict[str, Any]) -> SessionHandle:
        """POST ``/v1/managed_agents/sessions`` and return the handle.

        ``agent_config`` is the YAML-loaded agent definition.
        """
        payload = {"agent": agent_config}
        data = await self._request_json("POST", _SESSIONS_PATH, json_body=payload)
        sid = data.get("id") or data.get("session_id")
        if not sid:
            raise ManagedAgentsAPIError(
                500, f"response missing session id: {json.dumps(data)[:400]}"
            )
        return SessionHandle(
            session_id=str(sid),
            agent_name=str(agent_config.get("name", "unnamed")),
            created_at=str(data.get("created_at", "")),
            raw=data,
        )

    async def send_message(
        self,
        session_id: str,
        message: str,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        """Stream tokens produced by the agent in response to ``message``.

        Yields each ``text_delta`` as it arrives on the SSE stream.
        """
        url = f"{self._base_url}{_SESSIONS_PATH}/{session_id}/messages"
        body = {"message": message, "max_tokens": max_tokens, "stream": True}
        async with self._http.stream(
            "POST",
            url,
            headers=self._headers(stream=True),
            json=body,
        ) as response:
            if response.status_code >= 400:
                raw = await response.aread()
                raise ManagedAgentsAPIError(
                    response.status_code, raw.decode("utf-8", errors="replace")
                )
            async for raw_line in response.aiter_lines():
                if not raw_line or not raw_line.startswith("data:"):
                    continue
                chunk = raw_line[len("data:") :].strip()
                if not chunk or chunk == "[DONE]":
                    if chunk == "[DONE]":
                        break
                    continue
                try:
                    event = json.loads(chunk)
                except json.JSONDecodeError:
                    logger.debug("Managed Agents: skipping non-JSON SSE chunk")
                    continue
                delta = event.get("delta") or {}
                text = delta.get("text") if isinstance(delta, dict) else None
                if not text and event.get("type") == "text_delta":
                    text = event.get("text")
                if text:
                    yield text

    async def end_session(self, session_id: str) -> None:
        """DELETE the session on the server. Best-effort; errors are logged."""
        path = f"{_SESSIONS_PATH}/{session_id}"
        try:
            await self._request_json("DELETE", path)
        except ManagedAgentsAPIError as exc:
            # 404 = already gone; log and return
            if exc.status_code == 404:
                return
            raise
