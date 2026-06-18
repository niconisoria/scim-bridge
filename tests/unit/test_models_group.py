import pytest
from pydantic import ValidationError

from app.models.group import ScimGroup, ScimGroupResponse
from app.models.user import ScimMeta

_GROUP_URN = "urn:ietf:params:scim:schemas:core:2.0:Group"


def test_parse_minimal_body():
    g = ScimGroup.model_validate({"displayName": "Engineering"})
    assert g.displayName == "Engineering"
    assert g.members == []


def test_unknown_fields_dropped():
    g = ScimGroup.model_validate(
        {"displayName": "Eng", "foo": "bar", "password": "secret"}
    )
    assert not hasattr(g, "foo")


def test_display_name_max_35():
    with pytest.raises(ValidationError):
        ScimGroup.model_validate({"displayName": "x" * 36})


def test_display_name_exactly_35_ok():
    g = ScimGroup.model_validate({"displayName": "x" * 35})
    assert len(g.displayName) == 35


def test_members_default_empty():
    g = ScimGroup.model_validate({"displayName": "Eng"})
    assert g.members == []


def test_members_parsed():
    g = ScimGroup.model_validate(
        {
            "displayName": "Eng",
            "members": [{"value": "scim-uuid-1", "display": "john@example.com"}],
        }
    )
    assert len(g.members) == 1
    assert g.members[0].value == "scim-uuid-1"
    assert g.members[0].display == "john@example.com"


def test_member_display_optional():
    g = ScimGroup.model_validate(
        {"displayName": "Eng", "members": [{"value": "scim-uuid-1"}]}
    )
    assert g.members[0].display is None


def test_external_id_optional():
    g = ScimGroup.model_validate({"displayName": "Eng"})
    assert g.externalId is None
    g2 = ScimGroup.model_validate({"displayName": "Eng", "externalId": "okta-abc"})
    assert g2.externalId == "okta-abc"


def test_schemas_default():
    g = ScimGroup.model_validate({"displayName": "Eng"})
    assert g.schemas == [_GROUP_URN]


def test_response_requires_id_and_meta():
    with pytest.raises(ValidationError):
        ScimGroupResponse.model_validate({"displayName": "Eng"})


def test_response_valid():
    meta = ScimMeta(resourceType="Group", location="/scim/v2/Groups/uuid1")
    r = ScimGroupResponse.model_validate(
        {
            "id": "uuid1",
            "displayName": "Eng",
            "meta": meta.model_dump(),
        }
    )
    assert r.id == "uuid1"
    assert r.meta.resourceType == "Group"


def test_members_always_serialized():
    g = ScimGroup.model_validate({"displayName": "Eng"})
    d = g.model_dump()
    assert "members" in d
    assert d["members"] == []


def test_serialize_with_members():
    g = ScimGroup.model_validate(
        {
            "displayName": "Eng",
            "members": [{"value": "scim-uuid-1", "display": "john@example.com"}],
        }
    )
    d = g.model_dump()
    assert d["members"][0]["value"] == "scim-uuid-1"
