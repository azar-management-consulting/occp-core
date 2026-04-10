"""Credential Vault — REQ-SEC-03.

Per-organization encryption key isolation for managing secrets (API keys,
tokens, connection strings).  Extends the existing TokenEncryptor with
a full CRUD lifecycle and org-level key derivation.

Architecture:
- Master key → HKDF-SHA256(org_id) → Org DEK
- Each secret encrypted with Org DEK via AES-256-GCM envelope
- CRUD: store, retrieve, rotate, revoke
- Audit integration via callback hook

Usage::

    vault = CredentialVault(master_key="base64-key")
    vault.store("org-1", "openai-key", "sk-abc123...", labels={"provider": "openai"})
    secret = vault.retrieve("org-1", "openai-key")
    vault.rotate("org-1", "openai-key", "sk-new456...")
    vault.revoke("org-1", "openai-key")
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)

_KEY_LENGTH = 32  # AES-256
_NONCE_LENGTH = 12  # GCM standard
_SALT_LENGTH = 16
_V1_PREFIX = b"\x02"  # Version 2 — vault envelope (distinct from encryption.py v1)


class SecretStatus(str, Enum):
    """Lifecycle status of a vault secret."""

    ACTIVE = "active"
    ROTATED = "rotated"  # Previous version still decryptable
    REVOKED = "revoked"  # Permanently invalidated


@dataclass
class VaultEntry:
    """A single secret stored in the vault."""

    org_id: str
    key_name: str
    encrypted_value: str  # base64-encoded AES-256-GCM envelope
    masked_value: str  # For display: "sk-ab***3abc"
    status: SecretStatus = SecretStatus.ACTIVE
    labels: dict[str, str] = field(default_factory=dict)
    version: int = 1
    created_at: str = ""
    updated_at: str = ""
    rotated_from: str = ""  # Previous encrypted value (for rollback)

    def __post_init__(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now

    def to_dict(self) -> dict[str, Any]:
        """Serialize for API response (never includes encrypted_value)."""
        return {
            "org_id": self.org_id,
            "key_name": self.key_name,
            "masked_value": self.masked_value,
            "status": self.status.value,
            "labels": self.labels,
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class VaultAuditEvent:
    """Structured audit event emitted by vault operations."""

    action: str  # store, retrieve, rotate, revoke, list
    org_id: str
    key_name: str = ""
    detail: dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


# Type for audit callback
AuditCallback = Callable[[VaultAuditEvent], None]


class CredentialVault:
    """Org-isolated credential vault with AES-256-GCM encryption.

    Each organization gets a unique DEK derived from the master key via
    HKDF-SHA256(master_key, salt=org_id, info="occp-vault-org-dek-v1").

    All mutations emit VaultAuditEvent via the registered callback.
    """

    def __init__(
        self,
        master_key: str,
        *,
        audit_callback: AuditCallback | None = None,
    ) -> None:
        if not master_key:
            self._master = secrets.token_bytes(_KEY_LENGTH)
            logger.warning("No vault master key — using ephemeral key.")
        else:
            try:
                self._master = base64.b64decode(master_key)
            except Exception:
                self._master = hashlib.sha256(master_key.encode()).digest()
            if len(self._master) != _KEY_LENGTH:
                self._master = hashlib.sha256(self._master).digest()

        self._store: dict[str, dict[str, VaultEntry]] = {}  # org_id → {key_name → entry}
        self._audit_cb = audit_callback

    # -- CRUD API -----------------------------------------------------------

    def store(
        self,
        org_id: str,
        key_name: str,
        plaintext: str,
        *,
        labels: dict[str, str] | None = None,
    ) -> VaultEntry:
        """Store a new secret or overwrite an existing one.

        Returns the VaultEntry (encrypted_value is populated but should
        not be exposed via API).
        """
        if not org_id or not key_name:
            raise ValueError("org_id and key_name are required")
        if not plaintext:
            raise ValueError("plaintext secret cannot be empty")

        encrypted = self._encrypt(org_id, plaintext)
        masked = _mask_secret(plaintext)

        entry = VaultEntry(
            org_id=org_id,
            key_name=key_name,
            encrypted_value=encrypted,
            masked_value=masked,
            labels=labels or {},
        )

        if org_id not in self._store:
            self._store[org_id] = {}
        self._store[org_id][key_name] = entry

        self._emit_audit("store", org_id, key_name, {"masked": masked})
        logger.info("Vault: stored secret %s/%s", org_id, key_name)
        return entry

    def retrieve(self, org_id: str, key_name: str) -> str:
        """Retrieve and decrypt a secret by org + key name.

        Returns the plaintext value.  Raises KeyError if not found
        or ValueError if secret is revoked.
        """
        entry = self._get_entry(org_id, key_name)

        if entry.status == SecretStatus.REVOKED:
            self._emit_audit("retrieve_denied", org_id, key_name, {"reason": "revoked"})
            raise ValueError(f"Secret {org_id}/{key_name} has been revoked")

        plaintext = self._decrypt(org_id, entry.encrypted_value)
        self._emit_audit("retrieve", org_id, key_name)
        return plaintext

    def rotate(
        self,
        org_id: str,
        key_name: str,
        new_plaintext: str,
    ) -> VaultEntry:
        """Rotate a secret — replaces value, increments version.

        The previous encrypted value is kept in ``rotated_from`` for
        audit/rollback capability.
        """
        if not new_plaintext:
            raise ValueError("New secret value cannot be empty")

        entry = self._get_entry(org_id, key_name)

        if entry.status == SecretStatus.REVOKED:
            raise ValueError(f"Cannot rotate revoked secret {org_id}/{key_name}")

        old_encrypted = entry.encrypted_value
        new_encrypted = self._encrypt(org_id, new_plaintext)
        new_masked = _mask_secret(new_plaintext)

        entry.rotated_from = old_encrypted
        entry.encrypted_value = new_encrypted
        entry.masked_value = new_masked
        entry.version += 1
        entry.status = SecretStatus.ACTIVE
        entry.updated_at = datetime.now(timezone.utc).isoformat()

        self._emit_audit("rotate", org_id, key_name, {
            "new_version": entry.version,
            "masked": new_masked,
        })
        logger.info("Vault: rotated secret %s/%s to v%d", org_id, key_name, entry.version)
        return entry

    def revoke(self, org_id: str, key_name: str) -> VaultEntry:
        """Revoke a secret — marks it as permanently invalidated.

        The encrypted value is zeroed out.  This is irreversible.
        """
        entry = self._get_entry(org_id, key_name)
        entry.status = SecretStatus.REVOKED
        entry.encrypted_value = ""
        entry.rotated_from = ""
        entry.updated_at = datetime.now(timezone.utc).isoformat()

        self._emit_audit("revoke", org_id, key_name)
        logger.info("Vault: revoked secret %s/%s", org_id, key_name)
        return entry

    def list_secrets(self, org_id: str) -> list[dict[str, Any]]:
        """List all secrets for an org (metadata only, never plaintext)."""
        org_store = self._store.get(org_id, {})
        self._emit_audit("list", org_id)
        return [entry.to_dict() for entry in org_store.values()]

    def has_secret(self, org_id: str, key_name: str) -> bool:
        """Check if a secret exists (any status)."""
        return key_name in self._store.get(org_id, {})

    def get_metadata(self, org_id: str, key_name: str) -> dict[str, Any]:
        """Get secret metadata without decrypting."""
        entry = self._get_entry(org_id, key_name)
        return entry.to_dict()

    # -- Org key management -------------------------------------------------

    def rotate_org_key(self, org_id: str, new_master_key: str) -> int:
        """Re-encrypt all active secrets for an org under a new master key.

        Returns the number of secrets re-encrypted.
        """
        org_store = self._store.get(org_id, {})
        if not org_store:
            return 0

        re_encrypted = 0
        for key_name, entry in org_store.items():
            if entry.status == SecretStatus.REVOKED:
                continue

            plaintext = self._decrypt(org_id, entry.encrypted_value)

            # Temporarily swap master for re-encryption
            old_master = self._master
            try:
                decoded = base64.b64decode(new_master_key)
            except Exception:
                decoded = hashlib.sha256(new_master_key.encode()).digest()
            if len(decoded) != _KEY_LENGTH:
                decoded = hashlib.sha256(decoded).digest()

            self._master = decoded
            entry.encrypted_value = self._encrypt(org_id, plaintext)
            entry.updated_at = datetime.now(timezone.utc).isoformat()
            self._master = old_master
            re_encrypted += 1

        self._emit_audit("rotate_org_key", org_id, detail={"re_encrypted": re_encrypted})
        return re_encrypted

    # -- Stats --------------------------------------------------------------

    @property
    def org_count(self) -> int:
        """Number of organizations with stored secrets."""
        return len(self._store)

    def secret_count(self, org_id: str) -> int:
        """Number of secrets stored for an org."""
        return len(self._store.get(org_id, {}))

    def health_check(self) -> dict[str, Any]:
        """Vault health summary for security audit CLI."""
        total = sum(len(v) for v in self._store.values())
        active = sum(
            1
            for org_store in self._store.values()
            for entry in org_store.values()
            if entry.status == SecretStatus.ACTIVE
        )
        revoked = sum(
            1
            for org_store in self._store.values()
            for entry in org_store.values()
            if entry.status == SecretStatus.REVOKED
        )
        return {
            "org_count": self.org_count,
            "total_secrets": total,
            "active_secrets": active,
            "revoked_secrets": revoked,
            "master_key_set": True,
        }

    # -- Internal -----------------------------------------------------------

    def _get_entry(self, org_id: str, key_name: str) -> VaultEntry:
        """Fetch entry or raise KeyError."""
        org_store = self._store.get(org_id)
        if org_store is None:
            raise KeyError(f"No secrets for org: {org_id}")
        entry = org_store.get(key_name)
        if entry is None:
            raise KeyError(f"Secret not found: {org_id}/{key_name}")
        return entry

    def _derive_org_dek(self, org_id: str, salt: bytes) -> bytes:
        """Derive per-org DEK via HKDF-SHA256."""
        from cryptography.hazmat.primitives.kdf.hkdf import HKDF
        from cryptography.hazmat.primitives import hashes

        # Combine org_id into info to ensure org isolation
        info = f"occp-vault-org-dek-v1:{org_id}".encode()
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=_KEY_LENGTH,
            salt=salt,
            info=info,
        )
        return hkdf.derive(self._master)

    def _encrypt(self, org_id: str, plaintext: str) -> str:
        """Encrypt plaintext with org-specific DEK → base64 envelope."""
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        salt = os.urandom(_SALT_LENGTH)
        dek = self._derive_org_dek(org_id, salt)
        nonce = os.urandom(_NONCE_LENGTH)

        aesgcm = AESGCM(dek)
        aad = _V1_PREFIX + org_id.encode("utf-8")
        ct_and_tag = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), aad)

        # Pack: version(1) + salt(16) + nonce(12) + ciphertext_with_tag
        envelope = _V1_PREFIX + salt + nonce + ct_and_tag
        return base64.b64encode(envelope).decode("ascii")

    def _decrypt(self, org_id: str, encrypted_b64: str) -> str:
        """Decrypt base64 envelope with org-specific DEK → plaintext."""
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        raw = base64.b64decode(encrypted_b64)
        if len(raw) < 1 + _SALT_LENGTH + _NONCE_LENGTH + 16:
            raise ValueError("Invalid vault envelope: too short")

        version = raw[0]
        if version != 2:
            raise ValueError(f"Unsupported vault envelope version: {version}")

        salt = raw[1 : 1 + _SALT_LENGTH]
        nonce = raw[1 + _SALT_LENGTH : 1 + _SALT_LENGTH + _NONCE_LENGTH]
        ct_and_tag = raw[1 + _SALT_LENGTH + _NONCE_LENGTH :]

        dek = self._derive_org_dek(org_id, salt)
        aad = _V1_PREFIX + org_id.encode("utf-8")

        aesgcm = AESGCM(dek)
        plaintext = aesgcm.decrypt(nonce, ct_and_tag, aad)
        return plaintext.decode("utf-8")

    def _emit_audit(
        self,
        action: str,
        org_id: str,
        key_name: str = "",
        detail: dict[str, Any] | None = None,
    ) -> None:
        """Emit audit event via callback if registered."""
        if self._audit_cb is None:
            return
        event = VaultAuditEvent(
            action=action,
            org_id=org_id,
            key_name=key_name,
            detail=detail or {},
        )
        try:
            self._audit_cb(event)
        except Exception:
            logger.exception("Vault audit callback failed")


def _mask_secret(value: str) -> str:
    """Return masked version for display: first 4 + *** + last 4."""
    if len(value) <= 10:
        return "***"
    return f"{value[:4]}***{value[-4:]}"
