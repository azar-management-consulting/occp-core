"""AES-256-GCM envelope encryption for LLM API tokens.

Implements a two-layer key hierarchy:
- Master key (OCCP_ENCRYPTION_KEY) — derives per-token DEKs
- Data Encryption Key (DEK) — unique per stored secret, rotatable

All secrets are stored as: nonce (12B) || ciphertext || tag (16B)
Base64-encoded for DB storage.

Usage::

    enc = TokenEncryptor(master_key="base64-encoded-32-byte-key")
    encrypted = enc.encrypt("sk-ant-api03-...")
    decrypted = enc.decrypt(encrypted)
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
import secrets
from typing import NamedTuple

logger = logging.getLogger(__name__)

# AES-256-GCM constants
_KEY_LENGTH = 32  # 256 bits
_NONCE_LENGTH = 12  # 96 bits (GCM standard)
_TAG_LENGTH = 16  # 128 bits

# Version prefix for future algorithm migration
_V1_PREFIX = b"\x01"


class EncryptedBlob(NamedTuple):
    """Structured representation of an encrypted value."""

    version: int
    nonce: bytes
    ciphertext: bytes
    tag: bytes


class TokenEncryptor:
    """AES-256-GCM envelope encryption for API tokens.

    The master key is used to derive per-encryption DEKs via
    HKDF-SHA256(master_key, salt=random_salt, info=b"occp-token-dek").
    """

    def __init__(self, master_key: str) -> None:
        """Initialize with a base64-encoded 32-byte master key.

        If *master_key* is empty, generates an ephemeral key (dev mode).
        """
        if not master_key:
            self._master = secrets.token_bytes(_KEY_LENGTH)
            logger.warning(
                "No OCCP_ENCRYPTION_KEY set — using ephemeral key. "
                "Tokens will NOT survive restart."
            )
        else:
            try:
                self._master = base64.b64decode(master_key)
            except Exception:
                # Treat as passphrase — derive key via SHA-256
                self._master = hashlib.sha256(master_key.encode()).digest()

            if len(self._master) != _KEY_LENGTH:
                self._master = hashlib.sha256(self._master).digest()

    @staticmethod
    def generate_master_key() -> str:
        """Generate a cryptographically secure master key (base64)."""
        return base64.b64encode(secrets.token_bytes(_KEY_LENGTH)).decode()

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a plaintext token → base64-encoded envelope.

        Format: version(1B) || nonce(12B) || ciphertext(N) || tag(16B)
        """
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        # Derive a unique DEK per encryption via HKDF
        salt = os.urandom(16)
        dek = self._derive_dek(salt)

        nonce = os.urandom(_NONCE_LENGTH)
        aesgcm = AESGCM(dek)

        # AAD = version + salt for binding
        aad = _V1_PREFIX + salt
        ct_and_tag = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), aad)

        # Pack: version(1) + salt(16) + nonce(12) + ciphertext_with_tag
        envelope = _V1_PREFIX + salt + nonce + ct_and_tag
        return base64.b64encode(envelope).decode("ascii")

    def decrypt(self, encrypted_b64: str) -> str:
        """Decrypt a base64-encoded envelope → plaintext token."""
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        raw = base64.b64decode(encrypted_b64)

        # Parse envelope
        if len(raw) < 1 + 16 + _NONCE_LENGTH + _TAG_LENGTH:
            raise ValueError("Invalid encrypted blob: too short")

        version = raw[0]
        if version != 1:
            raise ValueError(f"Unsupported encryption version: {version}")

        salt = raw[1:17]
        nonce = raw[17 : 17 + _NONCE_LENGTH]
        ct_and_tag = raw[17 + _NONCE_LENGTH :]

        dek = self._derive_dek(salt)
        aad = _V1_PREFIX + salt

        aesgcm = AESGCM(dek)
        plaintext = aesgcm.decrypt(nonce, ct_and_tag, aad)
        return plaintext.decode("utf-8")

    def _derive_dek(self, salt: bytes) -> bytes:
        """Derive a per-encryption DEK from master key + salt via HKDF."""
        from cryptography.hazmat.primitives.kdf.hkdf import HKDF
        from cryptography.hazmat.primitives import hashes

        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=_KEY_LENGTH,
            salt=salt,
            info=b"occp-token-dek-v1",
        )
        return hkdf.derive(self._master)

    def rotate_master_key(
        self, encrypted_values: list[str], new_master_key: str
    ) -> list[str]:
        """Re-encrypt all values under a new master key.

        Returns list of new encrypted blobs in the same order.
        """
        new_encryptor = TokenEncryptor(new_master_key)
        result = []
        for enc in encrypted_values:
            plaintext = self.decrypt(enc)
            result.append(new_encryptor.encrypt(plaintext))
        return result


def mask_token(token: str) -> str:
    """Return a safely masked version for display/logging.

    Shows first 6 and last 4 characters: ``sk-ant-***...***3abc``
    """
    if len(token) <= 12:
        return "***"
    return f"{token[:6]}***{token[-4:]}"
