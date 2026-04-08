"""Tests for security.signing — Ed25519 artifact signing (REQ-CPC-02).

Covers:
- KeyPair: generation, base64 encoding
- ArtifactSigner: sign bytes, sign JSON, algorithm detection
- SignatureVerifier: verify valid, reject tampered, reject expired, reject unknown key
- SignatureEnvelope: serialization round-trip
- HMAC-SHA256 fallback path
"""

from __future__ import annotations

import base64
import hashlib
import json
import time
import pytest

from security.signing import (
    ArtifactSigner,
    KeyPair,
    SignatureEnvelope,
    SignatureVerifier,
    SigningError,
    VerificationError,
    VerificationResult,
    _HAS_ED25519,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def keypair() -> KeyPair:
    return KeyPair.generate(key_id="test-key-1")


@pytest.fixture
def signer(keypair: KeyPair) -> ArtifactSigner:
    return ArtifactSigner(keypair.private_key, key_id=keypair.key_id)


@pytest.fixture
def verifier(keypair: KeyPair) -> SignatureVerifier:
    v = SignatureVerifier()
    v.add_trusted_key(keypair.key_id, keypair.public_key)
    return v


# ---------------------------------------------------------------------------
# KeyPair
# ---------------------------------------------------------------------------

class TestKeyPair:
    def test_generate(self) -> None:
        kp = KeyPair.generate()
        assert kp.private_key
        assert kp.public_key
        assert kp.key_id
        # Base64 decodable
        priv = base64.b64decode(kp.private_key)
        pub = base64.b64decode(kp.public_key)
        assert len(priv) == 32
        assert len(pub) == 32

    def test_generate_custom_key_id(self) -> None:
        kp = KeyPair.generate(key_id="custom-id")
        assert kp.key_id == "custom-id"

    def test_generate_auto_key_id(self) -> None:
        kp = KeyPair.generate()
        assert len(kp.key_id) == 16  # sha256[:16]

    def test_unique_keys(self) -> None:
        kp1 = KeyPair.generate()
        kp2 = KeyPair.generate()
        assert kp1.private_key != kp2.private_key
        assert kp1.public_key != kp2.public_key

    def test_frozen(self) -> None:
        kp = KeyPair.generate()
        with pytest.raises(AttributeError):
            kp.private_key = "x"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ArtifactSigner
# ---------------------------------------------------------------------------

class TestArtifactSigner:
    def test_sign_bytes(self, signer: ArtifactSigner) -> None:
        content = b"hello world"
        env = signer.sign(content)
        assert env.payload_hash == hashlib.sha256(content).hexdigest()
        assert env.key_id == signer.key_id
        assert env.signature  # non-empty
        assert env.timestamp > 0
        assert env.algorithm in ("ed25519", "hmac-sha256")

    def test_sign_json(self, signer: ArtifactSigner) -> None:
        data = {"action": "deploy", "version": "1.0"}
        env = signer.sign_json(data)
        canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
        expected_hash = hashlib.sha256(canonical.encode()).hexdigest()
        assert env.payload_hash == expected_hash

    def test_key_id_property(self, keypair: KeyPair) -> None:
        s = ArtifactSigner(keypair.private_key, key_id="my-id")
        assert s.key_id == "my-id"

    def test_auto_key_id(self, keypair: KeyPair) -> None:
        s = ArtifactSigner(keypair.private_key)
        assert len(s.key_id) == 16

    def test_algorithm_property(self, signer: ArtifactSigner) -> None:
        assert signer.algorithm in ("ed25519", "hmac-sha256")

    def test_different_content_different_signature(self, signer: ArtifactSigner) -> None:
        e1 = signer.sign(b"content-a")
        e2 = signer.sign(b"content-b")
        assert e1.signature != e2.signature
        assert e1.payload_hash != e2.payload_hash


# ---------------------------------------------------------------------------
# SignatureEnvelope
# ---------------------------------------------------------------------------

class TestSignatureEnvelope:
    def test_to_dict(self, signer: ArtifactSigner) -> None:
        env = signer.sign(b"data")
        d = env.to_dict()
        assert "payloadHash" in d
        assert "signature" in d
        assert "keyId" in d
        assert "timestamp" in d
        assert "algorithm" in d

    def test_to_json(self, signer: ArtifactSigner) -> None:
        env = signer.sign(b"data")
        j = env.to_json()
        parsed = json.loads(j)
        assert parsed["keyId"] == signer.key_id

    def test_from_dict_roundtrip(self, signer: ArtifactSigner) -> None:
        env = signer.sign(b"data")
        d = env.to_dict()
        restored = SignatureEnvelope.from_dict(d)
        assert restored.payload_hash == env.payload_hash
        assert restored.signature == env.signature
        assert restored.key_id == env.key_id
        assert restored.timestamp == env.timestamp
        assert restored.algorithm == env.algorithm

    def test_from_json_roundtrip(self, signer: ArtifactSigner) -> None:
        env = signer.sign(b"test")
        j = env.to_json()
        restored = SignatureEnvelope.from_json(j)
        assert restored.payload_hash == env.payload_hash
        assert restored.signature == env.signature

    def test_frozen(self, signer: ArtifactSigner) -> None:
        env = signer.sign(b"data")
        with pytest.raises(AttributeError):
            env.signature = "x"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# SignatureVerifier — valid signatures
# ---------------------------------------------------------------------------

class TestSignatureVerifierValid:
    def test_verify_valid(self, signer: ArtifactSigner, verifier: SignatureVerifier) -> None:
        content = b"artifact content"
        env = signer.sign(content)
        result = verifier.verify(content, env)
        assert result.valid is True
        assert result.key_id == signer.key_id
        assert result.payload_hash == hashlib.sha256(content).hexdigest()

    def test_verify_with_expected_key_id(
        self, signer: ArtifactSigner, verifier: SignatureVerifier
    ) -> None:
        content = b"data"
        env = signer.sign(content)
        result = verifier.verify(content, env, expected_key_id=signer.key_id)
        assert result.valid is True

    def test_verify_json(self, signer: ArtifactSigner, verifier: SignatureVerifier) -> None:
        data = {"key": "value", "num": 42}
        env = signer.sign_json(data)
        result = verifier.verify_json(data, env)
        assert result.valid is True

    def test_verify_empty_content(self, signer: ArtifactSigner, verifier: SignatureVerifier) -> None:
        content = b""
        env = signer.sign(content)
        result = verifier.verify(content, env)
        assert result.valid is True

    def test_verify_large_content(self, signer: ArtifactSigner, verifier: SignatureVerifier) -> None:
        content = b"x" * 1_000_000  # 1MB
        env = signer.sign(content)
        result = verifier.verify(content, env)
        assert result.valid is True


# ---------------------------------------------------------------------------
# SignatureVerifier — rejection cases
# ---------------------------------------------------------------------------

class TestSignatureVerifierReject:
    def test_reject_tampered_content(
        self, signer: ArtifactSigner, verifier: SignatureVerifier
    ) -> None:
        env = signer.sign(b"original")
        result = verifier.verify(b"tampered", env)
        assert result.valid is False
        assert "hash mismatch" in result.reason.lower() or "tampered" in result.reason.lower()

    def test_reject_wrong_key_id(
        self, signer: ArtifactSigner, verifier: SignatureVerifier
    ) -> None:
        env = signer.sign(b"data")
        result = verifier.verify(b"data", env, expected_key_id="wrong-key")
        assert result.valid is False
        assert "mismatch" in result.reason.lower()

    def test_reject_unknown_key(self, signer: ArtifactSigner) -> None:
        v = SignatureVerifier()  # no trusted keys
        env = signer.sign(b"data")
        result = v.verify(b"data", env)
        assert result.valid is False
        assert "No trusted key" in result.reason

    def test_reject_expired_signature(
        self, signer: ArtifactSigner, verifier: SignatureVerifier
    ) -> None:
        verifier.set_max_age(1)  # 1 second
        env = signer.sign(b"data")
        # Forge an old timestamp
        old_env = SignatureEnvelope(
            payload_hash=env.payload_hash,
            signature=env.signature,
            key_id=env.key_id,
            timestamp=time.time() - 100,  # 100 seconds ago
            algorithm=env.algorithm,
        )
        result = verifier.verify(b"data", old_env)
        assert result.valid is False
        assert "expired" in result.reason.lower()

    def test_reject_unsupported_algorithm(
        self, signer: ArtifactSigner, verifier: SignatureVerifier
    ) -> None:
        env = signer.sign(b"data")
        bad_env = SignatureEnvelope(
            payload_hash=env.payload_hash,
            signature=env.signature,
            key_id=env.key_id,
            timestamp=env.timestamp,
            algorithm="rsa-sha512",
        )
        result = verifier.verify(b"data", bad_env)
        assert result.valid is False
        assert "Unsupported" in result.reason

    def test_reject_tampered_signature(
        self, signer: ArtifactSigner, verifier: SignatureVerifier
    ) -> None:
        content = b"data"
        env = signer.sign(content)
        # Corrupt signature bytes
        sig_bytes = base64.b64decode(env.signature)
        corrupted = bytes([b ^ 0xFF for b in sig_bytes])
        bad_env = SignatureEnvelope(
            payload_hash=env.payload_hash,
            signature=base64.b64encode(corrupted).decode(),
            key_id=env.key_id,
            timestamp=env.timestamp,
            algorithm=env.algorithm,
        )
        result = verifier.verify(content, bad_env)
        assert result.valid is False

    def test_future_timestamp_warning(
        self, signer: ArtifactSigner, verifier: SignatureVerifier
    ) -> None:
        content = b"data"
        env = signer.sign(content)
        future_env = SignatureEnvelope(
            payload_hash=env.payload_hash,
            signature=env.signature,
            key_id=env.key_id,
            timestamp=time.time() + 3600,  # 1 hour in future
            algorithm=env.algorithm,
        )
        result = verifier.verify(content, future_env)
        # Should still be valid (just a warning)
        assert result.valid is True
        assert any("future" in w.lower() for w in result.warnings)


# ---------------------------------------------------------------------------
# Key management
# ---------------------------------------------------------------------------

class TestKeyManagement:
    def test_add_and_list_keys(self) -> None:
        v = SignatureVerifier()
        v.add_trusted_key("k1", "pubkey1")
        v.add_trusted_key("k2", "pubkey2")
        assert set(v.trusted_key_ids) == {"k1", "k2"}

    def test_remove_key(self) -> None:
        v = SignatureVerifier()
        v.add_trusted_key("k1", "pubkey1")
        assert v.remove_trusted_key("k1") is True
        assert "k1" not in v.trusted_key_ids

    def test_remove_nonexistent_key(self) -> None:
        v = SignatureVerifier()
        assert v.remove_trusted_key("nope") is False

    def test_set_max_age(self) -> None:
        v = SignatureVerifier()
        v.set_max_age(3600)
        # No direct getter, but we verify it works through rejection
        # (tested in reject_expired above)


# ---------------------------------------------------------------------------
# Cross-key isolation
# ---------------------------------------------------------------------------

class TestCrossKeyIsolation:
    def test_different_key_cannot_verify(self) -> None:
        kp1 = KeyPair.generate(key_id="k1")
        kp2 = KeyPair.generate(key_id="k2")
        signer1 = ArtifactSigner(kp1.private_key, key_id="k1")
        v = SignatureVerifier()
        v.add_trusted_key("k1", kp2.public_key)  # wrong public key for k1
        content = b"data"
        env = signer1.sign(content)
        result = v.verify(content, env)
        assert result.valid is False

    def test_multi_key_verifier(self) -> None:
        kp1 = KeyPair.generate(key_id="k1")
        kp2 = KeyPair.generate(key_id="k2")
        s1 = ArtifactSigner(kp1.private_key, key_id="k1")
        s2 = ArtifactSigner(kp2.private_key, key_id="k2")
        v = SignatureVerifier()
        v.add_trusted_key("k1", kp1.public_key)
        v.add_trusted_key("k2", kp2.public_key)
        content = b"shared data"
        r1 = v.verify(content, s1.sign(content))
        r2 = v.verify(content, s2.sign(content))
        assert r1.valid is True
        assert r2.valid is True
