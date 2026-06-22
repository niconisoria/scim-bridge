from unittest.mock import AsyncMock, MagicMock

import pytest

from app.brivo.client import BrivoNotFoundError
from app.core.errors import ScimNotFound
from app.services.delete_group import delete_group
from app.services.saga import SagaError


def _idmap(target_id: str = "99", external_id: str = "ext-g1") -> dict:
    return {"target_id": target_id, "external_id": external_id}


@pytest.mark.asyncio
async def test_scim_id_not_found_raises():
    store = AsyncMock()
    store.get_by_scim.return_value = None
    client = MagicMock()

    with pytest.raises(ScimNotFound):
        await delete_group("scim-g1", store, client)

    client.delete_group.assert_not_called()


@pytest.mark.asyncio
async def test_happy_path_deletes_group_and_clears_idmap():
    store = AsyncMock()
    store.get_by_scim.return_value = _idmap()
    client = AsyncMock()

    await delete_group("scim-g1", store, client)

    client.delete_group.assert_called_once_with(99)
    store.del_idmap.assert_called_once_with("group", "scim-g1", "99", "ext-g1")
    assert store.cache_del.call_count == 2
    store.cache_del.assert_any_call("group", "99")
    store.cache_del.assert_any_call("group", "99", "members")


@pytest.mark.asyncio
async def test_brivo_404_swallowed_saga_completes():
    store = AsyncMock()
    store.get_by_scim.return_value = _idmap()
    client = AsyncMock()
    client.delete_group.side_effect = BrivoNotFoundError(404)

    await delete_group("scim-g1", store, client)

    store.del_idmap.assert_called_once()


@pytest.mark.asyncio
async def test_brivo_delete_fails_logs_alert_raises_saga_error():
    store = AsyncMock()
    store.get_by_scim.return_value = _idmap()
    client = AsyncMock()
    client.delete_group.side_effect = RuntimeError("brivo down")

    with pytest.raises(SagaError):
        await delete_group("scim-g1", store, client)

    store.del_idmap.assert_not_called()


@pytest.mark.asyncio
async def test_idmap_del_fails_restores_idmap():
    store = AsyncMock()
    store.get_by_scim.return_value = _idmap()
    store.del_idmap.side_effect = RuntimeError("redis down")
    client = AsyncMock()

    with pytest.raises(SagaError):
        await delete_group("scim-g1", store, client)

    store.set_idmap.assert_called_once_with("group", "scim-g1", "99", "ext-g1")
