"""Historical workflow replay harness (L6 foundation skeleton).

Purpose: Given a past workflow execution (from workflow_executions table)
and a candidate code change, re-run the same input through the candidate
and compare output / timing / policy outcomes.

This is the **skeleton** — production implementation will require:
- Snapshot of old inputs (already stored in dag_definition JSON)
- Sandboxed execution environment
- Output comparison rules
- Metric regression thresholds

For v0.10.0 this module provides the data contracts only.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ReplayScenario:
    """A single replay input: historical workflow to be re-run."""

    scenario_id: str
    source_execution_id: str
    workflow_definition: dict[str, Any]
    original_outcome: str  # "success" | "failed" | "rejected"
    original_duration_seconds: float
    original_stages: list[str]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ReplayResult:
    """Result of running a ReplayScenario against a candidate change."""

    scenario_id: str
    candidate_ref: str  # commit SHA or branch name
    outcome: str  # "success" | "failed" | "rejected" | "regression"
    duration_seconds: float
    delta_seconds: float  # candidate - original
    stage_parity: bool  # same stages completed in same order
    output_equivalent: bool  # output matches (within tolerance)
    regressions: list[str] = field(default_factory=list)
    improvements: list[str] = field(default_factory=list)
    run_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_regression(self) -> bool:
        return len(self.regressions) > 0 or self.outcome == "regression"


class ReplayHarness:
    """Skeleton replay harness.

    v0.10.0: stores scenarios + provides the .compare() API surface.
    Actual execution is a TODO for v0.11.0 (requires sandbox integration).
    """

    def __init__(self) -> None:
        self._scenarios: dict[str, ReplayScenario] = {}
        self._results: dict[str, list[ReplayResult]] = {}

    def register_scenario(self, scenario: ReplayScenario) -> None:
        self._scenarios[scenario.scenario_id] = scenario
        self._results.setdefault(scenario.scenario_id, [])
        logger.info("replay: registered scenario id=%s", scenario.scenario_id)

    def get_scenario(self, scenario_id: str) -> ReplayScenario | None:
        return self._scenarios.get(scenario_id)

    def list_scenarios(self) -> list[ReplayScenario]:
        return list(self._scenarios.values())

    def record_result(self, result: ReplayResult) -> None:
        self._results.setdefault(result.scenario_id, []).append(result)
        logger.info(
            "replay: result scenario=%s candidate=%s outcome=%s delta=%.3fs",
            result.scenario_id,
            result.candidate_ref,
            result.outcome,
            result.delta_seconds,
        )

    def get_results(self, scenario_id: str) -> list[ReplayResult]:
        return list(self._results.get(scenario_id, []))

    async def run(
        self,
        scenario: ReplayScenario,
        candidate_ref: str,
    ) -> ReplayResult:
        """Execute a scenario against a candidate change.

        v0.10.0: STUB — returns a skipped result. Full implementation
        in v0.11.0 will:
        1. Checkout candidate_ref in a git worktree
        2. Start a sandboxed OCCP instance
        3. POST the historical workflow_definition
        4. Capture outcome, timings, outputs
        5. Diff against scenario.original_*
        6. Classify regressions
        """
        logger.warning(
            "replay.run is a stub in v0.10.0 — candidate_ref=%s scenario=%s",
            candidate_ref,
            scenario.scenario_id,
        )
        result = ReplayResult(
            scenario_id=scenario.scenario_id,
            candidate_ref=candidate_ref,
            outcome="skipped",
            duration_seconds=0.0,
            delta_seconds=0.0,
            stage_parity=True,
            output_equivalent=True,
            improvements=["stub: actual replay not implemented in v0.10.0"],
        )
        self.record_result(result)
        return result


# ── Singleton accessor ────────────────────────────────────────
_global_harness: ReplayHarness | None = None


def get_replay_harness() -> ReplayHarness:
    """Return the process-global replay harness."""
    global _global_harness
    if _global_harness is None:
        _global_harness = ReplayHarness()
    return _global_harness
