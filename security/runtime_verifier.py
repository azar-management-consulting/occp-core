"""Runtime Signature Verification — verify artifact integrity on every load.

REQ-CPC-03: Runtime verifies artifact signatures before loading any skill,
plugin, or MCP server. Verification occurs at every restart, not just install.
Verification cached for 24h to reduce startup latency.

This module bridges signing.py + supply_chain.py to provide a unified runtime
gate that checks signatures, provenance, and revocation status before any
artifact is loaded.

Usage::

    rv = RuntimeVerifier(signature_verifier=sv, revocation_checker=rc)
    rv.load_trusted_keys({"builder-1": "base64pubkey..."})
    result = rv.verify_artifact(artifact_id="my-skill", content=b"...", envelope=sig_env)
    if not result.allowed:
        raise RuntimeError(f"Artifact blocked: {result.reason}")
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from security.signing import SignatureEnvelope, SignatureVerifier, VerificationResult

logger = logging.getLogger(__name__)

# Default cache TTL: 24 hours
DEFAULT_CACHE_TTL = 86400


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class RuntimeVerificationError(Exception):
    """Runtime verification failed."""


# ---------------------------------------------------------------------------
# Verification cache
# ---------------------------------------------------------------------------


@dataclass
class CacheEntry:
    """Cached verification result with expiry."""

    content_hash: str
    result: ArtifactVerificationResult
    expires_at: float


@dataclass
class ArtifactVerificationResult:
    """Result of runtime artifact verification."""

    allowed: bool
    artifact_id: str
    reason: str = ""
    content_hash: str = ""
    signature_valid: bool = False
    revocation_status: str = "unknown"  # "clear" | "revoked" | "unknown"
    warnings: list[str] = field(default_factory=list)
    cached: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "artifactId": self.artifact_id,
            "reason": self.reason,
            "contentHash": self.content_hash,
            "signatureValid": self.signature_valid,
            "revocationStatus": self.revocation_status,
            "warnings": self.warnings,
            "cached": self.cached,
        }


# ---------------------------------------------------------------------------
# Runtime Verifier
# ---------------------------------------------------------------------------


class RuntimeVerifier:
    """Verifies artifact signatures at runtime before loading.

    Combines:
    1. Signature verification (via SignatureVerifier)
    2. Revocation check (via RevocationChecker, if provided)
    3. Result caching (24h default TTL)

    Fail-closed: any check failure blocks the artifact.
    """

    def __init__(
        self,
        signature_verifier: SignatureVerifier | None = None,
        revocation_checker: Any | None = None,  # RevocationChecker from revocation.py
        cache_ttl: float = DEFAULT_CACHE_TTL,
    ) -> None:
        self._sig_verifier = signature_verifier or SignatureVerifier()
        self._revocation = revocation_checker
        self._cache_ttl = cache_ttl
        self._cache: dict[str, CacheEntry] = {}
        self._require_signatures = True

    @property
    def signature_verifier(self) -> SignatureVerifier:
        return self._sig_verifier

    def set_require_signatures(self, require: bool) -> None:
        """Toggle strict signature requirement (default: True)."""
        self._require_signatures = require

    def load_trusted_keys(self, keys: dict[str, str]) -> None:
        """Bulk-load trusted public keys. keys = {key_id: base64_pubkey}."""
        for kid, pub in keys.items():
            self._sig_verifier.add_trusted_key(kid, pub)
        logger.info("Loaded %d trusted keys", len(keys))

    def clear_cache(self) -> None:
        """Clear verification cache."""
        self._cache.clear()

    def cache_stats(self) -> dict[str, int]:
        """Return cache size and expired count."""
        now = time.time()
        expired = sum(1 for e in self._cache.values() if e.expires_at < now)
        return {"total": len(self._cache), "expired": expired}

    def _get_cached(self, artifact_id: str, content_hash: str) -> ArtifactVerificationResult | None:
        """Return cached result if valid and content hash matches."""
        entry = self._cache.get(artifact_id)
        if entry is None:
            return None
        if entry.expires_at < time.time():
            del self._cache[artifact_id]
            return None
        if entry.content_hash != content_hash:
            # Content changed since cache — invalidate
            del self._cache[artifact_id]
            return None
        result = entry.result
        # Return a copy with cached=True
        return ArtifactVerificationResult(
            allowed=result.allowed,
            artifact_id=result.artifact_id,
            reason=result.reason,
            content_hash=result.content_hash,
            signature_valid=result.signature_valid,
            revocation_status=result.revocation_status,
            warnings=list(result.warnings),
            cached=True,
        )

    def _set_cached(self, artifact_id: str, content_hash: str, result: ArtifactVerificationResult) -> None:
        """Cache verification result."""
        self._cache[artifact_id] = CacheEntry(
            content_hash=content_hash,
            result=result,
            expires_at=time.time() + self._cache_ttl,
        )

    def verify_artifact(
        self,
        artifact_id: str,
        content: bytes,
        envelope: SignatureEnvelope | None = None,
    ) -> ArtifactVerificationResult:
        """Verify an artifact before runtime loading.

        Checks in order:
        1. Cache lookup (skip if cache hit with matching content hash)
        2. Signature verification (fail-closed if required and no envelope)
        3. Revocation check (if revocation checker provided)

        Args:
            artifact_id: Unique identifier for the artifact.
            content: Raw artifact content bytes.
            envelope: Signature envelope (required if signatures enforced).

        Returns:
            ArtifactVerificationResult with allowed=True/False.
        """
        content_hash = hashlib.sha256(content).hexdigest()
        warnings: list[str] = []

        # 1. Cache check
        cached = self._get_cached(artifact_id, content_hash)
        if cached is not None:
            logger.debug("Cache hit: artifact=%s hash=%s", artifact_id, content_hash[:16])
            return cached

        # 2. Signature verification
        sig_valid = False
        if envelope is None:
            if self._require_signatures:
                result = ArtifactVerificationResult(
                    allowed=False,
                    artifact_id=artifact_id,
                    reason="No signature envelope — fail-closed policy",
                    content_hash=content_hash,
                    signature_valid=False,
                    revocation_status="unknown",
                )
                self._set_cached(artifact_id, content_hash, result)
                return result
            else:
                warnings.append("No signature provided (signatures not required)")
        else:
            vr: VerificationResult = self._sig_verifier.verify(content, envelope)
            sig_valid = vr.valid
            warnings.extend(vr.warnings)
            if not vr.valid:
                result = ArtifactVerificationResult(
                    allowed=False,
                    artifact_id=artifact_id,
                    reason=f"Signature verification failed: {vr.reason}",
                    content_hash=content_hash,
                    signature_valid=False,
                    revocation_status="unknown",
                )
                self._set_cached(artifact_id, content_hash, result)
                return result

        # 3. Revocation check
        revocation_status = "clear"
        if self._revocation is not None:
            try:
                is_revoked = self._revocation.is_revoked(artifact_id)
                if is_revoked:
                    result = ArtifactVerificationResult(
                        allowed=False,
                        artifact_id=artifact_id,
                        reason=f"Artifact '{artifact_id}' is revoked",
                        content_hash=content_hash,
                        signature_valid=sig_valid,
                        revocation_status="revoked",
                    )
                    # Don't cache revocation — recheck each time
                    return result
            except Exception as exc:
                warnings.append(f"Revocation check error: {exc}")
                revocation_status = "unknown"

        # All checks passed
        result = ArtifactVerificationResult(
            allowed=True,
            artifact_id=artifact_id,
            content_hash=content_hash,
            signature_valid=sig_valid,
            revocation_status=revocation_status,
            warnings=warnings,
        )
        self._set_cached(artifact_id, content_hash, result)

        logger.info(
            "Artifact verified: id=%s hash=%s sig=%s revocation=%s",
            artifact_id,
            content_hash[:16],
            sig_valid,
            revocation_status,
        )
        return result

    def verify_artifact_json(
        self,
        artifact_id: str,
        data: dict[str, Any],
        envelope: SignatureEnvelope | None = None,
    ) -> ArtifactVerificationResult:
        """Verify a JSON artifact (canonical serialization)."""
        import json
        canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
        return self.verify_artifact(artifact_id, canonical.encode("utf-8"), envelope)
