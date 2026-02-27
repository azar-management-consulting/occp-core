"""Encrypted token store — persists LLM API keys with AES-256-GCM.

Tokens are encrypted at rest using the ``TokenEncryptor``. Each user
can store multiple provider tokens (anthropic, openai, etc.).

The store never returns plaintext tokens in list operations — only
masked versions for UI display.
"""

from __future__ import annotations

import uuid
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from security.encryption import TokenEncryptor, mask_token
from store.models import EncryptedTokenRow

logger = logging.getLogger(__name__)


class TokenStore:
    """CRUD for encrypted API tokens with per-user isolation."""

    def __init__(self, session: AsyncSession, encryptor: TokenEncryptor) -> None:
        self._session = session
        self._enc = encryptor

    async def store_token(
        self,
        user_id: str,
        provider: str,
        token: str,
        *,
        label: str = "",
    ) -> EncryptedTokenRow:
        """Encrypt and store a token. Replaces existing token for same user+provider."""
        # Remove existing token for this user+provider
        await self._session.execute(
            delete(EncryptedTokenRow).where(
                EncryptedTokenRow.user_id == user_id,
                EncryptedTokenRow.provider == provider,
            )
        )
        await self._session.flush()

        now = datetime.now(timezone.utc).isoformat()
        encrypted = self._enc.encrypt(token)
        masked = mask_token(token)

        row = EncryptedTokenRow(
            id=uuid.uuid4().hex[:32],
            user_id=user_id,
            provider=provider,
            encrypted_value=encrypted,
            masked_value=masked,
            label=label or f"{provider} API key",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        self._session.add(row)
        await self._session.flush()

        logger.info(
            "Stored encrypted %s token for user=%s (masked=%s)",
            provider,
            user_id,
            masked,
        )
        return row

    async def get_decrypted(self, user_id: str, provider: str) -> str | None:
        """Retrieve and decrypt a token. Returns None if not found."""
        result = await self._session.execute(
            select(EncryptedTokenRow).where(
                EncryptedTokenRow.user_id == user_id,
                EncryptedTokenRow.provider == provider,
                EncryptedTokenRow.is_active == True,  # noqa: E712
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None

        try:
            return self._enc.decrypt(row.encrypted_value)
        except Exception:
            logger.error(
                "Failed to decrypt %s token for user=%s — key rotation needed?",
                provider,
                user_id,
            )
            return None

    async def list_tokens(self, user_id: str) -> list[dict[str, Any]]:
        """List all tokens for a user (masked, never plaintext)."""
        result = await self._session.execute(
            select(EncryptedTokenRow).where(
                EncryptedTokenRow.user_id == user_id,
            )
        )
        rows = result.scalars().all()
        return [
            {
                "id": r.id,
                "provider": r.provider,
                "masked_value": r.masked_value,
                "label": r.label,
                "is_active": r.is_active,
                "created_at": r.created_at,
                "updated_at": r.updated_at,
            }
            for r in rows
        ]

    async def has_active_token(self, user_id: str, provider: str | None = None) -> bool:
        """Check if user has any active token (optionally for a specific provider)."""
        stmt = select(EncryptedTokenRow.id).where(
            EncryptedTokenRow.user_id == user_id,
            EncryptedTokenRow.is_active == True,  # noqa: E712
        )
        if provider:
            stmt = stmt.where(EncryptedTokenRow.provider == provider)
        result = await self._session.execute(stmt.limit(1))
        return result.scalar_one_or_none() is not None

    async def revoke_token(self, user_id: str, provider: str) -> bool:
        """Soft-delete a token (set is_active=False)."""
        result = await self._session.execute(
            select(EncryptedTokenRow).where(
                EncryptedTokenRow.user_id == user_id,
                EncryptedTokenRow.provider == provider,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return False

        row.is_active = False
        row.updated_at = datetime.now(timezone.utc).isoformat()
        await self._session.flush()
        logger.info("Revoked %s token for user=%s", provider, user_id)
        return True

    async def delete_token(self, user_id: str, provider: str) -> bool:
        """Hard-delete a token (irreversible)."""
        result = await self._session.execute(
            delete(EncryptedTokenRow).where(
                EncryptedTokenRow.user_id == user_id,
                EncryptedTokenRow.provider == provider,
            )
        )
        await self._session.flush()
        deleted = result.rowcount > 0  # type: ignore[union-attr]
        if deleted:
            logger.info("Deleted %s token for user=%s", provider, user_id)
        return deleted

    async def rotate_all(self, new_encryptor: TokenEncryptor) -> int:
        """Re-encrypt all active tokens with a new master key.

        Returns count of re-encrypted tokens.
        """
        result = await self._session.execute(
            select(EncryptedTokenRow).where(
                EncryptedTokenRow.is_active == True,  # noqa: E712
            )
        )
        rows = result.scalars().all()
        count = 0
        for row in rows:
            try:
                plaintext = self._enc.decrypt(row.encrypted_value)
                row.encrypted_value = new_encryptor.encrypt(plaintext)
                row.updated_at = datetime.now(timezone.utc).isoformat()
                count += 1
            except Exception:
                logger.error(
                    "Failed to rotate token id=%s for user=%s",
                    row.id,
                    row.user_id,
                )
        await self._session.flush()
        self._enc = new_encryptor
        logger.info("Rotated %d/%d tokens", count, len(rows))
        return count
