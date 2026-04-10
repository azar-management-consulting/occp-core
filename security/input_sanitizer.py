"""Input sanitization layer — runs before Brain processes any message.

OWASP ASI01: Prevents prompt injection, goal hijacking, and identity abuse
across all input channels (Telegram, API, CloudCode).
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SanitizationResult:
    safe: bool
    original: str
    sanitized: str
    threats_detected: list[str]
    risk_score: float  # 0.0 = safe, 1.0 = definite attack


class InputSanitizer:
    """Sanitizes all user input before it reaches the Brain pipeline."""

    # Prompt injection patterns (OWASP ASI01)
    INJECTION_PATTERNS: list[tuple[str, re.Pattern, float]] = [
        ("system_override", re.compile(r"(?:ignore|forget|disregard)\s+(?:all\s+)?(?:previous|prior|above)\s+(?:instructions|rules|prompts)", re.I), 0.95),
        ("role_hijack", re.compile(r"you\s+are\s+(?:now|actually|really)\s+(?:a|an|the)\s+", re.I), 0.8),
        ("system_prompt_leak", re.compile(r"(?:reveal|show|print|output|repeat)\s+(?:your\s+)?(?:system\s+)?(?:prompt|instructions|rules)", re.I), 0.85),
        ("delimiter_injection", re.compile(r"```\s*system\b|<\|system\|>|\[SYSTEM\]|\[INST\]", re.I), 0.9),
        ("encoding_bypass", re.compile(r"(?:base64|rot13|hex)\s*(?:decode|encode)\s*:", re.I), 0.7),
        ("jailbreak_dan", re.compile(r"\bDAN\b.*(?:mode|anything|now|enable)", re.I), 0.95),
        ("identity_override", re.compile(r"(?:from\s+now\s+on|henceforth)\s+(?:you\s+are|act\s+as|pretend)", re.I), 0.85),
        ("tool_abuse", re.compile(r"(?:execute|run|call)\s+(?:bash|shell|exec|system|rm\s+-rf)", re.I), 0.9),
    ]

    # Content that should be stripped (not blocked, just cleaned)
    STRIP_PATTERNS: list[tuple[str, re.Pattern]] = [
        ("invisible_chars", re.compile(r"[\u200b\u200c\u200d\u2060\ufeff]")),  # zero-width chars
        ("excessive_whitespace", re.compile(r"\s{50,}")),  # 50+ consecutive whitespace
        ("null_bytes", re.compile(r"\x00")),
    ]

    # Max input length (prevent resource exhaustion)
    MAX_INPUT_LENGTH = 10000

    def __init__(self, strict: bool = False):
        self._strict = strict
        self._total_checked: int = 0
        self._total_blocked: int = 0

    def sanitize(self, text: str, channel: str = "unknown") -> SanitizationResult:
        """Sanitize input text. Returns SanitizationResult."""
        self._total_checked += 1
        threats: list[str] = []
        risk_score = 0.0

        # Length check
        if len(text) > self.MAX_INPUT_LENGTH:
            text = text[:self.MAX_INPUT_LENGTH]
            threats.append("truncated_overlength")
            risk_score = max(risk_score, 0.3)

        # Strip invisible/malicious characters
        sanitized = text
        for name, pattern in self.STRIP_PATTERNS:
            if pattern.search(sanitized):
                sanitized = pattern.sub("", sanitized)
                threats.append(f"stripped_{name}")
                risk_score = max(risk_score, 0.2)

        # Check injection patterns
        for name, pattern, score in self.INJECTION_PATTERNS:
            if pattern.search(sanitized):
                threats.append(name)
                risk_score = max(risk_score, score)

        # Decision
        safe = risk_score < 0.7 if not self._strict else risk_score < 0.5

        if not safe:
            self._total_blocked += 1
            logger.warning(
                "Input BLOCKED channel=%s threats=%s risk=%.2f text=%s",
                channel, threats, risk_score, sanitized[:100],
            )

        return SanitizationResult(
            safe=safe,
            original=text,
            sanitized=sanitized,
            threats_detected=threats,
            risk_score=risk_score,
        )

    @property
    def stats(self) -> dict[str, Any]:
        return {
            "total_checked": self._total_checked,
            "total_blocked": self._total_blocked,
            "block_rate": self._total_blocked / max(1, self._total_checked),
        }
