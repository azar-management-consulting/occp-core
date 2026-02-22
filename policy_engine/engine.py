"""Core Policy Engine – evaluates tasks against loaded policies and guards."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from policy_engine.exceptions import PolicyLoadError
from policy_engine.guards import (
    GuardResult,
    PIIGuard,
    PromptInjectionGuard,
    ResourceLimitGuard,
)
from policy_engine.models import AuditEntry, Policy, PolicyRule, RuleAction

logger = logging.getLogger(__name__)


@dataclass
class GateResult:
    """Outcome of the Gate evaluation."""

    approved: bool
    reason: str = ""
    violated_rules: list[str] = field(default_factory=list)
    guard_results: list[GuardResult] = field(default_factory=list)


class PolicyEngine:
    """Evaluates tasks through loaded policies and built-in guards.

    Usage::

        engine = PolicyEngine()
        engine.load_policy_file("policies/default.json")
        result = await engine.evaluate(task)
    """

    def __init__(self, audit_store: Any = None) -> None:
        self._policies: list[Policy] = []
        self._guards = [
            PIIGuard(),
            PromptInjectionGuard(),
            ResourceLimitGuard(),
        ]
        self._audit_chain: list[AuditEntry] = []
        self._audit_store = audit_store  # Optional AuditStore for persistence

    # ------------------------------------------------------------------
    # Chain head management (for restart continuity)
    # ------------------------------------------------------------------

    def set_chain_head(self, entry: AuditEntry) -> None:
        """Set the last known audit entry for hash chain continuity on restart."""
        if not self._audit_chain:
            self._audit_chain.append(entry)

    # ------------------------------------------------------------------
    # Policy loading
    # ------------------------------------------------------------------

    def load_policy_file(self, path: str | Path) -> Policy:
        """Load a JSON policy file and register it."""
        p = Path(path)
        if not p.exists():
            raise PolicyLoadError(str(p), "file not found")

        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise PolicyLoadError(str(p), str(exc)) from exc

        rules = [
            PolicyRule(
                id=r["id"],
                description=r.get("description", ""),
                action=RuleAction(r["action"]),
                conditions=r.get("conditions", {}),
                metadata=r.get("metadata", {}),
            )
            for r in data.get("rules", [])
        ]

        policy = Policy(
            name=data["name"],
            version=data.get("version", "1.0"),
            rules=rules,
            description=data.get("description", ""),
        )
        self._policies.append(policy)
        logger.info("Loaded policy '%s' v%s (%d rules)", policy.name, policy.version, len(rules))
        return policy

    def add_policy(self, policy: Policy) -> None:
        """Register a programmatically created policy."""
        self._policies.append(policy)

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    async def evaluate(self, task: Any) -> GateResult:
        """Run all guards and policy rules against *task*.

        Returns a :class:`GateResult` with ``approved=True`` only if
        **all** guards pass and no DENY rule matches.
        """
        guard_results: list[GuardResult] = []
        payload = _task_to_payload(task)

        # Run guards
        for guard in self._guards:
            gr = guard.check(payload)
            guard_results.append(gr)
            if not gr.passed:
                logger.warning(
                    "Guard %s failed for task=%s: %s",
                    gr.guard_name,
                    getattr(task, "id", "?"),
                    gr.detail,
                )

        failed_guards = [g for g in guard_results if not g.passed]

        # Run policy rules
        violated: list[str] = []
        requires_approval = False

        for policy in self._policies:
            for rule in policy.rules:
                if _rule_matches(rule, payload):
                    if rule.action == RuleAction.DENY:
                        violated.append(rule.id)
                    elif rule.action == RuleAction.REQUIRE_APPROVAL:
                        requires_approval = True

        # Build result
        if failed_guards or violated:
            reasons: list[str] = []
            if failed_guards:
                reasons.append(
                    f"Guards failed: {', '.join(g.guard_name for g in failed_guards)}"
                )
            if violated:
                reasons.append(f"Policy violations: {', '.join(violated)}")
            result = GateResult(
                approved=False,
                reason="; ".join(reasons),
                violated_rules=violated,
                guard_results=guard_results,
            )
        elif requires_approval:
            result = GateResult(
                approved=False,
                reason="Manual approval required by policy",
                guard_results=guard_results,
            )
        else:
            result = GateResult(approved=True, guard_results=guard_results)

        # Audit – in-memory chain + optional persistent store
        entry = self._append_audit(
            actor="policy_engine",
            action="gate_evaluation",
            task_id=getattr(task, "id", ""),
            detail={"approved": result.approved, "reason": result.reason},
        )
        if self._audit_store:
            await self._audit_store.append(entry)

        return result

    # ------------------------------------------------------------------
    # Audit
    # ------------------------------------------------------------------

    def _append_audit(self, **kwargs: Any) -> AuditEntry:
        prev_hash = self._audit_chain[-1].hash if self._audit_chain else ""
        entry = AuditEntry(**kwargs)
        entry.compute_hash(prev_hash)
        self._audit_chain.append(entry)
        return entry

    @property
    def audit_log(self) -> list[AuditEntry]:
        return list(self._audit_chain)

    def verify_audit_chain(self) -> bool:
        """Verify integrity of the audit hash chain."""
        prev = ""
        for entry in self._audit_chain:
            expected = AuditEntry(
                id=entry.id,
                timestamp=entry.timestamp,
                actor=entry.actor,
                action=entry.action,
                task_id=entry.task_id,
                detail=entry.detail,
            )
            expected.compute_hash(prev)
            if expected.hash != entry.hash:
                return False
            prev = entry.hash
        return True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _task_to_payload(task: Any) -> dict[str, Any]:
    """Extract a dict payload from a Task object."""
    if isinstance(task, dict):
        return task
    payload: dict[str, Any] = {}
    for attr in ("name", "description", "agent_type", "plan", "metadata"):
        if hasattr(task, attr):
            payload[attr] = getattr(task, attr)
    return payload


def _rule_matches(rule: PolicyRule, payload: dict[str, Any]) -> bool:
    """Simple condition matcher – checks equality of condition keys."""
    if not rule.conditions:
        return True
    for key, expected in rule.conditions.items():
        actual = payload.get(key)
        if actual != expected:
            return False
    return True
