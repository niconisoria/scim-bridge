from datetime import datetime, timezone

import fakeredis.aioredis
import httpx
import pytest
import respx

from app.brivo.client import BrivoClient
from app.brivo.dependencies import get_client
from app.brivo.rate_limiter import make_limiter
from app.redis.store import RedisStore, get_store

AUTH = {"Authorization": "Bearer test-token"}
BRIVO = "http://test-brivo"
NOW = datetime(2024, 1, 1, tzinfo=timezone.utc).isoformat()
SCIM_ERROR_SCHEMA = "urn:ietf:params:scim:api:messages:2.0:Error"


def _group_json(gid: int = 10, name: str = "Engineering") -> dict:
    return {
        "id": gid,
        "name": name,
        "keypadUnlock": False,
        "immuneToAntipassback": False,
        "antipassbackResetTime": 0,
    }


def _user_json(uid: int = 5) -> dict:
    return {
        "id": uid,
        "firstName": "Jane",
        "lastName": "Doe",
        "emails": [{"address": "jane@example.com", "type": "work"}],
        "phoneNumbers": [],
        "suspended": False,
        "created": NOW,
        "updated": NOW,
    }


def _group_page(groups: list[dict], count: int | None = None) -> dict:
    return {
        "data": groups,
        "offset": 0,
        "pageSize": 100,
        "count": count if count is not None else len(groups),
    }


def _user_page(users: list[dict], count: int | None = None) -> dict:
    return {
        "data": users,
        "offset": 0,
        "pageSize": 200,
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
    return BrivoClient(http, make_limiter(1000))


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


# --- POST /scim/v2/Groups ---


async def test_post_group_happy_path(ac, brivo_mock):
    brivo_mock.post(f"{BRIVO}/v1/api/groups").mock(
        return_value=httpx.Response(201, json=_group_json())
    )
    body = {
        "displayName": "Engineering",
        "externalId": "ext-grp",
        "members": [],
    }
    r = await ac.post("/scim/v2/Groups", json=body, headers=AUTH)

    assert r.status_code == 201
    assert "Location" in r.headers
    assert r.headers["Location"].startswith("/scim/v2/Groups/")
    data = r.json()
    assert data["displayName"] == "Engineering"
    assert "id" in data


async def test_post_group_conflict(ac, store):
    await store._r.set("lock:brivo:create:group:ext-grp", "other", nx=True, ex=300)
    body = {"displayName": "Engineering", "externalId": "ext-grp", "members": []}
    r = await ac.post("/scim/v2/Groups", json=body, headers=AUTH)

    assert r.status_code == 409
    assert SCIM_ERROR_SCHEMA in r.json()["schemas"]


# --- GET /scim/v2/Groups/{id} ---


async def test_get_group_cache_miss(ac, brivo_mock, store):
    await store.set_idmap("group", "scim-grp", "10", "ext-grp")
    brivo_mock.get(f"{BRIVO}/v1/api/groups/10").mock(
        return_value=httpx.Response(200, json=_group_json())
    )
    brivo_mock.get(f"{BRIVO}/v1/api/groups/10/users").mock(
        return_value=httpx.Response(200, json=_user_page([]))
    )

    r = await ac.get("/scim/v2/Groups/scim-grp", headers=AUTH)

    assert r.status_code == 200
    data = r.json()
    assert data["id"] == "scim-grp"
    assert data["displayName"] == "Engineering"
    cached = await store.cache_get("group", "10")
    assert cached is not None


async def test_get_group_not_found(ac):
    r = await ac.get("/scim/v2/Groups/no-such-id", headers=AUTH)

    assert r.status_code == 404
    assert SCIM_ERROR_SCHEMA in r.json()["schemas"]


# --- PUT /scim/v2/Groups/{id} ---


async def test_put_group_happy_path(ac, brivo_mock, store):
    await store.set_idmap("group", "scim-grp", "10", "ext-grp")
    brivo_mock.get(f"{BRIVO}/v1/api/groups/10").mock(
        return_value=httpx.Response(200, json=_group_json())
    )
    brivo_mock.put(f"{BRIVO}/v1/api/groups/10").mock(
        return_value=httpx.Response(200, json=_group_json())
    )
    brivo_mock.get(f"{BRIVO}/v1/api/groups/10/users").mock(
        return_value=httpx.Response(200, json=_user_page([]))
    )
    body = {"displayName": "Engineering", "members": []}

    r = await ac.put("/scim/v2/Groups/scim-grp", json=body, headers=AUTH)

    assert r.status_code == 200
    assert r.json()["id"] == "scim-grp"


async def test_put_group_not_found(ac):
    body = {"displayName": "Engineering", "members": []}
    r = await ac.put("/scim/v2/Groups/no-such-id", json=body, headers=AUTH)

    assert r.status_code == 404
    assert SCIM_ERROR_SCHEMA in r.json()["schemas"]


# --- PATCH /scim/v2/Groups/{id} ---


async def test_patch_group_replace_display_name(ac, brivo_mock, store):
    await store.set_idmap("group", "scim-grp", "10", "ext-grp")
    brivo_mock.get(f"{BRIVO}/v1/api/groups/10").mock(
        return_value=httpx.Response(200, json=_group_json())
    )
    brivo_mock.put(f"{BRIVO}/v1/api/groups/10").mock(
        return_value=httpx.Response(200, json=_group_json(name="DevOps"))
    )
    brivo_mock.get(f"{BRIVO}/v1/api/groups/10/users").mock(
        return_value=httpx.Response(200, json=_user_page([]))
    )
    body = {
        "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
        "Operations": [{"op": "replace", "path": "displayName", "value": "DevOps"}],
    }

    r = await ac.patch("/scim/v2/Groups/scim-grp", json=body, headers=AUTH)

    assert r.status_code == 200
    assert r.json()["id"] == "scim-grp"


async def test_patch_group_add_member(ac, brivo_mock, store):
    await store.set_idmap("group", "scim-grp", "10", "ext-grp")
    await store.set_idmap("user", "scim-user", "5", "ext-user")
    brivo_mock.put(f"{BRIVO}/v1/api/groups/10/users/5").mock(
        return_value=httpx.Response(204)
    )
    brivo_mock.get(f"{BRIVO}/v1/api/groups/10").mock(
        return_value=httpx.Response(200, json=_group_json())
    )
    brivo_mock.get(f"{BRIVO}/v1/api/groups/10/users").mock(
        return_value=httpx.Response(200, json=_user_page([_user_json()]))
    )
    body = {
        "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
        "Operations": [
            {"op": "add", "path": "members", "value": [{"value": "scim-user"}]}
        ],
    }

    r = await ac.patch("/scim/v2/Groups/scim-grp", json=body, headers=AUTH)

    assert r.status_code == 200
    data = r.json()
    assert data["id"] == "scim-grp"
    assert any(m["value"] == "scim-user" for m in data["members"])


async def test_patch_group_remove_member(ac, brivo_mock, store):
    await store.set_idmap("group", "scim-grp", "10", "ext-grp")
    await store.set_idmap("user", "scim-user", "5", "ext-user")
    brivo_mock.delete(f"{BRIVO}/v1/api/groups/10/users/5").mock(
        return_value=httpx.Response(204)
    )
    brivo_mock.get(f"{BRIVO}/v1/api/groups/10").mock(
        return_value=httpx.Response(200, json=_group_json())
    )
    brivo_mock.get(f"{BRIVO}/v1/api/groups/10/users").mock(
        return_value=httpx.Response(200, json=_user_page([]))
    )
    body = {
        "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
        "Operations": [
            {"op": "remove", "path": "members", "value": [{"value": "scim-user"}]}
        ],
    }

    r = await ac.patch("/scim/v2/Groups/scim-grp", json=body, headers=AUTH)

    assert r.status_code == 200
    assert r.json()["id"] == "scim-grp"


async def test_patch_group_not_found(ac):
    body = {
        "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
        "Operations": [{"op": "replace", "path": "displayName", "value": "X"}],
    }
    r = await ac.patch("/scim/v2/Groups/no-such-id", json=body, headers=AUTH)

    assert r.status_code == 404
    assert SCIM_ERROR_SCHEMA in r.json()["schemas"]


# --- DELETE /scim/v2/Groups/{id} ---


async def test_delete_group_happy_path(ac, brivo_mock, store):
    await store.set_idmap("group", "scim-grp", "10", "ext-grp")
    brivo_mock.delete(f"{BRIVO}/v1/api/groups/10").mock(
        return_value=httpx.Response(204)
    )

    r = await ac.delete("/scim/v2/Groups/scim-grp", headers=AUTH)

    assert r.status_code == 204
    assert r.content == b""


# --- GET /scim/v2/Groups (list) ---


async def test_list_groups_no_filter(ac, brivo_mock, store):
    await store.set_idmap("group", "scim-grp", "10", "ext-grp")
    brivo_mock.get(f"{BRIVO}/v1/api/groups").mock(
        return_value=httpx.Response(200, json=_group_page([_group_json()]))
    )

    r = await ac.get("/scim/v2/Groups", headers=AUTH)

    assert r.status_code == 200
    data = r.json()
    assert data["totalResults"] == 1
    assert data["itemsPerPage"] == 1
    assert data["Resources"][0]["id"] == "scim-grp"


async def test_list_groups_filter_match(ac, brivo_mock, store):
    await store.set_idmap("group", "scim-grp", "10", "ext-grp")
    brivo_mock.get(f"{BRIVO}/v1/api/groups").mock(
        return_value=httpx.Response(200, json=_group_page([_group_json()]))
    )

    r = await ac.get(
        '/scim/v2/Groups?filter=displayName eq "Engineering"', headers=AUTH
    )

    assert r.status_code == 200
    data = r.json()
    assert data["totalResults"] == 1
    assert data["Resources"][0]["id"] == "scim-grp"


async def test_list_groups_filter_no_match(ac, brivo_mock):
    brivo_mock.get(f"{BRIVO}/v1/api/groups").mock(
        return_value=httpx.Response(200, json=_group_page([_group_json()]))
    )

    r = await ac.get('/scim/v2/Groups?filter=displayName eq "Nobody"', headers=AUTH)

    assert r.status_code == 200
    data = r.json()
    assert data["totalResults"] == 0
    assert data["Resources"] == []
