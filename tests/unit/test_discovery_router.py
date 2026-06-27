import pytest
from httpx import AsyncClient, ASGITransport


@pytest.fixture
async def ac():
    from main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


async def test_service_provider_config_no_auth(ac):
    r = await ac.get("/scim/v2/ServiceProviderConfig")

    assert r.status_code == 200
    data = r.json()
    assert data["patch"]["supported"] is True
    assert data["filter"]["supported"] is True
    assert data["etag"]["supported"] is True
    assert data["bulk"]["supported"] is False
    assert data["changePassword"]["supported"] is False
    assert "urn:ietf:params:scim:schemas:core:2.0:ServiceProviderConfig" in data["schemas"]


async def test_resource_types_no_auth(ac):
    r = await ac.get("/scim/v2/ResourceTypes")

    assert r.status_code == 200
    data = r.json()
    assert data["totalResults"] == 2
    ids = {rt["id"] for rt in data["Resources"]}
    assert ids == {"User", "Group"}


async def test_schemas_no_auth(ac):
    r = await ac.get("/scim/v2/Schemas")

    assert r.status_code == 200
    data = r.json()
    assert data["totalResults"] == 2
    schema_ids = {s["id"] for s in data["Resources"]}
    assert "urn:ietf:params:scim:schemas:core:2.0:User" in schema_ids
    assert "urn:ietf:params:scim:schemas:core:2.0:Group" in schema_ids
    user_schema = next(s for s in data["Resources"] if s["id"].endswith(":User"))
    assert len(user_schema["attributes"]) > 0
