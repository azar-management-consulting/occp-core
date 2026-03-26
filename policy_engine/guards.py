"""Built-in security guards for the Policy Engine.

Guards run as part of the Gate stage and can block task execution.
CE includes PII detection, prompt injection detection, and resource limits.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class GuardResult:
    """Outcome of a guard check."""

    passed: bool
    guard_name: str
    detail: str = ""
    matched_patterns: list[str] | None = None


class PIIGuard:
    """Detects common PII patterns in task payloads.

    Checks for: email addresses, phone numbers, SSN-like patterns,
    credit card numbers.
    """

    NAME = "pii_guard"

    PATTERNS: dict[str, re.Pattern[str]] = {
        "email": re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
        "phone": re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"),
        "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        "credit_card": re.compile(
            r"\b(?:4\d{3}|5[1-5]\d{2}|3[47]\d{2}|6(?:011|5\d{2}))"
            r"[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{1,4}\b"
        ),
    }

    # Fields that contain LLM-generated technical content — skip PII scan
    # to avoid false positives on task IDs, token counts, IP addresses, etc.
    SKIP_FIELDS: set[str] = {"plan", "metadata", "capabilities"}

    def check(self, payload: dict[str, Any]) -> GuardResult:
        """Scan *payload* user-facing values for PII patterns.

        Skips LLM-generated fields (plan, metadata, capabilities) to
        avoid false positives on technical content.
        """
        filtered = {k: v for k, v in payload.items() if k not in self.SKIP_FIELDS}
        text = _flatten_to_text(filtered)
        matches: list[str] = []

        for label, pattern in self.PATTERNS.items():
            found = pattern.search(text)
            if found:
                # Credit card: Luhn check to reduce false positives
                if label == "credit_card" and not _luhn_check(found.group()):
                    continue
                matches.append(label)

        if matches:
            return GuardResult(
                passed=False,
                guard_name=self.NAME,
                detail=f"PII detected: {', '.join(matches)}",
                matched_patterns=matches,
            )
        return GuardResult(passed=True, guard_name=self.NAME)


class PromptInjectionGuard:
    """Detects prompt injection, jailbreak, and manipulation patterns."""

    NAME = "prompt_injection_guard"

    SUSPICIOUS_PATTERNS: list[re.Pattern[str]] = [
        # Classic instruction override
        re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.I),
        re.compile(r"disregard\s+(all\s+)?(prior|previous|above)\s+", re.I),
        re.compile(r"forget\s+(all\s+)?(your|the)\s+(instructions|rules|guidelines)", re.I),
        # Role manipulation
        re.compile(r"you\s+are\s+now\s+(a|an)\s+", re.I),
        re.compile(r"act\s+as\s+(if\s+you\s+are|a|an)\s+", re.I),
        re.compile(r"pretend\s+(to\s+be|you\s+are)\s+", re.I),
        re.compile(r"roleplay\s+as\s+", re.I),
        # System prompt / delimiter injection
        re.compile(r"system\s*:\s*", re.I),
        re.compile(r"<\s*/?system\s*>", re.I),
        re.compile(r"\[INST\]|\[/INST\]", re.I),
        re.compile(r"<<\s*SYS\s*>>|<<\s*/SYS\s*>>", re.I),
        re.compile(r"###\s*(system|instruction|human|assistant)\s*:", re.I),
        # Authority claims
        re.compile(r"ADMIN\s+OVERRIDE", re.I),
        re.compile(r"(developer|maintenance|debug)\s+mode\s*(enabled|activated|on)", re.I),
        re.compile(r"emergency\s+protocol", re.I),
        # DAN / jailbreak patterns
        re.compile(r"\bDAN\b.*\b(mode|enabled|jailbreak)", re.I),
        re.compile(r"do\s+anything\s+now", re.I),
        re.compile(r"jailbreak(ed|ing)?", re.I),
        # Output manipulation
        re.compile(r"begin\s+your\s+(response|answer|output)\s+with", re.I),
        re.compile(r"respond\s+(only\s+)?with\s+(yes|no|true|false|ok)", re.I),
        # Encoded / obfuscated injection
        re.compile(r"base64\s*:\s*[A-Za-z0-9+/=]{20,}", re.I),
        re.compile(r"hex\s*:\s*[0-9a-fA-F]{20,}", re.I),
    ]

    def check(self, payload: dict[str, Any]) -> GuardResult:
        """Scan *payload* for prompt injection indicators."""
        text = _flatten_to_text(payload)
        matches: list[str] = []

        for pat in self.SUSPICIOUS_PATTERNS:
            if pat.search(text):
                matches.append(pat.pattern)

        if matches:
            return GuardResult(
                passed=False,
                guard_name=self.NAME,
                detail=f"Prompt injection patterns detected ({len(matches)})",
                matched_patterns=matches,
            )
        return GuardResult(passed=True, guard_name=self.NAME)


class OutputSanitizationGuard:
    """Post-execution guard – scans executor output for PII leakage.

    Unlike PIIGuard (pre-gate), this runs after execution to catch
    PII that may have been introduced by the executor itself.
    """

    NAME = "output_sanitization_guard"

    PATTERNS: dict[str, re.Pattern[str]] = {
        "email": re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
        "phone": re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"),
        "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        "credit_card": re.compile(
            r"\b(?:4\d{3}|5[1-5]\d{2}|3[47]\d{2}|6(?:011|5\d{2}))"
            r"[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{1,4}\b"
        ),
        "ip_address": re.compile(
            r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}"
            r"(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b"
        ),
        "api_key": re.compile(
            r"(?:sk|pk|api[_-]?key|token|secret)[_-]?[a-zA-Z0-9_-]{20,}", re.I
        ),
        "jwt": re.compile(r"eyJ[a-zA-Z0-9_-]{10,}\.eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]+"),
    }

    def __init__(self, *, allowed: set[str] | None = None) -> None:
        self._allowed = allowed or set()

    def check(self, output: dict[str, Any]) -> GuardResult:
        """Scan execution *output* for PII / secret leakage."""
        text = _flatten_to_text(output)
        matches: list[str] = []

        for label, pattern in self.PATTERNS.items():
            if label in self._allowed:
                continue
            found = pattern.search(text)
            if found:
                if label == "credit_card" and not _luhn_check(found.group()):
                    continue
                matches.append(label)

        if matches:
            return GuardResult(
                passed=False,
                guard_name=self.NAME,
                detail=f"Output contains sensitive data: {', '.join(matches)}",
                matched_patterns=matches,
            )
        return GuardResult(passed=True, guard_name=self.NAME)


class ResourceLimitGuard:
    """Enforces resource limits on task parameters."""

    NAME = "resource_limit_guard"

    def __init__(
        self,
        max_timeout_seconds: int = 600,
        max_output_bytes: int = 10 * 1024 * 1024,  # 10 MB
    ) -> None:
        self.max_timeout_seconds = max_timeout_seconds
        self.max_output_bytes = max_output_bytes

    def check(self, payload: dict[str, Any]) -> GuardResult:
        """Check that requested resources are within limits."""
        issues: list[str] = []

        timeout = payload.get("timeout_seconds", 0)
        if isinstance(timeout, (int, float)) and timeout > self.max_timeout_seconds:
            issues.append(
                f"timeout {timeout}s exceeds max {self.max_timeout_seconds}s"
            )

        max_out = payload.get("max_output_bytes", 0)
        if isinstance(max_out, (int, float)) and max_out > self.max_output_bytes:
            issues.append(
                f"output limit {max_out}B exceeds max {self.max_output_bytes}B"
            )

        if issues:
            return GuardResult(
                passed=False,
                guard_name=self.NAME,
                detail="; ".join(issues),
            )
        return GuardResult(passed=True, guard_name=self.NAME)


class HumanOversightGuard:
    """Enforces human-in-the-loop for sensitive operations.

    Operations requiring human approval:
    - Policy changes (runtime policy modifications)
    - Agent activation (new agent types enabled)
    - Skills outside sandbox (unverified/untrusted skills)

    The flag is stored per-session and checked by the pipeline Gate stage.
    """

    NAME = "human_oversight_guard"

    # Actions that always require human approval
    OVERSIGHT_REQUIRED: set[str] = {
        "policy.update",
        "policy.delete",
        "agent.activate",
        "agent.register",
        "skill.enable_untrusted",
        "skill.enable_unsandboxed",
        "governance.override",
        "token.rotate_all",
    }

    def __init__(self, *, enabled: bool = True) -> None:
        self._enabled = enabled
        self._approved_actions: set[str] = set()

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value

    def requires_approval(self, action: str) -> bool:
        """Check if an action requires human approval."""
        if not self._enabled:
            return False
        return action in self.OVERSIGHT_REQUIRED and action not in self._approved_actions

    def approve(self, action: str) -> None:
        """Record human approval for an action (single-use)."""
        self._approved_actions.add(action)

    def revoke_approval(self, action: str) -> None:
        """Revoke previous approval."""
        self._approved_actions.discard(action)

    def clear_approvals(self) -> None:
        """Clear all recorded approvals (session reset)."""
        self._approved_actions.clear()

    def check(self, payload: dict[str, Any]) -> GuardResult:
        """Check if the action in payload requires and has human approval."""
        if not self._enabled:
            return GuardResult(passed=True, guard_name=self.NAME)

        action = payload.get("action", "")
        if not action:
            return GuardResult(passed=True, guard_name=self.NAME)

        if self.requires_approval(action):
            return GuardResult(
                passed=False,
                guard_name=self.NAME,
                detail=f"Action '{action}' requires human approval before execution",
            )
        return GuardResult(passed=True, guard_name=self.NAME)

    def to_dict(self) -> dict[str, Any]:
        """Serialize state for audit/persistence."""
        return {
            "enabled": self._enabled,
            "oversight_actions": sorted(self.OVERSIGHT_REQUIRED),
            "approved_actions": sorted(self._approved_actions),
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _luhn_check(raw: str) -> bool:
    """Validate a number string with the Luhn algorithm (ISO/IEC 7812)."""
    digits = [int(c) for c in raw if c.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False
    checksum = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


def _flatten_to_text(data: Any, _depth: int = 0) -> str:
    """Recursively flatten a dict/list to a single text blob for scanning."""
    if _depth > 10:
        return ""
    if isinstance(data, str):
        return data
    if isinstance(data, dict):
        return " ".join(_flatten_to_text(v, _depth + 1) for v in data.values())
    if isinstance(data, (list, tuple)):
        return " ".join(_flatten_to_text(v, _depth + 1) for v in data)
    return str(data)
