from unittest.mock import AsyncMock, MagicMock

import pytest

from app.brivo.client import BrivoNotFoundError
from app.core.errors import ScimNotFound
from app.models.brivo import BrivoGroupRef, BrivoUser
from app.services.delete_user import delete_user
from app.services.saga import SagaError


def _idmap(target_id: str = "42", external_id: str = "ext-123") -> dict:
    return {"target_id": target_id, "external_id": external_id}


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


def _groups() -> list[BrivoGroupRef]:
    return [BrivoGroupRef(id=10, name="g1"), BrivoGroupRef(id=11, name="g2")]


@pytest.mark.asyncio
async def test_scim_id_not_found_raises():
    store = AsyncMock()
    store.get_by_scim.return_value = None
    client = MagicMock()

    with pytest.raises(ScimNotFound):
        await delete_user("scim-1", store, client)

    client.list_user_groups.assert_not_called()


@pytest.mark.asyncio
async def test_happy_path_deletes_user_and_clears_idmap():
    store = AsyncMock()
    store.get_by_scim.return_value = _idmap()
    client = AsyncMock()
    client.list_user_groups.return_value = _groups()
    client.get_user.return_value = _brivo_user()

    await delete_user("scim-1", store, client)

    assert client.remove_user_from_group.call_count == 2
    client.get_user.assert_called_once_with(42)
    client.delete_user.assert_called_once_with(42)
    store.del_idmap.assert_called_once_with("user", "scim-1", "42", "ext-123")
    store.cache_del.assert_called_once_with("user", "42")


@pytest.mark.asyncio
async def test_group_removal_404_swallowed_saga_completes():
    store = AsyncMock()
    store.get_by_scim.return_value = _idmap()
    client = AsyncMock()
    client.list_user_groups.return_value = _groups()
    client.remove_user_from_group.side_effect = [None, BrivoNotFoundError(404)]
    client.get_user.return_value = _brivo_user()

    await delete_user("scim-1", store, client)

    assert client.remove_user_from_group.call_count == 2
    store.del_idmap.assert_called_once()


@pytest.mark.asyncio
async def test_brivo_delete_fails_readds_groups_and_recreates():
    store = AsyncMock()
    store.get_by_scim.return_value = _idmap()
    client = AsyncMock()
    client.list_user_groups.return_value = [BrivoGroupRef(id=10, name="g1")]
    client.get_user.return_value = _brivo_user()
    client.delete_user.side_effect = RuntimeError("brivo down")

    with pytest.raises(SagaError):
        await delete_user("scim-1", store, client)

    client.create_user.assert_called_once()
    client.add_user_to_group.assert_called_once_with(10, 42)
    store.del_idmap.assert_not_called()


@pytest.mark.asyncio
async def test_idmap_del_fails_full_compensation():
    store = AsyncMock()
    store.get_by_scim.return_value = _idmap()
    store.del_idmap.side_effect = RuntimeError("redis down")
    client = AsyncMock()
    client.list_user_groups.return_value = [BrivoGroupRef(id=10, name="g1")]
    client.get_user.return_value = _brivo_user()

    with pytest.raises(SagaError):
        await delete_user("scim-1", store, client)

    store.set_idmap.assert_called_once()
    store.cache_set.assert_called_once()
    client.create_user.assert_called_once()
    client.add_user_to_group.assert_called_once_with(10, 42)
