"""OCCP Policy Engine – policy-as-code, audit log, PII/injection guard.

Community Edition: alapszintű policy enforcement, PII guard, audit log.
Enterprise Edition: RBAC, compliance export, advanced guards.
"""

__version__ = "0.8.2"

from policy_engine.engine import PolicyEngine, GateResult
from policy_engine.models import Policy, PolicyRule, AuditEntry
from policy_engine.guards import PIIGuard, PromptInjectionGuard, ResourceLimitGuard
from policy_engine.budget_policy import (
    BudgetExceededError,
    BudgetPolicy,
    BudgetSpend,
    CacheBreakdown,
    Model,
    PRICING,
    estimate_tokens,
    get_budget_policy,
    price_call,
)

__all__ = [
    "PolicyEngine",
    "GateResult",
    "Policy",
    "PolicyRule",
    "AuditEntry",
    "PIIGuard",
    "PromptInjectionGuard",
    "ResourceLimitGuard",
    # Budget policy
    "BudgetPolicy",
    "BudgetExceededError",
    "BudgetSpend",
    "CacheBreakdown",
    "Model",
    "PRICING",
    "price_call",
    "estimate_tokens",
    "get_budget_policy",
]
