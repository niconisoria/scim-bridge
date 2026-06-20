import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from app.models.brivo import (
    BrivoEmail,
    BrivoPhoneNumber,
    BrivoUser,
    BrivoUserWrite,
    BrivoGroup,
    BrivoGroupWrite,
    BrivoGroupRef,
    BrivoPaginatedList,
)

NOW = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
NOW_STR = "2024-01-01T12:00:00+00:00"


def test_brivo_email_fields():
    e = BrivoEmail(address="a@b.com", type="work")
    assert e.address == "a@b.com"
    assert e.type == "work"


def test_brivo_phone_fields():
    p = BrivoPhoneNumber(number="+1234567890", type="mobile")
    assert p.number == "+1234567890"
    assert p.type == "mobile"


def test_brivo_user_read():
    u = BrivoUser(
        id=42,
        firstName="Jane",
        lastName="Doe",
        emails=[{"address": "jane@example.com", "type": "work"}],
        phoneNumbers=[],
        suspended=False,
        created=NOW_STR,
        updated=NOW_STR,
    )
    assert u.id == 42
    assert u.firstName == "Jane"
    assert u.externalId is None
    assert isinstance(u.created, datetime)


def test_brivo_user_external_id_optional():
    u = BrivoUser(
        id=1,
        firstName="A",
        lastName="B",
        emails=[{"address": "a@b.com", "type": "work"}],
        phoneNumbers=[],
        suspended=False,
        created=NOW_STR,
        updated=NOW_STR,
        externalId="ext-123",
    )
    assert u.externalId == "ext-123"


def test_brivo_user_write_omits_readonly_fields():
    w = BrivoUserWrite(
        firstName="Jane",
        lastName="Doe",
        emails=[{"address": "jane@example.com", "type": "work"}],
        phoneNumbers=[],
        suspended=False,
    )
    assert not hasattr(w, "id") or not w.model_fields.get("id")
    data = w.model_dump()
    assert "id" not in data
    assert "created" not in data
    assert "updated" not in data


def test_brivo_group_read():
    g = BrivoGroup(
        id=10,
        name="Employees",
        keypadUnlock=True,
        immuneToAntipassback=False,
        antipassbackResetTime=0,
    )
    assert g.id == 10
    assert g.name == "Employees"


def test_brivo_group_name_max_35_chars():
    with pytest.raises(ValidationError):
        BrivoGroup(
            id=1,
            name="A" * 36,
            keypadUnlock=False,
            immuneToAntipassback=False,
            antipassbackResetTime=0,
        )


def test_brivo_group_write_omits_id():
    w = BrivoGroupWrite(
        name="Staff",
        keypadUnlock=False,
        immuneToAntipassback=False,
        antipassbackResetTime=0,
    )
    data = w.model_dump()
    assert "id" not in data


def test_brivo_group_ref():
    ref = BrivoGroupRef(id=5, name="Lobby")
    assert ref.id == 5
    assert ref.name == "Lobby"


def test_brivo_paginated_list():
    pl = BrivoPaginatedList[BrivoGroupRef](
        data=[{"id": 1, "name": "A"}],
        offset=0,
        pageSize=10,
        count=1,
    )
    assert pl.count == 1
    assert pl.data[0].name == "A"


def test_brivo_paginated_list_empty():
    pl = BrivoPaginatedList[BrivoGroupRef](data=[], offset=0, pageSize=10, count=0)
    assert pl.data == []


def test_round_trip_user_json():
    payload = {
        "id": 7,
        "firstName": "John",
        "lastName": "Smith",
        "emails": [{"address": "john@acme.com", "type": "work"}],
        "phoneNumbers": [{"number": "555-0100", "type": "work"}],
        "suspended": False,
        "created": NOW_STR,
        "updated": NOW_STR,
    }
    u = BrivoUser.model_validate(payload)
    assert u.id == 7
    assert u.emails[0].address == "john@acme.com"
