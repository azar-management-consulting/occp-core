"""SLSA Provenance — Build L2+ provenance metadata for OCCP artifacts.

REQ-CPC-01: All skills, MCP servers, and container images include SLSA
Build L2+ provenance metadata attesting: source repo, build system,
build inputs (commit SHA, builder identity, timestamp).

Provenance is stored as an in-toto Statement (SLSA Provenance v1.0 predicate)
serialized to JSON and signed via the `signing` module.

Usage::

    gen = ProvenanceGenerator(builder_id="occp-ci/v1")
    stmt = gen.generate(
        subject_name="my-skill",
        subject_digest={"sha256": "abc123..."},
        source_repo="https://github.com/org/repo",
        source_commit="deadbeef",
    )
    # stmt is a SLSAStatement dataclass — .to_dict() for JSON serialization
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SLSA constants
# ---------------------------------------------------------------------------

SLSA_STATEMENT_TYPE = "https://in-toto.io/Statement/v1"
SLSA_PROVENANCE_PREDICATE_TYPE = "https://slsa.dev/provenance/v1"
SLSA_BUILD_LEVEL_MIN = 2  # L2+ required


class BuildLevel(Enum):
    """SLSA Build Track levels."""

    L0 = 0
    L1 = 1
    L2 = 2
    L3 = 3


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ResourceDescriptor:
    """SLSA resource descriptor — identifies a subject or material."""

    name: str
    digest: dict[str, str]
    uri: str = ""
    annotations: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"name": self.name, "digest": dict(self.digest)}
        if self.uri:
            d["uri"] = self.uri
        if self.annotations:
            d["annotations"] = dict(self.annotations)
        return d


@dataclass(frozen=True)
class BuildDefinition:
    """SLSA Build Definition — describes how the artifact was built."""

    build_type: str
    external_parameters: dict[str, Any] = field(default_factory=dict)
    internal_parameters: dict[str, Any] = field(default_factory=dict)
    resolved_dependencies: list[ResourceDescriptor] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "buildType": self.build_type,
            "externalParameters": dict(self.external_parameters),
            "internalParameters": dict(self.internal_parameters),
            "resolvedDependencies": [d.to_dict() for d in self.resolved_dependencies],
        }


@dataclass(frozen=True)
class RunDetails:
    """SLSA Run Details — who/when/where the build happened."""

    builder_id: str
    build_level: BuildLevel = BuildLevel.L2
    invocation_id: str = ""
    started_on: str = ""
    finished_on: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "builder": {
                "id": self.builder_id,
                "builderDependencies": [],
                "version": {},
            },
            "metadata": {
                "buildInvocationId": self.invocation_id,
                "buildStartedOn": self.started_on,
                "buildFinishedOn": self.finished_on,
                **self.metadata,
            },
        }
        return d


@dataclass(frozen=True)
class SLSAProvenance:
    """SLSA Provenance v1.0 predicate."""

    build_definition: BuildDefinition
    run_details: RunDetails

    def to_dict(self) -> dict[str, Any]:
        return {
            "buildDefinition": self.build_definition.to_dict(),
            "runDetails": self.run_details.to_dict(),
        }


@dataclass(frozen=True)
class SLSAStatement:
    """In-toto Statement wrapping SLSA Provenance."""

    subjects: list[ResourceDescriptor]
    predicate: SLSAProvenance
    statement_type: str = SLSA_STATEMENT_TYPE
    predicate_type: str = SLSA_PROVENANCE_PREDICATE_TYPE

    def to_dict(self) -> dict[str, Any]:
        return {
            "_type": self.statement_type,
            "predicateType": self.predicate_type,
            "subject": [s.to_dict() for s in self.subjects],
            "predicate": self.predicate.to_dict(),
        }

    def to_json(self) -> str:
        """Canonical JSON serialization (sorted keys, no indent)."""
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

    def content_hash(self) -> str:
        """SHA-256 of the canonical JSON — used for signing."""
        return hashlib.sha256(self.to_json().encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Provenance errors
# ---------------------------------------------------------------------------


class ProvenanceError(Exception):
    """Base error for provenance operations."""


class ProvenanceValidationError(ProvenanceError):
    """Provenance metadata failed validation."""


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------


class ProvenanceGenerator:
    """Generates SLSA Build L2+ provenance statements for OCCP artifacts.

    Args:
        builder_id: URI identifying the build system (e.g. ``occp-ci/v1``).
        build_type: URI describing the build process type.
        min_level: Minimum SLSA Build level to enforce.
    """

    DEFAULT_BUILD_TYPE = "https://occp.ai/OCCPSkillBuild/v1"

    def __init__(
        self,
        builder_id: str,
        build_type: str = "",
        min_level: BuildLevel = BuildLevel.L2,
    ) -> None:
        if not builder_id:
            raise ProvenanceError("builder_id is required")
        self._builder_id = builder_id
        self._build_type = build_type or self.DEFAULT_BUILD_TYPE
        self._min_level = min_level

    @property
    def builder_id(self) -> str:
        return self._builder_id

    def generate(
        self,
        *,
        subject_name: str,
        subject_digest: dict[str, str],
        source_repo: str = "",
        source_commit: str = "",
        build_inputs: dict[str, Any] | None = None,
        dependencies: list[ResourceDescriptor] | None = None,
        invocation_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> SLSAStatement:
        """Create a signed SLSA provenance statement.

        Args:
            subject_name: Name of the artifact (e.g. skill ID).
            subject_digest: Digest map (``{"sha256": "..."}``).
            source_repo: Source repository URI.
            source_commit: Git commit SHA.
            build_inputs: External build parameters.
            dependencies: Resolved build dependencies.
            invocation_id: Unique build invocation identifier.
            metadata: Extra metadata to include in run details.

        Returns:
            SLSAStatement ready for signing and distribution.

        Raises:
            ProvenanceError: If required fields are missing.
        """
        if not subject_name:
            raise ProvenanceError("subject_name is required")
        if "sha256" not in subject_digest:
            raise ProvenanceError("subject_digest must contain 'sha256' key")

        now = datetime.now(timezone.utc).isoformat()

        # Build subject
        subject = ResourceDescriptor(
            name=subject_name,
            digest=subject_digest,
        )

        # External parameters
        ext_params: dict[str, Any] = dict(build_inputs or {})
        if source_repo:
            ext_params["source"] = {
                "uri": source_repo,
                "digest": {"sha1": source_commit} if source_commit else {},
            }

        # Resolved dependencies
        deps = list(dependencies or [])
        if source_repo and source_commit:
            deps.insert(
                0,
                ResourceDescriptor(
                    name="source",
                    uri=source_repo,
                    digest={"sha1": source_commit},
                ),
            )

        build_def = BuildDefinition(
            build_type=self._build_type,
            external_parameters=ext_params,
            resolved_dependencies=deps,
        )

        run = RunDetails(
            builder_id=self._builder_id,
            build_level=self._min_level,
            invocation_id=invocation_id,
            started_on=now,
            finished_on=now,
            metadata=metadata or {},
        )

        provenance = SLSAProvenance(
            build_definition=build_def,
            run_details=run,
        )

        stmt = SLSAStatement(
            subjects=[subject],
            predicate=provenance,
        )

        logger.info(
            "Generated SLSA provenance: subject=%s digest=%s builder=%s",
            subject_name,
            subject_digest.get("sha256", "")[:16],
            self._builder_id,
        )
        return stmt


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------


class ProvenanceValidator:
    """Validates SLSA provenance statements.

    Checks:
    1. Statement type and predicate type are correct.
    2. Subject has sha256 digest.
    3. Builder ID is present.
    4. Build level meets minimum.
    5. Source commit is present (for L2+).
    """

    def __init__(
        self,
        *,
        allowed_builders: list[str] | None = None,
        min_level: BuildLevel = BuildLevel.L2,
    ) -> None:
        self._allowed_builders = set(allowed_builders) if allowed_builders else None
        self._min_level = min_level

    def validate_statement(self, stmt: SLSAStatement) -> list[str]:
        """Validate a provenance statement. Returns list of violation strings (empty = valid)."""
        violations: list[str] = []

        # Type checks
        if stmt.statement_type != SLSA_STATEMENT_TYPE:
            violations.append(f"Invalid statement type: {stmt.statement_type}")
        if stmt.predicate_type != SLSA_PROVENANCE_PREDICATE_TYPE:
            violations.append(f"Invalid predicate type: {stmt.predicate_type}")

        # Subject checks
        if not stmt.subjects:
            violations.append("No subjects in statement")
        else:
            for subj in stmt.subjects:
                if "sha256" not in subj.digest:
                    violations.append(f"Subject '{subj.name}' missing sha256 digest")

        # Builder checks
        builder_id = stmt.predicate.run_details.builder_id
        if not builder_id:
            violations.append("No builder_id in run details")
        elif self._allowed_builders and builder_id not in self._allowed_builders:
            violations.append(f"Builder '{builder_id}' not in allowed list")

        # Build level check
        level = stmt.predicate.run_details.build_level
        if level.value < self._min_level.value:
            violations.append(
                f"Build level {level.name} below minimum {self._min_level.name}"
            )

        # Source commit (L2+ requires source traceability)
        if self._min_level.value >= BuildLevel.L2.value:
            ext = stmt.predicate.build_definition.external_parameters
            source = ext.get("source", {})
            source_digest = source.get("digest", {}) if isinstance(source, dict) else {}
            if not source_digest:
                deps = stmt.predicate.build_definition.resolved_dependencies
                has_source = any(d.name == "source" and d.digest for d in deps)
                if not has_source:
                    violations.append("L2+ requires source commit traceability")

        return violations

    def validate_dict(self, data: dict[str, Any]) -> list[str]:
        """Validate provenance from a raw dict (deserialized JSON).

        Lighter validation for JSON payloads without full deserialization.
        """
        violations: list[str] = []

        if data.get("_type") != SLSA_STATEMENT_TYPE:
            violations.append(f"Invalid _type: {data.get('_type')}")
        if data.get("predicateType") != SLSA_PROVENANCE_PREDICATE_TYPE:
            violations.append(f"Invalid predicateType: {data.get('predicateType')}")

        subjects = data.get("subject", [])
        if not subjects:
            violations.append("No subject entries")
        for subj in subjects:
            if "sha256" not in subj.get("digest", {}):
                violations.append(f"Subject '{subj.get('name')}' missing sha256")

        predicate = data.get("predicate", {})
        run_details = predicate.get("runDetails", {})
        builder = run_details.get("builder", {})
        builder_id = builder.get("id", "")
        if not builder_id:
            violations.append("Missing builder id")
        elif self._allowed_builders and builder_id not in self._allowed_builders:
            violations.append(f"Builder '{builder_id}' not allowed")

        return violations
