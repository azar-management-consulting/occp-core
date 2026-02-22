"""OCCP Python SDK client – stdlib-only HTTP client."""

from __future__ import annotations

import json
import urllib.request
import urllib.error
from typing import Any
from dataclasses import dataclass

from sdk.python.exceptions import (
    AuthenticationError,
    NotFoundError,
    OCCPAPIError,
    RateLimitError,
)


@dataclass
class OCCPClient:
    """Lightweight Python client for the OCCP REST API.

    Uses only stdlib ``urllib`` – no requests/httpx dependency.

    Usage::

        client = OCCPClient(base_url="http://localhost:3000", api_key="...")
        status = client.get_status()
        result = client.run_workflow({"name": "my_wf", "tasks": [...]})
    """

    base_url: str = "http://localhost:3000"
    api_key: str = ""
    timeout: int = 30

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def login(self, username: str, password: str) -> str:
        """POST /api/v1/auth/login — returns and stores access token."""
        data = self._request(
            "POST",
            "/api/v1/auth/login",
            body={"username": username, "password": password},
        )
        token = data.get("access_token", "")
        self.api_key = token
        return token

    def get_status(self) -> dict[str, Any]:
        """GET /api/v1/status"""
        return self._request("GET", "/api/v1/status")

    def list_agents(self) -> dict[str, Any]:
        """GET /api/v1/agents"""
        return self._request("GET", "/api/v1/agents")

    def create_task(
        self,
        name: str,
        description: str,
        agent_type: str,
        risk_level: str = "low",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """POST /api/v1/tasks — requires auth."""
        body: dict[str, Any] = {
            "name": name,
            "description": description,
            "agent_type": agent_type,
            "risk_level": risk_level,
        }
        if metadata:
            body["metadata"] = metadata
        return self._request("POST", "/api/v1/tasks", body=body)

    def run_pipeline(self, task_id: str) -> dict[str, Any]:
        """POST /api/v1/pipeline/run/{task_id} — requires auth."""
        return self._request("POST", f"/api/v1/pipeline/run/{task_id}")

    def run_workflow(self, workflow: dict[str, Any]) -> dict[str, Any]:
        """POST /api/v1/workflows/run"""
        return self._request("POST", "/api/v1/workflows/run", body=workflow)

    def get_task(self, task_id: str) -> dict[str, Any]:
        """GET /api/v1/tasks/{task_id}"""
        return self._request("GET", f"/api/v1/tasks/{task_id}")

    def list_tasks(self, status: str | None = None) -> dict[str, Any]:
        """GET /api/v1/tasks"""
        params = f"?status={status}" if status else ""
        return self._request("GET", f"/api/v1/tasks{params}")

    def get_audit_log(
        self, limit: int = 100, offset: int = 0
    ) -> dict[str, Any]:
        """GET /api/v1/audit"""
        return self._request(
            "GET", f"/api/v1/audit?limit={limit}&offset={offset}"
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self.base_url.rstrip('/')}{path}"
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        data = json.dumps(body).encode() if body else None
        req = urllib.request.Request(
            url, data=data, headers=headers, method=method
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            status = exc.code
            try:
                detail = json.loads(exc.read().decode())
            except Exception:
                detail = {}
            msg = detail.get("message", str(exc.reason))

            if status == 401 or status == 403:
                raise AuthenticationError(msg) from exc
            if status == 404:
                raise NotFoundError(path) from exc
            if status == 429:
                retry = int(exc.headers.get("Retry-After", "60"))
                raise RateLimitError(retry) from exc
            raise OCCPAPIError(status, msg, str(detail)) from exc
        except urllib.error.URLError as exc:
            raise OCCPAPIError(0, f"Connection error: {exc.reason}") from exc
