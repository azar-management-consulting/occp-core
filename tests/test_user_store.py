"""Tests for UserStore — CRUD, authentication, and argon2 password hashing."""

from __future__ import annotations

import pytest

from store.database import Database
from store.user_store import UserStore, User, VALID_ROLES


@pytest.fixture
async def db(tmp_path):
    """Create a fresh SQLite database for each test."""
    db = Database(url=f"sqlite+aiosqlite:///{tmp_path}/test_users.db")
    await db.connect()
    yield db
    await db.close()


@pytest.fixture
async def store(db):
    """UserStore backed by a fresh database."""
    return UserStore(db.session())


class TestUserCreate:
    async def test_create_user(self, store: UserStore) -> None:
        user = await store.create("alice", "s3cure-pass!", role="operator")
        assert isinstance(user, User)
        assert user.username == "alice"
        assert user.role == "operator"
        assert user.is_active is True
        assert len(user.id) == 12

    async def test_create_default_role(self, store: UserStore) -> None:
        user = await store.create("bob", "password123")
        assert user.role == "viewer"

    async def test_create_with_email(self, store: UserStore) -> None:
        user = await store.create(
            "carol", "pass123",
            email="carol@example.com",
            display_name="Carol D.",
        )
        assert user.email == "carol@example.com"
        assert user.display_name == "Carol D."

    async def test_create_with_metadata(self, store: UserStore) -> None:
        user = await store.create("dave", "pass123", metadata={"org": "acme"})
        assert user.metadata == {"org": "acme"}

    async def test_create_invalid_role(self, store: UserStore) -> None:
        with pytest.raises(ValueError, match="Invalid role"):
            await store.create("eve", "pass123", role="superuser")

    async def test_create_all_valid_roles(self, store: UserStore) -> None:
        for i, role in enumerate(VALID_ROLES):
            user = await store.create(f"user_{i}", "pass123", role=role)
            assert user.role == role


class TestAuthenticate:
    async def test_authenticate_success(self, store: UserStore) -> None:
        await store.create("alice", "correct-horse-battery")
        user = await store.authenticate("alice", "correct-horse-battery")
        assert user is not None
        assert user.username == "alice"

    async def test_authenticate_wrong_password(self, store: UserStore) -> None:
        await store.create("bob", "right-password")
        user = await store.authenticate("bob", "wrong-password")
        assert user is None

    async def test_authenticate_unknown_user(self, store: UserStore) -> None:
        user = await store.authenticate("ghost", "any-password")
        assert user is None

    async def test_authenticate_inactive_user(self, store: UserStore) -> None:
        await store.create("carol", "my-password")
        await store.deactivate("carol")
        user = await store.authenticate("carol", "my-password")
        assert user is None

    async def test_authenticate_returns_no_password(self, store: UserStore) -> None:
        await store.create("dave", "secret")
        user = await store.authenticate("dave", "secret")
        assert user is not None
        # User domain model should NOT have password_hash
        assert not hasattr(user, "password_hash")


class TestUpdatePassword:
    async def test_update_password_success(self, store: UserStore) -> None:
        await store.create("alice", "old-pass")
        result = await store.update_password("alice", "new-pass")
        assert result is True

        # Old password no longer works
        assert await store.authenticate("alice", "old-pass") is None
        # New password works
        user = await store.authenticate("alice", "new-pass")
        assert user is not None

    async def test_update_password_unknown_user(self, store: UserStore) -> None:
        result = await store.update_password("ghost", "new-pass")
        assert result is False


class TestUpdateRole:
    async def test_update_role_success(self, store: UserStore) -> None:
        await store.create("alice", "pass", role="viewer")
        result = await store.update_role("alice", "operator")
        assert result is True

        user = await store.get_by_username("alice")
        assert user is not None
        assert user.role == "operator"

    async def test_update_role_invalid(self, store: UserStore) -> None:
        await store.create("bob", "pass", role="viewer")
        with pytest.raises(ValueError, match="Invalid role"):
            await store.update_role("bob", "overlord")

    async def test_update_role_unknown_user(self, store: UserStore) -> None:
        result = await store.update_role("ghost", "viewer")
        assert result is False


class TestDeactivateDelete:
    async def test_deactivate(self, store: UserStore) -> None:
        await store.create("alice", "pass")
        result = await store.deactivate("alice")
        assert result is True

        user = await store.get_by_username("alice")
        assert user is not None
        assert user.is_active is False

    async def test_deactivate_unknown(self, store: UserStore) -> None:
        result = await store.deactivate("ghost")
        assert result is False

    async def test_hard_delete(self, store: UserStore) -> None:
        await store.create("alice", "pass")
        result = await store.delete("alice")
        assert result is True
        assert await store.get_by_username("alice") is None

    async def test_hard_delete_unknown(self, store: UserStore) -> None:
        result = await store.delete("ghost")
        assert result is False


class TestRead:
    async def test_get_by_username(self, store: UserStore) -> None:
        await store.create("alice", "pass", role="operator")
        user = await store.get_by_username("alice")
        assert user is not None
        assert user.username == "alice"
        assert user.role == "operator"

    async def test_get_by_username_not_found(self, store: UserStore) -> None:
        assert await store.get_by_username("ghost") is None

    async def test_get_by_id(self, store: UserStore) -> None:
        created = await store.create("alice", "pass")
        user = await store.get_by_id(created.id)
        assert user is not None
        assert user.username == "alice"

    async def test_get_by_id_not_found(self, store: UserStore) -> None:
        assert await store.get_by_id("nonexistent") is None

    async def test_list_all(self, store: UserStore) -> None:
        await store.create("alice", "pass")
        await store.create("bob", "pass")
        await store.create("carol", "pass")
        users = await store.list_all()
        assert len(users) == 3
        # Ordered by username
        assert [u.username for u in users] == ["alice", "bob", "carol"]

    async def test_count(self, store: UserStore) -> None:
        assert await store.count() == 0
        await store.create("alice", "pass")
        await store.create("bob", "pass")
        assert await store.count() == 2


class TestArgon2:
    """Verify that passwords are actually hashed with argon2."""

    async def test_password_not_stored_plain(self, db, store: UserStore) -> None:
        await store.create("alice", "plaintext-secret")
        # Query the raw row to check hash format
        from sqlalchemy import select
        from store.models import UserRow
        async with db.engine.connect() as conn:
            result = await conn.execute(
                select(UserRow.password_hash).where(UserRow.username == "alice")
            )
            hash_val = result.scalar_one()
        assert hash_val != "plaintext-secret"
        assert hash_val.startswith("$argon2")
