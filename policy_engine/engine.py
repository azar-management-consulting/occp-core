"""Core Policy Engine – evaluates tasks against loaded policies and guards.

REQ-POL-02: Structured decision records with full audit trail.
REQ-GOV-02: Policy-as-Code with YAML loading and version hash tracking.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from policy_engine.abac import (
    ABACDecision,
    ABACEvaluator,
    Effect,
    RequestContext,
)
from policy_engine.exceptions import PolicyLoadError
from policy_engine.guards import (
    GuardResult,
    HumanOversightGuard,
    OutputSanitizationGuard,
    PIIGuard,
    PromptInjectionGuard,
    ResourceLimitGuard,
)
from policy_engine.models import AuditEntry, Policy, PolicyRule, RuleAction

logger = logging.getLogger(__name__)


@dataclass
class GateResult:
    """Outcome of the Gate evaluation.

    Extended for REQ-POL-02 with structured decision records
    and REQ-GOV-02 with policy hash tracking.
    """

    approved: bool
    reason: str = ""
    violated_rules: list[str] = field(default_factory=list)
    guard_results: list[GuardResult] = field(default_factory=list)
    policy_hash: str = ""
    abac_decision: ABACDecision | None = None

    def to_decision_record(self) -> dict[str, Any]:
        """Structured decision record for audit trail (REQ-POL-02).

        Contains all information needed for decision replay:
        same input + same policy_hash = same output.
        """
        record: dict[str, Any] = {
            "approved": self.approved,
            "reason": self.reason,
            "policy_hash": self.policy_hash,
            "violated_rules": self.violated_rules,
            "guards": [
                {
                    "name": g.guard_name,
                    "passed": g.passed,
                    "detail": g.detail,
                }
                for g in self.guard_results
            ],
        }
        if self.abac_decision is not None:
            record["abac"] = self.abac_decision.to_audit_dict()
        return record


class PolicyEngine:
    """Evaluates tasks through loaded policies and built-in guards.

    REQ-POL-02: Emits structured decision records with policy version hash.
    REQ-GOV-02: Supports YAML policy files alongside JSON.

    Usage::

        engine = PolicyEngine()
        engine.load_policy_file("policies/default.json")   # JSON
        engine.load_policy_file("policies/abac.yaml")      # YAML
        result = await engine.evaluate(task)
        record = result.to_decision_record()  # structured audit
    """

    def __init__(self, audit_store: Any = None) -> None:
        self._policies: list[Policy] = []
        self._guards = [
            PIIGuard(),
            PromptInjectionGuard(),
            ResourceLimitGuard(),
            OutputSanitizationGuard(),
            HumanOversightGuard(),
        ]
        self._audit_chain: list[AuditEntry] = []
        self._audit_store = audit_store  # Optional AuditStore for persistence
        self._abac_evaluator: ABACEvaluator | None = None
        self._policy_hash = ""

    @property
    def guard_count(self) -> int:
        """Number of loaded guards."""
        return len(self._guards)

    @property
    def policy_hash(self) -> str:
        """SHA-256 hash of all loaded policies + ABAC rules (REQ-GOV-02)."""
        return self._policy_hash

    @property
    def abac_evaluator(self) -> ABACEvaluator | None:
        """The ABAC evaluator, if configured."""
        return self._abac_evaluator

    def set_abac_evaluator(self, evaluator: ABACEvaluator) -> None:
        """Attach an ABAC evaluator for context-dependent decisions."""
        self._abac_evaluator = evaluator
        self._recompute_policy_hash()

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
        """Load a policy file (JSON or YAML) and register it.

        REQ-GOV-02: Supports both JSON (.json) and YAML (.yaml/.yml) formats.
        YAML files with an ``abac_rules`` or ``rules`` key containing ABAC
        condition dicts are loaded into the ABAC evaluator.
        """
        p = Path(path)
        if not p.exists():
            raise PolicyLoadError(str(p), "file not found")

        suffix = p.suffix.lower()
        if suffix in (".yaml", ".yml"):
            return self._load_yaml_policy(p)
        return self._load_json_policy(p)

    def _load_json_policy(self, p: Path) -> Policy:
        """Load a JSON policy file (original format)."""
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
        self._recompute_policy_hash()
        logger.info("Loaded JSON policy '%s' v%s (%d rules)", policy.name, policy.version, len(rules))
        return policy

    def _load_yaml_policy(self, p: Path) -> Policy:
        """Load a YAML policy file (REQ-GOV-02).

        Supports two formats:
        1. Standard policy rules (same schema as JSON but in YAML)
        2. ABAC rules (loaded into ABAC evaluator)
        """
        import yaml  # Lazy import — yaml is optional dependency

        try:
            data = yaml.safe_load(p.read_text(encoding="utf-8"))
        except Exception as exc:
            raise PolicyLoadError(str(p), str(exc)) from exc

        if not data:
            raise PolicyLoadError(str(p), "empty or invalid YAML")

        policy_name = data.get("name", p.stem)
        policy_version = data.get("version", "1.0")
        description = data.get("description", "")

        # Load ABAC rules if present
        abac_count = 0
        if "abac_rules" in data or (
            "rules" in data
            and data["rules"]
            and isinstance(data["rules"][0].get("conditions", None), dict)
            and "effect" in data["rules"][0]
        ):
            if self._abac_evaluator is None:
                self._abac_evaluator = ABACEvaluator()
            abac_count = self._abac_evaluator.load_rules_from_yaml(p)

        # Load standard policy rules if present
        std_rules: list[PolicyRule] = []
        for r in data.get("policy_rules", []):
            std_rules.append(PolicyRule(
                id=r["id"],
                description=r.get("description", ""),
                action=RuleAction(r["action"]),
                conditions=r.get("conditions", {}),
                metadata=r.get("metadata", {}),
            ))

        policy = Policy(
            name=policy_name,
            version=policy_version,
            rules=std_rules,
            description=description,
        )
        self._policies.append(policy)
        self._recompute_policy_hash()
        logger.info(
            "Loaded YAML policy '%s' v%s (%d std rules, %d ABAC rules)",
            policy_name, policy_version, len(std_rules), abac_count,
        )
        return policy

    def add_policy(self, policy: Policy) -> None:
        """Register a programmatically created policy."""
        self._policies.append(policy)
        self._recompute_policy_hash()

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    async def evaluate(self, task: Any) -> GateResult:
        """Run all guards, policy rules, and ABAC rules against *task*.

        REQ-POL-02: Emits structured decision records.
        REQ-GOV-02: Includes policy hash for decision replay.

        Returns a :class:`GateResult` with ``approved=True`` only if
        **all** guards pass, no DENY rule matches, and ABAC allows.
        """
        guard_results: list[GuardResult] = []
        payload = _task_to_payload(task)

        # Phase 1: Run guards
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

        # Phase 2: Run standard policy rules
        violated: list[str] = []
        requires_approval = False

        for policy in self._policies:
            for rule in policy.rules:
                if _rule_matches(rule, payload):
                    if rule.action == RuleAction.DENY:
                        violated.append(rule.id)
                    elif rule.action == RuleAction.REQUIRE_APPROVAL:
                        requires_approval = True

        # Phase 3: Run ABAC evaluation (REQ-POL-01 integration)
        abac_decision: ABACDecision | None = None
        if self._abac_evaluator and self._abac_evaluator.rule_count > 0:
            ctx = _build_abac_context(task, payload)
            abac_decision = self._abac_evaluator.evaluate(ctx)

            if abac_decision.denied:
                violated.extend(abac_decision.matched_rules)
            elif abac_decision.effect == Effect.REQUIRE_APPROVAL:
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
                policy_hash=self._policy_hash,
                abac_decision=abac_decision,
            )
        elif requires_approval:
            result = GateResult(
                approved=False,
                reason="Manual approval required by policy",
                guard_results=guard_results,
                policy_hash=self._policy_hash,
                abac_decision=abac_decision,
            )
        else:
            result = GateResult(
                approved=True,
                guard_results=guard_results,
                policy_hash=self._policy_hash,
                abac_decision=abac_decision,
            )

        # Audit – structured decision record (REQ-POL-02)
        entry = self._append_audit(
            actor="policy_engine",
            action="gate_evaluation",
            task_id=getattr(task, "id", ""),
            detail=result.to_decision_record(),
        )
        if self._audit_store:
            await self._audit_store.append(entry)

        return result

    # ------------------------------------------------------------------
    # Audit
    # ------------------------------------------------------------------

    async def audit(
        self,
        *,
        actor: str,
        action: str,
        task_id: str = "",
        detail: dict[str, Any] | None = None,
        audit_store: Any = None,
    ) -> AuditEntry:
        """Public audit method — append to chain and optionally persist.

        Use this for non-gate events (token operations, onboarding steps, etc.)
        that still need hash-chained audit trail integrity.
        """
        entry = self._append_audit(
            actor=actor,
            action=action,
            task_id=task_id,
            detail=detail or {},
        )
        store = audit_store or self._audit_store
        if store:
            await store.append(entry)
        return entry

    def _recompute_policy_hash(self) -> None:
        """Recompute the combined SHA-256 hash of all policies + ABAC rules.

        REQ-GOV-02: Policy version tracking for decision replay.
        """
        parts: list[str] = []

        # Standard policies
        for p in self._policies:
            policy_blob = json.dumps({
                "name": p.name,
                "version": p.version,
                "rules": [
                    {"id": r.id, "action": r.action.value, "conditions": r.conditions}
                    for r in p.rules
                ],
            }, sort_keys=True)
            parts.append(policy_blob)

        # ABAC evaluator hash
        if self._abac_evaluator:
            parts.append(f"abac:{self._abac_evaluator.policy_hash}")

        combined = "|".join(parts)
        self._policy_hash = hashlib.sha256(combined.encode()).hexdigest()

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
        """Verify integrity of the in-memory audit hash chain."""
        return self.verify_entries(self._audit_chain)

    @staticmethod
    def verify_entries(entries: list[AuditEntry]) -> bool:
        """Verify integrity of any audit entry list (in-memory or persistent)."""
        if not entries:
            return True
        prev = ""
        for entry in entries:
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
    for attr in ("name", "description", "agent_type", "plan", "metadata", "capabilities"):
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


def _build_abac_context(task: Any, payload: dict[str, Any]) -> RequestContext:
    """Build ABAC RequestContext from a task and its payload.

    Attempts RequestContext.from_task() first, then falls back to
    building from the payload dict.
    """
    if hasattr(task, "agent_type") or hasattr(task, "metadata"):
        try:
            return RequestContext.from_task(task)
        except Exception:
            pass

    # Fallback: build from payload
    ctx_data: dict[str, Any] = {}
    for key in ("user_role", "agent_type", "tool_category", "tool_name",
                "data_classification", "source_ip", "session_type",
                "trust_level", "action", "resource"):
        if key in payload:
            ctx_data[key] = payload[key]
        elif "metadata" in payload and isinstance(payload["metadata"], dict):
            if key in payload["metadata"]:
                ctx_data[key] = payload["metadata"][key]

    return RequestContext.from_dict(ctx_data)
