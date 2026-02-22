"""LogShipper – demo Shipper adapter that logs to the audit trail."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from orchestrator.models import Task

logger = logging.getLogger(__name__)


class LogShipper:
    """Implements the :class:`orchestrator.pipeline.Shipper` protocol.

    Instead of creating a real PR or deployment, logs the ship event
    and returns a summary dict.  Useful for demos and integration tests.
    """

    def __init__(self) -> None:
        self._shipped: list[dict[str, Any]] = []

    async def ship(self, task: Task) -> dict[str, Any]:
        record = {
            "task_id": task.id,
            "task_name": task.name,
            "shipped_at": datetime.now(timezone.utc).isoformat(),
            "destination": "audit_log",
        }
        self._shipped.append(record)
        logger.info("Shipped task=%s name='%s'", task.id, task.name)
        return record

    @property
    def history(self) -> list[dict[str, Any]]:
        """Returns all shipped records (for testing/inspection)."""
        return list(self._shipped)
