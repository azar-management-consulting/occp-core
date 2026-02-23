"""StructuredValidator – validates plan structure, risk constraints, and output integrity."""

from __future__ import annotations

import logging
from typing import Any

from orchestrator.models import RiskLevel, Task

logger = logging.getLogger(__name__)

# Maximum allowed steps per risk level
_MAX_STEPS: dict[RiskLevel, int] = {
    RiskLevel.LOW: 20,
    RiskLevel.MEDIUM: 15,
    RiskLevel.HIGH: 10,
    RiskLevel.CRITICAL: 5,
}

# Required plan keys
_REQUIRED_PLAN_KEYS = {"strategy", "steps"}


class BasicValidator:
    """Implements the :class:`orchestrator.pipeline.Validator` protocol.

    Performs structured validation:
    - Task must have a non-empty plan dict.
    - Plan must contain required keys (strategy, steps).
    - Steps must be a non-empty list of strings.
    - Step count must respect risk-level limits.
    - Task description must not be empty.
    - If execution evidence exists, validates exit code.

    Returns an empty list (no failures) if all checks pass.
    """

    def __init__(
        self,
        *,
        require_plan_keys: bool = True,
        enforce_step_limits: bool = True,
        validate_execution: bool = True,
    ) -> None:
        self._require_plan_keys = require_plan_keys
        self._enforce_step_limits = enforce_step_limits
        self._validate_execution = validate_execution

    async def validate(self, task: Task) -> list[str]:
        failures: list[str] = []

        # 1. Description check
        if not task.description.strip():
            failures.append("Task description is empty")

        # 2. Plan existence
        if not task.plan:
            failures.append("No plan attached to task")
            return failures  # Can't validate plan structure without a plan

        # 3. Plan structure checks
        if self._require_plan_keys:
            failures.extend(self._check_plan_structure(task.plan))

        # 4. Risk-level step limits
        if self._enforce_step_limits:
            steps = task.plan.get("steps", [])
            max_steps = _MAX_STEPS.get(task.risk_level, 20)
            if isinstance(steps, list) and len(steps) > max_steps:
                failures.append(
                    f"Plan has {len(steps)} steps, max {max_steps} "
                    f"for risk level {task.risk_level.value}"
                )

        # 5. Execution output validation
        if self._validate_execution and task.result:
            failures.extend(self._check_execution(task.result))

        if failures:
            logger.warning(
                "Validation failures for task=%s: %s",
                task.id,
                "; ".join(failures),
            )

        return failures

    @staticmethod
    def _check_plan_structure(plan: dict[str, Any]) -> list[str]:
        """Validate plan has required keys and valid types."""
        issues: list[str] = []

        missing = _REQUIRED_PLAN_KEYS - set(plan.keys())
        if missing:
            issues.append(f"Plan missing required keys: {', '.join(sorted(missing))}")

        steps = plan.get("steps")
        if steps is not None:
            if not isinstance(steps, list):
                issues.append(f"Plan 'steps' must be a list, got {type(steps).__name__}")
            elif len(steps) == 0:
                issues.append("Plan 'steps' is empty")
            elif not all(isinstance(s, str) for s in steps):
                issues.append("All plan steps must be strings")

        strategy = plan.get("strategy")
        if strategy is not None and not isinstance(strategy, str):
            issues.append(f"Plan 'strategy' must be a string, got {type(strategy).__name__}")

        return issues

    @staticmethod
    def _check_execution(result: dict[str, Any]) -> list[str]:
        """Validate execution output if present."""
        issues: list[str] = []

        exit_code = result.get("exit_code")
        if exit_code is not None and exit_code != 0:
            issues.append(f"Execution returned non-zero exit code: {exit_code}")

        return issues
