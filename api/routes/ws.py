"""WebSocket endpoint for real-time pipeline event streaming."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from api.auth import decode_token
from api.rbac import check_permission
from api.deps import AppState, get_state

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/pipeline/{task_id}")
async def pipeline_ws(
    websocket: WebSocket,
    task_id: str,
    state: AppState = Depends(get_state),
) -> None:
    # Authenticate via query parameter token
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return

    try:
        payload = decode_token(token, state.settings)
    except Exception:
        await websocket.close(code=4001, reason="Invalid token")
        return

    role = payload.get("role", "viewer")
    if not check_permission(role, "tasks", "read"):
        await websocket.close(code=4003, reason="Forbidden")
        return

    await state.ws_manager.connect(task_id, websocket)
    try:
        while True:
            # Keep connection alive; client can send pings
            await websocket.receive_text()
    except WebSocketDisconnect:
        await state.ws_manager.disconnect(task_id, websocket)
