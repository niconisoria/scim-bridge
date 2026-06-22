from app.brivo.client import BrivoClient
from app.core.errors import ScimBadRequest
from app.redis.store import RedisStore
from app.services.saga import Step, run_saga


async def add_members(
    group_target_id: int,
    member_scim_ids: list[str],
    store: RedisStore,
    client: BrivoClient,
) -> None:
    if not member_scim_ids:
        return

    resolved: list[int] = []
    for scim_id in member_scim_ids:
        record = await store.get_by_scim("user", scim_id)
        if record is None:
            raise ScimBadRequest(f"Member {scim_id!r} not found in idmap")
        resolved.append(int(record["target_id"]))

    ctx: dict = {"added": []}

    async def step_forward() -> None:
        for target_user_id in resolved:
            await client.add_user_to_group(group_target_id, target_user_id)
            ctx["added"].append(target_user_id)
        await store.cache_del("group", str(group_target_id), "members")

    async def step_rollback() -> None:
        for uid in reversed(ctx["added"]):
            try:
                await client.remove_user_from_group(group_target_id, uid)
            except Exception:
                pass
        await store.cache_del("group", str(group_target_id), "members")

    await run_saga([Step("add-members", step_forward, step_rollback)])
