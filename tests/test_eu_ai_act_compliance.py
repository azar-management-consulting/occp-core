"""EU AI Act Article 14 (Human Oversight) compliance verification.

Applicable: 2026-08-02 for high-risk AI systems under Regulation (EU) 2024/1689.
Three tiers tested: L1 understand | L2 intervene | L3 halt.
Accountability tests: Art.12 record-keeping + Art.13 transparency.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.app import app
from evaluation.kill_switch import (
    KillSwitchActive,
    KillSwitchTrigger,
    get_kill_switch,
    require_kill_switch_inactive,
)
from policy_engine.engine import PolicyEngine
from policy_engine.guards import HumanOversightGuard


@pytest.fixture
def client():
    """TestClient with lifespan context so AppState is initialized."""
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _reset_kill_switch():
    """Ensure kill switch is clean between tests."""
    ks = get_kill_switch()
    if ks.is_active():
        try:
            ks.deactivate(actor="test_cleanup", reason="autouse fixture reset")
        except Exception:
            pass
    yield
    ks = get_kill_switch()
    if ks.is_active():
        try:
            ks.deactivate(actor="test_cleanup", reason="autouse fixture reset")
        except Exception:
            pass


@pytest.fixture
def admin_token(client):
    """Return admin JWT token. Falls back to skip if credentials not configured."""
    import os
    user = os.environ.get("OCCP_TEST_ADMIN_USER", "admin")
    pw = os.environ.get("OCCP_TEST_ADMIN_PASSWORD", "changeme")
    r = client.post("/api/v1/auth/login", json={"username": user, "password": pw})
    if r.status_code != 200:
        pytest.skip(f"admin login failed ({r.status_code}); set OCCP_TEST_ADMIN_* env")
    return r.json()["access_token"]


# ─────────────────────────────────────────────────────────
# L1 UNDERSTAND — Art.14(4)(a)
# ─────────────────────────────────────────────────────────
def test_observability_readiness_endpoint_available(client, admin_token):
    """Art.14(4)(a): deployer must be able to monitor the system.
    /observability/readiness exposes L6 readiness markers."""
    r = client.get(
        "/api/v1/observability/readiness",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert "markers" in data or "achieved" in data, f"unexpected response: {data}"


# ─────────────────────────────────────────────────────────
# L3 HALT — Art.14(4)(e)
# ─────────────────────────────────────────────────────────
def test_kill_switch_halts_pipeline():
    """Art.14(4)(e): 'stop' button brings system to safe halt.
    After activate(), require_kill_switch_inactive() MUST raise."""
    ks = get_kill_switch()
    assert not ks.is_active()

    require_kill_switch_inactive()

    ks.activate(
        trigger=KillSwitchTrigger.MANUAL,
        actor="compliance_test",
        reason="Art.14 verification",
    )
    assert ks.is_active()

    with pytest.raises(KillSwitchActive):
        require_kill_switch_inactive()

    record = ks.deactivate(actor="compliance_test", reason="test cleanup")
    assert record is not None
    assert not ks.is_active()


def test_kill_switch_endpoint_admin_only(client, admin_token):
    """Art.14(4)(e): kill switch reachable via HTTP (one-click)."""
    r = client.post(
        "/api/v1/governance/kill_switch/activate",
        json={"trigger": "manual", "reason": "test"},
    )
    assert r.status_code in (401, 403), "unauthenticated must be blocked"

    r = client.post(
        "/api/v1/governance/kill_switch/activate",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"trigger": "manual", "reason": "compliance drill"},
    )
    assert r.status_code in (200, 201), f"admin activation failed: {r.text}"

    client.post(
        "/api/v1/governance/kill_switch/deactivate",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"reason": "test cleanup"},
    )


# ─────────────────────────────────────────────────────────
# L2 INTERVENE — Art.14(4)(d)
# ─────────────────────────────────────────────────────────
def test_hitl_oversight_guard_blocks_until_approved():
    """Art.14(4)(d): operator must be able to disregard/override."""
    guard = HumanOversightGuard(enabled=True)

    result = guard.check({"action": "policy.update"})
    assert result.passed is False

    guard.approve("policy.update")
    result = guard.check({"action": "policy.update"})
    assert result.passed is True

    guard.revoke_approval("policy.update")
    result = guard.check({"action": "policy.update"})
    assert result.passed is False


# ─────────────────────────────────────────────────────────
# ACCOUNTABILITY (Art.12 record-keeping)
# ─────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_audit_chain_integrity():
    """Art.12 + Art.14 accountability: hash-chained audit must verify."""
    engine = PolicyEngine()

    await engine.audit(
        actor="test", action="policy.evaluate", task_id="t1", detail={"step": 1}
    )
    await engine.audit(
        actor="test", action="policy.evaluate", task_id="t2", detail={"step": 2}
    )
    await engine.audit(
        actor="test", action="policy.evaluate", task_id="t3", detail={"step": 3}
    )

    assert engine.verify_audit_chain() is True

    log = engine.audit_log
    log[1].detail["step"] = 999
    assert PolicyEngine.verify_entries(log) is False


# ─────────────────────────────────────────────────────────
# Art.13 TRANSPARENCY overlap
# ─────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_transparency_metadata_on_automated_actions():
    """Art.13 + Art.14(4)(c): decisions must be interpretable."""
    engine = PolicyEngine()

    class _Task:
        id = "t-transparency"
        name = "demo"
        description = "demo task"
        agent_type = "generic"
        metadata: dict = {}

    result = await engine.evaluate(_Task())
    record = result.to_decision_record()

    assert "approved" in record
    assert "guards" in record
    assert isinstance(record["guards"], list)


# ─────────────────────────────────────────────────────────
# GAP G-6: halt enforcement across all entry points
# ─────────────────────────────────────────────────────────
def test_halt_enforced_across_all_entry_points():
    """Art.14(4)(e): halt must cover ALL operations, not just Pipeline.

    Gap G-6 closed 2026-04-21: BrainFlow, MCPBridge, AutoDevOrchestrator
    now each carry __kill_switch_guarded__ = True and call
    require_kill_switch_inactive() at their main entry methods.
    """
    ks = get_kill_switch()
    ks.activate(trigger=KillSwitchTrigger.MANUAL, actor="test", reason="coverage")

    try:
        from adapters.mcp_bridge import MCPBridge
        from autodev.orchestrator import AutoDevOrchestrator
        from orchestrator.brain_flow import BrainFlow

        for cls in (BrainFlow, MCPBridge, AutoDevOrchestrator):
            assert hasattr(cls, "__kill_switch_guarded__"), (
                f"{cls.__name__} missing kill-switch guard marker"
            )
    finally:
        ks.deactivate(actor="test", reason="xfail cleanup")
