"""Artifact Signing — Ed25519-based signing and verification for OCCP artifacts.

REQ-CPC-02: All distributed artifacts signed. Signatures verified at install
time and runtime load. Uses Ed25519 (via ``cryptography`` library) for
deterministic, fast signing with small key sizes.

In production, this integrates with Sigstore/cosign for keyless signing
via OIDC identity. This module provides the local-key fallback and the
verification interface used by both modes.

Usage::

    kp = KeyPair.generate()
    signer = ArtifactSigner(kp.private_key)
    sig = signer.sign(b"artifact content")

    verifier = SignatureVerifier()
    verifier.add_trusted_key("builder-1", kp.public_key)
    result = verifier.verify(b"artifact content", sig, "builder-1")
    assert result.valid
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Try to import cryptography; fall back to HMAC-SHA256 stub if unavailable
# ---------------------------------------------------------------------------

_HAS_ED25519 = False
try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )
    from cryptography.exceptions import InvalidSignature

    _HAS_ED25519 = True
except ImportError:
    pass


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class SigningError(Exception):
    """Base error for signing operations."""


class VerificationError(SigningError):
    """Signature verification failed."""


# ---------------------------------------------------------------------------
# Key management
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class KeyPair:
    """Ed25519 key pair for artifact signing.

    Keys are stored as base64-encoded raw bytes.
    """

    private_key: str  # base64(raw 32 bytes)
    public_key: str  # base64(raw 32 bytes)
    key_id: str = ""

    @classmethod
    def generate(cls, key_id: str = "") -> KeyPair:
        """Generate a new Ed25519 key pair."""
        if _HAS_ED25519:
            sk = Ed25519PrivateKey.generate()
            pk = sk.public_key()
            priv_bytes = sk.private_bytes(
                serialization.Encoding.Raw,
                serialization.PrivateFormat.Raw,
                serialization.NoEncryption(),
            )
            pub_bytes = pk.public_bytes(
                serialization.Encoding.Raw,
                serialization.PublicFormat.Raw,
            )
            return cls(
                private_key=base64.b64encode(priv_bytes).decode(),
                public_key=base64.b64encode(pub_bytes).decode(),
                key_id=key_id or hashlib.sha256(pub_bytes).hexdigest()[:16],
            )
        # HMAC fallback — generate random 32-byte key
        secret = os.urandom(32)
        pub = hashlib.sha256(secret).digest()
        return cls(
            private_key=base64.b64encode(secret).decode(),
            public_key=base64.b64encode(pub).decode(),
            key_id=key_id or hashlib.sha256(pub).hexdigest()[:16],
        )


# ---------------------------------------------------------------------------
# Signature envelope
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SignatureEnvelope:
    """DSSE-style envelope wrapping an artifact signature."""

    payload_hash: str  # sha256 hex of the signed content
    signature: str  # base64(signature bytes)
    key_id: str  # identifies the signing key
    timestamp: float  # UNIX timestamp of signing
    algorithm: str = "ed25519"  # or "hmac-sha256" for fallback

    def to_dict(self) -> dict[str, Any]:
        return {
            "payloadHash": self.payload_hash,
            "signature": self.signature,
            "keyId": self.key_id,
            "timestamp": self.timestamp,
            "algorithm": self.algorithm,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SignatureEnvelope:
        return cls(
            payload_hash=data["payloadHash"],
            signature=data["signature"],
            key_id=data["keyId"],
            timestamp=data["timestamp"],
            algorithm=data.get("algorithm", "ed25519"),
        )

    @classmethod
    def from_json(cls, raw: str) -> SignatureEnvelope:
        return cls.from_dict(json.loads(raw))


# ---------------------------------------------------------------------------
# Signer
# ---------------------------------------------------------------------------


class ArtifactSigner:
    """Signs artifact content using Ed25519 (or HMAC-SHA256 fallback).

    Args:
        private_key_b64: Base64-encoded raw Ed25519 private key (32 bytes).
        key_id: Identifier for this signing key.
    """

    def __init__(self, private_key_b64: str, key_id: str = "") -> None:
        self._priv_b64 = private_key_b64
        self._key_id = key_id
        self._priv_bytes = base64.b64decode(private_key_b64)

        if _HAS_ED25519:
            self._sk = Ed25519PrivateKey.from_private_bytes(self._priv_bytes)
            pk = self._sk.public_key()
            pub_bytes = pk.public_bytes(
                serialization.Encoding.Raw,
                serialization.PublicFormat.Raw,
            )
            self._algorithm = "ed25519"
        else:
            self._sk = None
            pub_bytes = hashlib.sha256(self._priv_bytes).digest()
            self._algorithm = "hmac-sha256"

        if not key_id:
            self._key_id = hashlib.sha256(pub_bytes).hexdigest()[:16]

    @property
    def key_id(self) -> str:
        return self._key_id

    @property
    def algorithm(self) -> str:
        return self._algorithm

    def sign(self, content: bytes) -> SignatureEnvelope:
        """Sign raw content bytes. Returns a SignatureEnvelope."""
        payload_hash = hashlib.sha256(content).hexdigest()

        if _HAS_ED25519 and self._sk is not None:
            sig_bytes = self._sk.sign(content)
        else:
            # HMAC-SHA256 fallback
            import hmac

            sig_bytes = hmac.new(
                self._priv_bytes, content, hashlib.sha256
            ).digest()

        return SignatureEnvelope(
            payload_hash=payload_hash,
            signature=base64.b64encode(sig_bytes).decode(),
            key_id=self._key_id,
            timestamp=time.time(),
            algorithm=self._algorithm,
        )

    def sign_json(self, data: dict[str, Any]) -> SignatureEnvelope:
        """Sign a JSON-serializable dict (canonical form)."""
        canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
        return self.sign(canonical.encode("utf-8"))


# ---------------------------------------------------------------------------
# Verifier
# ---------------------------------------------------------------------------


@dataclass
class VerificationResult:
    """Result of signature verification."""

    valid: bool
    key_id: str = ""
    reason: str = ""
    payload_hash: str = ""
    algorithm: str = ""
    warnings: list[str] = field(default_factory=list)


class SignatureVerifier:
    """Verifies artifact signatures against trusted public keys.

    Fail-closed: missing key or invalid signature → reject.
    """

    def __init__(self) -> None:
        self._trusted_keys: dict[str, str] = {}  # key_id → base64(public_key)
        self._max_age_seconds: float = 86400 * 365  # 1 year default

    def add_trusted_key(self, key_id: str, public_key_b64: str) -> None:
        """Register a trusted public key."""
        self._trusted_keys[key_id] = public_key_b64
        logger.info("Added trusted key: key_id=%s", key_id)

    def remove_trusted_key(self, key_id: str) -> bool:
        """Remove a trusted key. Returns True if it existed."""
        return self._trusted_keys.pop(key_id, None) is not None

    @property
    def trusted_key_ids(self) -> list[str]:
        return list(self._trusted_keys.keys())

    def set_max_age(self, seconds: float) -> None:
        """Set maximum signature age. Signatures older than this are rejected."""
        self._max_age_seconds = seconds

    def verify(
        self,
        content: bytes,
        envelope: SignatureEnvelope,
        expected_key_id: str = "",
    ) -> VerificationResult:
        """Verify a signature envelope against content.

        Args:
            content: The original signed content bytes.
            envelope: The signature envelope to verify.
            expected_key_id: If set, envelope.key_id must match.

        Returns:
            VerificationResult indicating whether the signature is valid.
        """
        warnings: list[str] = []

        # Key ID match
        key_id = envelope.key_id
        if expected_key_id and key_id != expected_key_id:
            return VerificationResult(
                valid=False,
                key_id=key_id,
                reason=f"Key ID mismatch: expected={expected_key_id}, got={key_id}",
                algorithm=envelope.algorithm,
            )

        # Payload hash check
        actual_hash = hashlib.sha256(content).hexdigest()
        if actual_hash != envelope.payload_hash:
            return VerificationResult(
                valid=False,
                key_id=key_id,
                reason="Payload hash mismatch — content tampered",
                payload_hash=actual_hash,
                algorithm=envelope.algorithm,
            )

        # Signature age check
        age = time.time() - envelope.timestamp
        if age > self._max_age_seconds:
            return VerificationResult(
                valid=False,
                key_id=key_id,
                reason=f"Signature expired: age={age:.0f}s > max={self._max_age_seconds:.0f}s",
                payload_hash=actual_hash,
                algorithm=envelope.algorithm,
            )
        if age < 0:
            warnings.append("Signature timestamp is in the future")

        # Lookup trusted key
        pub_b64 = self._trusted_keys.get(key_id)
        if pub_b64 is None:
            return VerificationResult(
                valid=False,
                key_id=key_id,
                reason=f"No trusted key found for key_id={key_id}",
                payload_hash=actual_hash,
                algorithm=envelope.algorithm,
            )

        # Cryptographic verification
        sig_bytes = base64.b64decode(envelope.signature)
        pub_bytes = base64.b64decode(pub_b64)

        if envelope.algorithm == "ed25519" and _HAS_ED25519:
            try:
                pk = Ed25519PublicKey.from_public_bytes(pub_bytes)
                pk.verify(sig_bytes, content)
            except (InvalidSignature, Exception) as exc:
                return VerificationResult(
                    valid=False,
                    key_id=key_id,
                    reason=f"Ed25519 signature invalid: {exc}",
                    payload_hash=actual_hash,
                    algorithm=envelope.algorithm,
                )
        elif envelope.algorithm == "hmac-sha256":
            import hmac

            expected_sig = hmac.new(
                pub_bytes, content, hashlib.sha256
            ).digest()
            if not hmac.compare_digest(sig_bytes, expected_sig):
                return VerificationResult(
                    valid=False,
                    key_id=key_id,
                    reason="HMAC signature mismatch",
                    payload_hash=actual_hash,
                    algorithm=envelope.algorithm,
                )
        else:
            return VerificationResult(
                valid=False,
                key_id=key_id,
                reason=f"Unsupported algorithm: {envelope.algorithm}",
                payload_hash=actual_hash,
                algorithm=envelope.algorithm,
            )

        logger.info(
            "Signature verified: key_id=%s hash=%s",
            key_id,
            actual_hash[:16],
        )
        return VerificationResult(
            valid=True,
            key_id=key_id,
            payload_hash=actual_hash,
            algorithm=envelope.algorithm,
            warnings=warnings,
        )

    def verify_json(
        self,
        data: dict[str, Any],
        envelope: SignatureEnvelope,
        expected_key_id: str = "",
    ) -> VerificationResult:
        """Verify a JSON dict against its signature."""
        canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
        return self.verify(canonical.encode("utf-8"), envelope, expected_key_id)
