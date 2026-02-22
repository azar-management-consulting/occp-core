"""WebSocket connection manager for real-time pipeline event streaming."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections per task_id for pipeline event streaming."""

    def __init__(self) -> None:
        self._connections: dict[str, list[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, task_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            if task_id not in self._connections:
                self._connections[task_id] = []
            self._connections[task_id].append(websocket)
        logger.info("WS connected: task=%s", task_id)

    async def disconnect(self, task_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            conns = self._connections.get(task_id, [])
            if websocket in conns:
                conns.remove(websocket)
            if not conns:
                self._connections.pop(task_id, None)
        logger.info("WS disconnected: task=%s", task_id)

    async def broadcast(self, task_id: str, event: dict[str, Any]) -> None:
        """Send an event to all WebSocket clients watching *task_id*."""
        async with self._lock:
            conns = list(self._connections.get(task_id, []))

        message = json.dumps(event)
        dead: list[WebSocket] = []

        for ws in conns:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)

        if dead:
            async with self._lock:
                for ws in dead:
                    conns_list = self._connections.get(task_id, [])
                    if ws in conns_list:
                        conns_list.remove(ws)
