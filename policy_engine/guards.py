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
        "credit_card": re.compile(r"\b(?:\d[ -]*?){13,16}\b"),
    }

    def check(self, payload: dict[str, Any]) -> GuardResult:
        """Scan *payload* values for PII patterns."""
        text = _flatten_to_text(payload)
        matches: list[str] = []

        for label, pattern in self.PATTERNS.items():
            if pattern.search(text):
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
    """Detects common prompt injection patterns."""

    NAME = "prompt_injection_guard"

    SUSPICIOUS_PATTERNS: list[re.Pattern[str]] = [
        re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.I),
        re.compile(r"you\s+are\s+now\s+(a|an)\s+", re.I),
        re.compile(r"system\s*:\s*", re.I),
        re.compile(r"<\s*/?system\s*>", re.I),
        re.compile(r"ADMIN\s+OVERRIDE", re.I),
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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
