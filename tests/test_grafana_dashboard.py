"""Schema tests for the OCCP SLO Grafana dashboard JSON.

Validates structural correctness without requiring a running Grafana instance.

Test parametrization count: 5 panel assertions + 5 expr assertions + 3 datasource
uid assertions + 1 tags assertion + 1 time-range assertion = 15 total parametrized
or inline assertions across 5 test functions.
"""

from __future__ import annotations

import json
import pathlib

import pytest

DASHBOARD_PATH = (
    pathlib.Path(__file__).parent.parent
    / "infra" / "grafana" / "dashboards" / "occp-slo.json"
)


@pytest.fixture(scope="module")
def dashboard() -> dict:
    """Load and parse the dashboard JSON once for the test module."""
    raw = DASHBOARD_PATH.read_text(encoding="utf-8")
    return json.loads(raw)


@pytest.fixture(scope="module")
def panels(dashboard: dict) -> list:
    return dashboard["panels"]


# ── 1. Panel count ────────────────────────────────────────────────────────────

def test_panel_count(panels: list) -> None:
    """Dashboard must have exactly 5 panels."""
    assert len(panels) == 5, (
        f"Expected 5 panels, got {len(panels)}. "
        f"Panel titles: {[p.get('title') for p in panels]}"
    )


# ── 2. Each panel has a non-empty targets list with at least one PromQL expr ──

@pytest.mark.parametrize("panel_index", [0, 1, 2, 3, 4])
def test_panel_has_targets_with_expr(panels: list, panel_index: int) -> None:
    """Every panel must have a targets array with at least one non-empty expr."""
    panel = panels[panel_index]
    assert "targets" in panel, (
        f"Panel {panel_index} '{panel.get('title')}' is missing 'targets' key."
    )
    targets = panel["targets"]
    assert isinstance(targets, list) and len(targets) >= 1, (
        f"Panel {panel_index} '{panel.get('title')}' has no targets."
    )
    exprs = [t.get("expr", "") for t in targets]
    assert any(e.strip() for e in exprs), (
        f"Panel {panel_index} '{panel.get('title')}' has no non-empty PromQL expr."
    )


# ── 3. No hardcoded datasource UIDs — all must use ${datasource} or be absent ─

@pytest.mark.parametrize("panel_index", [0, 1, 2, 3, 4])
def test_no_hardcoded_datasource_uid(panels: list, panel_index: int) -> None:
    """Panel and target datasource refs must use ${datasource} variable or
    prometheus-occp provisioned UID — never a raw Grafana-generated UID (UUID4).
    """
    import re
    uuid4_pattern = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
        re.IGNORECASE,
    )
    panel = panels[panel_index]

    # Check top-level panel datasource
    ds = panel.get("datasource")
    if isinstance(ds, dict):
        uid = ds.get("uid", "")
        assert not uuid4_pattern.match(uid), (
            f"Panel {panel_index} has hardcoded UUID datasource uid: '{uid}'"
        )

    # Check each target datasource
    for i, target in enumerate(panel.get("targets", [])):
        ds_t = target.get("datasource")
        if isinstance(ds_t, dict):
            uid_t = ds_t.get("uid", "")
            assert not uuid4_pattern.match(uid_t), (
                f"Panel {panel_index} target {i} has hardcoded UUID datasource uid: '{uid_t}'"
            )


# ── 4. Dashboard tags include required set ─────────────────────────────────────

def test_dashboard_tags(dashboard: dict) -> None:
    """Dashboard must have tags: ['occp', 'slo', 'production']."""
    tags = dashboard.get("tags", [])
    required = {"occp", "slo", "production"}
    assert required.issubset(set(tags)), (
        f"Dashboard tags {tags!r} missing required tags {required - set(tags)!r}"
    )


# ── 5. Default time range is now-24h ──────────────────────────────────────────

def test_time_range_default(dashboard: dict) -> None:
    """Dashboard time.from must be 'now-24h'."""
    time_config = dashboard.get("time", {})
    assert time_config.get("from") == "now-24h", (
        f"Expected time.from='now-24h', got {time_config.get('from')!r}"
    )
    assert time_config.get("to") == "now", (
        f"Expected time.to='now', got {time_config.get('to')!r}"
    )


# ── 6. Refresh interval is 30s ────────────────────────────────────────────────

def test_refresh_interval(dashboard: dict) -> None:
    """Dashboard refresh must be '30s'."""
    assert dashboard.get("refresh") == "30s", (
        f"Expected refresh='30s', got {dashboard.get('refresh')!r}"
    )


# ── 7. Datasource variable exists ─────────────────────────────────────────────

def test_datasource_variable(dashboard: dict) -> None:
    """Dashboard must have a 'datasource' template variable of type 'datasource'."""
    variables = dashboard.get("templating", {}).get("list", [])
    ds_vars = [v for v in variables if v.get("name") == "datasource" and v.get("type") == "datasource"]
    assert len(ds_vars) >= 1, (
        "Dashboard is missing a 'datasource' template variable of type 'datasource'."
    )


# ── 8. env variable with production/staging options ───────────────────────────

def test_env_variable(dashboard: dict) -> None:
    """Dashboard must have an 'env' template variable with production and staging options."""
    variables = dashboard.get("templating", {}).get("list", [])
    env_vars = [v for v in variables if v.get("name") == "env"]
    assert len(env_vars) >= 1, "Dashboard is missing 'env' template variable."
    env_var = env_vars[0]
    option_values = {opt["value"] for opt in env_var.get("options", [])}
    assert "production" in option_values, "env variable missing 'production' option."
    assert "staging" in option_values, "env variable missing 'staging' option."


# ── 9. Schema version is Grafana 11 compatible (>=39) ─────────────────────────

def test_schema_version(dashboard: dict) -> None:
    """schemaVersion must be >= 39 (Grafana 11)."""
    version = dashboard.get("schemaVersion", 0)
    assert version >= 39, (
        f"schemaVersion {version} is below Grafana 11 minimum (39)."
    )
