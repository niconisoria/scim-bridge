import pytest
from httpx import AsyncClient, ASGITransport
from mock_brivo.main import app, users, groups, group_members, _counters

HEADERS = {"api-key": "test-key"}


@pytest.fixture(autouse=True)
def reset_store():
    users.clear()
    groups.clear()
    group_members.clear()
    _counters["users"] = 0
    _counters["groups"] = 0
    yield


@pytest.mark.asyncio
async def test_create_user_returns_200_with_full_body():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.post(
            "/v1/api/users",
            json={"firstName": "Jane", "lastName": "Smith"},
            headers=HEADERS,
        )
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == 1
    assert data["firstName"] == "Jane"
    assert data["lastName"] == "Smith"
    assert "externalId" in data
    assert "created" in data
    assert "updated" in data


@pytest.mark.asyncio
async def test_create_user_with_external_id():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.post(
            "/v1/api/users",
            json={"firstName": "Jane", "lastName": "Smith", "externalId": "ext-123"},
            headers=HEADERS,
        )
    assert r.status_code == 200
    assert r.json()["externalId"] == "ext-123"


@pytest.mark.asyncio
async def test_get_user():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        created = (
            await client.post(
                "/v1/api/users",
                json={"firstName": "A", "lastName": "B"},
                headers=HEADERS,
            )
        ).json()
        r = await client.get(f"/v1/api/users/{created['id']}", headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["id"] == created["id"]


@pytest.mark.asyncio
async def test_get_user_not_found():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.get("/v1/api/users/999", headers=HEADERS)
    assert r.status_code == 404
    assert r.json()["code"] == 404


@pytest.mark.asyncio
async def test_update_user_replaces_fields():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        created = (
            await client.post(
                "/v1/api/users",
                json={"firstName": "Old", "lastName": "Name"},
                headers=HEADERS,
            )
        ).json()
        r = await client.put(
            f"/v1/api/users/{created['id']}",
            json={"firstName": "New", "lastName": "Name"},
            headers=HEADERS,
        )
    assert r.status_code == 200
    assert r.json()["firstName"] == "New"


@pytest.mark.asyncio
async def test_update_user_bumps_updated_timestamp():
    import asyncio

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        created = (
            await client.post(
                "/v1/api/users",
                json={"firstName": "Old", "lastName": "Name"},
                headers=HEADERS,
            )
        ).json()
        await asyncio.sleep(0.01)
        r = await client.put(
            f"/v1/api/users/{created['id']}",
            json={"firstName": "New", "lastName": "Name"},
            headers=HEADERS,
        )
    assert r.json()["updated"] > created["updated"]


@pytest.mark.asyncio
async def test_update_user_not_found():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.put(
            "/v1/api/users/999",
            json={"firstName": "X", "lastName": "Y"},
            headers=HEADERS,
        )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_delete_user_returns_204():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        created = (
            await client.post(
                "/v1/api/users",
                json={"firstName": "Del", "lastName": "Me"},
                headers=HEADERS,
            )
        ).json()
        r = await client.delete(f"/v1/api/users/{created['id']}", headers=HEADERS)
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_delete_user_not_found():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.delete("/v1/api/users/999", headers=HEADERS)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_delete_user_removes_from_store():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        created = (
            await client.post(
                "/v1/api/users",
                json={"firstName": "Del", "lastName": "Me"},
                headers=HEADERS,
            )
        ).json()
        await client.delete(f"/v1/api/users/{created['id']}", headers=HEADERS)
        r = await client.get(f"/v1/api/users/{created['id']}", headers=HEADERS)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_list_user_groups_empty():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        created = (
            await client.post(
                "/v1/api/users",
                json={"firstName": "A", "lastName": "B"},
                headers=HEADERS,
            )
        ).json()
        r = await client.get(f"/v1/api/users/{created['id']}/groups", headers=HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 0
    assert body["data"] == []


@pytest.mark.asyncio
async def test_list_user_groups_not_found():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.get("/v1/api/users/999/groups", headers=HEADERS)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_create_user_no_api_key_returns_403():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.post("/v1/api/users", json={"firstName": "X", "lastName": "Y"})
    assert r.status_code == 403
