from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.errors import ScimConflict
from app.models.brivo import BrivoUser
from app.models.user import ScimEmail, ScimName, ScimUser
from app.services.create_user import create_user
from app.services.saga import SagaError


def _body(**kwargs) -> ScimUser:
    defaults = dict(
        userName="jane@example.com",
        name=ScimName(givenName="Jane", familyName="Doe"),
        emails=[ScimEmail(value="jane@example.com", primary=True)],
        externalId="ext-123",
    )
    defaults.update(kwargs)
    return ScimUser(**defaults)


def _brivo_user() -> BrivoUser:
    return BrivoUser(
        id=42,
        firstName="Jane",
        lastName="Doe",
        emails=[{"address": "jane@example.com", "type": "work"}],
        phoneNumbers=[],
        suspended=False,
        created="2024-01-01T00:00:00Z",
        updated="2024-01-01T00:00:00Z",
    )


def _fresh_store() -> AsyncMock:
    store = AsyncMock()
    store.get_by_external.return_value = None
    store.acquire_lock.return_value = True
    return store


@pytest.mark.asyncio
async def test_no_external_id_falls_back_to_username():
    store = _fresh_store()
    client = AsyncMock()
    client.create_user.return_value = _brivo_user()

    brivo_user, scim_id = await create_user(_body(externalId=None), store, client)

    assert brivo_user.id == 42
    store.acquire_lock.assert_called_once_with("user", "jane@example.com", scim_id)
    store.set_idmap.assert_called_once_with("user", scim_id, "42", "jane@example.com")
    store.release_lock.assert_called_once_with("user", "jane@example.com")


@pytest.mark.asyncio
async def test_duplicate_user_returns_existing():
    store = AsyncMock()
    store.get_by_external.return_value = {"scim_id": "existing", "target_id": "1"}
    store.cache_get.return_value = None
    client = AsyncMock()
    client.get_user.return_value = _brivo_user()

    brivo_user, scim_id = await create_user(_body(), store, client)

    assert scim_id == "existing"
    assert brivo_user.id == 42
    store.acquire_lock.assert_not_called()
    client.create_user.assert_not_called()


@pytest.mark.asyncio
async def test_lock_conflict_raises_scim_conflict():
    store = AsyncMock()
    store.get_by_external.return_value = None
    store.acquire_lock.return_value = False
    client = MagicMock()

    with pytest.raises(ScimConflict):
        await create_user(_body(), store, client)


@pytest.mark.asyncio
async def test_happy_path_returns_brivo_user_and_scim_id():
    store = _fresh_store()
    client = AsyncMock()
    client.create_user.return_value = _brivo_user()

    brivo_user, scim_id = await create_user(_body(), store, client)

    assert brivo_user.id == 42
    assert len(scim_id) == 36
    store.set_idmap.assert_called_once_with("user", scim_id, "42", "ext-123")
    store.release_lock.assert_called_once_with("user", "ext-123")


@pytest.mark.asyncio
async def test_brivo_create_fails_releases_lock():
    store = _fresh_store()
    client = AsyncMock()
    client.create_user.side_effect = RuntimeError("brivo down")

    with pytest.raises(SagaError):
        await create_user(_body(), store, client)

    store.release_lock.assert_called_once_with("user", "ext-123")


@pytest.mark.asyncio
async def test_idmap_write_fails_deletes_brivo_user_and_releases_lock():
    store = _fresh_store()
    store.set_idmap.side_effect = RuntimeError("redis down")
    client = AsyncMock()
    client.create_user.return_value = _brivo_user()

    with pytest.raises(SagaError):
        await create_user(_body(), store, client)

    client.delete_user.assert_called_once_with(42)
    store.release_lock.assert_called_once_with("user", "ext-123")
