"""PolicyGate – adapter wrapping the real PolicyEngine for the Gate stage.

This is NOT a Pipeline Protocol adapter (the Pipeline already accepts a
PolicyEngine directly).  Instead it provides a convenience wrapper that
can be used standalone to evaluate content against all guards.
"""

from __future__ import annotations

from typing import Any

from policy_engine.engine import GateResult, PolicyEngine


class PolicyGate:
    """Thin wrapper around :class:`PolicyEngine` for standalone evaluations.

    Usage::

        gate = PolicyGate()
        result = gate.check_content("some text to scan")
    """

    def __init__(self, engine: PolicyEngine | None = None) -> None:
        self._engine = engine or PolicyEngine()

    @property
    def engine(self) -> PolicyEngine:
        return self._engine

    def check_content(self, text: str) -> list[dict[str, Any]]:
        """Synchronously check *text* through all guards.

        Returns a list of dicts, one per guard, with keys
        ``guard``, ``passed``, ``detail``.
        """
        from policy_engine.guards import _flatten_to_text  # noqa: WPS450

        payload = {"description": text}
        results = []
        for guard in self._engine._guards:
            gr = guard.check(payload)
            results.append({
                "guard": gr.guard_name,
                "passed": gr.passed,
                "detail": gr.detail,
            })
        return results

    async def evaluate(self, task: Any) -> GateResult:
        """Async evaluation passthrough to the engine."""
        return await self._engine.evaluate(task)
