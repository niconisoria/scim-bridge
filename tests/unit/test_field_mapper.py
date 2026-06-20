from datetime import datetime, timezone

import fakeredis.aioredis
import pytest

from app.models.brivo import (
    BrivoEmail,
    BrivoGroup,
    BrivoGroupWrite,
    BrivoPhoneNumber,
    BrivoUser,
    BrivoUserWrite,
)
from app.models.group import ScimGroup, ScimMember
from app.models.user import ScimEmail, ScimName, ScimPhone, ScimUser
from app.redis.store import RedisStore
from app.services.field_mapper import (
    brivo_group_to_scim,
    brivo_user_to_scim,
    hydrate_members,
    scim_group_to_brivo,
    scim_user_to_brivo,
)

_NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def _brivo_user(**kwargs) -> BrivoUser:
    defaults: dict = {
        "id": 42,
        "firstName": "Jane",
        "lastName": "Smith",
        "emails": [BrivoEmail(address="jane@example.com", type="work")],
        "phoneNumbers": [BrivoPhoneNumber(number="+15559876543", type="work")],
        "suspended": False,
        "created": _NOW,
        "updated": _NOW,
    }
    return BrivoUser(**(defaults | kwargs))


def _brivo_group(**kwargs) -> BrivoGroup:
    defaults: dict = {
        "id": 1,
        "name": "Engineering",
        "keypadUnlock": False,
        "immuneToAntipassback": False,
        "antipassbackResetTime": 0,
    }
    return BrivoGroup(**(defaults | kwargs))


def _user(**kwargs) -> ScimUser:
    defaults = {
        "userName": "john@example.com",
        "name": ScimName(givenName="John", familyName="Doe"),
        "emails": [ScimEmail(value="john@example.com", primary=True)],
        "active": True,
    }
    return ScimUser(**(defaults | kwargs))


def test_user_name_fields_mapped():
    result = scim_user_to_brivo(_user())
    assert result.firstName == "John"
    assert result.lastName == "Doe"


def test_active_true_maps_to_suspended_false():
    result = scim_user_to_brivo(_user(active=True))
    assert result.suspended is False


def test_active_false_maps_to_suspended_true():
    result = scim_user_to_brivo(_user(active=False))
    assert result.suspended is True


def test_primary_email_used():
    emails = [
        ScimEmail(value="other@example.com", primary=False),
        ScimEmail(value="main@example.com", primary=True),
    ]
    result = scim_user_to_brivo(_user(emails=emails))
    assert result.emails[0].address == "main@example.com"


def test_email_fallback_to_first_when_no_primary():
    emails = [
        ScimEmail(value="first@example.com", primary=False),
        ScimEmail(value="second@example.com", primary=False),
    ]
    result = scim_user_to_brivo(_user(emails=emails))
    assert result.emails[0].address == "first@example.com"


def test_primary_phone_used():
    phones = [
        ScimPhone(value="+10000000000", primary=False),
        ScimPhone(value="+15551234567", primary=True),
    ]
    result = scim_user_to_brivo(_user(phoneNumbers=phones))
    assert result.phoneNumbers[0].number == "+15551234567"


def test_phone_fallback_to_first_when_no_primary():
    phones = [
        ScimPhone(value="+10000000001", primary=False),
        ScimPhone(value="+10000000002", primary=False),
    ]
    result = scim_user_to_brivo(_user(phoneNumbers=phones))
    assert result.phoneNumbers[0].number == "+10000000001"


def test_no_phones_returns_empty_list():
    result = scim_user_to_brivo(_user(phoneNumbers=None))
    assert result.phoneNumbers == []


def test_returns_brivo_user_write():
    assert isinstance(scim_user_to_brivo(_user()), BrivoUserWrite)


def test_group_display_name_mapped():
    group = ScimGroup(displayName="Engineering")
    result = scim_group_to_brivo(group)
    assert result.name == "Engineering"


def test_group_display_name_35_chars_ok():
    group = ScimGroup(displayName="A" * 35)
    result = scim_group_to_brivo(group)
    assert result.name == "A" * 35


def test_group_display_name_over_35_raises():
    group = ScimGroup(displayName="A" * 35)
    group.displayName = "B" * 36  # bypass Pydantic to test mapper guard
    with pytest.raises(ValueError, match="35-character limit"):
        scim_group_to_brivo(group)


def test_group_brivo_defaults_set():
    result = scim_group_to_brivo(ScimGroup(displayName="Test"))
    assert result.keypadUnlock is False
    assert result.immuneToAntipassback is False
    assert result.antipassbackResetTime == 0


def test_returns_brivo_group_write():
    assert isinstance(
        scim_group_to_brivo(ScimGroup(displayName="Test")), BrivoGroupWrite
    )


def test_brivo_user_name_mapped():
    result = brivo_user_to_scim(_brivo_user(), "scim-1", _NOW)
    assert result.name.givenName == "Jane"
    assert result.name.familyName == "Smith"


def test_brivo_suspended_false_maps_to_active_true():
    result = brivo_user_to_scim(_brivo_user(suspended=False), "scim-1", _NOW)
    assert result.active is True


def test_brivo_suspended_true_maps_to_active_false():
    result = brivo_user_to_scim(_brivo_user(suspended=True), "scim-1", _NOW)
    assert result.active is False


def test_brivo_email_mapped_primary():
    result = brivo_user_to_scim(_brivo_user(), "scim-1", _NOW)
    assert result.emails[0].value == "jane@example.com"
    assert result.emails[0].primary is True


def test_brivo_phone_mapped_primary():
    result = brivo_user_to_scim(_brivo_user(), "scim-1", _NOW)
    assert result.phoneNumbers[0].value == "+15559876543"
    assert result.phoneNumbers[0].primary is True


def test_brivo_empty_phones_returns_empty_list():
    result = brivo_user_to_scim(_brivo_user(phoneNumbers=[]), "scim-1", _NOW)
    assert result.phoneNumbers == []


def test_brivo_user_meta_fields():
    result = brivo_user_to_scim(_brivo_user(), "scim-1", _NOW, location="/Users/1")
    assert result.meta.resourceType == "User"
    assert result.meta.created == _NOW.isoformat()
    assert result.meta.lastModified == _NOW.isoformat()
    assert result.meta.location == "/Users/1"
    assert result.meta.version is not None


def test_brivo_user_version_stable():
    user = _brivo_user()
    v1 = brivo_user_to_scim(user, "scim-1", _NOW).meta.version
    v2 = brivo_user_to_scim(user, "scim-1", _NOW).meta.version
    assert v1 == v2


def test_brivo_group_display_name_mapped():
    result = brivo_group_to_scim(_brivo_group(), "scim-g1", [], _NOW)
    assert result.displayName == "Engineering"


def test_brivo_group_members_passed_through():
    members = [ScimMember(value="scim-1", display="Jane Smith")]
    result = brivo_group_to_scim(_brivo_group(), "scim-g1", members, _NOW)
    assert result.members == members


def test_brivo_group_meta_fields():
    result = brivo_group_to_scim(_brivo_group(), "scim-g1", [], _NOW)
    assert result.meta.resourceType == "Group"
    assert result.meta.lastModified is None
    assert result.meta.created == _NOW.isoformat()
    assert result.meta.version is not None


def test_brivo_group_version_stable():
    v1 = brivo_group_to_scim(_brivo_group(), "scim-g1", [], _NOW).meta.version
    v2 = brivo_group_to_scim(_brivo_group(), "scim-g1", [], _NOW).meta.version
    assert v1 == v2


@pytest.fixture
async def store():
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    return RedisStore(client)


async def test_hydrate_members_all_found(store):
    await store.set_idmap("user", "scim-1", "101", "ext-1")
    await store.set_idmap("user", "scim-2", "102", "ext-2")
    result = await hydrate_members([101, 102], store)
    assert [m.value for m in result] == ["scim-1", "scim-2"]


async def test_hydrate_members_some_missing(store):
    await store.set_idmap("user", "scim-1", "101", "ext-1")
    result = await hydrate_members([101, 999], store)
    assert len(result) == 1
    assert result[0].value == "scim-1"


async def test_hydrate_members_empty_input(store):
    result = await hydrate_members([], store)
    assert result == []


async def test_hydrate_members_display_none(store):
    await store.set_idmap("user", "scim-1", "101", "ext-1")
    result = await hydrate_members([101], store)
    assert result[0].display is None
