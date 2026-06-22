from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.errors import ScimBadRequest
from app.services.remove_members import remove_members
from app.services.saga import SagaError


@pytest.mark.asyncio
async def test_empty_list_returns_without_brivo_calls():
    store = MagicMock()
    client = MagicMock()
    await remove_members(99, [], store, client)
    client.remove_user_from_group.assert_not_called()


@pytest.mark.asyncio
async def test_unresolvable_member_raises_bad_request():
    store = AsyncMock()
    store.get_by_scim.return_value = None
    client = MagicMock()
    with pytest.raises(ScimBadRequest):
        await remove_members(99, ["scim-u1"], store, client)
    client.remove_user_from_group.assert_not_called()


@pytest.mark.asyncio
async def test_happy_path_removes_all_members_and_dels_cache():
    store = AsyncMock()
    store.get_by_scim.side_effect = [{"target_id": "101"}, {"target_id": "102"}]
    client = AsyncMock()

    await remove_members(99, ["scim-u1", "scim-u2"], store, client)

    assert client.remove_user_from_group.call_count == 2
    client.remove_user_from_group.assert_any_call(99, 101)
    client.remove_user_from_group.assert_any_call(99, 102)
    store.cache_del.assert_called_once_with("group", "99", "members")


@pytest.mark.asyncio
async def test_partial_failure_re_adds_removed_in_reverse():
    store = AsyncMock()
    store.get_by_scim.side_effect = [{"target_id": "101"}, {"target_id": "102"}]
    client = AsyncMock()
    client.remove_user_from_group.side_effect = [None, RuntimeError("brivo down")]

    with pytest.raises(SagaError):
        await remove_members(99, ["scim-u1", "scim-u2"], store, client)

    client.add_user_to_group.assert_called_once_with(99, 101)
    store.cache_del.assert_called()
