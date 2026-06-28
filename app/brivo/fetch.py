from app.brivo.client import BrivoClient
from app.models.brivo import BrivoGroup, BrivoUser
from app.redis.store import RedisStore


async def fetch_user(
    target_id: str, store: RedisStore, client: BrivoClient
) -> BrivoUser:
    cached = await store.cache_get("user", target_id)
    if cached:
        return BrivoUser.model_validate(cached)
    user = await client.get_user(int(target_id))
    await store.cache_set("user", target_id, value=user.model_dump(mode="json"))
    return user


async def fetch_group(
    target_id: str, store: RedisStore, client: BrivoClient
) -> BrivoGroup:
    cached = await store.cache_get("group", target_id)
    if cached:
        return BrivoGroup.model_validate(cached)
    group = await client.get_group(int(target_id))
    await store.cache_set("group", target_id, value=group.model_dump(mode="json"))
    return group


async def fetch_group_members(
    target_id: str, store: RedisStore, client: BrivoClient
) -> list[int]:
    cached = await store.cache_get("group", target_id, "members")
    if cached is not None:
        return cached
    page = await client.list_group_users(int(target_id), page_size=200)
    target_ids = [u.id for u in page.data]
    await store.cache_set("group", target_id, "members", value=target_ids)
    return target_ids
