"""Architecture YAML memory schema validators.

These tests ensure that the YAML files under `architecture/` are:
1. Valid YAML that parses
2. Have the expected top-level schema version
3. Cross-reference each other consistently
4. Match the actual code (no drift)

If any test fails, the system has architectural drift and Claude Code
should refuse self-modification proposals until the drift is resolved.
"""

from __future__ import annotations

import pathlib

import pytest
import yaml

REPO_ROOT = pathlib.Path(__file__).parent.parent.parent
ARCH_DIR = REPO_ROOT / "architecture"


@pytest.fixture(scope="module")
def services():
    with (ARCH_DIR / "services.yaml").open() as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
def agents():
    with (ARCH_DIR / "agents.yaml").open() as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
def tools():
    with (ARCH_DIR / "tools.yaml").open() as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
def dataflows():
    with (ARCH_DIR / "dataflows.yaml").open() as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
def boundaries():
    with (ARCH_DIR / "boundaries.yaml").open() as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
def governance():
    with (ARCH_DIR / "governance.yaml").open() as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
def runtime_inventory():
    with (ARCH_DIR / "runtime_inventory.yaml").open() as f:
        return yaml.safe_load(f)


# ─── Basic parse + schema version ─────────────────────────────

class TestBasicSchema:

    def test_all_files_exist(self):
        expected = [
            "services.yaml",
            "agents.yaml",
            "tools.yaml",
            "dataflows.yaml",
            "boundaries.yaml",
            "runtime_inventory.yaml",
            "governance.yaml",
            "README.md",
        ]
        for name in expected:
            assert (ARCH_DIR / name).exists(), f"Missing architecture/{name}"

    def test_schema_versions(
        self, services, agents, tools, dataflows, boundaries, governance, runtime_inventory
    ):
        for name, data in [
            ("services", services),
            ("agents", agents),
            ("tools", tools),
            ("dataflows", dataflows),
            ("boundaries", boundaries),
            ("governance", governance),
            ("runtime_inventory", runtime_inventory),
        ]:
            assert data.get("version") == 1, f"{name}: version must be 1"
            assert "schema" in data, f"{name}: schema key required"
            assert data["schema"].startswith("occp.architecture."), \
                f"{name}: schema must start with 'occp.architecture.'"


# ─── services.yaml ────────────────────────────────────────────

class TestServices:

    def test_services_list_present(self, services):
        assert "services" in services
        assert len(services["services"]) >= 6

    def test_critical_services_defined(self, services):
        ids = {s["id"] for s in services["services"]}
        required = {"occp-api", "occp-dash", "occp-db", "telegram-bot", "mcp-bridge"}
        assert required.issubset(ids), f"missing critical services: {required - ids}"

    def test_every_service_has_host(self, services):
        for svc in services["services"]:
            assert "host" in svc or svc.get("external_to_occp_core"), \
                f"service {svc['id']} missing host"

    def test_hosts_list(self, services):
        assert "hosts" in services
        assert len(services["hosts"]) >= 3


# ─── agents.yaml ──────────────────────────────────────────────

class TestAgents:

    def test_8_specialists(self, agents):
        assert len(agents["specialists"]) == 8

    def test_specialist_ids_match_allowlist_file(self, agents):
        # Sanity: IDs in agents.yaml must match security/agent_allowlist.py
        from security.agent_allowlist import AGENT_TOOL_ALLOWLISTS
        yaml_ids = {a["id"] for a in agents["specialists"]}
        allowlist_ids = set(AGENT_TOOL_ALLOWLISTS.keys())
        # yaml specialists must be subset of allowlist
        missing = yaml_ids - allowlist_ids
        assert not missing, f"specialists in yaml not in allowlist: {missing}"

    def test_high_risk_agents_require_approval(self, agents):
        for spec in agents["specialists"]:
            if spec.get("risk_default") == "high":
                assert spec.get("requires_approval"), \
                    f"agent {spec['id']} is high risk but has no requires_approval list"

    def test_brain_orchestrator_defined(self, agents):
        assert len(agents["orchestrators"]) >= 1
        brain = next(
            (o for o in agents["orchestrators"] if o["id"] == "brain"), None
        )
        assert brain is not None
        assert "brain.status" in brain["allowlist_tools"]


# ─── tools.yaml ───────────────────────────────────────────────

class TestTools:

    def test_tools_list_non_empty(self, tools):
        assert len(tools["tools"]) >= 5

    def test_filesystem_tools_have_workspace_root(self, tools):
        for t in tools["tools"]:
            if t["namespace"] == "filesystem":
                assert "workspace_root" in t
                assert t["workspace_root"] == "/tmp/occp-workspace"
                assert t.get("path_escape_protection") is True

    def test_http_tools_https_only(self, tools):
        for t in tools["tools"]:
            if t["namespace"] == "http":
                assert t.get("allowed_schemes") == ["https"]


# ─── dataflows.yaml ───────────────────────────────────────────

class TestDataflows:

    def test_telegram_flow_exists(self, dataflows):
        ids = {f["id"] for f in dataflows["flows"]}
        assert "flow.telegram.voice" in ids

    def test_every_critical_flow_has_latency_budget(self, dataflows):
        for flow in dataflows["flows"]:
            if flow.get("critical_path"):
                assert "latency_budget_seconds" in flow, \
                    f"critical flow {flow['id']} missing latency_budget_seconds"

    def test_every_flow_has_at_least_one_denial_stage(self, dataflows):
        for flow in dataflows["flows"]:
            denials = [s for s in flow["stages"] if s.get("can_deny")]
            assert len(denials) >= 1, \
                f"flow {flow['id']} has no denial stages — violates invariant"


# ─── boundaries.yaml ──────────────────────────────────────────

class TestBoundaries:

    def test_three_tiers_present(self, boundaries):
        assert "autonomous_safe" in boundaries
        assert "human_review_required" in boundaries
        assert "immutable" in boundaries

    def test_immutable_security_paths(self, boundaries):
        immutable_globs = {item["path_glob"] for item in boundaries["immutable"]}
        # These MUST always be immutable
        must_be_immutable = {
            "security/agent_allowlist.py",
            "policy_engine/guards.py",
            "policy_engine/engine.py",
            "api/auth.py",
            "api/rbac.py",
        }
        missing = must_be_immutable - immutable_globs
        assert not missing, f"these paths must be immutable: {missing}"

    def test_no_overlap_autonomous_and_immutable(self, boundaries):
        auto_globs = {item["path_glob"] for item in boundaries["autonomous_safe"]}
        imm_globs = {item["path_glob"] for item in boundaries["immutable"]}
        overlap = auto_globs & imm_globs
        assert not overlap, f"overlap between autonomous_safe and immutable: {overlap}"


# ─── governance.yaml ──────────────────────────────────────────

class TestGovernance:

    def test_governance_is_immutable_marker(self, governance):
        assert governance.get("status") == "IMMUTABLE"

    def test_principal_agent_is_claude_code(self, governance):
        assert governance["principal_agent"]["id"] == "claude-code"
        assert "Claude Code" in governance["principal_agent"]["name"]

    def test_forbidden_actions_listed(self, governance):
        assert "forbidden" in governance
        forbidden_cats = {item["category"] for item in governance["forbidden"]}
        required = {"security_bypass", "destructive", "self_escalation"}
        assert required.issubset(forbidden_cats), \
            f"missing forbidden categories: {required - forbidden_cats}"

    def test_kill_switch_defined(self, governance):
        assert "kill_switch" in governance
        assert len(governance["kill_switch"]["triggers"]) >= 2

    def test_l6_readiness_markers(self, governance):
        assert "l6_readiness" in governance
        required_markers = governance["l6_readiness"]["required"]
        expected_keys = {
            "architecture_memory_complete",
            "telemetry_active",
            "rfc_template_exists",
            "governance_enforced",
        }
        assert expected_keys.issubset(required_markers.keys())


# ─── runtime_inventory.yaml ───────────────────────────────────

class TestRuntimeInventory:

    def test_backend_section(self, runtime_inventory):
        assert "backend" in runtime_inventory
        assert runtime_inventory["backend"]["python"].startswith("3.")

    def test_git_remote_is_occp_core(self, runtime_inventory):
        assert "azar-management-consulting/occp-core" in \
            runtime_inventory["git"]["remote"]

    def test_control_plane_mesh_has_all_nodes(self, runtime_inventory):
        ids = {n["id"] for n in runtime_inventory["control_plane_mesh"]["nodes"]}
        required = {"mba-henry", "imac-henry", "mbp-henry", "hetzner-occp-brain"}
        assert required.issubset(ids)
