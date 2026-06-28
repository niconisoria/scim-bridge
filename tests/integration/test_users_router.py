from datetime import datetime, timezone

import fakeredis.aioredis
import httpx
import pytest
import respx

from app.brivo.client import BrivoClient
from app.brivo.dependencies import get_client
from aiolimiter import AsyncLimiter
from app.redis.store import RedisStore, get_store

AUTH = {"Authorization": "Bearer test-token"}
BRIVO = "http://test-brivo"
NOW = datetime(2024, 1, 1, tzinfo=timezone.utc).isoformat()
SCIM_ERROR_SCHEMA = "urn:ietf:params:scim:api:messages:2.0:Error"


def _user_json(uid: int = 1, email: str = "jane@example.com") -> dict:
    return {
        "id": uid,
        "externalId": "ext-123",
        "firstName": "Jane",
        "lastName": "Doe",
        "emails": [{"address": email, "type": "work"}],
        "phoneNumbers": [],
        "suspended": False,
        "created": NOW,
        "updated": NOW,
    }


def _page(users: list[dict], count: int | None = None) -> dict:
    return {
        "data": users,
        "offset": 0,
        "pageSize": 100,
        "count": count if count is not None else len(users),
    }


@pytest.fixture
def fake_redis():
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


@pytest.fixture
def store(fake_redis):
    return RedisStore(fake_redis)


@pytest.fixture
def brivo_mock():
    with respx.mock(assert_all_called=False) as mock:
        yield mock


@pytest.fixture
def brivo_client(brivo_mock):
    http = httpx.AsyncClient(base_url=BRIVO, headers={"api-key": "test"})
    return BrivoClient(http, AsyncLimiter(max_rate=1000, time_period=1))


@pytest.fixture
async def ac(store, brivo_client):
    from main import app

    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_client] = lambda: brivo_client
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client
    app.dependency_overrides.clear()


# --- POST /scim/v2/Users ---


async def test_post_user_happy_path(ac, brivo_mock):
    brivo_mock.post(f"{BRIVO}/v1/api/users").mock(
        return_value=httpx.Response(201, json=_user_json())
    )
    body = {
        "userName": "jane@example.com",
        "name": {"givenName": "Jane", "familyName": "Doe"},
        "emails": [{"value": "jane@example.com", "type": "work", "primary": True}],
        "externalId": "ext-123",
    }
    r = await ac.post("/scim/v2/Users", json=body, headers=AUTH)

    assert r.status_code == 201
    assert "Location" in r.headers
    assert r.headers["Location"].startswith("/scim/v2/Users/")
    data = r.json()
    assert data["userName"] == "jane@example.com"
    assert "id" in data
    assert data["active"] is True


async def test_post_user_conflict(ac, store):
    await store._r.set("lock:brivo:create:user:ext-123", "other", nx=True, ex=300)
    body = {
        "userName": "jane@example.com",
        "emails": [{"value": "jane@example.com", "primary": True}],
        "externalId": "ext-123",
    }
    r = await ac.post("/scim/v2/Users", json=body, headers=AUTH)

    assert r.status_code == 409
    assert SCIM_ERROR_SCHEMA in r.json()["schemas"]


async def test_post_user_no_external_id_uses_username(ac, brivo_mock):
    brivo_mock.post(f"{BRIVO}/v1/api/users").mock(
        return_value=httpx.Response(201, json=_user_json())
    )
    body = {
        "userName": "jane@example.com",
        "emails": [{"value": "jane@example.com", "primary": True}],
    }
    r = await ac.post("/scim/v2/Users", json=body, headers=AUTH)

    assert r.status_code == 201
    assert r.json()["userName"] == "jane@example.com"


# --- GET /scim/v2/Users/{id} ---


async def test_get_user_cache_miss(ac, brivo_mock, store):
    await store.set_idmap("user", "scim-abc", "1", "ext-123")
    brivo_mock.get(f"{BRIVO}/v1/api/users/1").mock(
        return_value=httpx.Response(200, json=_user_json())
    )

    r = await ac.get("/scim/v2/Users/scim-abc", headers=AUTH)

    assert r.status_code == 200
    data = r.json()
    assert data["id"] == "scim-abc"
    assert data["userName"] == "jane@example.com"
    cached = await store.cache_get("user", "1")
    assert cached is not None


async def test_get_user_not_found(ac):
    r = await ac.get("/scim/v2/Users/no-such-id", headers=AUTH)

    assert r.status_code == 404
    assert SCIM_ERROR_SCHEMA in r.json()["schemas"]


# --- PUT /scim/v2/Users/{id} ---


async def test_put_user_happy_path(ac, brivo_mock, store):
    await store.set_idmap("user", "scim-abc", "1", "ext-123")
    brivo_mock.get(f"{BRIVO}/v1/api/users/1").mock(
        return_value=httpx.Response(200, json=_user_json())
    )
    brivo_mock.put(f"{BRIVO}/v1/api/users/1").mock(
        return_value=httpx.Response(200, json=_user_json())
    )
    body = {
        "userName": "jane@example.com",
        "name": {"givenName": "Jane", "familyName": "Doe"},
        "emails": [{"value": "jane@example.com", "primary": True}],
    }

    r = await ac.put("/scim/v2/Users/scim-abc", json=body, headers=AUTH)

    assert r.status_code == 200
    assert r.json()["id"] == "scim-abc"


async def test_put_user_not_found(ac):
    body = {
        "userName": "jane@example.com",
        "emails": [{"value": "jane@example.com", "primary": True}],
    }
    r = await ac.put("/scim/v2/Users/no-such-id", json=body, headers=AUTH)

    assert r.status_code == 404
    assert SCIM_ERROR_SCHEMA in r.json()["schemas"]


# --- PATCH /scim/v2/Users/{id} ---


async def test_patch_user_happy_path(ac, brivo_mock, store):
    await store.set_idmap("user", "scim-abc", "1", "ext-123")
    brivo_mock.get(f"{BRIVO}/v1/api/users/1").mock(
        return_value=httpx.Response(200, json=_user_json())
    )
    brivo_mock.put(f"{BRIVO}/v1/api/users/1").mock(
        return_value=httpx.Response(200, json=_user_json())
    )
    body = {
        "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
        "Operations": [{"op": "replace", "path": "active", "value": False}],
    }

    r = await ac.patch("/scim/v2/Users/scim-abc", json=body, headers=AUTH)

    assert r.status_code == 200
    assert r.json()["id"] == "scim-abc"


async def test_patch_user_not_found(ac):
    body = {
        "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
        "Operations": [{"op": "replace", "path": "active", "value": False}],
    }
    r = await ac.patch("/scim/v2/Users/no-such-id", json=body, headers=AUTH)

    assert r.status_code == 404
    assert SCIM_ERROR_SCHEMA in r.json()["schemas"]


# --- DELETE /scim/v2/Users/{id} ---


async def test_delete_user_happy_path(ac, brivo_mock, store):
    await store.set_idmap("user", "scim-abc", "1", "ext-123")
    brivo_mock.get(f"{BRIVO}/v1/api/users/1/groups").mock(
        return_value=httpx.Response(200, json={"count": 0, "data": []})
    )
    brivo_mock.get(f"{BRIVO}/v1/api/users/1").mock(
        return_value=httpx.Response(200, json=_user_json())
    )
    brivo_mock.delete(f"{BRIVO}/v1/api/users/1").mock(return_value=httpx.Response(204))

    r = await ac.delete("/scim/v2/Users/scim-abc", headers=AUTH)

    assert r.status_code == 204
    assert r.content == b""


# --- GET /scim/v2/Users (list) ---


async def test_list_users_no_filter(ac, brivo_mock, store):
    await store.set_idmap("user", "scim-abc", "1", "ext-123")
    brivo_mock.get(f"{BRIVO}/v1/api/users").mock(
        return_value=httpx.Response(200, json=_page([_user_json()]))
    )

    r = await ac.get("/scim/v2/Users", headers=AUTH)

    assert r.status_code == 200
    data = r.json()
    assert data["totalResults"] == 1
    assert data["itemsPerPage"] == 1
    assert data["Resources"][0]["id"] == "scim-abc"


async def test_list_users_filter_match(ac, brivo_mock, store):
    await store.set_idmap("user", "scim-abc", "1", "ext-123")
    brivo_mock.get(f"{BRIVO}/v1/api/users").mock(
        return_value=httpx.Response(200, json=_page([_user_json()]))
    )

    r = await ac.get(
        '/scim/v2/Users?filter=userName eq "jane@example.com"', headers=AUTH
    )

    assert r.status_code == 200
    data = r.json()
    assert data["totalResults"] == 1
    assert data["Resources"][0]["id"] == "scim-abc"


async def test_list_users_filter_no_match(ac, brivo_mock):
    brivo_mock.get(f"{BRIVO}/v1/api/users").mock(
        return_value=httpx.Response(200, json=_page([_user_json()]))
    )

    r = await ac.get(
        '/scim/v2/Users?filter=userName eq "nobody@example.com"', headers=AUTH
    )

    assert r.status_code == 200
    data = r.json()
    assert data["totalResults"] == 0
    assert data["Resources"] == []
