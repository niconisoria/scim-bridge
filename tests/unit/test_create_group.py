from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.errors import ScimBadRequest, ScimConflict
from app.models.brivo import BrivoGroup
from app.models.group import ScimGroup, ScimMember
from app.services.create_group import create_group
from app.services.saga import SagaError


def _body(**kwargs) -> ScimGroup:
    defaults = dict(displayName="Engineering", externalId="ext-g1", members=[])
    defaults.update(kwargs)
    return ScimGroup(**defaults)


def _brivo_group() -> BrivoGroup:
    return BrivoGroup(
        id=99,
        name="Engineering",
        keypadUnlock=False,
        immuneToAntipassback=False,
        antipassbackResetTime=0,
    )


def _member(scim_id: str) -> ScimMember:
    return ScimMember(value=scim_id)


@pytest.mark.asyncio
async def test_missing_external_id_raises_bad_request():
    store = MagicMock()
    client = MagicMock()
    with pytest.raises(ScimBadRequest):
        await create_group(_body(externalId=None), store, client)


@pytest.mark.asyncio
async def test_unresolvable_member_raises_bad_request_before_lock():
    store = AsyncMock()
    store.get_by_scim.return_value = None
    client = MagicMock()
    with pytest.raises(ScimBadRequest):
        await create_group(_body(members=[_member("scim-u1")]), store, client)
    store.acquire_lock.assert_not_called()


@pytest.mark.asyncio
async def test_lock_conflict_raises_scim_conflict():
    store = AsyncMock()
    store.acquire_lock.return_value = False
    client = MagicMock()
    with pytest.raises(ScimConflict):
        await create_group(_body(), store, client)


@pytest.mark.asyncio
async def test_happy_path_with_members():
    store = AsyncMock()
    store.get_by_scim.return_value = {"target_id": "101"}
    store.acquire_lock.return_value = True
    client = AsyncMock()
    client.create_group.return_value = _brivo_group()

    group, scim_id = await create_group(
        _body(members=[_member("scim-u1")]), store, client
    )

    assert group.id == 99
    assert len(scim_id) == 36
    store.set_idmap.assert_called_once_with("group", scim_id, "99", "ext-g1")
    store.release_lock.assert_called_once_with("group", "ext-g1")
    client.add_user_to_group.assert_called_once_with(99, 101)
    store.cache_del.assert_called_once_with("group", "99", "members")


@pytest.mark.asyncio
async def test_happy_path_empty_members_skips_add():
    store = AsyncMock()
    store.acquire_lock.return_value = True
    client = AsyncMock()
    client.create_group.return_value = _brivo_group()

    group, scim_id = await create_group(_body(), store, client)

    assert group.id == 99
    client.add_user_to_group.assert_not_called()
    store.cache_del.assert_not_called()


@pytest.mark.asyncio
async def test_brivo_create_fails_releases_lock():
    store = AsyncMock()
    store.acquire_lock.return_value = True
    client = AsyncMock()
    client.create_group.side_effect = RuntimeError("brivo down")

    with pytest.raises(SagaError):
        await create_group(_body(), store, client)

    store.release_lock.assert_called_once_with("group", "ext-g1")


@pytest.mark.asyncio
async def test_idmap_write_fails_deletes_group_and_releases_lock():
    store = AsyncMock()
    store.acquire_lock.return_value = True
    store.set_idmap.side_effect = RuntimeError("redis down")
    client = AsyncMock()
    client.create_group.return_value = _brivo_group()

    with pytest.raises(SagaError):
        await create_group(_body(), store, client)

    client.delete_group.assert_called_once_with(99)
    store.release_lock.assert_called_once_with("group", "ext-g1")


@pytest.mark.asyncio
async def test_member_add_fails_removes_added_in_reverse():
    store = AsyncMock()
    store.get_by_scim.side_effect = [{"target_id": "101"}, {"target_id": "102"}]
    store.acquire_lock.return_value = True
    client = AsyncMock()
    client.create_group.return_value = _brivo_group()
    client.add_user_to_group.side_effect = [None, RuntimeError("brivo down")]

    with pytest.raises(SagaError):
        await create_group(
            _body(members=[_member("scim-u1"), _member("scim-u2")]), store, client
        )

    client.remove_user_from_group.assert_called_once_with(99, 101)
    store.cache_del.assert_called()
