"""OpenClaw webhook integration client.

Handles task dispatch to OpenClaw agent runtime at claw.occp.ai,
result polling, parallel dispatch, and HMAC-signed callback handling.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class OpenClawTask:
    """Represents a task dispatched to an OpenClaw agent."""

    task_id: str
    agent_id: str
    input_text: str
    session_key: Optional[str] = None
    status: str = "pending"  # pending|running|completed|failed|timeout
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class OpenClawClient:
    """HTTP client for communicating with OpenClaw gateway.

    Handles task dispatch, result polling, parallel execution,
    and HMAC-SHA256 signed callback verification.
    """

    def __init__(
        self,
        base_url: str = "https://claw.occp.ai",
        auth_user: Optional[str] = None,
        auth_pass: Optional[str] = None,
        webhook_secret: Optional[str] = None,
        callback_url: Optional[str] = None,
        timeout: float = 300.0,
        max_retries: int = 2,
        retry_delay: float = 5.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._auth = (auth_user, auth_pass) if auth_user and auth_pass else None
        self._webhook_secret = webhook_secret or ""
        self._callback_url = callback_url
        self._timeout = timeout
        self._max_retries = max_retries
        self._retry_delay = retry_delay
        self._tasks: dict[str, OpenClawTask] = {}

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def tasks(self) -> dict[str, OpenClawTask]:
        return self._tasks

    async def dispatch_task(
        self,
        agent_id: str,
        input_text: str,
        task_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> OpenClawTask:
        """Send a task to an OpenClaw agent via the sessions API."""
        task = OpenClawTask(
            task_id=task_id or self._generate_id(),
            agent_id=agent_id,
            input_text=input_text,
            started_at=datetime.now(timezone.utc),
        )

        payload: dict[str, Any] = {
            "agent": agent_id,
            "input": input_text,
            "taskId": task.task_id,
            "callback": self._callback_url,
            "metadata": metadata or {},
        }

        signature = self._sign_payload(payload)

        headers = {
            "Content-Type": "application/json",
            "X-OCCP-Signature": f"sha256={signature}",
            "X-OCCP-Task-ID": task.task_id,
        }

        last_error = ""
        for attempt in range(1, self._max_retries + 1):
            async with httpx.AsyncClient(verify=True, timeout=self._timeout) as client:
                try:
                    resp = await client.post(
                        f"{self._base_url}/api/v1/sessions",
                        json=payload,
                        headers=headers,
                        auth=self._auth,
                    )
                    if resp.status_code in (200, 201):
                        data = resp.json()
                        task.session_key = data.get("sessionKey") or data.get("session_key")
                        task.status = "running"
                        break
                    else:
                        last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
                        if resp.status_code < 500:
                            task.status = "failed"
                            task.error = last_error
                            break
                except httpx.ConnectError as exc:
                    last_error = f"Connection failed: {exc}"
                except httpx.TimeoutException:
                    last_error = f"Timeout after {self._timeout}s (attempt {attempt}/{self._max_retries})"

            if attempt < self._max_retries:
                logger.warning(
                    "OpenClaw dispatch retry %d/%d for task=%s: %s",
                    attempt, self._max_retries, task.task_id, last_error,
                )
                await asyncio.sleep(self._retry_delay)
        else:
            if task.status == "pending":
                task.status = "failed"
                task.error = last_error

        self._tasks[task.task_id] = task
        logger.info(
            "OpenClaw dispatch: task_id=%s agent=%s status=%s",
            task.task_id,
            agent_id,
            task.status,
        )
        return task

    async def get_task_result(self, task_id: str) -> Optional[OpenClawTask]:
        """Poll OpenClaw session history for task result."""
        task = self._tasks.get(task_id)
        if not task or not task.session_key:
            return task

        async with httpx.AsyncClient(verify=True, timeout=self._timeout) as client:
            try:
                resp = await client.get(
                    f"{self._base_url}/api/v1/sessions/{task.session_key}/history",
                    auth=self._auth,
                )
                if resp.status_code == 200:
                    history = resp.json()
                    text = self._extract_assistant_text(history)
                    if text:
                        task.result = {"text": text, "raw": history}
                        task.status = "completed"
                        task.completed_at = datetime.now(timezone.utc)
            except Exception as exc:
                logger.warning(
                    "Failed to poll task %s: %s", task_id, exc
                )
                task.error = str(exc)

        return task

    async def dispatch_parallel(
        self, tasks: list[dict[str, Any]]
    ) -> list[OpenClawTask | BaseException]:
        """Dispatch multiple tasks in parallel."""
        coros = [
            self.dispatch_task(
                agent_id=t["agent_id"],
                input_text=t["input"],
                task_id=t.get("task_id"),
                metadata=t.get("metadata"),
            )
            for t in tasks
        ]
        results = await asyncio.gather(*coros, return_exceptions=True)
        return list(results)

    async def poll_until_complete(
        self,
        task_id: str,
        max_wait: int = 120,
        interval: int = 5,
    ) -> Optional[OpenClawTask]:
        """Poll a task until it completes or times out."""
        elapsed = 0
        while elapsed < max_wait:
            task = await self.get_task_result(task_id)
            if task and task.status in ("completed", "failed"):
                return task
            await asyncio.sleep(interval)
            elapsed += interval

        task = self._tasks.get(task_id)
        if task:
            task.status = "timeout"
            task.error = f"Timed out after {max_wait}s"
        return task

    def handle_callback(
        self, payload: dict[str, Any], signature: str
    ) -> Optional[OpenClawTask]:
        """Handle incoming callback from OpenClaw agent.

        Verifies HMAC signature and updates task state.
        Raises ValueError on invalid signature.
        """
        if self._webhook_secret:
            expected = self._sign_payload(payload)
            if not hmac.compare_digest(f"sha256={expected}", signature):
                raise ValueError("Invalid callback signature")

        task_id = payload.get("taskId") or payload.get("task_id")
        task = self._tasks.get(task_id)  # type: ignore[arg-type]
        if not task:
            return None

        task.status = payload.get("status", "completed")
        task.result = payload.get("result")
        task.completed_at = datetime.now(timezone.utc)
        if payload.get("error"):
            task.error = payload["error"]
        return task

    def _sign_payload(self, payload: dict[str, Any]) -> str:
        """Compute HMAC-SHA256 signature for a JSON payload."""
        if not self._webhook_secret:
            return ""
        body = json.dumps(payload, sort_keys=True, default=str).encode()
        return hmac.new(
            self._webhook_secret.encode(), body, hashlib.sha256
        ).hexdigest()

    @staticmethod
    def _extract_assistant_text(history: Any) -> Optional[str]:
        """Extract the last assistant/agent text from various history formats."""
        if isinstance(history, list):
            for msg in reversed(history):
                if isinstance(msg, dict):
                    role = msg.get("role", "")
                    if role in ("assistant", "agent"):
                        content = msg.get("content", "")
                        if isinstance(content, str) and content.strip():
                            return content.strip()
                        if isinstance(content, list):
                            texts = [
                                p.get("text", "")
                                for p in content
                                if isinstance(p, dict)
                            ]
                            combined = " ".join(t for t in texts if t)
                            if combined:
                                return combined
        elif isinstance(history, dict):
            messages = history.get("messages") or history.get("history") or []
            return OpenClawClient._extract_assistant_text(messages)
        return None

    @staticmethod
    def _generate_id() -> str:
        return uuid.uuid4().hex[:16]

    def clear_tasks(self) -> None:
        """Clear all tracked tasks."""
        self._tasks.clear()
