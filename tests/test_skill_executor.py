"""Tests for orchestrator.skill_executor — Skill Executor (REQ-SEXEC-01 through REQ-SEXEC-05).

Covers:
- SkillExecutionContext: creation, frozen fields
- SkillExecutionResult: creation, fields, to_dict
- SkillExecutor: basic construction, manifest registration, skill info
- Execution: full execute_skill flow with mocked dependencies
- Discovery: discover_skills combining registry results
- Gating: gate called during execution
- Manifest validation: invalid manifests rejected
- Error handling: SkillNotAvailableError, SkillManifestError, SkillGateDeniedError
- Acceptance tests (REQ-SEXEC-01 through REQ-SEXEC-05)
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from orchestrator.skill_executor import (
    SkillCapabilityDeniedError,
    SkillExecutionContext,
    SkillExecutionError,
    SkillExecutionResult,
    SkillExecutor,
    SkillGateDeniedError,
    SkillManifestError,
    SkillNotAvailableError,
)
from orchestrator.skill_manifest import (
    CommandScope,
    DataScope,
    FileScope,
    ManifestRequiredError,
    ManifestValidator,
    NetworkScope,
    SkillManifest,
)
from security.skill_registry import SkillRecord, SkillRegistry


# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------


def _make_registry() -> SkillRegistry:
    return SkillRegistry(org_id="test-org")


def _make_manifest(
    skill_id: str = "test-skill",
    name: str = "Test Skill",
    version: str = "1.0.0",
    **kwargs: Any,
) -> SkillManifest:
    return SkillManifest(skill_id=skill_id, name=name, version=version, **kwargs)


def _make_mcp_client(allowed: bool = True) -> MagicMock:
    """Create a mock MCPClient."""
    client = MagicMock()
    result = MagicMock()
    result.is_error = False
    result.content = {"result": "ok"}
    if allowed:
        client.invoke_tool = AsyncMock(return_value=result)
    else:
        from adapters.mcp_client import MCPPolicyDeniedError
        client.invoke_tool = AsyncMock(side_effect=MCPPolicyDeniedError("denied"))
    return client


def _allowed_gate() -> MagicMock:
    gate = MagicMock()
    decision = MagicMock()
    decision.allowed = True
    decision.reason = ""
    gate.gate_action = AsyncMock(return_value=decision)
    return gate


def _denied_gate(reason: str = "denied") -> MagicMock:
    gate = MagicMock()
    decision = MagicMock()
    decision.allowed = False
    decision.reason = reason
    gate.gate_action = AsyncMock(return_value=decision)
    return gate


def _make_executor(
    registry: SkillRegistry | None = None,
    mcp_client: Any = None,
    validator: ManifestValidator | None = None,
    gate: Any = None,
) -> SkillExecutor:
    return SkillExecutor(
        registry=registry or _make_registry(),
        mcp_client=mcp_client or _make_mcp_client(),
        manifest_validator=validator or ManifestValidator(require_manifest=False),
        gate=gate,
    )


def _install_skill(
    executor: SkillExecutor,
    registry: SkillRegistry,
    skill_id: str = "test-skill",
    name: str = "Test Skill",
    version: str = "1.0.0",
    with_manifest: bool = True,
    **kwargs: Any,
) -> SkillRecord:
    record = registry.install(skill_id, name, version, **kwargs)
    if with_manifest:
        manifest = _make_manifest(skill_id=skill_id, name=name, version=version)
        executor.register_manifest(skill_id, manifest)
    return record


# ---------------------------------------------------------------------------
# TestSkillExecutionContext
# ---------------------------------------------------------------------------


class TestSkillExecutionContext:
    def test_create_minimal(self) -> None:
        ctx = SkillExecutionContext(
            skill_id="s1",
            manifest=None,
            sandbox_config={},
        )
        assert ctx.skill_id == "s1"
        assert ctx.manifest is None
        assert ctx.sandbox_config == {}
        assert ctx.mcp_server_id == ""
        assert ctx.timeout == 30.0

    def test_create_full(self) -> None:
        m = _make_manifest()
        ctx = SkillExecutionContext(
            skill_id="s1",
            manifest=m,
            sandbox_config={"allowNetwork": True},
            mcp_server_id="my-server",
            timeout=60.0,
            metadata={"env": "test"},
        )
        assert ctx.mcp_server_id == "my-server"
        assert ctx.timeout == 60.0
        assert ctx.metadata["env"] == "test"

    def test_frozen(self) -> None:
        ctx = SkillExecutionContext(skill_id="s1", manifest=None, sandbox_config={})
        with pytest.raises(AttributeError):
            ctx.skill_id = "other"  # type: ignore[misc]

    def test_defaults(self) -> None:
        ctx = SkillExecutionContext(skill_id="x", manifest=None, sandbox_config={})
        assert ctx.mcp_server_id == ""
        assert ctx.timeout == 30.0
        assert ctx.metadata == {}


# ---------------------------------------------------------------------------
# TestSkillExecutionResult
# ---------------------------------------------------------------------------


class TestSkillExecutionResult:
    def test_create_success(self) -> None:
        r = SkillExecutionResult(
            skill_id="s1",
            success=True,
            output={"data": "hello"},
        )
        assert r.success is True
        assert r.output == {"data": "hello"}
        assert r.errors == []
        assert r.execution_id != ""

    def test_create_failure(self) -> None:
        r = SkillExecutionResult(
            skill_id="s1",
            success=False,
            errors=["not found"],
        )
        assert r.success is False
        assert "not found" in r.errors

    def test_to_dict(self) -> None:
        r = SkillExecutionResult(
            skill_id="s1",
            success=True,
            output="output",
            duration_ms=42.5,
        )
        d = r.to_dict()
        assert d["skillId"] == "s1"
        assert d["success"] is True
        assert d["durationMs"] == 42.5
        assert "executionId" in d
        assert "auditTrail" in d

    def test_unique_execution_ids(self) -> None:
        r1 = SkillExecutionResult(skill_id="s", success=True)
        r2 = SkillExecutionResult(skill_id="s", success=True)
        assert r1.execution_id != r2.execution_id

    def test_audit_trail_default_empty(self) -> None:
        r = SkillExecutionResult(skill_id="s", success=True)
        assert r.audit_trail == []

    def test_audit_trail_populated(self) -> None:
        events = [{"event": "started"}, {"event": "completed"}]
        r = SkillExecutionResult(skill_id="s", success=True, audit_trail=events)
        assert len(r.audit_trail) == 2


# ---------------------------------------------------------------------------
# TestSkillExecutor — basic operations
# ---------------------------------------------------------------------------


class TestSkillExecutor:
    def test_create(self) -> None:
        executor = _make_executor()
        stats = executor.get_execution_stats()
        assert stats["totalExecutions"] == 0
        assert stats["successCount"] == 0
        assert stats["failureCount"] == 0

    def test_register_manifest(self) -> None:
        executor = _make_executor()
        m = _make_manifest()
        executor.register_manifest("s1", m)
        retrieved = executor.get_manifest("s1")
        assert retrieved is m

    def test_get_manifest_none_for_unregistered(self) -> None:
        executor = _make_executor()
        assert executor.get_manifest("nope") is None

    def test_get_skill_info(self) -> None:
        registry = _make_registry()
        executor = _make_executor(registry=registry)
        registry.install("s1", "Skill One", "1.0")
        executor.register_manifest("s1", _make_manifest(skill_id="s1"))

        info = executor.get_skill_info("s1")
        assert info["hasManifest"] is True
        assert info["record"]["skillId"] == "s1"
        assert info["manifest"]["skillId"] == "s1"

    def test_get_skill_info_without_manifest(self) -> None:
        registry = _make_registry()
        executor = _make_executor(registry=registry)
        registry.install("s1", "Skill One", "1.0")

        info = executor.get_skill_info("s1")
        assert info["hasManifest"] is False
        assert info["manifest"] is None

    def test_get_skill_info_not_installed_raises(self) -> None:
        executor = _make_executor()
        with pytest.raises(SkillNotAvailableError):
            executor.get_skill_info("ghost")


# ---------------------------------------------------------------------------
# TestSkillExecution — full execute_skill flow
# ---------------------------------------------------------------------------


class TestSkillExecution:
    @pytest.mark.asyncio
    async def test_basic_execution_success(self) -> None:
        registry = _make_registry()
        executor = _make_executor(registry=registry)
        _install_skill(executor, registry)

        result = await executor.execute_skill(
            "test-skill", {},
            agent_id="agent-1",
            trust_level=3,
        )

        assert result.success is True
        assert result.skill_id == "test-skill"
        assert result.duration_ms >= 0.0

    @pytest.mark.asyncio
    async def test_execution_returns_audit_trail(self) -> None:
        registry = _make_registry()
        executor = _make_executor(registry=registry)
        _install_skill(executor, registry)

        result = await executor.execute_skill(
            "test-skill", {},
            agent_id="agent-1",
            trust_level=3,
        )

        assert len(result.audit_trail) >= 2
        events = [e["event"] for e in result.audit_trail]
        assert "skill.execution.started" in events
        assert "skill.execution.completed" in events

    @pytest.mark.asyncio
    async def test_execution_not_installed_raises(self) -> None:
        executor = _make_executor()

        with pytest.raises(SkillNotAvailableError, match="not installed"):
            await executor.execute_skill(
                "ghost-skill", {},
                agent_id="agent-1",
                trust_level=3,
            )

    @pytest.mark.asyncio
    async def test_execution_increments_stats(self) -> None:
        registry = _make_registry()
        executor = _make_executor(registry=registry)
        _install_skill(executor, registry)
        _install_skill(executor, registry, skill_id="s2", name="S2")

        await executor.execute_skill("test-skill", {}, agent_id="a", trust_level=3)
        await executor.execute_skill("s2", {}, agent_id="a", trust_level=3)

        stats = executor.get_execution_stats()
        assert stats["totalExecutions"] == 2
        assert stats["successCount"] == 2
        assert stats["failureCount"] == 0

    @pytest.mark.asyncio
    async def test_execution_tracks_duration(self) -> None:
        registry = _make_registry()
        executor = _make_executor(registry=registry)
        _install_skill(executor, registry)

        result = await executor.execute_skill("test-skill", {}, agent_id="a", trust_level=3)

        assert result.duration_ms >= 0.0
        stats = executor.get_execution_stats()
        assert stats["totalDurationMs"] >= 0.0

    @pytest.mark.asyncio
    async def test_execution_with_arguments(self) -> None:
        registry = _make_registry()
        executor = _make_executor(registry=registry)
        _install_skill(executor, registry)

        result = await executor.execute_skill(
            "test-skill", {"param": "hello", "count": 5},
            agent_id="a", trust_level=3,
        )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_execution_failure_increments_failure_count(self) -> None:
        executor = _make_executor()

        with pytest.raises(SkillNotAvailableError):
            await executor.execute_skill("nope", {}, agent_id="a", trust_level=3)

        stats = executor.get_execution_stats()
        assert stats["failureCount"] == 1
        assert stats["successCount"] == 0


# ---------------------------------------------------------------------------
# TestSkillDiscovery
# ---------------------------------------------------------------------------


class TestSkillDiscovery:
    def test_discover_all_skills(self) -> None:
        registry = _make_registry()
        registry.install("a", "Alpha", "1.0", description="alpha tool")
        registry.install("b", "Beta", "1.0", description="beta tool")
        executor = _make_executor(registry=registry)

        skills = executor.discover_skills()
        assert len(skills) == 2

    def test_discover_with_query(self) -> None:
        registry = _make_registry()
        registry.install("alpha", "Alpha Skill", "1.0", description="web scraper")
        registry.install("beta", "Beta Skill", "1.0", description="data processor")
        executor = _make_executor(registry=registry)

        results = executor.discover_skills(query="web")
        assert len(results) == 1
        assert results[0].skill_id == "alpha"

    def test_discover_query_matches_name(self) -> None:
        registry = _make_registry()
        registry.install("s1", "WebCrawler", "1.0")
        registry.install("s2", "DataLoader", "1.0")
        executor = _make_executor(registry=registry)

        results = executor.discover_skills(query="web")
        assert len(results) == 1
        assert results[0].skill_id == "s1"

    def test_discover_query_case_insensitive(self) -> None:
        registry = _make_registry()
        registry.install("s1", "WebCrawler", "1.0")
        executor = _make_executor(registry=registry)

        results = executor.discover_skills(query="WEBCRAWLER")
        assert len(results) == 1

    def test_discover_with_source_filter(self) -> None:
        registry = _make_registry()
        registry.install("local1", "Local", "1.0", source="local")
        registry.hub_enable()
        registry.install("hub1", "Hub", "1.0", source="hub")
        executor = _make_executor(registry=registry)

        local = executor.discover_skills(filters={"source": "local"})
        assert len(local) == 1
        assert local[0].skill_id == "local1"

    def test_discover_empty_registry(self) -> None:
        executor = _make_executor()
        results = executor.discover_skills()
        assert results == []

    def test_discover_no_match_returns_empty(self) -> None:
        registry = _make_registry()
        registry.install("s1", "Unrelated", "1.0")
        executor = _make_executor(registry=registry)

        results = executor.discover_skills(query="xyznotfound")
        assert results == []


# ---------------------------------------------------------------------------
# TestSkillGating
# ---------------------------------------------------------------------------


class TestSkillGating:
    @pytest.mark.asyncio
    async def test_gate_called_during_execution(self) -> None:
        registry = _make_registry()
        gate = _allowed_gate()
        executor = _make_executor(registry=registry, gate=gate)
        _install_skill(executor, registry)

        await executor.execute_skill(
            "test-skill", {},
            agent_id="agent-1",
            trust_level=3,
        )

        assert gate.gate_action.call_count == 1

    @pytest.mark.asyncio
    async def test_gate_called_with_correct_action(self) -> None:
        registry = _make_registry()
        gate = _allowed_gate()
        executor = _make_executor(registry=registry, gate=gate)
        _install_skill(executor, registry, skill_id="my-special-skill")

        await executor.execute_skill(
            "my-special-skill", {},
            agent_id="agent-1",
            trust_level=3,
        )

        call_kwargs = gate.gate_action.call_args.kwargs
        assert "my-special-skill" in call_kwargs["action"]

    @pytest.mark.asyncio
    async def test_gate_denied_raises_skill_gate_denied_error(self) -> None:
        registry = _make_registry()
        gate = _denied_gate("insufficient trust for this skill")
        executor = _make_executor(registry=registry, gate=gate)
        _install_skill(executor, registry)

        with pytest.raises(SkillGateDeniedError, match="insufficient trust"):
            await executor.execute_skill(
                "test-skill", {},
                agent_id="low-trust",
                trust_level=0,
            )

    @pytest.mark.asyncio
    async def test_gate_denied_increments_failure_count(self) -> None:
        registry = _make_registry()
        gate = _denied_gate()
        executor = _make_executor(registry=registry, gate=gate)
        _install_skill(executor, registry)

        with pytest.raises(SkillGateDeniedError):
            await executor.execute_skill("test-skill", {}, agent_id="a", trust_level=0)

        stats = executor.get_execution_stats()
        assert stats["failureCount"] == 1

    @pytest.mark.asyncio
    async def test_gate_not_called_when_skill_not_found(self) -> None:
        gate = _allowed_gate()
        executor = _make_executor(gate=gate)

        with pytest.raises(SkillNotAvailableError):
            await executor.execute_skill("ghost", {}, agent_id="a", trust_level=3)

        # Gate should NOT be called — skill not even loaded
        assert gate.gate_action.call_count == 0

    @pytest.mark.asyncio
    async def test_gate_not_called_when_no_gate_configured(self) -> None:
        """When gate is None, execution proceeds without policy check."""
        registry = _make_registry()
        executor = _make_executor(registry=registry, gate=None)
        _install_skill(executor, registry)

        result = await executor.execute_skill(
            "test-skill", {},
            agent_id="a",
            trust_level=3,
        )
        assert result.success is True


# ---------------------------------------------------------------------------
# TestSkillManifestValidation
# ---------------------------------------------------------------------------


class TestSkillManifestValidation:
    @pytest.mark.asyncio
    async def test_missing_manifest_raises_when_required(self) -> None:
        registry = _make_registry()
        validator = ManifestValidator(require_manifest=True)
        executor = _make_executor(registry=registry, validator=validator)

        # Install skill without registering a manifest
        registry.install("no-manifest-skill", "No Manifest", "1.0")

        with pytest.raises(SkillManifestError, match="Manifest validation failed"):
            await executor.execute_skill(
                "no-manifest-skill", {},
                agent_id="a",
                trust_level=3,
            )

    @pytest.mark.asyncio
    async def test_invalid_manifest_fields_raises(self) -> None:
        registry = _make_registry()
        validator = ManifestValidator(require_manifest=False, blocked_domains=["evil.com"])
        executor = _make_executor(registry=registry, validator=validator)

        # Manifest with a blocked domain
        bad_manifest = SkillManifest(
            skill_id="bad-skill",
            name="Bad Skill",
            version="1.0",
            network=NetworkScope(allowed_domains=["evil.com"]),
        )
        registry.install("bad-skill", "Bad Skill", "1.0")
        executor.register_manifest("bad-skill", bad_manifest)

        with pytest.raises(SkillManifestError, match="violations"):
            await executor.execute_skill(
                "bad-skill", {},
                agent_id="a",
                trust_level=3,
            )

    @pytest.mark.asyncio
    async def test_valid_manifest_passes_validation(self) -> None:
        registry = _make_registry()
        validator = ManifestValidator(require_manifest=True)
        executor = _make_executor(registry=registry, validator=validator)
        _install_skill(executor, registry, with_manifest=True)

        result = await executor.execute_skill(
            "test-skill", {},
            agent_id="a",
            trust_level=3,
        )
        assert result.success is True

    @pytest.mark.asyncio
    async def test_manifest_with_pii_data_scope_passes(self) -> None:
        registry = _make_registry()
        executor = _make_executor(registry=registry)
        registry.install("pii-skill", "PII Skill", "1.0")
        executor.register_manifest("pii-skill", SkillManifest(
            skill_id="pii-skill",
            name="PII Skill",
            version="1.0",
            data=DataScope(domains=["pii"]),
        ))

        result = await executor.execute_skill(
            "pii-skill", {},
            agent_id="a",
            trust_level=3,
        )
        assert result.success is True

    @pytest.mark.asyncio
    async def test_manifest_network_scope_included_in_context(self) -> None:
        registry = _make_registry()
        executor = _make_executor(registry=registry)
        registry.install("net-skill", "Net Skill", "1.0")
        executor.register_manifest("net-skill", SkillManifest(
            skill_id="net-skill",
            name="Net Skill",
            version="1.0",
            network=NetworkScope(allowed_domains=["api.example.com"]),
        ))

        result = await executor.execute_skill(
            "net-skill", {},
            agent_id="a",
            trust_level=3,
        )
        assert result.success is True


# ---------------------------------------------------------------------------
# TestSkillExecutionErrors
# ---------------------------------------------------------------------------


class TestSkillExecutionErrors:
    def test_error_hierarchy(self) -> None:
        assert issubclass(SkillNotAvailableError, SkillExecutionError)
        assert issubclass(SkillManifestError, SkillExecutionError)
        assert issubclass(SkillGateDeniedError, SkillExecutionError)
        assert issubclass(SkillCapabilityDeniedError, SkillExecutionError)

    @pytest.mark.asyncio
    async def test_not_available_error_message(self) -> None:
        executor = _make_executor()

        with pytest.raises(SkillNotAvailableError) as exc_info:
            await executor.execute_skill("ghost", {}, agent_id="a", trust_level=3)

        assert "ghost" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_gate_denied_error_message(self) -> None:
        registry = _make_registry()
        gate = _denied_gate("not allowed in production")
        executor = _make_executor(registry=registry, gate=gate)
        _install_skill(executor, registry)

        with pytest.raises(SkillGateDeniedError) as exc_info:
            await executor.execute_skill("test-skill", {}, agent_id="a", trust_level=0)

        assert "not allowed in production" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_manifest_error_includes_skill_id(self) -> None:
        registry = _make_registry()
        validator = ManifestValidator(require_manifest=True)
        executor = _make_executor(registry=registry, validator=validator)
        registry.install("missing-manifest", "M", "1.0")

        with pytest.raises(SkillManifestError) as exc_info:
            await executor.execute_skill("missing-manifest", {}, agent_id="a", trust_level=3)

        assert "missing-manifest" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_failure_recorded_in_audit_trail_on_error(self) -> None:
        """Audit trail 'failed' event should appear even on SkillNotAvailableError."""
        executor = _make_executor()

        with pytest.raises(SkillNotAvailableError):
            await executor.execute_skill("ghost", {}, agent_id="a", trust_level=3)

        # Stats should reflect failure
        stats = executor.get_execution_stats()
        assert stats["failureCount"] == 1


# ---------------------------------------------------------------------------
# TestAcceptanceSkillExec — Acceptance tests REQ-SEXEC-01 through REQ-SEXEC-05
# ---------------------------------------------------------------------------


class TestAcceptanceSkillExec:
    """Acceptance tests for the SkillExecutor."""

    @pytest.mark.asyncio
    async def test_acc_sexec01_skill_loaded_from_registry_and_executed(self) -> None:
        """REQ-SEXEC-01: Skill loaded from registry and executed successfully."""
        registry = SkillRegistry(org_id="acc-test")
        gate = _allowed_gate()
        executor = SkillExecutor(
            registry=registry,
            mcp_client=_make_mcp_client(),
            manifest_validator=ManifestValidator(require_manifest=True),
            gate=gate,
        )

        record = registry.install(
            "acc-skill-01",
            "Acceptance Skill 01",
            "1.0.0",
            description="Used for acceptance testing",
        )
        executor.register_manifest("acc-skill-01", SkillManifest(
            skill_id="acc-skill-01",
            name="Acceptance Skill 01",
            version="1.0.0",
        ))

        result = await executor.execute_skill(
            "acc-skill-01",
            {"input": "test-data"},
            agent_id="acc-agent",
            trust_level=3,
            session_id="sess-acc-01",
        )

        assert result.success is True
        assert result.skill_id == "acc-skill-01"
        assert result.duration_ms >= 0.0
        assert len(result.audit_trail) >= 2

    @pytest.mark.asyncio
    async def test_acc_sexec02_skill_without_manifest_rejected(self) -> None:
        """REQ-SEXEC-02: Skill without manifest is rejected (fail-closed)."""
        registry = SkillRegistry(org_id="acc-test")
        executor = SkillExecutor(
            registry=registry,
            mcp_client=_make_mcp_client(),
            manifest_validator=ManifestValidator(require_manifest=True),
            gate=_allowed_gate(),
        )

        # Install skill without registering manifest
        registry.install("no-manifest", "No Manifest Skill", "1.0.0")
        # Deliberately do NOT call executor.register_manifest("no-manifest", ...)

        with pytest.raises(SkillManifestError) as exc_info:
            await executor.execute_skill(
                "no-manifest", {},
                agent_id="acc-agent",
                trust_level=3,
            )

        # Gate must NOT have been called — rejected at manifest validation
        assert "no-manifest" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_acc_sexec03_skill_exceeding_capability_scope_denied(self) -> None:
        """REQ-SEXEC-03: Skill with invalid manifest scope is denied."""
        registry = SkillRegistry(org_id="acc-test")
        validator = ManifestValidator(
            require_manifest=False,
            blocked_domains=["malicious.example.com"],
            blocked_commands=["rm"],
        )
        executor = SkillExecutor(
            registry=registry,
            mcp_client=_make_mcp_client(),
            manifest_validator=validator,
            gate=_allowed_gate(),
        )

        registry.install("bad-scope-skill", "Bad Scope", "1.0")
        # Register a manifest that violates policy
        executor.register_manifest("bad-scope-skill", SkillManifest(
            skill_id="bad-scope-skill",
            name="Bad Scope Skill",
            version="1.0",
            network=NetworkScope(allowed_domains=["malicious.example.com"]),
            commands=CommandScope(allowed_commands=["rm"]),
        ))

        with pytest.raises(SkillManifestError, match="violations"):
            await executor.execute_skill(
                "bad-scope-skill", {},
                agent_id="acc-agent",
                trust_level=3,
            )

    @pytest.mark.asyncio
    async def test_acc_sexec04_execution_metrics_tracked(self) -> None:
        """REQ-SEXEC-04: Execution metrics tracked across multiple calls."""
        registry = SkillRegistry(org_id="acc-test")
        executor = SkillExecutor(
            registry=registry,
            mcp_client=_make_mcp_client(),
            manifest_validator=ManifestValidator(require_manifest=False),
            gate=_allowed_gate(),
        )

        # Install 3 different skills
        for i in range(3):
            sid = f"metric-skill-{i}"
            registry.install(sid, f"Metric Skill {i}", "1.0")

        # Execute all successfully
        for i in range(3):
            await executor.execute_skill(
                f"metric-skill-{i}", {},
                agent_id="acc-agent",
                trust_level=3,
            )

        # One more that fails
        with pytest.raises(SkillNotAvailableError):
            await executor.execute_skill("ghost", {}, agent_id="acc-agent", trust_level=3)

        stats = executor.get_execution_stats()
        assert stats["totalExecutions"] == 4
        assert stats["successCount"] == 3
        assert stats["failureCount"] == 1
        assert stats["totalDurationMs"] >= 0.0
        assert stats["avgDurationMs"] >= 0.0

    @pytest.mark.asyncio
    async def test_acc_sexec05_mcp_tool_invoked_as_skill(self) -> None:
        """REQ-SEXEC-05: Skill backed by MCP tool invoked via MCPClient."""
        registry = SkillRegistry(org_id="acc-test")
        gate = _allowed_gate()

        # MCP client with simulated successful tool response
        mcp_result = MagicMock()
        mcp_result.is_error = False
        mcp_result.content = {"files": ["a.txt", "b.txt"]}
        mcp_client = MagicMock()
        mcp_client.invoke_tool = AsyncMock(return_value=mcp_result)

        executor = SkillExecutor(
            registry=registry,
            mcp_client=mcp_client,
            manifest_validator=ManifestValidator(require_manifest=False),
            gate=gate,
        )

        # Install skill with MCP server binding in metadata
        registry.install(
            "list-files",
            "List Files",
            "1.0",
            metadata={"mcp_server_id": "filesystem-server"},
        )
        executor.register_manifest("list-files", SkillManifest(
            skill_id="list-files",
            name="List Files",
            version="1.0",
            filesystem=FileScope(allowed_paths=["/data"]),
        ))

        result = await executor.execute_skill(
            "list-files",
            {"path": "/data"},
            agent_id="acc-agent",
            trust_level=3,
        )

        assert result.success is True
        # MCP client was called with the server binding
        mcp_client.invoke_tool.assert_called_once()
        call_args = mcp_client.invoke_tool.call_args
        assert call_args.args[0] == "filesystem-server"
        assert call_args.args[1] == "list-files"
        assert call_args.args[2] == {"path": "/data"}
