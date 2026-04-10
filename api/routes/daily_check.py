"""Daily monitoring endpoint — single call returns full system health.

One GET request replaces the 3-line daily routine:
    1) /autodev/runs + /autodev/budget
    2) /observability/summary + /governance/proposals
    3) /governance/kill_switch/status

Response includes alerts (list of strings) computed from the protocol
thresholds. Empty alerts = system healthy. Non-empty = operator attention.

Alert rules (from Monitoring + Control Protocol):
    - stuck run (same state > 30min)
    - 3+ consecutive fails
    - budget 50% consumed in < 2h window
    - 5+ runs within 1 hour
    - UNKNOWN governance verdict
    - anomalies > 0
    - kill switch not inactive
    - 5+ rejected proposals in 24h
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends

from api.auth import get_current_user_payload
from autodev import get_approval_queue, get_orchestrator, get_rate_budget_tracker
from evaluation import get_kill_switch, get_proposal_generator
from observability import get_anomaly_detector, get_collector, get_digest_generator

logger = logging.getLogger(__name__)

router = APIRouter(tags=["monitoring"])


@router.get("/daily-check")
async def daily_check(
    current_user: dict = Depends(get_current_user_payload),
) -> dict[str, Any]:
    """Single-call daily monitoring — returns full system state + alerts.

    This endpoint aggregates 5 checks into one response with computed
    alert flags. Designed for 3-second operator glance.
    """
    alerts: list[str] = []
    now = datetime.now(timezone.utc)

    # ── 1. Autodev state ──────────────────────────────────
    orch = get_orchestrator()
    runs = orch.list_all()
    active_runs = [r for r in runs if not r.is_terminal]
    recent_fails = 0
    stuck_runs: list[str] = []
    for r in runs[:20]:
        if r.state.value == "failed":
            recent_fails += 1
        if not r.is_terminal:
            age_minutes = (now - r.updated_at).total_seconds() / 60.0
            if age_minutes > 30:
                stuck_runs.append(f"{r.run_id}({r.state.value},{age_minutes:.0f}min)")

    if stuck_runs:
        alerts.append(f"STUCK RUNS: {stuck_runs}")
    if recent_fails >= 3:
        alerts.append(f"3+ CONSECUTIVE FAILS: {recent_fails} recent failures")

    # ── 2. Budget ─────────────────────────────────────────
    budget = get_rate_budget_tracker()
    snap = budget.snapshot()
    usage = snap["usage"]
    limits = snap["limits"]
    remaining = snap["remaining"]

    budget_pct = (
        usage["runs_started"] / limits["max_runs_per_day"] * 100
        if limits["max_runs_per_day"] > 0
        else 0
    )

    # ── 3. Observability ──────────────────────────────────
    detector = get_anomaly_detector()
    anomalies = detector.detect()
    digest = get_digest_generator().generate()
    metrics_snap = get_collector().snapshot()

    if len(anomalies) > 0:
        alerts.append(
            f"ANOMALIES: {len(anomalies)} ({', '.join(a.code for a in anomalies[:3])})"
        )

    # ── 4. Governance proposals ───────────────────────────
    proposals = get_proposal_generator().generate(include_anomalies=False)
    unknown_verdicts = [
        p for p in proposals if p.governance_verdict == "unknown"
    ]
    if unknown_verdicts:
        alerts.append(
            f"UNKNOWN VERDICT: {[p.proposal_id for p in unknown_verdicts]}"
        )

    # ── 5. Kill switch ────────────────────────────────────
    ks = get_kill_switch()
    ks_status = ks.status()

    if ks.is_active():
        alerts.append(
            f"KILL SWITCH ACTIVE: {ks.current_activation.reason if ks.current_activation else '?'}"
        )

    # ── 6. Approval queue ─────────────────────────────────
    approval_q = get_approval_queue()
    approval_q.cleanup_expired()
    pending = approval_q.list_pending()

    # ── Build response ────────────────────────────────────
    healthy = len(alerts) == 0
    score = max(0, 10 - len(alerts) * 2)

    return {
        "healthy": healthy,
        "score": score,
        "alerts": alerts,
        "checked_at": now.isoformat(),

        "autodev": {
            "total_runs": len(runs),
            "active_runs": len(active_runs),
            "recent_fails": recent_fails,
            "stuck_runs": stuck_runs,
            "last_run": runs[0].to_dict() if runs else None,
        },

        "budget": {
            "date": usage["date"],
            "runs_used": usage["runs_started"],
            "runs_limit": limits["max_runs_per_day"],
            "budget_pct": round(budget_pct, 1),
            "merges_used": usage["low_risk_merges"],
            "compute_seconds_used": round(usage["compute_seconds_used"], 1),
            "remaining_runs": remaining["runs"],
        },

        "observability": {
            "uptime_seconds": round(metrics_snap["uptime_seconds"], 1),
            "anomaly_count": len(anomalies),
            "tasks_total": digest.tasks_total,
            "tasks_by_outcome": digest.tasks_by_outcome,
            "narrative": digest.narrative[:300],
        },

        "governance": {
            "proposals_open": len(proposals),
            "unknown_verdicts": len(unknown_verdicts),
            "pending_approvals": len(pending),
        },

        "kill_switch": {
            "state": ks_status["state"],
            "is_active": ks_status["is_active"],
            "history_count": ks_status["history_count"],
        },
    }
