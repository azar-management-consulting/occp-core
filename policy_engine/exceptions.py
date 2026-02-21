"""Policy Engine exception hierarchy."""

from __future__ import annotations


class PolicyEngineError(Exception):
    """Base exception for the Policy Engine module."""


class PolicyViolationError(PolicyEngineError):
    """Raised when a task violates one or more policy rules."""

    def __init__(self, rule_id: str, detail: str) -> None:
        self.rule_id = rule_id
        self.detail = detail
        super().__init__(f"Policy violation [{rule_id}]: {detail}")


class GuardViolationError(PolicyEngineError):
    """Raised when a built-in guard detects a violation."""

    def __init__(self, guard_name: str, detail: str) -> None:
        self.guard_name = guard_name
        self.detail = detail
        super().__init__(f"Guard [{guard_name}] violation: {detail}")


class AuditError(PolicyEngineError):
    """Raised when audit logging fails."""


class PolicyLoadError(PolicyEngineError):
    """Raised when a policy file cannot be loaded or parsed."""

    def __init__(self, path: str, reason: str) -> None:
        self.path = path
        self.reason = reason
        super().__init__(f"Failed to load policy {path}: {reason}")
