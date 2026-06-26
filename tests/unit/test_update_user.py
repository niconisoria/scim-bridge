from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from app.models.brivo import BrivoEmail, BrivoUser
from app.models.common import PatchOp
from app.models.user import ScimEmail, ScimName, ScimUser
from app.services.update_user import update_user


def _brivo_user(
    external_id: str | None = "ext-123",
    first: str = "John",
    last: str = "Doe",
    email: str = "john@example.com",
    suspended: bool = False,
) -> BrivoUser:
    return BrivoUser(
        id=99,
        externalId=external_id,
        firstName=first,
        lastName=last,
        emails=[BrivoEmail(address=email, type="work")],
        phoneNumbers=[],
        suspended=suspended,
        created=datetime.now(timezone.utc),
        updated=datetime.now(timezone.utc),
    )


def _scim_user(
    first: str = "Jane",
    last: str = "Smith",
    email: str = "jane@example.com",
    active: bool = True,
) -> ScimUser:
    return ScimUser(
        userName=email,
        name=ScimName(givenName=first, familyName=last),
        emails=[ScimEmail(value=email, primary=True)],
        active=active,
    )


def _patch(path: str | None, value: object) -> PatchOp:
    return PatchOp(op="replace", path=path, value=value)


@pytest.mark.asyncio
async def test_cache_miss_calls_get_user():
    store = AsyncMock()
    store.cache_get.return_value = None
    client = AsyncMock()
    current = _brivo_user()
    client.get_user.return_value = current
    client.update_user.return_value = current

    await update_user(99, _scim_user(), None, store, client)

    client.get_user.assert_called_once_with(99)


@pytest.mark.asyncio
async def test_cache_hit_skips_get_user():
    current = _brivo_user()
    store = AsyncMock()
    store.cache_get.return_value = current.model_dump(mode="json")
    client = AsyncMock()
    client.update_user.return_value = current

    await update_user(99, _scim_user(), None, store, client)

    client.get_user.assert_not_called()


@pytest.mark.asyncio
async def test_put_calls_update_user_with_mapped_fields():
    store = AsyncMock()
    store.cache_get.return_value = None
    current = _brivo_user()
    client = AsyncMock()
    client.get_user.return_value = current
    client.update_user.return_value = current

    await update_user(99, _scim_user(first="Jane", last="Smith"), None, store, client)

    write = client.update_user.call_args.args[1]
    assert write.firstName == "Jane"
    assert write.lastName == "Smith"


@pytest.mark.asyncio
async def test_put_preserves_external_id_from_current():
    store = AsyncMock()
    store.cache_get.return_value = None
    current = _brivo_user(external_id="okta-abc")
    client = AsyncMock()
    client.get_user.return_value = current
    client.update_user.return_value = current

    await update_user(99, _scim_user(), None, store, client)

    write = client.update_user.call_args.args[1]
    assert write.externalId == "okta-abc"


@pytest.mark.asyncio
async def test_patch_active_false_sets_suspended():
    store = AsyncMock()
    store.cache_get.return_value = None
    current = _brivo_user(suspended=False)
    client = AsyncMock()
    client.get_user.return_value = current
    client.update_user.return_value = current

    await update_user(99, None, [_patch("active", False)], store, client)

    write = client.update_user.call_args.args[1]
    assert write.suspended is True


@pytest.mark.asyncio
async def test_patch_active_true_clears_suspended():
    store = AsyncMock()
    store.cache_get.return_value = None
    current = _brivo_user(suspended=True)
    client = AsyncMock()
    client.get_user.return_value = current
    client.update_user.return_value = current

    await update_user(99, None, [_patch("active", True)], store, client)

    write = client.update_user.call_args.args[1]
    assert write.suspended is False


@pytest.mark.asyncio
async def test_patch_given_name_updates_first_name():
    store = AsyncMock()
    store.cache_get.return_value = None
    current = _brivo_user(first="Old")
    client = AsyncMock()
    client.get_user.return_value = current
    client.update_user.return_value = current

    await update_user(99, None, [_patch("name.givenName", "New")], store, client)

    write = client.update_user.call_args.args[1]
    assert write.firstName == "New"


@pytest.mark.asyncio
async def test_patch_family_name_updates_last_name():
    store = AsyncMock()
    store.cache_get.return_value = None
    current = _brivo_user(last="Old")
    client = AsyncMock()
    client.get_user.return_value = current
    client.update_user.return_value = current

    await update_user(99, None, [_patch("name.familyName", "New")], store, client)

    write = client.update_user.call_args.args[1]
    assert write.lastName == "New"


@pytest.mark.asyncio
async def test_patch_user_name_updates_email():
    store = AsyncMock()
    store.cache_get.return_value = None
    current = _brivo_user(email="old@example.com")
    client = AsyncMock()
    client.get_user.return_value = current
    client.update_user.return_value = current

    await update_user(99, None, [_patch("userName", "new@example.com")], store, client)

    write = client.update_user.call_args.args[1]
    assert write.emails[0].address == "new@example.com"


@pytest.mark.asyncio
async def test_patch_unknown_path_ignored():
    store = AsyncMock()
    store.cache_get.return_value = None
    current = _brivo_user(first="John")
    client = AsyncMock()
    client.get_user.return_value = current
    client.update_user.return_value = current

    await update_user(99, None, [_patch("locale", "en-US")], store, client)

    write = client.update_user.call_args.args[1]
    assert write.firstName == "John"  # unchanged


@pytest.mark.asyncio
async def test_cache_invalidated_after_update():
    store = AsyncMock()
    store.cache_get.return_value = None
    current = _brivo_user()
    client = AsyncMock()
    client.get_user.return_value = current
    client.update_user.return_value = current

    await update_user(99, _scim_user(), None, store, client)

    store.cache_del.assert_called_once_with("user", "99")


@pytest.mark.asyncio
async def test_brivo_error_propagates():
    store = AsyncMock()
    store.cache_get.return_value = None
    current = _brivo_user()
    client = AsyncMock()
    client.get_user.return_value = current
    client.update_user.side_effect = RuntimeError("brivo down")

    with pytest.raises(RuntimeError, match="brivo down"):
        await update_user(99, _scim_user(), None, store, client)

    store.cache_del.assert_not_called()
