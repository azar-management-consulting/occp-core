"""Quality Gate — cross-review and automated checks for agent outputs.

Ensures all agent outputs meet quality standards before delivery to Henry.
Supports self-review, cross-review (agent-to-agent), brain-level review,
and automated checks per agent type.

Integration:
- Pipeline: runs after EXECUTE, before VALIDATE
- FeedbackLoop: records quality outcomes for agent performance tracking
"""

from __future__ import annotations

import asyncio
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class QualityCheck:
    """Result of a single quality check on agent output."""

    check_id: str
    agent_id: str
    task_id: str
    check_type: str  # "self_review"|"cross_review"|"brain_review"|"automated"
    status: str  # "pending"|"passed"|"failed"|"needs_revision"
    score: float  # 0.0-1.0
    feedback: str
    reviewer: str  # agent_id or "brain" or "automated"
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "agent_id": self.agent_id,
            "task_id": self.task_id,
            "check_type": self.check_type,
            "status": self.status,
            "score": self.score,
            "feedback": self.feedback,
            "reviewer": self.reviewer,
            "timestamp": self.timestamp.isoformat(),
        }


# ---------------------------------------------------------------------------
# Quality Gate
# ---------------------------------------------------------------------------


# Placeholder markers that should not appear in production output
_PLACEHOLDER_PATTERNS = [
    r"\[TODO\]",
    r"\[PLACEHOLDER\]",
    r"\[INSERT\s",
    r"Lorem ipsum",
    r"\[TBD\]",
    r"\[FIXME\]",
]

# Common secret patterns (simplified)
_SECRET_PATTERNS = [
    r"(?:api[_-]?key|secret|token|password)\s*[:=]\s*['\"][^'\"]{8,}['\"]",
    r"sk-[a-zA-Z0-9]{20,}",
    r"ghp_[a-zA-Z0-9]{36}",
    r"AKIA[A-Z0-9]{16}",
]

# Destructive command patterns
_DESTRUCTIVE_PATTERNS = [
    r"\brm\s+-rf\s+/",
    r"\bdd\s+if=",
    r"\bmkfs\b",
    r"\bgit\s+push\s+--force\s+.*main",
    r"\bgit\s+reset\s+--hard\b",
    r"\bdrop\s+database\b",
    r"\bdrop\s+table\b",
]

# Hallucination markers
_HALLUCINATION_MARKERS = [
    r"(?i)as\s+an?\s+AI\s+language\s+model",
    r"(?i)I\s+cannot\s+actually",
    r"(?i)I\s+don'?t\s+have\s+access",
    r"(?i)hypothetical",
    r"(?i)made-?up",
]


class QualityGate:
    """Ensures all agent outputs meet quality standards before delivery.

    Orchestrates three layers of quality checking:
    1. Automated checks (syntax, secrets, lint, content rules)
    2. Cross-review (peer agent evaluates output)
    3. Brain final review (aggregates all checks, decides pass/fail)
    """

    # Which agents review which
    CROSS_REVIEW_MAP: dict[str, list[str]] = {
        "eng-core": ["wp-web"],
        "wp-web": ["eng-core"],
        "content-forge": ["social-growth"],
        "social-growth": ["content-forge"],
        "design-lab": ["wp-web"],
        "biz-strategy": ["intel-research"],
        "intel-research": ["biz-strategy"],
        "infra-ops": ["eng-core"],
    }

    # Automated checks per agent type
    AUTOMATED_CHECKS: dict[str, list[str]] = {
        "eng-core": ["syntax_valid", "tests_pass", "no_secrets", "lint_clean"],
        "wp-web": ["syntax_valid", "no_secrets", "wp_standards"],
        "infra-ops": ["no_secrets", "no_destructive_commands", "backup_exists"],
        "content-forge": ["min_length", "no_placeholder", "brand_consistent"],
        "social-growth": ["char_limit", "cta_present", "no_placeholder"],
        "design-lab": ["file_format_valid", "responsive_check"],
        "intel-research": ["has_sources", "min_depth", "no_hallucination_markers"],
        "biz-strategy": ["has_pricing", "has_roi", "professional_tone"],
    }

    # Minimum score thresholds
    PASS_THRESHOLD: float = 0.7
    BRAIN_OVERRIDE_THRESHOLD: float = 0.5

    def __init__(
        self,
        *,
        cross_review_handler: Callable[..., Any] | None = None,
        max_revision_rounds: int = 2,
    ) -> None:
        """Initialize the QualityGate.

        Args:
            cross_review_handler: Optional async callable that dispatches
                cross-review requests to peer agents. Signature:
                ``(reviewer_agent_id, task_id, output) -> QualityCheck``
            max_revision_rounds: Maximum revision attempts before forced fail.
        """
        self._cross_review_handler = cross_review_handler
        self._max_revision_rounds = max_revision_rounds
        # task_id -> list of QualityCheck
        self._check_store: dict[str, list[QualityCheck]] = {}
        # Stats
        self._total_checks: int = 0
        self._total_passed: int = 0
        self._total_failed: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run_quality_gate(
        self,
        agent_id: str,
        task_id: str,
        output: dict[str, Any],
    ) -> list[QualityCheck]:
        """Run the full quality gate pipeline for an agent's output.

        Runs automated checks and cross-review in parallel, then
        executes the brain final review.

        Returns:
            List of all QualityCheck results.
        """
        # Run automated + cross-review in parallel
        automated_task = self.run_automated_checks(agent_id, task_id, output)
        cross_task = self.request_cross_review(agent_id, task_id, output)

        automated_checks, cross_check = await asyncio.gather(
            automated_task, cross_task
        )

        all_checks = list(automated_checks)
        if cross_check is not None:
            all_checks.append(cross_check)

        # Store checks
        if task_id not in self._check_store:
            self._check_store[task_id] = []
        self._check_store[task_id].extend(all_checks)

        self._total_checks += len(all_checks)

        return all_checks

    async def request_cross_review(
        self,
        agent_id: str,
        task_id: str,
        output: dict[str, Any],
    ) -> QualityCheck | None:
        """Request a cross-review from a peer agent.

        Returns None if no cross-review is configured for this agent type.
        """
        reviewers = self.CROSS_REVIEW_MAP.get(agent_id)
        if not reviewers:
            return None

        reviewer_id = reviewers[0]  # Primary reviewer

        # If we have a handler, delegate to it
        if self._cross_review_handler is not None:
            try:
                result = await self._cross_review_handler(
                    reviewer_id, task_id, output
                )
                if isinstance(result, QualityCheck):
                    return result
            except Exception as exc:
                logger.warning(
                    "Cross-review handler failed for task=%s reviewer=%s: %s",
                    task_id,
                    reviewer_id,
                    exc,
                )

        # Default: create a pending cross-review check
        return QualityCheck(
            check_id=uuid.uuid4().hex[:12],
            agent_id=agent_id,
            task_id=task_id,
            check_type="cross_review",
            status="pending",
            score=0.0,
            feedback=f"Cross-review requested from {reviewer_id}",
            reviewer=reviewer_id,
        )

    async def run_automated_checks(
        self,
        agent_id: str,
        task_id: str,
        output: dict[str, Any],
    ) -> list[QualityCheck]:
        """Run all automated checks for an agent type.

        Returns:
            List of QualityCheck results, one per check.
        """
        check_names = self.AUTOMATED_CHECKS.get(agent_id, [])
        if not check_names:
            return []

        results: list[QualityCheck] = []
        content = self._extract_content(output)

        for check_name in check_names:
            checker = self._get_checker(check_name)
            passed, feedback = checker(content, output)
            score = 1.0 if passed else 0.0
            status = "passed" if passed else "failed"

            results.append(
                QualityCheck(
                    check_id=uuid.uuid4().hex[:12],
                    agent_id=agent_id,
                    task_id=task_id,
                    check_type="automated",
                    status=status,
                    score=score,
                    feedback=feedback,
                    reviewer="automated",
                )
            )

        return results

    async def brain_final_review(
        self,
        task_id: str,
        all_checks: list[QualityCheck],
    ) -> bool:
        """Brain aggregates all checks and decides pass/fail.

        Pass criteria:
        - No failed automated checks with score 0.0
        - Average score >= PASS_THRESHOLD
        - OR if average >= BRAIN_OVERRIDE_THRESHOLD and no critical failures

        Returns:
            True if the output passes the brain review.
        """
        if not all_checks:
            return True  # No checks = pass

        # Filter out pending checks
        completed = [c for c in all_checks if c.status != "pending"]
        if not completed:
            return True  # Only pending = pass (optimistic)

        # Check for hard failures (automated checks that failed)
        hard_failures = [
            c for c in completed
            if c.check_type == "automated" and c.status == "failed"
        ]

        # Calculate average score
        avg_score = sum(c.score for c in completed) / len(completed)

        # Store brain review check
        brain_passed = len(hard_failures) == 0 and avg_score >= self.PASS_THRESHOLD
        # Security-critical checks cannot be overridden
        _CRITICAL_CHECKS = {"no_secrets", "no_destructive_commands"}
        critical_failures = [
            c for c in hard_failures
            if any(cc in c.feedback.lower() for cc in ("secret", "destructive"))
            or c.check_id in _CRITICAL_CHECKS
        ]
        brain_override = (
            len(hard_failures) <= 1
            and len(critical_failures) == 0
            and avg_score >= self.BRAIN_OVERRIDE_THRESHOLD
        )

        passed = brain_passed or brain_override

        brain_check = QualityCheck(
            check_id=uuid.uuid4().hex[:12],
            agent_id="brain",
            task_id=task_id,
            check_type="brain_review",
            status="passed" if passed else "failed",
            score=avg_score,
            feedback=(
                f"Brain review: avg_score={avg_score:.2f}, "
                f"hard_failures={len(hard_failures)}, "
                f"total_checks={len(completed)}"
            ),
            reviewer="brain",
        )

        if task_id not in self._check_store:
            self._check_store[task_id] = []
        self._check_store[task_id].append(brain_check)

        if passed:
            self._total_passed += 1
        else:
            self._total_failed += 1

        logger.info(
            "Brain review for task=%s: passed=%s avg_score=%.2f hard_failures=%d",
            task_id,
            passed,
            avg_score,
            len(hard_failures),
        )

        return passed

    def needs_revision(self, checks: list[QualityCheck]) -> bool:
        """Determine if the output needs revision based on check results.

        Returns True if any automated check failed or average score is
        below the pass threshold.
        """
        if not checks:
            return False

        completed = [c for c in checks if c.status != "pending"]
        if not completed:
            return False

        has_failures = any(
            c.status == "failed" and c.check_type == "automated"
            for c in completed
        )
        if has_failures:
            return True

        avg_score = sum(c.score for c in completed) / len(completed)
        return avg_score < self.PASS_THRESHOLD

    def get_revision_instructions(self, checks: list[QualityCheck]) -> str:
        """Generate revision instructions from failed checks.

        Returns a human-readable string describing what needs to be fixed.
        """
        failed = [c for c in checks if c.status == "failed"]
        if not failed:
            return "No revisions needed."

        lines = ["The following quality checks failed:"]
        for i, check in enumerate(failed, 1):
            lines.append(
                f"  {i}. [{check.check_type}] {check.feedback} "
                f"(reviewer: {check.reviewer})"
            )
        lines.append("")
        lines.append("Please address each issue and resubmit.")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_checks(self, task_id: str) -> list[QualityCheck]:
        """Return all quality checks for a task."""
        return list(self._check_store.get(task_id, []))

    def get_stats(self) -> dict[str, Any]:
        """Return quality gate statistics."""
        return {
            "total_checks": self._total_checks,
            "total_passed": self._total_passed,
            "total_failed": self._total_failed,
            "tasks_tracked": len(self._check_store),
        }

    # ------------------------------------------------------------------
    # Automated check implementations
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_content(output: dict[str, Any]) -> str:
        """Extract text content from agent output for checking."""
        # Try common output keys
        for key in ("content", "text", "code", "body", "output", "result"):
            val = output.get(key)
            if isinstance(val, str) and val:
                return val
        # Fallback: serialize the whole output
        import json
        return json.dumps(output, default=str)

    def _get_checker(
        self, check_name: str
    ) -> Callable[[str, dict[str, Any]], tuple[bool, str]]:
        """Return the checker function for a named check."""
        checkers: dict[str, Callable[[str, dict[str, Any]], tuple[bool, str]]] = {
            "syntax_valid": self._check_syntax_valid,
            "tests_pass": self._check_tests_pass,
            "no_secrets": self._check_no_secrets,
            "lint_clean": self._check_lint_clean,
            "wp_standards": self._check_wp_standards,
            "no_destructive_commands": self._check_no_destructive,
            "backup_exists": self._check_backup_exists,
            "min_length": self._check_min_length,
            "no_placeholder": self._check_no_placeholder,
            "brand_consistent": self._check_brand_consistent,
            "char_limit": self._check_char_limit,
            "cta_present": self._check_cta_present,
            "file_format_valid": self._check_file_format,
            "responsive_check": self._check_responsive,
            "has_sources": self._check_has_sources,
            "min_depth": self._check_min_depth,
            "no_hallucination_markers": self._check_no_hallucination,
            "has_pricing": self._check_has_pricing,
            "has_roi": self._check_has_roi,
            "professional_tone": self._check_professional_tone,
        }
        return checkers.get(check_name, self._check_noop)

    @staticmethod
    def _check_noop(content: str, output: dict[str, Any]) -> tuple[bool, str]:
        return True, "No-op check passed"

    @staticmethod
    def _check_syntax_valid(content: str, output: dict[str, Any]) -> tuple[bool, str]:
        """Check if content has basic syntactic validity (balanced brackets, etc.)."""
        open_count = content.count("{") + content.count("[") + content.count("(")
        close_count = content.count("}") + content.count("]") + content.count(")")
        if abs(open_count - close_count) > 2:
            return False, f"Unbalanced brackets: open={open_count} close={close_count}"
        return True, "Syntax check passed"

    @staticmethod
    def _check_tests_pass(content: str, output: dict[str, Any]) -> tuple[bool, str]:
        """Check if output includes test results (from metadata)."""
        tests = output.get("tests_passed")
        if tests is False:
            return False, "Tests did not pass"
        return True, "Tests pass check OK"

    @staticmethod
    def _check_no_secrets(content: str, output: dict[str, Any]) -> tuple[bool, str]:
        """Scan for common secret patterns in content."""
        for pattern in _SECRET_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                return False, f"Potential secret detected: pattern={pattern}"
        return True, "No secrets detected"

    @staticmethod
    def _check_lint_clean(content: str, output: dict[str, Any]) -> tuple[bool, str]:
        """Check lint status from output metadata."""
        lint = output.get("lint_errors", 0)
        if isinstance(lint, int) and lint > 0:
            return False, f"Lint errors found: {lint}"
        if isinstance(lint, list) and len(lint) > 0:
            return False, f"Lint errors found: {len(lint)}"
        return True, "Lint check passed"

    @staticmethod
    def _check_wp_standards(content: str, output: dict[str, Any]) -> tuple[bool, str]:
        """Basic WordPress coding standards check."""
        # Check for direct DB queries without prepare
        if "$wpdb->query(" in content and "$wpdb->prepare" not in content:
            return False, "Direct $wpdb->query without $wpdb->prepare"
        return True, "WordPress standards check passed"

    @staticmethod
    def _check_no_destructive(content: str, output: dict[str, Any]) -> tuple[bool, str]:
        """Check for destructive commands."""
        for pattern in _DESTRUCTIVE_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                return False, f"Destructive command detected: {pattern}"
        return True, "No destructive commands"

    @staticmethod
    def _check_backup_exists(content: str, output: dict[str, Any]) -> tuple[bool, str]:
        """Check if backup strategy is mentioned."""
        backup_keywords = ["backup", "snapshot", "rollback", "restore"]
        has_backup = any(kw in content.lower() for kw in backup_keywords)
        if output.get("backup_confirmed"):
            has_backup = True
        if not has_backup:
            return False, "No backup/rollback strategy mentioned"
        return True, "Backup strategy present"

    @staticmethod
    def _check_min_length(content: str, output: dict[str, Any]) -> tuple[bool, str]:
        """Content must be at least 50 characters."""
        if len(content.strip()) < 50:
            return False, f"Content too short: {len(content.strip())} chars (min 50)"
        return True, "Minimum length met"

    @staticmethod
    def _check_no_placeholder(content: str, output: dict[str, Any]) -> tuple[bool, str]:
        """Check for placeholder text."""
        for pattern in _PLACEHOLDER_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                return False, f"Placeholder text found: {pattern}"
        return True, "No placeholder text"

    @staticmethod
    def _check_brand_consistent(content: str, output: dict[str, Any]) -> tuple[bool, str]:
        """Basic brand consistency (no competitor mentions in output)."""
        brand = output.get("brand_name", "")
        if brand and brand.lower() not in content.lower():
            return False, f"Brand name '{brand}' not found in content"
        return True, "Brand consistency OK"

    @staticmethod
    def _check_char_limit(content: str, output: dict[str, Any]) -> tuple[bool, str]:
        """Social media character limit check."""
        limit = output.get("char_limit", 280)
        if len(content) > limit:
            return False, f"Exceeds character limit: {len(content)}/{limit}"
        return True, "Character limit OK"

    @staticmethod
    def _check_cta_present(content: str, output: dict[str, Any]) -> tuple[bool, str]:
        """Check for call-to-action presence."""
        cta_patterns = [
            r"(?i)(click|tap|sign\s*up|register|subscribe|buy|order|get\s+started|learn\s+more|contact|call|download)",
            r"(?i)(kattints|regisztr|vásárol|iratkozz|kezdd\s+el|tudj\s+meg|hivj)",
        ]
        for pattern in cta_patterns:
            if re.search(pattern, content):
                return True, "CTA present"
        return False, "No call-to-action found in content"

    @staticmethod
    def _check_file_format(content: str, output: dict[str, Any]) -> tuple[bool, str]:
        """Validate file format from output metadata."""
        fmt = output.get("file_format", "")
        valid = {"svg", "png", "jpg", "jpeg", "webp", "pdf", "figma", "sketch"}
        if fmt and fmt.lower() not in valid:
            return False, f"Invalid file format: {fmt}"
        return True, "File format valid"

    @staticmethod
    def _check_responsive(content: str, output: dict[str, Any]) -> tuple[bool, str]:
        """Check for responsive design indicators."""
        responsive_markers = [
            "@media", "responsive", "mobile", "breakpoint",
            "container-query", "grid", "flex",
        ]
        has_responsive = any(m in content.lower() for m in responsive_markers)
        if output.get("responsive_tested"):
            has_responsive = True
        if not has_responsive:
            return False, "No responsive design indicators found"
        return True, "Responsive design present"

    @staticmethod
    def _check_has_sources(content: str, output: dict[str, Any]) -> tuple[bool, str]:
        """Research output must include sources."""
        source_markers = ["http", "source:", "reference:", "citation:", "[1]", "doi:"]
        has_sources = any(m in content.lower() for m in source_markers)
        if output.get("sources") and len(output["sources"]) > 0:
            has_sources = True
        if not has_sources:
            return False, "No sources or citations found"
        return True, "Sources present"

    @staticmethod
    def _check_min_depth(content: str, output: dict[str, Any]) -> tuple[bool, str]:
        """Research must have minimum depth (word count)."""
        word_count = len(content.split())
        min_words = output.get("min_word_count", 200)
        if word_count < min_words:
            return False, f"Insufficient depth: {word_count} words (min {min_words})"
        return True, f"Depth OK: {word_count} words"

    @staticmethod
    def _check_no_hallucination(content: str, output: dict[str, Any]) -> tuple[bool, str]:
        """Check for common hallucination markers."""
        for pattern in _HALLUCINATION_MARKERS:
            if re.search(pattern, content):
                return False, f"Hallucination marker detected: {pattern}"
        return True, "No hallucination markers"

    @staticmethod
    def _check_has_pricing(content: str, output: dict[str, Any]) -> tuple[bool, str]:
        """Business output should include pricing."""
        pricing_markers = ["price", "cost", "fee", "ár", "díj", "Ft", "EUR", "USD", "$", "€"]
        has_pricing = any(m in content for m in pricing_markers)
        if output.get("pricing"):
            has_pricing = True
        if not has_pricing:
            return False, "No pricing information found"
        return True, "Pricing present"

    @staticmethod
    def _check_has_roi(content: str, output: dict[str, Any]) -> tuple[bool, str]:
        """Business output should include ROI/value proposition."""
        roi_markers = ["ROI", "return on investment", "value", "benefit", "megtérülés", "érték"]
        has_roi = any(m.lower() in content.lower() for m in roi_markers)
        if output.get("roi_estimate"):
            has_roi = True
        if not has_roi:
            return False, "No ROI/value proposition found"
        return True, "ROI present"

    @staticmethod
    def _check_professional_tone(content: str, output: dict[str, Any]) -> tuple[bool, str]:
        """Check for professional tone (no informal markers)."""
        informal = [r"\blol\b", r"\bomg\b", r"\bbtw\b", r"!!!", r"\bxd\b"]
        for pattern in informal:
            if re.search(pattern, content, re.IGNORECASE):
                return False, f"Informal tone detected: {pattern}"
        return True, "Professional tone OK"
