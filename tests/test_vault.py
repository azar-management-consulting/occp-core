"""Tests for Credential Vault — REQ-SEC-03."""

from __future__ import annotations

import base64
import secrets

import pytest

from security.vault import (
    CredentialVault,
    SecretStatus,
    VaultAuditEvent,
    VaultEntry,
    _mask_secret,
)


@pytest.fixture
def master_key() -> str:
    """Generate a valid base64-encoded 32-byte master key."""
    return base64.b64encode(secrets.token_bytes(32)).decode()


@pytest.fixture
def vault(master_key: str) -> CredentialVault:
    """Create a fresh vault instance."""
    return CredentialVault(master_key)


@pytest.fixture
def audit_log() -> list[VaultAuditEvent]:
    """Collect audit events."""
    return []


@pytest.fixture
def audited_vault(master_key: str, audit_log: list[VaultAuditEvent]) -> CredentialVault:
    """Vault with audit callback."""
    return CredentialVault(master_key, audit_callback=audit_log.append)


# ---------------------------------------------------------------------------
# Store + Retrieve
# ---------------------------------------------------------------------------


class TestStoreRetrieve:
    def test_store_and_retrieve(self, vault: CredentialVault) -> None:
        vault.store("org-1", "openai-key", "sk-abc123xyz789")
        result = vault.retrieve("org-1", "openai-key")
        assert result == "sk-abc123xyz789"

    def test_store_returns_entry_with_mask(self, vault: CredentialVault) -> None:
        entry = vault.store("org-1", "key", "sk-abc123xyz789")
        assert entry.masked_value == "sk-a***z789"
        assert entry.status == SecretStatus.ACTIVE
        assert entry.org_id == "org-1"
        assert entry.version == 1

    def test_store_with_labels(self, vault: CredentialVault) -> None:
        entry = vault.store("org-1", "key", "secret", labels={"provider": "openai"})
        assert entry.labels["provider"] == "openai"

    def test_store_overwrites_existing(self, vault: CredentialVault) -> None:
        vault.store("org-1", "key", "old-value")
        vault.store("org-1", "key", "new-value")
        assert vault.retrieve("org-1", "key") == "new-value"

    def test_retrieve_missing_org_raises(self, vault: CredentialVault) -> None:
        with pytest.raises(KeyError, match="No secrets for org"):
            vault.retrieve("nonexistent", "key")

    def test_retrieve_missing_key_raises(self, vault: CredentialVault) -> None:
        vault.store("org-1", "key", "value")
        with pytest.raises(KeyError, match="Secret not found"):
            vault.retrieve("org-1", "other-key")

    def test_store_empty_org_raises(self, vault: CredentialVault) -> None:
        with pytest.raises(ValueError, match="org_id and key_name"):
            vault.store("", "key", "value")

    def test_store_empty_secret_raises(self, vault: CredentialVault) -> None:
        with pytest.raises(ValueError, match="plaintext secret cannot be empty"):
            vault.store("org-1", "key", "")


# ---------------------------------------------------------------------------
# Org isolation
# ---------------------------------------------------------------------------


class TestOrgIsolation:
    def test_different_orgs_different_encryption(self, vault: CredentialVault) -> None:
        vault.store("org-1", "key", "same-secret")
        vault.store("org-2", "key", "same-secret")
        e1 = vault._store["org-1"]["key"].encrypted_value
        e2 = vault._store["org-2"]["key"].encrypted_value
        # Same plaintext, different orgs → different ciphertext
        assert e1 != e2

    def test_cross_org_retrieve_fails(self, vault: CredentialVault) -> None:
        vault.store("org-1", "key", "secret")
        with pytest.raises(KeyError):
            vault.retrieve("org-2", "key")

    def test_org_count(self, vault: CredentialVault) -> None:
        assert vault.org_count == 0
        vault.store("org-1", "k1", "v1")
        vault.store("org-2", "k2", "v2")
        assert vault.org_count == 2

    def test_secret_count(self, vault: CredentialVault) -> None:
        vault.store("org-1", "k1", "v1")
        vault.store("org-1", "k2", "v2")
        assert vault.secret_count("org-1") == 2
        assert vault.secret_count("org-2") == 0


# ---------------------------------------------------------------------------
# Rotate
# ---------------------------------------------------------------------------


class TestRotation:
    def test_rotate_updates_value(self, vault: CredentialVault) -> None:
        vault.store("org-1", "key", "old-secret")
        entry = vault.rotate("org-1", "key", "new-secret")
        assert vault.retrieve("org-1", "key") == "new-secret"
        assert entry.version == 2
        assert entry.rotated_from != ""

    def test_rotate_preserves_labels(self, vault: CredentialVault) -> None:
        vault.store("org-1", "key", "old", labels={"provider": "openai"})
        entry = vault.rotate("org-1", "key", "new")
        assert entry.labels["provider"] == "openai"

    def test_rotate_revoked_raises(self, vault: CredentialVault) -> None:
        vault.store("org-1", "key", "secret")
        vault.revoke("org-1", "key")
        with pytest.raises(ValueError, match="Cannot rotate revoked"):
            vault.rotate("org-1", "key", "new")

    def test_rotate_empty_value_raises(self, vault: CredentialVault) -> None:
        vault.store("org-1", "key", "secret")
        with pytest.raises(ValueError, match="New secret value cannot be empty"):
            vault.rotate("org-1", "key", "")


# ---------------------------------------------------------------------------
# Revoke
# ---------------------------------------------------------------------------


class TestRevocation:
    def test_revoke_marks_secret(self, vault: CredentialVault) -> None:
        vault.store("org-1", "key", "secret")
        entry = vault.revoke("org-1", "key")
        assert entry.status == SecretStatus.REVOKED
        assert entry.encrypted_value == ""

    def test_retrieve_revoked_raises(self, vault: CredentialVault) -> None:
        vault.store("org-1", "key", "secret")
        vault.revoke("org-1", "key")
        with pytest.raises(ValueError, match="has been revoked"):
            vault.retrieve("org-1", "key")


# ---------------------------------------------------------------------------
# List + Metadata
# ---------------------------------------------------------------------------


class TestListAndMetadata:
    def test_list_secrets(self, vault: CredentialVault) -> None:
        vault.store("org-1", "key-a", "secret-a")
        vault.store("org-1", "key-b", "secret-b")
        items = vault.list_secrets("org-1")
        assert len(items) == 2
        names = {i["key_name"] for i in items}
        assert names == {"key-a", "key-b"}
        # Ensure no encrypted values leak
        for item in items:
            assert "encrypted_value" not in item

    def test_list_empty_org(self, vault: CredentialVault) -> None:
        items = vault.list_secrets("nonexistent")
        assert items == []

    def test_has_secret(self, vault: CredentialVault) -> None:
        vault.store("org-1", "key", "secret")
        assert vault.has_secret("org-1", "key") is True
        assert vault.has_secret("org-1", "other") is False

    def test_get_metadata(self, vault: CredentialVault) -> None:
        vault.store("org-1", "key", "secret", labels={"env": "prod"})
        meta = vault.get_metadata("org-1", "key")
        assert meta["labels"]["env"] == "prod"
        assert meta["status"] == "active"


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------


class TestAudit:
    def test_store_emits_audit(
        self, audited_vault: CredentialVault, audit_log: list[VaultAuditEvent]
    ) -> None:
        audited_vault.store("org-1", "key", "secret")
        assert len(audit_log) == 1
        assert audit_log[0].action == "store"
        assert audit_log[0].org_id == "org-1"
        assert audit_log[0].key_name == "key"

    def test_retrieve_emits_audit(
        self, audited_vault: CredentialVault, audit_log: list[VaultAuditEvent]
    ) -> None:
        audited_vault.store("org-1", "key", "secret")
        audited_vault.retrieve("org-1", "key")
        assert audit_log[-1].action == "retrieve"

    def test_revoke_emits_audit(
        self, audited_vault: CredentialVault, audit_log: list[VaultAuditEvent]
    ) -> None:
        audited_vault.store("org-1", "key", "secret")
        audited_vault.revoke("org-1", "key")
        assert audit_log[-1].action == "revoke"

    def test_audit_callback_failure_is_caught(self, master_key: str) -> None:
        def bad_cb(_: VaultAuditEvent) -> None:
            raise RuntimeError("boom")

        vault = CredentialVault(master_key, audit_callback=bad_cb)
        # Should not raise despite callback failure
        vault.store("org-1", "key", "secret")


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


class TestHealthCheck:
    def test_health_check(self, vault: CredentialVault) -> None:
        vault.store("org-1", "k1", "v1")
        vault.store("org-1", "k2", "v2")
        vault.store("org-2", "k3", "v3")
        vault.revoke("org-1", "k2")

        health = vault.health_check()
        assert health["org_count"] == 2
        assert health["total_secrets"] == 3
        assert health["active_secrets"] == 2
        assert health["revoked_secrets"] == 1
        assert health["master_key_set"] is True


# ---------------------------------------------------------------------------
# Masking
# ---------------------------------------------------------------------------


class TestMasking:
    def test_mask_long_secret(self) -> None:
        assert _mask_secret("sk-abc123xyz789") == "sk-a***z789"

    def test_mask_short_secret(self) -> None:
        assert _mask_secret("short") == "***"

    def test_mask_boundary(self) -> None:
        assert _mask_secret("0123456789") == "***"  # exactly 10 chars
        assert _mask_secret("01234567890") == "0123***7890"  # 11 chars, first 4 + *** + last 4


# ---------------------------------------------------------------------------
# Ephemeral key mode
# ---------------------------------------------------------------------------


class TestEphemeralKey:
    def test_empty_master_key_works(self) -> None:
        vault = CredentialVault("")
        vault.store("org-1", "key", "secret-value")
        assert vault.retrieve("org-1", "key") == "secret-value"
