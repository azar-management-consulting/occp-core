"""Task → Anthropic model routing.

The :class:`ModelRouter` decides which Anthropic model should run a given
:class:`~orchestrator.models.Task` based on ``agent_type``, ``risk_level``
and description size.  Decisions are logged via ``structlog`` so the
dashboard can attribute spend back to routing policy.

Environment overrides:
  ``OCCP_MODEL_OVERRIDE``   Force every decision to the given model id.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Final

try:  # structlog is an OCCP-wide dependency, but keep stdlib fallback
    import structlog  # type: ignore[import-not-found]

    _log = structlog.get_logger("model_router")
except Exception:  # pragma: no cover — defensive
    _log = logging.getLogger("model_router")


# ---------------------------------------------------------------------------
# Model identifiers
# ---------------------------------------------------------------------------

HAIKU: Final[str] = "claude-haiku-4-5"
SONNET: Final[str] = "claude-sonnet-4-6"
OPUS: Final[str] = "claude-opus-4-7"

DEFAULT_MODEL: Final[str] = SONNET

ENV_OVERRIDE: Final[str] = "OCCP_MODEL_OVERRIDE"

# Approximation: 1 token ≈ 4 characters.  Used only when the task object
# doesn't carry a precomputed ``description_tokens`` field.
_CHARS_PER_TOKEN: Final[int] = 4

# Lightweight-task threshold (description tokens).
HAIKU_DESCRIPTION_TOKEN_BUDGET: Final[int] = 500

# Agent buckets (sets for O(1) lookup).
_HAIKU_AGENTS: Final[frozenset[str]] = frozenset({"classify"})

_SONNET_AGENTS: Final[frozenset[str]] = frozenset(
    {"deep-research", "content-forge", "seo", "intel-research"}
)

_OPUS_AGENTS: Final[frozenset[str]] = frozenset(
    {"eng-core", "architect", "autodev"}
)


@dataclass(frozen=True, slots=True)
class RoutingDecision:
    """Explainable output from :meth:`ModelRouter.route`."""

    model_id: str
    reason: str
    override: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "reason": self.reason,
            "override": self.override,
        }


def _task_attr(task: Any, name: str, default: Any = None) -> Any:
    """Tolerant attribute lookup — works with dataclasses, dicts, mocks."""
    if isinstance(task, dict):
        return task.get(name, default)
    return getattr(task, name, default)


def _risk_level_value(task: Any) -> str:
    """Return ``task.risk_level`` as a lowercase string, handling enums."""
    risk = _task_attr(task, "risk_level")
    if risk is None:
        return "low"
    # enum instance (RiskLevel.HIGH) — pull .value
    value = getattr(risk, "value", risk)
    return str(value).lower()


def _description_tokens(task: Any) -> tuple[int, bool]:
    """Return ``(tokens, is_explicit)``.

    ``is_explicit`` is ``True`` when the task supplies an explicit
    ``description_tokens`` attribute; otherwise the value is approximated
    from ``description`` length (1 token ≈ 4 characters).
    """
    explicit = _task_attr(task, "description_tokens")
    if explicit is not None:
        try:
            return max(0, int(explicit)), True
        except (TypeError, ValueError):
            pass
    description = _task_attr(task, "description", "") or ""
    return max(0, len(str(description)) // _CHARS_PER_TOKEN), False


class ModelRouter:
    """Deterministic task → model routing with env override support."""

    def __init__(
        self,
        *,
        override_env: str = ENV_OVERRIDE,
        default_model: str = DEFAULT_MODEL,
    ) -> None:
        self._override_env = override_env
        self._default_model = default_model

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def decide(self, task: Any) -> RoutingDecision:
        """Return the full :class:`RoutingDecision` for *task*."""
        override = os.environ.get(self._override_env, "").strip()
        if override:
            decision = RoutingDecision(
                model_id=override,
                reason=f"env override via {self._override_env}",
                override=True,
            )
            self._log_decision(task, decision)
            return decision

        agent_type = str(_task_attr(task, "agent_type", "") or "").lower()
        risk = _risk_level_value(task)
        desc_tokens, tokens_explicit = _description_tokens(task)

        # Rule 1 — eng-core / architect / autodev or any HIGH/CRITICAL risk → Opus
        # (checked first so a high-risk classify task still escalates)
        if agent_type in _OPUS_AGENTS or risk in {"high", "critical"}:
            reason = (
                f"high risk ({risk}) → opus"
                if risk in {"high", "critical"}
                else f"agent_type={agent_type} → opus"
            )
            decision = RoutingDecision(OPUS, reason=reason)
        # Rule 2 — research / content / SEO → Sonnet
        elif agent_type in _SONNET_AGENTS:
            decision = RoutingDecision(
                SONNET, reason=f"agent_type={agent_type} → sonnet"
            )
        # Rule 3 — explicit classify agent → Haiku
        elif agent_type == "classify" or agent_type in _HAIKU_AGENTS:
            decision = RoutingDecision(
                HAIKU, reason=f"agent_type={agent_type} → haiku"
            )
        # Rule 4 — generic low-risk lightweight tasks → Haiku.
        # Requires an *explicit* description_tokens value so we don't
        # downgrade tasks that simply have an empty description.
        elif (
            tokens_explicit
            and risk == "low"
            and 0 < desc_tokens < HAIKU_DESCRIPTION_TOKEN_BUDGET
        ):
            decision = RoutingDecision(
                HAIKU,
                reason=f"low risk + small prompt ({desc_tokens} tok) → haiku",
            )
        # Fallback — Sonnet
        else:
            decision = RoutingDecision(
                self._default_model,
                reason=f"fallback default (agent_type={agent_type or 'unknown'})",
            )

        self._log_decision(task, decision)
        return decision

    def route(self, task: Any) -> str:
        """Convenience wrapper returning only the model id string."""
        return self.decide(task).model_id

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _log_decision(self, task: Any, decision: RoutingDecision) -> None:
        try:
            self._emit_log(
                "model_router.decision",
                task_id=str(_task_attr(task, "id", "") or ""),
                agent_type=str(_task_attr(task, "agent_type", "") or ""),
                risk_level=_risk_level_value(task),
                model_id=decision.model_id,
                reason=decision.reason,
                override=decision.override,
            )
        except Exception:  # pragma: no cover — never let logging break routing
            pass

    def _emit_log(self, event: str, **fields: Any) -> None:
        """Bridge structlog vs stdlib logging call signatures."""
        info = getattr(_log, "info", None)
        if info is None:
            return
        try:
            info(event, **fields)
        except TypeError:
            info("%s %s", event, fields)
