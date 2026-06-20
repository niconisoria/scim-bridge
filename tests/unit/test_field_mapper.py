import pytest

from app.models.brivo import BrivoGroupWrite, BrivoUserWrite
from app.models.group import ScimGroup
from app.models.user import ScimEmail, ScimName, ScimPhone, ScimUser
from app.services.field_mapper import scim_group_to_brivo, scim_user_to_brivo


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
