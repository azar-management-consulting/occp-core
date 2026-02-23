"""User persistence — SQLAlchemy 2.0 ORM backend with argon2 password hashing.

Provides CRUD operations for users with secure password storage using
argon2-cffi (NOT passlib) per OCCP security requirements.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from dataclasses import dataclass, field

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from store.models import UserRow

_ph = PasswordHasher()


# ── Domain Model ─────────────────────────────────────────────────────


@dataclass
class User:
    """Domain user model (never contains raw password)."""

    username: str
    role: str = "viewer"
    display_name: str = ""
    email: str | None = None
    is_active: bool = True
    metadata: dict = field(default_factory=dict)
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# Valid RBAC roles — hierarchical
VALID_ROLES = ("system_admin", "org_admin", "operator", "viewer")


# ── Store ────────────────────────────────────────────────────────────


class UserStore:
    """CRUD operations for users with argon2 password hashing."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── Write ──────────────────────────────────────────────────────

    async def create(
        self,
        username: str,
        password: str,
        *,
        role: str = "viewer",
        display_name: str = "",
        email: str | None = None,
        metadata: dict | None = None,
    ) -> User:
        """Create a new user with hashed password."""
        if role not in VALID_ROLES:
            raise ValueError(f"Invalid role: {role}. Must be one of {VALID_ROLES}")

        now = datetime.now(timezone.utc).isoformat()
        user_id = uuid.uuid4().hex[:12]

        row = UserRow(
            id=user_id,
            username=username,
            password_hash=_ph.hash(password),
            role=role,
            is_active=True,
            display_name=display_name or username,
            email=email,
            metadata_=metadata or {},
            created_at=now,
            updated_at=now,
        )
        self._session.add(row)
        await self._session.commit()

        return User(
            id=user_id,
            username=username,
            role=role,
            display_name=display_name or username,
            email=email,
            metadata=metadata or {},
        )

    async def update_password(self, username: str, new_password: str) -> bool:
        """Update a user's password. Returns True if updated."""
        stmt = select(UserRow).where(UserRow.username == username)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return False

        row.password_hash = _ph.hash(new_password)
        row.updated_at = datetime.now(timezone.utc).isoformat()
        await self._session.commit()
        return True

    async def update_role(self, username: str, new_role: str) -> bool:
        """Update a user's role. Returns True if updated."""
        if new_role not in VALID_ROLES:
            raise ValueError(f"Invalid role: {new_role}")

        stmt = select(UserRow).where(UserRow.username == username)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return False

        row.role = new_role
        row.updated_at = datetime.now(timezone.utc).isoformat()
        await self._session.commit()
        return True

    async def deactivate(self, username: str) -> bool:
        """Soft-delete: set is_active=False."""
        stmt = select(UserRow).where(UserRow.username == username)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return False

        row.is_active = False
        row.updated_at = datetime.now(timezone.utc).isoformat()
        await self._session.commit()
        return True

    async def delete(self, username: str) -> bool:
        """Hard-delete a user. Returns True if deleted."""
        stmt = delete(UserRow).where(UserRow.username == username)
        result = await self._session.execute(stmt)
        await self._session.commit()
        return result.rowcount > 0

    # ── Read ───────────────────────────────────────────────────────

    async def authenticate(self, username: str, password: str) -> User | None:
        """Verify credentials. Returns User if valid, None otherwise.

        Also rehashes password if argon2 parameters have changed.
        """
        stmt = select(UserRow).where(
            UserRow.username == username,
            UserRow.is_active == True,  # noqa: E712
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            # Constant-time dummy hash to prevent timing attacks
            _ph.hash("dummy-password-for-timing")
            return None

        try:
            _ph.verify(row.password_hash, password)
        except VerifyMismatchError:
            return None

        # Rehash if argon2 parameters changed (transparent upgrade)
        if _ph.check_needs_rehash(row.password_hash):
            row.password_hash = _ph.hash(password)
            row.updated_at = datetime.now(timezone.utc).isoformat()
            await self._session.commit()

        return self._row_to_user(row)

    async def get_by_username(self, username: str) -> User | None:
        """Fetch a user by username."""
        stmt = select(UserRow).where(UserRow.username == username)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self._row_to_user(row)

    async def get_by_id(self, user_id: str) -> User | None:
        """Fetch a user by ID."""
        stmt = select(UserRow).where(UserRow.id == user_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self._row_to_user(row)

    async def list_all(self) -> list[User]:
        """Return all users ordered by username."""
        stmt = select(UserRow).order_by(UserRow.username)
        result = await self._session.execute(stmt)
        return [self._row_to_user(r) for r in result.scalars().all()]

    async def count(self) -> int:
        """Total user count."""
        stmt = select(func.count()).select_from(UserRow)
        result = await self._session.execute(stmt)
        return result.scalar_one()

    # ── Conversion ─────────────────────────────────────────────────

    @staticmethod
    def _row_to_user(row: UserRow) -> User:
        """Convert ORM row to domain User model (no password hash)."""
        return User(
            id=row.id,
            username=row.username,
            role=row.role,
            display_name=row.display_name,
            email=row.email,
            is_active=row.is_active,
            metadata=row.metadata_ if row.metadata_ else {},
            created_at=datetime.fromisoformat(row.created_at),
            updated_at=datetime.fromisoformat(row.updated_at),
        )
