"""Tests for security.provenance — SLSA Build L2+ provenance (REQ-CPC-01).

Covers:
- ProvenanceGenerator: generation with full/partial params, validation errors
- SLSAStatement: serialization, content_hash determinism, round-trip
- ProvenanceValidator: statement validation, dict validation, builder allowlist
- BuildLevel enforcement
"""

from __future__ import annotations

import json
import pytest

from security.provenance import (
    BuildLevel,
    ProvenanceError,
    ProvenanceGenerator,
    ProvenanceValidator,
    ProvenanceValidationError,
    ResourceDescriptor,
    BuildDefinition,
    RunDetails,
    SLSAProvenance,
    SLSAStatement,
    SLSA_STATEMENT_TYPE,
    SLSA_PROVENANCE_PREDICATE_TYPE,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def generator() -> ProvenanceGenerator:
    return ProvenanceGenerator(builder_id="occp-ci/v1")


@pytest.fixture
def sample_statement(generator: ProvenanceGenerator) -> SLSAStatement:
    return generator.generate(
        subject_name="my-skill",
        subject_digest={"sha256": "abc123def456"},
        source_repo="https://github.com/org/repo",
        source_commit="deadbeef1234",
        invocation_id="build-42",
    )


# ---------------------------------------------------------------------------
# ProvenanceGenerator
# ---------------------------------------------------------------------------

class TestProvenanceGenerator:
    def test_generate_full(self, generator: ProvenanceGenerator) -> None:
        stmt = generator.generate(
            subject_name="skill-a",
            subject_digest={"sha256": "aabbcc"},
            source_repo="https://github.com/org/repo",
            source_commit="abc123",
            build_inputs={"version": "1.0.0"},
            invocation_id="inv-1",
            metadata={"ci": "github-actions"},
        )
        assert stmt.statement_type == SLSA_STATEMENT_TYPE
        assert stmt.predicate_type == SLSA_PROVENANCE_PREDICATE_TYPE
        assert len(stmt.subjects) == 1
        assert stmt.subjects[0].name == "skill-a"
        assert stmt.subjects[0].digest == {"sha256": "aabbcc"}
        assert stmt.predicate.run_details.builder_id == "occp-ci/v1"
        assert stmt.predicate.run_details.build_level == BuildLevel.L2

    def test_generate_minimal(self, generator: ProvenanceGenerator) -> None:
        stmt = generator.generate(
            subject_name="minimal",
            subject_digest={"sha256": "000"},
        )
        assert stmt.subjects[0].name == "minimal"
        assert stmt.predicate.build_definition.build_type == generator.DEFAULT_BUILD_TYPE

    def test_generate_missing_subject_name(self, generator: ProvenanceGenerator) -> None:
        with pytest.raises(ProvenanceError, match="subject_name"):
            generator.generate(subject_name="", subject_digest={"sha256": "x"})

    def test_generate_missing_sha256(self, generator: ProvenanceGenerator) -> None:
        with pytest.raises(ProvenanceError, match="sha256"):
            generator.generate(subject_name="s", subject_digest={"md5": "x"})

    def test_generate_empty_builder_id(self) -> None:
        with pytest.raises(ProvenanceError, match="builder_id"):
            ProvenanceGenerator(builder_id="")

    def test_generate_with_dependencies(self, generator: ProvenanceGenerator) -> None:
        dep = ResourceDescriptor(
            name="base-image", digest={"sha256": "img123"}, uri="docker://alpine:3.18"
        )
        stmt = generator.generate(
            subject_name="s",
            subject_digest={"sha256": "x"},
            source_repo="https://github.com/org/repo",
            source_commit="abc",
            dependencies=[dep],
        )
        deps = stmt.predicate.build_definition.resolved_dependencies
        # source dep auto-inserted + our dep
        assert len(deps) == 2
        assert deps[0].name == "source"
        assert deps[1].name == "base-image"

    def test_generate_source_added_to_deps(self, generator: ProvenanceGenerator) -> None:
        stmt = generator.generate(
            subject_name="s",
            subject_digest={"sha256": "x"},
            source_repo="https://github.com/org/repo",
            source_commit="deadbeef",
        )
        deps = stmt.predicate.build_definition.resolved_dependencies
        assert any(d.name == "source" and d.digest.get("sha1") == "deadbeef" for d in deps)

    def test_generate_no_source_no_auto_dep(self, generator: ProvenanceGenerator) -> None:
        stmt = generator.generate(
            subject_name="s",
            subject_digest={"sha256": "x"},
        )
        assert len(stmt.predicate.build_definition.resolved_dependencies) == 0

    def test_custom_build_type(self) -> None:
        gen = ProvenanceGenerator(builder_id="b", build_type="https://custom/v2")
        stmt = gen.generate(subject_name="s", subject_digest={"sha256": "x"})
        assert stmt.predicate.build_definition.build_type == "https://custom/v2"

    def test_builder_id_property(self, generator: ProvenanceGenerator) -> None:
        assert generator.builder_id == "occp-ci/v1"


# ---------------------------------------------------------------------------
# SLSAStatement serialization
# ---------------------------------------------------------------------------

class TestSLSAStatement:
    def test_to_dict(self, sample_statement: SLSAStatement) -> None:
        d = sample_statement.to_dict()
        assert d["_type"] == SLSA_STATEMENT_TYPE
        assert d["predicateType"] == SLSA_PROVENANCE_PREDICATE_TYPE
        assert len(d["subject"]) == 1
        assert d["subject"][0]["name"] == "my-skill"
        assert "predicate" in d

    def test_to_json_deterministic(self, sample_statement: SLSAStatement) -> None:
        j1 = sample_statement.to_json()
        j2 = sample_statement.to_json()
        assert j1 == j2
        parsed = json.loads(j1)
        assert parsed["_type"] == SLSA_STATEMENT_TYPE

    def test_content_hash_deterministic(self, sample_statement: SLSAStatement) -> None:
        h1 = sample_statement.content_hash()
        h2 = sample_statement.content_hash()
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex

    def test_content_hash_different_for_different_input(self, generator: ProvenanceGenerator) -> None:
        s1 = generator.generate(subject_name="a", subject_digest={"sha256": "x"})
        s2 = generator.generate(subject_name="b", subject_digest={"sha256": "y"})
        assert s1.content_hash() != s2.content_hash()

    def test_to_json_roundtrip(self, sample_statement: SLSAStatement) -> None:
        j = sample_statement.to_json()
        parsed = json.loads(j)
        assert parsed["subject"][0]["digest"]["sha256"] == "abc123def456"


# ---------------------------------------------------------------------------
# ResourceDescriptor
# ---------------------------------------------------------------------------

class TestResourceDescriptor:
    def test_to_dict_minimal(self) -> None:
        rd = ResourceDescriptor(name="foo", digest={"sha256": "abc"})
        d = rd.to_dict()
        assert d == {"name": "foo", "digest": {"sha256": "abc"}}
        assert "uri" not in d
        assert "annotations" not in d

    def test_to_dict_full(self) -> None:
        rd = ResourceDescriptor(
            name="bar",
            digest={"sha256": "xyz"},
            uri="https://example.com",
            annotations={"key": "value"},
        )
        d = rd.to_dict()
        assert d["uri"] == "https://example.com"
        assert d["annotations"] == {"key": "value"}


# ---------------------------------------------------------------------------
# BuildDefinition / RunDetails
# ---------------------------------------------------------------------------

class TestBuildModels:
    def test_build_definition_to_dict(self) -> None:
        bd = BuildDefinition(
            build_type="https://type/v1",
            external_parameters={"a": 1},
            internal_parameters={"b": 2},
        )
        d = bd.to_dict()
        assert d["buildType"] == "https://type/v1"
        assert d["externalParameters"] == {"a": 1}
        assert d["internalParameters"] == {"b": 2}
        assert d["resolvedDependencies"] == []

    def test_run_details_to_dict(self) -> None:
        rd = RunDetails(
            builder_id="test-builder",
            build_level=BuildLevel.L3,
            invocation_id="inv-99",
            started_on="2026-01-01T00:00:00Z",
            finished_on="2026-01-01T00:01:00Z",
        )
        d = rd.to_dict()
        assert d["builder"]["id"] == "test-builder"
        assert d["metadata"]["buildInvocationId"] == "inv-99"
        assert d["metadata"]["buildStartedOn"] == "2026-01-01T00:00:00Z"


# ---------------------------------------------------------------------------
# ProvenanceValidator
# ---------------------------------------------------------------------------

class TestProvenanceValidator:
    def test_valid_statement(self, sample_statement: SLSAStatement) -> None:
        v = ProvenanceValidator()
        violations = v.validate_statement(sample_statement)
        assert violations == []

    def test_invalid_statement_type(self, generator: ProvenanceGenerator) -> None:
        stmt = generator.generate(subject_name="s", subject_digest={"sha256": "x"})
        bad = SLSAStatement(
            subjects=stmt.subjects,
            predicate=stmt.predicate,
            statement_type="wrong",
        )
        v = ProvenanceValidator()
        violations = v.validate_statement(bad)
        assert any("statement type" in v.lower() for v in violations)

    def test_invalid_predicate_type(self, generator: ProvenanceGenerator) -> None:
        stmt = generator.generate(subject_name="s", subject_digest={"sha256": "x"})
        bad = SLSAStatement(
            subjects=stmt.subjects,
            predicate=stmt.predicate,
            predicate_type="wrong",
        )
        v = ProvenanceValidator()
        violations = v.validate_statement(bad)
        assert any("predicate type" in v.lower() for v in violations)

    def test_no_subjects(self, generator: ProvenanceGenerator) -> None:
        stmt = generator.generate(subject_name="s", subject_digest={"sha256": "x"})
        empty = SLSAStatement(subjects=[], predicate=stmt.predicate)
        v = ProvenanceValidator()
        violations = v.validate_statement(empty)
        assert any("No subjects" in v for v in violations)

    def test_subject_missing_sha256(self, generator: ProvenanceGenerator) -> None:
        stmt = generator.generate(subject_name="s", subject_digest={"sha256": "x"})
        bad_subj = ResourceDescriptor(name="bad", digest={"md5": "abc"})
        bad = SLSAStatement(subjects=[bad_subj], predicate=stmt.predicate)
        v = ProvenanceValidator()
        violations = v.validate_statement(bad)
        assert any("sha256" in v for v in violations)

    def test_builder_allowlist_pass(self, sample_statement: SLSAStatement) -> None:
        v = ProvenanceValidator(allowed_builders=["occp-ci/v1", "other"])
        violations = v.validate_statement(sample_statement)
        assert violations == []

    def test_builder_allowlist_fail(self, sample_statement: SLSAStatement) -> None:
        v = ProvenanceValidator(allowed_builders=["only-this"])
        violations = v.validate_statement(sample_statement)
        assert any("not in allowed" in v for v in violations)

    def test_build_level_below_minimum(self, generator: ProvenanceGenerator) -> None:
        # Generator defaults to L2; create a validator requiring L3
        stmt = generator.generate(
            subject_name="s",
            subject_digest={"sha256": "x"},
            source_repo="r",
            source_commit="c",
        )
        v = ProvenanceValidator(min_level=BuildLevel.L3)
        violations = v.validate_statement(stmt)
        assert any("Build level" in v for v in violations)

    def test_l2_requires_source_traceability(self) -> None:
        # Create a statement with no source info
        gen = ProvenanceGenerator(builder_id="b")
        stmt = gen.generate(subject_name="s", subject_digest={"sha256": "x"})
        v = ProvenanceValidator(min_level=BuildLevel.L2)
        violations = v.validate_statement(stmt)
        assert any("source commit" in v.lower() for v in violations)

    def test_validate_dict_valid(self, sample_statement: SLSAStatement) -> None:
        d = sample_statement.to_dict()
        v = ProvenanceValidator()
        violations = v.validate_dict(d)
        assert violations == []

    def test_validate_dict_invalid_type(self) -> None:
        v = ProvenanceValidator()
        violations = v.validate_dict({"_type": "bad", "predicateType": "bad"})
        assert len(violations) >= 2

    def test_validate_dict_missing_builder(self, sample_statement: SLSAStatement) -> None:
        d = sample_statement.to_dict()
        d["predicate"]["runDetails"]["builder"]["id"] = ""
        v = ProvenanceValidator()
        violations = v.validate_dict(d)
        assert any("builder" in v.lower() for v in violations)

    def test_validate_dict_builder_allowlist(self, sample_statement: SLSAStatement) -> None:
        d = sample_statement.to_dict()
        v = ProvenanceValidator(allowed_builders=["not-this"])
        violations = v.validate_dict(d)
        assert any("not allowed" in v for v in violations)


# ---------------------------------------------------------------------------
# BuildLevel
# ---------------------------------------------------------------------------

class TestBuildLevel:
    def test_enum_values(self) -> None:
        assert BuildLevel.L0.value == 0
        assert BuildLevel.L1.value == 1
        assert BuildLevel.L2.value == 2
        assert BuildLevel.L3.value == 3

    def test_comparison(self) -> None:
        assert BuildLevel.L2.value >= BuildLevel.L2.value
        assert BuildLevel.L3.value > BuildLevel.L2.value
        assert BuildLevel.L1.value < BuildLevel.L2.value
