"""WebSocket endpoint for real-time pipeline event streaming."""

from __future__ import annotations

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from api.deps import AppState, get_state

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/pipeline/{task_id}")
async def pipeline_ws(
    websocket: WebSocket,
    task_id: str,
    state: AppState = Depends(get_state),
) -> None:
    await state.ws_manager.connect(task_id, websocket)
    try:
        while True:
            # Keep connection alive; client can send pings
            await websocket.receive_text()
    except WebSocketDisconnect:
        await state.ws_manager.disconnect(task_id, websocket)
