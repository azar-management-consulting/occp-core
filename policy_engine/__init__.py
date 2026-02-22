"""OCCP Policy Engine – policy-as-code, audit log, PII/injection guard.

Community Edition: alapszintű policy enforcement, PII guard, audit log.
Enterprise Edition: RBAC, compliance export, advanced guards.
"""

__version__ = "0.5.0"

from policy_engine.engine import PolicyEngine, GateResult
from policy_engine.models import Policy, PolicyRule, AuditEntry
from policy_engine.guards import PIIGuard, PromptInjectionGuard, ResourceLimitGuard

__all__ = [
    "PolicyEngine",
    "GateResult",
    "Policy",
    "PolicyRule",
    "AuditEntry",
    "PIIGuard",
    "PromptInjectionGuard",
    "ResourceLimitGuard",
]
