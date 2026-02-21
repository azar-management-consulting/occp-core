"""Data models for policies, rules and audit entries."""

from __future__ import annotations

import enum
import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


class RuleAction(enum.Enum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"


@dataclass
class PolicyRule:
    """A single rule inside a policy."""

    id: str
    description: str
    action: RuleAction
    conditions: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Policy:
    """A named collection of rules loaded from YAML/JSON."""

    name: str
    version: str
    rules: list[PolicyRule] = field(default_factory=list)
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AuditEntry:
    """Tamper-evident audit log entry with SHA-256 hash chain.

    Each entry's ``hash`` is computed over its payload **plus** the
    previous entry's hash, forming a verifiable chain.
    """

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    actor: str = ""
    action: str = ""
    task_id: str = ""
    detail: dict[str, Any] = field(default_factory=dict)
    prev_hash: str = ""
    hash: str = ""

    def compute_hash(self, prev_hash: str = "") -> str:
        """Compute SHA-256 hash over payload + previous hash."""
        payload = json.dumps(
            {
                "id": self.id,
                "timestamp": self.timestamp.isoformat(),
                "actor": self.actor,
                "action": self.action,
                "task_id": self.task_id,
                "detail": self.detail,
                "prev_hash": prev_hash,
            },
            sort_keys=True,
        )
        h = hashlib.sha256(payload.encode()).hexdigest()
        self.prev_hash = prev_hash
        self.hash = h
        return h
