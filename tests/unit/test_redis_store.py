import pytest
import fakeredis.aioredis

from app.redis.store import RedisStore


@pytest.fixture
async def store():
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    return RedisStore(client)


async def test_set_idmap_writes_all_three_keys(store):
    await store.set_idmap("user", "scim-1", "brivo-1", "ext-1")

    by_scim = await store.get_by_scim("user", "scim-1")
    by_ext = await store.get_by_external("user", "ext-1")
    by_tid = await store.get_by_target("user", "brivo-1")

    assert by_scim["target_id"] == "brivo-1"
    assert by_scim["external_id"] == "ext-1"
    assert "created_at" in by_scim

    assert by_ext["scim_id"] == "scim-1"
    assert by_ext["target_id"] == "brivo-1"

    assert by_tid["scim_id"] == "scim-1"
    assert by_tid["external_id"] == "ext-1"


async def test_get_missing_returns_none(store):
    assert await store.get_by_scim("user", "nonexistent") is None
    assert await store.get_by_external("user", "nonexistent") is None
    assert await store.get_by_target("user", "nonexistent") is None


async def test_del_idmap_removes_all_keys(store):
    await store.set_idmap("user", "scim-1", "brivo-1", "ext-1")
    await store.del_idmap("user", "scim-1", "brivo-1", "ext-1")

    assert await store.get_by_scim("user", "scim-1") is None
    assert await store.get_by_external("user", "ext-1") is None
    assert await store.get_by_target("user", "brivo-1") is None


async def test_acquire_lock_is_exclusive(store):
    assert await store.acquire_lock("user", "ext-1", "saga-a") is True
    assert await store.acquire_lock("user", "ext-1", "saga-b") is False


async def test_release_lock_allows_reacquire(store):
    await store.acquire_lock("user", "ext-1", "saga-a")
    await store.release_lock("user", "ext-1")
    assert await store.acquire_lock("user", "ext-1", "saga-b") is True


async def test_cache_set_get_del(store):
    payload = {"id": 42, "name": "Eng"}

    await store.cache_set("group", "42", value=payload)
    assert await store.cache_get("group", "42") == payload

    await store.cache_del("group", "42")
    assert await store.cache_get("group", "42") is None


async def test_cache_get_missing_returns_none(store):
    assert await store.cache_get("user", "999") is None


async def test_idmap_user_and_group_keys_are_isolated(store):
    await store.set_idmap("user", "scim-1", "brivo-1", "ext-1")
    await store.set_idmap("group", "scim-1", "brivo-g1", "ext-g1")

    user = await store.get_by_scim("user", "scim-1")
    group = await store.get_by_scim("group", "scim-1")

    assert user["target_id"] == "brivo-1"
    assert group["target_id"] == "brivo-g1"
