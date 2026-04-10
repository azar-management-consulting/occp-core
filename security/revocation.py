"""Revocation Framework — centralized artifact revocation with kill-switch.

REQ-CPC-04: Centralized revocation list with kill-switch capability. Revoked
artifacts blocked at runtime within 1 polling cycle (default: 5 minutes).
Revocation survives network partition (local cache).

Usage::

    rc = RevocationChecker()
    rc.revoke("malicious-skill-v1", reason="CVE-2026-1234")
    assert rc.is_revoked("malicious-skill-v1")

    # Kill-switch: block all non-core
    rc.activate_kill_switch(reason="Zero-day", activated_by="admin@org")
    assert rc.kill_switch_active

    # Persist/restore from JSON
    snapshot = rc.to_dict()
    rc2 = RevocationChecker.from_dict(snapshot)
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Default polling interval: 5 minutes
DEFAULT_POLL_INTERVAL = 300


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class RevocationError(Exception):
    """Base error for revocation operations."""


# ---------------------------------------------------------------------------
# Revocation entry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RevocationEntry:
    """Record of a revoked artifact."""

    artifact_id: str
    reason: str
    revoked_at: float  # UNIX timestamp
    revoked_by: str = ""
    severity: str = "high"  # "critical" | "high" | "medium"
    expires_at: float = 0.0  # 0 = permanent

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifactId": self.artifact_id,
            "reason": self.reason,
            "revokedAt": self.revoked_at,
            "revokedBy": self.revoked_by,
            "severity": self.severity,
            "expiresAt": self.expires_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RevocationEntry:
        return cls(
            artifact_id=data["artifactId"],
            reason=data["reason"],
            revoked_at=data["revokedAt"],
            revoked_by=data.get("revokedBy", ""),
            severity=data.get("severity", "high"),
            expires_at=data.get("expiresAt", 0.0),
        )

    @property
    def is_expired(self) -> bool:
        """Check if this revocation has expired (temporary revocations)."""
        if self.expires_at == 0.0:
            return False  # permanent
        return time.time() > self.expires_at


# ---------------------------------------------------------------------------
# Kill-switch state
# ---------------------------------------------------------------------------


@dataclass
class KillSwitchState:
    """Kill-switch blocks all non-core artifacts immediately."""

    active: bool = False
    reason: str = ""
    activated_at: float = 0.0
    activated_by: str = ""
    core_allowlist: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "active": self.active,
            "reason": self.reason,
            "activatedAt": self.activated_at,
            "activatedBy": self.activated_by,
            "coreAllowlist": list(self.core_allowlist),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KillSwitchState:
        return cls(
            active=data.get("active", False),
            reason=data.get("reason", ""),
            activated_at=data.get("activatedAt", 0.0),
            activated_by=data.get("activatedBy", ""),
            core_allowlist=list(data.get("coreAllowlist", [])),
        )


# ---------------------------------------------------------------------------
# RevocationChecker
# ---------------------------------------------------------------------------


class RevocationChecker:
    """Manages artifact revocation list with kill-switch capability.

    Features:
    - Per-artifact revocation with reason and severity
    - Temporary revocations (auto-expire)
    - Kill-switch: block all non-core artifacts immediately
    - Serializable state for persistence/network sync
    - Local cache survives network partition
    """

    # Default core artifacts that are never blocked by kill-switch
    DEFAULT_CORE = [
        "occp-core",
        "occp-policy-engine",
        "occp-orchestrator",
        "occp-api",
    ]

    def __init__(
        self,
        core_allowlist: list[str] | None = None,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
    ) -> None:
        self._revocations: dict[str, RevocationEntry] = {}
        self._kill_switch = KillSwitchState(
            core_allowlist=list(core_allowlist or self.DEFAULT_CORE)
        )
        self._poll_interval = poll_interval
        self._last_sync: float = 0.0

    # -- Revocation management -----------------------------------------------

    def revoke(
        self,
        artifact_id: str,
        *,
        reason: str = "",
        revoked_by: str = "",
        severity: str = "high",
        ttl_seconds: float = 0.0,
    ) -> RevocationEntry:
        """Add an artifact to the revocation list.

        Args:
            artifact_id: ID of the artifact to revoke.
            reason: Human-readable revocation reason.
            revoked_by: Identity of the revoker.
            severity: "critical", "high", or "medium".
            ttl_seconds: If > 0, revocation expires after this many seconds.

        Returns:
            The RevocationEntry created.
        """
        now = time.time()
        entry = RevocationEntry(
            artifact_id=artifact_id,
            reason=reason or "Revoked",
            revoked_at=now,
            revoked_by=revoked_by,
            severity=severity,
            expires_at=(now + ttl_seconds) if ttl_seconds > 0 else 0.0,
        )
        self._revocations[artifact_id] = entry
        logger.warning(
            "Artifact revoked: id=%s reason=%s severity=%s by=%s",
            artifact_id,
            reason,
            severity,
            revoked_by,
        )
        return entry

    def unrevoke(self, artifact_id: str) -> bool:
        """Remove an artifact from the revocation list. Returns True if existed."""
        removed = self._revocations.pop(artifact_id, None)
        if removed:
            logger.info("Artifact unrevoked: id=%s", artifact_id)
        return removed is not None

    def is_revoked(self, artifact_id: str) -> bool:
        """Check if an artifact is currently revoked.

        Also checks kill-switch status. Returns True if blocked.
        """
        # Kill-switch check
        if self._kill_switch.active:
            if artifact_id not in self._kill_switch.core_allowlist:
                return True

        # Revocation list check
        entry = self._revocations.get(artifact_id)
        if entry is None:
            return False

        # Check temporary revocation expiry
        if entry.is_expired:
            del self._revocations[artifact_id]
            logger.info("Temporary revocation expired: id=%s", artifact_id)
            return False

        return True

    def get_revocation(self, artifact_id: str) -> RevocationEntry | None:
        """Get revocation details for an artifact."""
        entry = self._revocations.get(artifact_id)
        if entry and entry.is_expired:
            del self._revocations[artifact_id]
            return None
        return entry

    @property
    def revoked_artifacts(self) -> list[str]:
        """Return list of currently revoked artifact IDs (excluding expired)."""
        self._clean_expired()
        return list(self._revocations.keys())

    @property
    def revocation_count(self) -> int:
        """Number of active revocations."""
        self._clean_expired()
        return len(self._revocations)

    def _clean_expired(self) -> None:
        """Remove expired temporary revocations."""
        expired = [k for k, v in self._revocations.items() if v.is_expired]
        for k in expired:
            del self._revocations[k]

    # -- Kill-switch ---------------------------------------------------------

    def activate_kill_switch(
        self,
        reason: str = "",
        activated_by: str = "",
    ) -> None:
        """Activate kill-switch — block all non-core artifacts immediately."""
        self._kill_switch.active = True
        self._kill_switch.reason = reason or "Kill-switch activated"
        self._kill_switch.activated_at = time.time()
        self._kill_switch.activated_by = activated_by
        logger.critical(
            "KILL-SWITCH ACTIVATED: reason=%s by=%s",
            reason,
            activated_by,
        )

    def deactivate_kill_switch(self) -> None:
        """Deactivate kill-switch — resume normal operation."""
        self._kill_switch.active = False
        logger.warning("Kill-switch deactivated")

    @property
    def kill_switch_active(self) -> bool:
        return self._kill_switch.active

    @property
    def kill_switch_state(self) -> KillSwitchState:
        return self._kill_switch

    def is_core_artifact(self, artifact_id: str) -> bool:
        """Check if artifact is in the core allowlist."""
        return artifact_id in self._kill_switch.core_allowlist

    # -- Serialization -------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize state for persistence or network sync."""
        self._clean_expired()
        return {
            "revocations": {k: v.to_dict() for k, v in self._revocations.items()},
            "killSwitch": self._kill_switch.to_dict(),
            "lastSync": self._last_sync,
            "pollInterval": self._poll_interval,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RevocationChecker:
        """Restore from serialized state."""
        ks_data = data.get("killSwitch", {})
        core = ks_data.get("coreAllowlist", cls.DEFAULT_CORE)
        rc = cls(
            core_allowlist=core,
            poll_interval=data.get("pollInterval", DEFAULT_POLL_INTERVAL),
        )
        # Restore revocations
        for _aid, entry_data in data.get("revocations", {}).items():
            entry = RevocationEntry.from_dict(entry_data)
            if not entry.is_expired:
                rc._revocations[entry.artifact_id] = entry
        # Restore kill-switch
        rc._kill_switch = KillSwitchState.from_dict(ks_data)
        rc._last_sync = data.get("lastSync", 0.0)
        return rc

    @classmethod
    def from_json(cls, raw: str) -> RevocationChecker:
        return cls.from_dict(json.loads(raw))

    # -- Sync metadata -------------------------------------------------------

    def mark_synced(self) -> None:
        """Record that a sync with the central revocation server happened."""
        self._last_sync = time.time()

    @property
    def last_sync(self) -> float:
        return self._last_sync

    @property
    def poll_interval(self) -> float:
        return self._poll_interval

    def needs_sync(self) -> bool:
        """Check if it's time to poll the central revocation server."""
        if self._last_sync == 0.0:
            return True
        return (time.time() - self._last_sync) >= self._poll_interval
