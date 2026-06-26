from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.errors import ScimBadRequest
from app.models.group import ScimGroup, ScimMember
from app.services.saga import SagaError
from app.services.update_group import update_group


def _brivo_group(name="TestGroup"):
    g = MagicMock()
    g.id = 99
    g.name = name
    g.keypadUnlock = False
    g.immuneToAntipassback = False
    g.antipassbackResetTime = 0
    return g


def _page(user_ids: list[int]):
    p = MagicMock()
    p.data = [MagicMock(id=uid) for uid in user_ids]
    return p


def _body(display_name="NewName", members: list[str] | None = None):
    return ScimGroup(
        displayName=display_name,
        members=[ScimMember(value=m) for m in (members or [])],
    )


@pytest.mark.asyncio
async def test_unresolvable_member_raises_bad_request():
    store = AsyncMock()
    store.get_by_scim.return_value = None
    client = AsyncMock()

    with pytest.raises(ScimBadRequest):
        await update_group(99, "scim-g1", _body(members=["unknown"]), store, client)

    client.update_group.assert_not_called()


@pytest.mark.asyncio
async def test_happy_path_name_update_no_member_changes():
    store = AsyncMock()
    store.get_by_scim.side_effect = [{"target_id": "101"}]
    store.cache_get.side_effect = [None, [101]]  # group cache miss, members cache hit
    brivo_g = _brivo_group("OldName")
    updated_g = _brivo_group("NewName")
    client = AsyncMock()
    client.get_group.return_value = brivo_g
    client.update_group.return_value = updated_g

    result_group, result_scim_id = await update_group(
        99, "scim-g1", _body(display_name="NewName", members=["scim-u1"]), store, client
    )

    assert result_scim_id == "scim-g1"
    client.update_group.assert_called_once()
    client.add_user_to_group.assert_not_called()
    client.remove_user_from_group.assert_not_called()
    store.cache_del.assert_any_call("group", "99")
    store.cache_del.assert_any_call("group", "99", "members")


@pytest.mark.asyncio
async def test_adds_new_members_not_in_current():
    store = AsyncMock()
    store.get_by_scim.side_effect = [{"target_id": "101"}]
    store.cache_get.side_effect = [None, []]  # group miss, members cache hit (empty)
    client = AsyncMock()
    client.get_group.return_value = _brivo_group()
    client.update_group.return_value = _brivo_group()

    await update_group(99, "scim-g1", _body(members=["scim-u1"]), store, client)

    client.add_user_to_group.assert_called_once_with(99, 101)
    client.remove_user_from_group.assert_not_called()


@pytest.mark.asyncio
async def test_removes_stale_members_not_in_new_list():
    store = AsyncMock()
    store.get_by_scim.return_value = None  # no members in body to resolve
    store.cache_get.side_effect = [None, [101]]  # members cache hit with one member
    client = AsyncMock()
    client.get_group.return_value = _brivo_group()
    client.update_group.return_value = _brivo_group()

    # Body has no members → 101 is stale
    await update_group(99, "scim-g1", _body(members=[]), store, client)

    client.remove_user_from_group.assert_called_once_with(99, 101)
    client.add_user_to_group.assert_not_called()


@pytest.mark.asyncio
async def test_members_cache_miss_calls_list_group_users():
    store = AsyncMock()
    store.get_by_scim.return_value = None
    store.cache_get.return_value = None  # all cache misses
    client = AsyncMock()
    client.get_group.return_value = _brivo_group()
    client.update_group.return_value = _brivo_group()
    client.list_group_users.return_value = _page([])

    await update_group(99, "scim-g1", _body(members=[]), store, client)

    client.list_group_users.assert_called_once_with(99, page_size=200)


@pytest.mark.asyncio
async def test_members_cache_hit_skips_list_group_users():
    store = AsyncMock()
    store.get_by_scim.return_value = None
    store.cache_get.side_effect = [None, []]  # group miss, members hit (empty list)
    client = AsyncMock()
    client.get_group.return_value = _brivo_group()
    client.update_group.return_value = _brivo_group()

    await update_group(99, "scim-g1", _body(members=[]), store, client)

    client.list_group_users.assert_not_called()


@pytest.mark.asyncio
async def test_name_update_failure_triggers_name_rollback():
    store = AsyncMock()
    store.get_by_scim.return_value = None
    store.cache_get.return_value = None
    client = AsyncMock()
    client.get_group.return_value = _brivo_group("OldName")
    client.update_group.side_effect = RuntimeError("brivo down")

    with pytest.raises(SagaError):
        await update_group(99, "scim-g1", _body(members=[]), store, client)

    # Rollback calls update_group with original name
    assert client.update_group.call_count == 2


@pytest.mark.asyncio
async def test_add_member_failure_rolls_back_added_and_name():
    store = AsyncMock()
    store.get_by_scim.side_effect = [{"target_id": "101"}, {"target_id": "102"}]
    store.cache_get.side_effect = [None, []]  # group miss, members cache hit (empty)
    original = _brivo_group("OldName")
    updated = _brivo_group("NewName")
    client = AsyncMock()
    client.get_group.return_value = original
    client.update_group.return_value = updated
    client.add_user_to_group.side_effect = [None, RuntimeError("brivo down")]

    with pytest.raises(SagaError):
        await update_group(
            99, "scim-g1", _body(members=["scim-u1", "scim-u2"]), store, client
        )

    # step3 rollback: remove the one that was added (101)
    client.remove_user_from_group.assert_called_once_with(99, 101)
    # step1 rollback: restore original name
    assert client.update_group.call_count == 2  # forward + rollback
