"""Attribute-Based Access Control (ABAC) evaluator — REQ-POL-01.

Implements ABAC alongside existing Casbin RBAC for context-dependent
policy decisions. Supports attributes: user_role, agent_type,
tool_category, data_classification, time_of_day, source_ip, session_type.

Rules are defined in YAML:

    rules:
      - id: allow-shell-business-hours
        effect: allow
        conditions:
          tool_category: shell
          user_role: operator
          time_of_day:
            after: "09:00"
            before: "17:00"

Usage::

    evaluator = ABACEvaluator()
    evaluator.load_rules_from_yaml("policies/abac_rules.yaml")
    result = evaluator.evaluate(request_context)
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, time, timezone
from enum import Enum
from ipaddress import IPv4Network, IPv6Network, ip_address
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class Effect(str, Enum):
    """ABAC rule effect — determines the outcome when conditions match."""

    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"


class CombineAlgorithm(str, Enum):
    """Policy combination algorithm for multiple matching rules."""

    DENY_OVERRIDES = "deny_overrides"  # Any deny → deny (default, most secure)
    ALLOW_OVERRIDES = "allow_overrides"  # Any allow → allow
    FIRST_MATCH = "first_match"  # First matching rule wins


@dataclass
class ABACCondition:
    """A single condition in an ABAC rule.

    Supports:
    - Exact match: ``{"tool_category": "shell"}``
    - Set membership: ``{"user_role": ["operator", "admin"]}``
    - Time range: ``{"time_of_day": {"after": "09:00", "before": "17:00"}}``
    - IP CIDR: ``{"source_ip": {"cidr": "10.0.0.0/8"}}``
    - Regex: ``{"agent_type": {"pattern": "^code_.*"}}``
    - Negation: ``{"data_classification": {"not": "top_secret"}}``
    """

    attribute: str
    operator: str  # eq, in, time_range, cidr, regex, not_eq, not_in
    value: Any

    def matches(self, actual: Any) -> bool:
        """Evaluate this condition against an actual attribute value."""
        if actual is None:
            return False

        if self.operator == "eq":
            return str(actual) == str(self.value)

        if self.operator == "not_eq":
            return str(actual) != str(self.value)

        if self.operator == "in":
            return str(actual) in [str(v) for v in self.value]

        if self.operator == "not_in":
            return str(actual) not in [str(v) for v in self.value]

        if self.operator == "time_range":
            return self._check_time_range(actual)

        if self.operator == "cidr":
            return self._check_cidr(actual)

        if self.operator == "regex":
            return bool(re.match(str(self.value), str(actual)))

        logger.warning("Unknown ABAC operator: %s", self.operator)
        return False

    def _check_time_range(self, actual: Any) -> bool:
        """Check if a time value falls within a range."""
        try:
            if isinstance(actual, str):
                current = time.fromisoformat(actual)
            elif isinstance(actual, time):
                current = actual
            elif isinstance(actual, datetime):
                current = actual.time()
            else:
                return False

            after_str = self.value.get("after", "00:00")
            before_str = self.value.get("before", "23:59")
            after = time.fromisoformat(after_str)
            before = time.fromisoformat(before_str)

            if after <= before:
                return after <= current <= before
            # Wraps midnight (e.g. 22:00 → 06:00)
            return current >= after or current <= before
        except (ValueError, AttributeError):
            return False

    def _check_cidr(self, actual: Any) -> bool:
        """Check if an IP address is within a CIDR range."""
        try:
            addr = ip_address(str(actual))
            cidr = str(self.value)
            if ":" in cidr:
                return addr in IPv6Network(cidr, strict=False)
            return addr in IPv4Network(cidr, strict=False)
        except (ValueError, TypeError):
            return False


@dataclass
class ABACRule:
    """An ABAC policy rule with conditions and effect."""

    id: str
    effect: Effect
    description: str = ""
    conditions: list[ABACCondition] = field(default_factory=list)
    priority: int = 0  # Higher = evaluated first
    metadata: dict[str, Any] = field(default_factory=dict)

    def matches(self, context: RequestContext) -> bool:
        """True if ALL conditions match the request context."""
        if not self.conditions:
            return True
        return all(
            cond.matches(context.get_attribute(cond.attribute))
            for cond in self.conditions
        )


@dataclass
class RequestContext:
    """Request context carrying all ABAC-relevant attributes.

    Attributes are extracted from the incoming request, session,
    and environment. The context is immutable during evaluation.
    """

    user_role: str = ""
    agent_type: str = ""
    tool_category: str = ""
    tool_name: str = ""
    data_classification: str = ""
    time_of_day: time | None = None
    source_ip: str = ""
    session_type: str = ""
    trust_level: int = -1
    action: str = ""
    resource: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def get_attribute(self, name: str) -> Any:
        """Get an attribute value by name, with fallback to extra dict."""
        if hasattr(self, name) and name != "extra":
            val = getattr(self, name)
            if val is not None and val != "" and val != -1:
                return val
        return self.extra.get(name)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RequestContext:
        """Create RequestContext from a flat dictionary."""
        known_fields = {
            "user_role", "agent_type", "tool_category", "tool_name",
            "data_classification", "source_ip", "session_type",
            "action", "resource",
        }
        kwargs: dict[str, Any] = {}
        extra: dict[str, Any] = {}

        for key, value in data.items():
            if key in known_fields:
                kwargs[key] = value
            elif key == "trust_level":
                kwargs[key] = int(value) if value is not None else -1
            elif key == "time_of_day":
                if isinstance(value, time):
                    kwargs[key] = value
                elif isinstance(value, str):
                    kwargs[key] = time.fromisoformat(value)
            else:
                extra[key] = value

        kwargs["extra"] = extra
        return cls(**kwargs)

    @classmethod
    def from_task(cls, task: Any) -> RequestContext:
        """Extract RequestContext from a Task object."""
        data: dict[str, Any] = {}
        for attr in (
            "agent_type", "name", "capabilities", "metadata",
            "trust_level", "session_type",
        ):
            if hasattr(task, attr):
                val = getattr(task, attr)
                if val is not None:
                    data[attr] = val

        # Extract nested metadata attributes
        meta = getattr(task, "metadata", None) or {}
        if isinstance(meta, dict):
            for key in ("user_role", "tool_category", "tool_name",
                        "data_classification", "source_ip"):
                if key in meta:
                    data[key] = meta[key]

        # Current time
        data["time_of_day"] = datetime.now(timezone.utc).time()

        return cls.from_dict(data)


@dataclass
class ABACDecision:
    """Result of ABAC evaluation with full audit trail."""

    effect: Effect
    matched_rules: list[str] = field(default_factory=list)
    reason: str = ""
    context_snapshot: dict[str, Any] = field(default_factory=dict)
    policy_hash: str = ""  # SHA-256 of the evaluated ruleset

    @property
    def allowed(self) -> bool:
        return self.effect == Effect.ALLOW

    @property
    def denied(self) -> bool:
        return self.effect == Effect.DENY

    def to_audit_dict(self) -> dict[str, Any]:
        """Structured dict for audit trail (REQ-POL-02)."""
        return {
            "effect": self.effect.value,
            "matched_rules": self.matched_rules,
            "reason": self.reason,
            "policy_hash": self.policy_hash,
            "context": self.context_snapshot,
        }


class ABACEvaluator:
    """Evaluates request contexts against ABAC rules.

    Supports multiple combination algorithms:
    - deny_overrides (default): any DENY rule → deny
    - allow_overrides: any ALLOW rule → allow
    - first_match: first matching rule's effect wins

    Usage::

        evaluator = ABACEvaluator()
        evaluator.load_rules_from_yaml("policies/abac.yaml")
        decision = evaluator.evaluate(context)
    """

    def __init__(
        self,
        *,
        algorithm: CombineAlgorithm = CombineAlgorithm.DENY_OVERRIDES,
        default_effect: Effect = Effect.DENY,
    ) -> None:
        self._rules: list[ABACRule] = []
        self._algorithm = algorithm
        self._default_effect = default_effect
        self._policy_hash = ""

    @property
    def rule_count(self) -> int:
        return len(self._rules)

    @property
    def policy_hash(self) -> str:
        """SHA-256 hash of current ruleset for version tracking."""
        return self._policy_hash

    def add_rule(self, rule: ABACRule) -> None:
        """Add a single ABAC rule and recompute policy hash."""
        self._rules.append(rule)
        self._rules.sort(key=lambda r: r.priority, reverse=True)
        self._recompute_hash()

    def load_rules(self, rules: list[ABACRule]) -> None:
        """Load a batch of ABAC rules."""
        self._rules.extend(rules)
        self._rules.sort(key=lambda r: r.priority, reverse=True)
        self._recompute_hash()

    def load_rules_from_yaml(self, path: str | Path) -> int:
        """Load ABAC rules from a YAML file.

        Returns the number of rules loaded.
        """
        import yaml  # Lazy import — yaml is optional dependency

        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"ABAC rules file not found: {p}")

        data = yaml.safe_load(p.read_text(encoding="utf-8"))
        if not data or "rules" not in data:
            return 0

        rules = []
        for r in data["rules"]:
            conditions = _parse_conditions(r.get("conditions", {}))
            rule = ABACRule(
                id=r["id"],
                effect=Effect(r.get("effect", "deny")),
                description=r.get("description", ""),
                conditions=conditions,
                priority=r.get("priority", 0),
                metadata=r.get("metadata", {}),
            )
            rules.append(rule)

        self.load_rules(rules)
        logger.info("Loaded %d ABAC rules from %s", len(rules), p)
        return len(rules)

    def evaluate(self, context: RequestContext) -> ABACDecision:
        """Evaluate a request context against all loaded rules.

        Returns an ABACDecision with:
        - effect: the combined decision
        - matched_rules: IDs of all rules that matched
        - context_snapshot: the attributes used in evaluation
        - policy_hash: SHA-256 of the current ruleset
        """
        matched: list[tuple[ABACRule, Effect]] = []
        context_snap = _context_to_dict(context)

        for rule in self._rules:
            if rule.matches(context):
                matched.append((rule, rule.effect))

        if not matched:
            return ABACDecision(
                effect=self._default_effect,
                reason="No matching rules — default effect applied",
                context_snapshot=context_snap,
                policy_hash=self._policy_hash,
            )

        # Apply combination algorithm
        effect = self._combine(matched)
        matched_ids = [r.id for r, _ in matched]

        return ABACDecision(
            effect=effect,
            matched_rules=matched_ids,
            reason=f"Matched {len(matched)} rules, algorithm={self._algorithm.value}",
            context_snapshot=context_snap,
            policy_hash=self._policy_hash,
        )

    def _combine(self, matched: list[tuple[ABACRule, Effect]]) -> Effect:
        """Apply combination algorithm to matched rules."""
        if self._algorithm == CombineAlgorithm.FIRST_MATCH:
            return matched[0][1]

        effects = {e for _, e in matched}

        if self._algorithm == CombineAlgorithm.DENY_OVERRIDES:
            if Effect.DENY in effects:
                return Effect.DENY
            if Effect.REQUIRE_APPROVAL in effects:
                return Effect.REQUIRE_APPROVAL
            return Effect.ALLOW

        if self._algorithm == CombineAlgorithm.ALLOW_OVERRIDES:
            if Effect.ALLOW in effects:
                return Effect.ALLOW
            if Effect.REQUIRE_APPROVAL in effects:
                return Effect.REQUIRE_APPROVAL
            return Effect.DENY

        return self._default_effect

    def _recompute_hash(self) -> None:
        """Recompute policy hash from all rules."""
        rule_data = [
            {
                "id": r.id,
                "effect": r.effect.value,
                "conditions": [
                    {"attr": c.attribute, "op": c.operator, "val": str(c.value)}
                    for c in r.conditions
                ],
                "priority": r.priority,
            }
            for r in self._rules
        ]
        blob = json.dumps(rule_data, sort_keys=True)
        self._policy_hash = hashlib.sha256(blob.encode()).hexdigest()

    def clear(self) -> None:
        """Remove all loaded rules."""
        self._rules.clear()
        self._policy_hash = ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_conditions(raw: dict[str, Any]) -> list[ABACCondition]:
    """Parse YAML condition dict into ABACCondition objects."""
    conditions = []
    for attr, value in raw.items():
        if isinstance(value, dict):
            if "after" in value or "before" in value:
                conditions.append(ABACCondition(attr, "time_range", value))
            elif "cidr" in value:
                conditions.append(ABACCondition(attr, "cidr", value["cidr"]))
            elif "pattern" in value:
                conditions.append(ABACCondition(attr, "regex", value["pattern"]))
            elif "not" in value:
                conditions.append(ABACCondition(attr, "not_eq", value["not"]))
            elif "not_in" in value:
                conditions.append(ABACCondition(attr, "not_in", value["not_in"]))
            elif "in" in value:
                conditions.append(ABACCondition(attr, "in", value["in"]))
            else:
                conditions.append(ABACCondition(attr, "eq", value))
        elif isinstance(value, list):
            conditions.append(ABACCondition(attr, "in", value))
        else:
            conditions.append(ABACCondition(attr, "eq", value))
    return conditions


def _context_to_dict(ctx: RequestContext) -> dict[str, Any]:
    """Serialize RequestContext to dict for audit snapshot."""
    result: dict[str, Any] = {}
    for attr in (
        "user_role", "agent_type", "tool_category", "tool_name",
        "data_classification", "source_ip", "session_type",
        "trust_level", "action", "resource",
    ):
        val = getattr(ctx, attr, None)
        if val is not None and val != "" and val != -1:
            result[attr] = val
    if ctx.time_of_day:
        result["time_of_day"] = ctx.time_of_day.isoformat()
    if ctx.extra:
        result["extra"] = ctx.extra
    return result
