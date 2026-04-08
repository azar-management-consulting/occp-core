"""Historical workflow replay harness (L6 foundation — real execution).

Purpose: Given a past workflow scenario and a candidate (module reference
or pipeline-like callable), re-run the same input and compare output,
stage sequence, and timing against the original.

v0.10.0 completion: replaces the stub with a working, deterministic
in-process replay that exercises the *current* Pipeline abstractions
via injected Planner/Executor/Validator/Shipper instances. No git
worktree, no sandbox boot — that stays for v0.11.0. But the harness
now actually produces a real pass/fail verdict for a simple scenario.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Protocol

logger = logging.getLogger(__name__)


# ── Data contracts ────────────────────────────────────────────

@dataclass
class ReplayScenario:
    """A single replay input: historical workflow to be re-run."""

    scenario_id: str
    source_execution_id: str
    workflow_definition: dict[str, Any]
    original_outcome: str  # "success" | "failed" | "rejected"
    original_duration_seconds: float
    original_stages: list[str]
    original_output: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ReplayResult:
    """Result of running a ReplayScenario against a candidate."""

    scenario_id: str
    candidate_ref: str  # commit SHA, branch, or module path
    outcome: str  # "success" | "failed" | "rejected" | "regression" | "skipped"
    duration_seconds: float
    delta_seconds: float  # candidate - original
    stage_parity: bool
    output_equivalent: bool
    stages_run: list[str] = field(default_factory=list)
    regressions: list[str] = field(default_factory=list)
    improvements: list[str] = field(default_factory=list)
    candidate_output: dict[str, Any] = field(default_factory=dict)
    run_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_regression(self) -> bool:
        return len(self.regressions) > 0 or self.outcome in {"regression", "failed"}

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "candidate_ref": self.candidate_ref,
            "outcome": self.outcome,
            "duration_seconds": self.duration_seconds,
            "delta_seconds": self.delta_seconds,
            "stage_parity": self.stage_parity,
            "output_equivalent": self.output_equivalent,
            "stages_run": self.stages_run,
            "regressions": self.regressions,
            "improvements": self.improvements,
            "candidate_output": self.candidate_output,
            "run_at": self.run_at.isoformat(),
            "is_regression": self.is_regression,
        }


# ── Candidate execution protocol ──────────────────────────────

class ReplayCandidate(Protocol):
    """A replay candidate exposes a single coroutine: run(scenario) -> output.

    The harness calls candidate.run(scenario) and measures time + output.
    Candidates may be:
    - a wrapper around current Pipeline.run (Planner/Executor/Validator/Shipper)
    - a pure mock for tests
    - a future git-worktree-based candidate
    """

    async def run(self, scenario: ReplayScenario) -> dict[str, Any]: ...


@dataclass
class _CallableCandidate:
    """Adapter for plain callables / coroutines to become ReplayCandidate."""

    ref: str
    fn: Callable[[ReplayScenario], Awaitable[dict[str, Any]]]

    async def run(self, scenario: ReplayScenario) -> dict[str, Any]:
        return await self.fn(scenario)


# ── Harness ───────────────────────────────────────────────────

class ReplayHarness:
    """Deterministic in-process replay harness.

    Store scenarios, register candidates, run them, record results.
    """

    # Relative tolerance: candidate_duration is acceptable if within this
    # multiple of the original duration.
    DURATION_TOLERANCE = 2.0

    def __init__(self) -> None:
        self._scenarios: dict[str, ReplayScenario] = {}
        self._results: dict[str, list[ReplayResult]] = {}

    # ── Scenario management ──────────────────────────────────
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
            "replay: result scenario=%s candidate=%s outcome=%s delta=%.3fs regressions=%d",
            result.scenario_id,
            result.candidate_ref,
            result.outcome,
            result.delta_seconds,
            len(result.regressions),
        )

    def get_results(self, scenario_id: str) -> list[ReplayResult]:
        return list(self._results.get(scenario_id, []))

    def reset(self) -> None:
        self._scenarios.clear()
        self._results.clear()

    # ── Execution ────────────────────────────────────────────

    async def run(
        self,
        scenario: ReplayScenario,
        candidate: ReplayCandidate | Callable[[ReplayScenario], Awaitable[dict[str, Any]]],
        candidate_ref: str = "inline",
    ) -> ReplayResult:
        """Execute a scenario against a candidate, compare, and record.

        Candidate may be a ReplayCandidate or an async callable.
        Returns the ReplayResult (already recorded in the harness).
        """
        # Adapt callable to candidate protocol
        if not hasattr(candidate, "run"):
            candidate = _CallableCandidate(ref=candidate_ref, fn=candidate)  # type: ignore[arg-type]

        t_start = time.monotonic()
        regressions: list[str] = []
        improvements: list[str] = []
        outcome = "success"
        output: dict[str, Any] = {}
        stages_run: list[str] = []

        try:
            output = await candidate.run(scenario)
            duration = time.monotonic() - t_start

            stages_run = list(output.get("stages", [])) or []
            candidate_outcome = output.get("outcome", "success")

            # ── Comparison ──────────────────────────────────
            stage_parity = (stages_run == scenario.original_stages)
            if not stage_parity:
                regressions.append(
                    f"stage sequence mismatch: candidate={stages_run} "
                    f"original={scenario.original_stages}"
                )

            output_equivalent = self._outputs_equivalent(
                scenario.original_output, output
            )
            if not output_equivalent:
                regressions.append("candidate output diverges from original")

            delta = duration - scenario.original_duration_seconds
            if scenario.original_duration_seconds > 0 and duration > (
                scenario.original_duration_seconds * self.DURATION_TOLERANCE
            ):
                regressions.append(
                    f"candidate duration {duration:.2f}s > "
                    f"{self.DURATION_TOLERANCE:.1f}x original "
                    f"({scenario.original_duration_seconds:.2f}s)"
                )
            elif delta < -0.05:
                improvements.append(
                    f"candidate is {abs(delta):.2f}s faster than original"
                )

            if candidate_outcome != scenario.original_outcome:
                if scenario.original_outcome == "success" and candidate_outcome != "success":
                    regressions.append(
                        f"outcome regressed: {scenario.original_outcome} → "
                        f"{candidate_outcome}"
                    )
                    outcome = "regression"
                elif scenario.original_outcome != "success" and candidate_outcome == "success":
                    improvements.append(
                        f"outcome improved: {scenario.original_outcome} → {candidate_outcome}"
                    )

            if regressions and outcome == "success":
                outcome = "regression"

        except Exception as exc:
            duration = time.monotonic() - t_start
            delta = duration - scenario.original_duration_seconds
            stage_parity = False
            output_equivalent = False
            regressions.append(f"candidate raised: {type(exc).__name__}: {exc}")
            outcome = "failed"
            logger.warning(
                "replay: candidate %s raised on scenario %s: %s",
                candidate_ref,
                scenario.scenario_id,
                exc,
            )

        result = ReplayResult(
            scenario_id=scenario.scenario_id,
            candidate_ref=candidate_ref,
            outcome=outcome,
            duration_seconds=duration,
            delta_seconds=delta,
            stage_parity=stage_parity,
            output_equivalent=output_equivalent,
            stages_run=stages_run,
            regressions=regressions,
            improvements=improvements,
            candidate_output=output if isinstance(output, dict) else {},
        )
        self.record_result(result)
        return result

    async def run_all(
        self,
        candidate: ReplayCandidate | Callable[[ReplayScenario], Awaitable[dict[str, Any]]],
        candidate_ref: str = "inline",
    ) -> list[ReplayResult]:
        """Run every registered scenario against the given candidate."""
        results = []
        for scenario in self._scenarios.values():
            results.append(await self.run(scenario, candidate, candidate_ref))
        return results

    # ── Output comparison ────────────────────────────────────
    @staticmethod
    def _outputs_equivalent(a: dict[str, Any], b: dict[str, Any]) -> bool:
        """Lightweight equivalence check.

        Ignores volatile fields (timestamps, ids). Compares stable keys.
        """
        ignore = {"timestamp", "run_id", "correlation_id", "generated_at",
                  "ts", "started_at", "finished_at"}

        def normalize(d: Any) -> Any:
            if isinstance(d, dict):
                return {
                    k: normalize(v) for k, v in d.items() if k not in ignore
                }
            if isinstance(d, list):
                return [normalize(x) for x in d]
            return d

        return normalize(a) == normalize(b)

    # ── Stats ────────────────────────────────────────────────
    @property
    def stats(self) -> dict[str, Any]:
        total_results = sum(len(r) for r in self._results.values())
        total_regressions = sum(
            1
            for results in self._results.values()
            for r in results
            if r.is_regression
        )
        return {
            "scenarios_registered": len(self._scenarios),
            "total_runs": total_results,
            "total_regressions": total_regressions,
            "regression_rate": (
                total_regressions / total_results if total_results else 0.0
            ),
        }


# ── Singleton accessor ────────────────────────────────────────
_global_harness: ReplayHarness | None = None


def get_replay_harness() -> ReplayHarness:
    """Return the process-global replay harness."""
    global _global_harness
    if _global_harness is None:
        _global_harness = ReplayHarness()
    return _global_harness
