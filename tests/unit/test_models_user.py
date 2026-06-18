import pytest
from pydantic import ValidationError

from app.models.user import ScimMeta, ScimUser, ScimUserResponse

_URN = "urn:ietf:params:scim:schemas:core:2.0:User"
_BASE = {"userName": "john@example.com", "emails": [{"value": "john@example.com", "primary": True}]}


def test_extra_fields_ignored():
    user = ScimUser(**_BASE, password="secret", displayName="John", locale="en", groups=[])
    assert not hasattr(user, "password")
    assert not hasattr(user, "displayName")


def test_emails_min_one_required():
    with pytest.raises(ValidationError):
        ScimUser(userName="john@example.com", emails=[])


def test_phone_optional_absent_by_default():
    assert ScimUser(**_BASE).phoneNumbers is None


def test_active_defaults_true():
    assert ScimUser(**_BASE).active is True


def test_external_id_optional():
    assert ScimUser(**_BASE).externalId is None


def test_name_fields_optional():
    user = ScimUser(**_BASE, name={"givenName": "John"})
    assert user.name.givenName == "John"
    assert user.name.familyName is None


def test_meta_all_fields_optional():
    meta = ScimMeta()
    assert meta.resourceType is None
    assert meta.lastModified is None
    assert meta.version is None


def test_response_requires_id_and_meta():
    with pytest.raises(ValidationError):
        ScimUserResponse(**_BASE)


def test_schemas_default_is_scim_urn():
    assert ScimUser(**_BASE).schemas == [_URN]


def test_username_required():
    with pytest.raises(ValidationError):
        ScimUser(emails=[{"value": "x@x.com"}])


def test_camelcase_field_names_in_dump():
    user = ScimUser(**_BASE, name={"givenName": "John", "familyName": "Doe"})
    data = user.model_dump(exclude_none=True)
    assert "userName" in data
    assert "givenName" in data["name"]
    assert "familyName" in data["name"]
