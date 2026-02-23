"""Audit log endpoint – read tamper-evident audit chain."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from api.deps import AppState, get_state
from api.models import AuditEntryResponse, AuditLogResponse
from policy_engine.engine import PolicyEngine

router = APIRouter(tags=["audit"])


@router.get("/audit", response_model=AuditLogResponse)
async def get_audit_log(
    state: AppState = Depends(get_state),
) -> AuditLogResponse:
    # Read from persistent store if available, else in-memory
    if state.audit_store:
        entries = await state.audit_store.list_all()
    else:
        entries = state.policy_engine.audit_log

    # Verify using the actual entries source (persistent > in-memory)
    chain_valid = PolicyEngine.verify_entries(entries)

    return AuditLogResponse(
        entries=[
            AuditEntryResponse(
                id=e.id,
                timestamp=e.timestamp,
                actor=e.actor,
                action=e.action,
                task_id=e.task_id,
                detail=e.detail,
                prev_hash=e.prev_hash,
                hash=e.hash,
            )
            for e in entries
        ],
        chain_valid=chain_valid,
        total=len(entries),
    )
