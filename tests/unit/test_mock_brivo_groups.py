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


async def _create_group(client, name="Engineering", **kwargs):
    r = await client.post(
        "/v1/api/groups", json={"name": name, **kwargs}, headers=HEADERS
    )
    return r.json()


async def _create_user(client, first="Jane", last="Smith"):
    r = await client.post(
        "/v1/api/users", json={"firstName": first, "lastName": last}, headers=HEADERS
    )
    return r.json()


@pytest.mark.asyncio
async def test_create_group_returns_200_with_full_body():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        r = await c.post(
            "/v1/api/groups", json={"name": "Engineering"}, headers=HEADERS
        )
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == 1
    assert data["name"] == "Engineering"
    assert "keypadUnlock" in data
    assert "immuneToAntipassback" in data
    assert "antipassbackResetTime" in data


@pytest.mark.asyncio
async def test_create_group_name_too_long_returns_400():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        r = await c.post("/v1/api/groups", json={"name": "A" * 36}, headers=HEADERS)
    assert r.status_code == 400
    assert r.json()["code"] == 400


@pytest.mark.asyncio
async def test_create_group_name_exactly_35_chars_allowed():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        r = await c.post("/v1/api/groups", json={"name": "A" * 35}, headers=HEADERS)
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_get_group():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        created = await _create_group(c)
        r = await c.get(f"/v1/api/groups/{created['id']}", headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["id"] == created["id"]


@pytest.mark.asyncio
async def test_get_group_not_found():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        r = await c.get("/v1/api/groups/999", headers=HEADERS)
    assert r.status_code == 404
    assert r.json()["code"] == 404


@pytest.mark.asyncio
async def test_update_group_replaces_fields():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        created = await _create_group(c, name="Old Name")
        r = await c.put(
            f"/v1/api/groups/{created['id']}",
            json={"name": "New Name", "keypadUnlock": True},
            headers=HEADERS,
        )
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "New Name"
    assert data["keypadUnlock"] is True


@pytest.mark.asyncio
async def test_update_group_name_too_long_returns_400():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        created = await _create_group(c)
        r = await c.put(
            f"/v1/api/groups/{created['id']}",
            json={"name": "B" * 36},
            headers=HEADERS,
        )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_update_group_not_found():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        r = await c.put("/v1/api/groups/999", json={"name": "X"}, headers=HEADERS)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_delete_group_returns_204():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        created = await _create_group(c)
        r = await c.delete(f"/v1/api/groups/{created['id']}", headers=HEADERS)
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_delete_group_not_found():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        r = await c.delete("/v1/api/groups/999", headers=HEADERS)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_delete_group_clears_group_members_entry():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        g = await _create_group(c)
        u = await _create_user(c)
        await c.put(f"/v1/api/groups/{g['id']}/users/{u['id']}", headers=HEADERS)
        await c.delete(f"/v1/api/groups/{g['id']}", headers=HEADERS)
    assert g["id"] not in group_members


@pytest.mark.asyncio
async def test_list_group_users_empty():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        g = await _create_group(c)
        r = await c.get(f"/v1/api/groups/{g['id']}/users", headers=HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 0
    assert body["data"] == []


@pytest.mark.asyncio
async def test_list_group_users_returns_members():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        g = await _create_group(c)
        u = await _create_user(c)
        await c.put(f"/v1/api/groups/{g['id']}/users/{u['id']}", headers=HEADERS)
        r = await c.get(f"/v1/api/groups/{g['id']}/users", headers=HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 1
    assert body["data"][0]["id"] == u["id"]


@pytest.mark.asyncio
async def test_list_group_users_not_found():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        r = await c.get("/v1/api/groups/999/users", headers=HEADERS)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_add_user_to_group_returns_204():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        g = await _create_group(c)
        u = await _create_user(c)
        r = await c.put(f"/v1/api/groups/{g['id']}/users/{u['id']}", headers=HEADERS)
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_add_user_to_group_group_not_found():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        u = await _create_user(c)
        r = await c.put(f"/v1/api/groups/999/users/{u['id']}", headers=HEADERS)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_add_user_to_group_user_not_found():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        g = await _create_group(c)
        r = await c.put(f"/v1/api/groups/{g['id']}/users/999", headers=HEADERS)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_remove_user_from_group_returns_204():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        g = await _create_group(c)
        u = await _create_user(c)
        await c.put(f"/v1/api/groups/{g['id']}/users/{u['id']}", headers=HEADERS)
        r = await c.delete(f"/v1/api/groups/{g['id']}/users/{u['id']}", headers=HEADERS)
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_remove_user_from_group_group_not_found():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        u = await _create_user(c)
        r = await c.delete(f"/v1/api/groups/999/users/{u['id']}", headers=HEADERS)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_remove_user_from_group_user_not_found():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        g = await _create_group(c)
        r = await c.delete(f"/v1/api/groups/{g['id']}/users/999", headers=HEADERS)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_create_group_no_api_key_returns_403():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        r = await c.post("/v1/api/groups", json={"name": "Eng"})
    assert r.status_code == 403
