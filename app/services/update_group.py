from app.brivo.client import BrivoClient
from app.core.errors import ScimBadRequest
from app.models.brivo import BrivoGroup, BrivoGroupWrite
from app.models.group import ScimGroup
from app.redis.store import RedisStore
from app.services.saga import Step, run_saga


async def update_group(
    target_group_id: int,
    scim_id: str,
    body: ScimGroup,
    store: RedisStore,
    client: BrivoClient,
) -> tuple[BrivoGroup, str]:
    new_target_ids: list[int] = []
    for member in body.members:
        record = await store.get_by_scim("user", member.value)
        if record is None:
            raise ScimBadRequest(f"Member {member.value!r} not found in idmap")
        new_target_ids.append(int(record["target_id"]))

    new_set = set(new_target_ids)
    ctx: dict = {
        "original_group": None,
        "updated_group": None,
        "current_target_ids": set(),
        "added": [],
        "removed": [],
    }

    async def step1_forward() -> None:
        cached = await store.cache_get("group", str(target_group_id))
        if cached:
            current = BrivoGroup.model_validate(cached)
        else:
            current = await client.get_group(target_group_id)
        ctx["original_group"] = current
        write = BrivoGroupWrite(
            name=body.displayName,
            keypadUnlock=current.keypadUnlock,
            immuneToAntipassback=current.immuneToAntipassback,
            antipassbackResetTime=current.antipassbackResetTime,
        )
        ctx["updated_group"] = await client.update_group(target_group_id, write)
        await store.cache_del("group", str(target_group_id))

    async def step1_rollback() -> None:
        og = ctx["original_group"]
        if og is not None:
            try:
                await client.update_group(
                    target_group_id,
                    BrivoGroupWrite(
                        name=og.name,
                        keypadUnlock=og.keypadUnlock,
                        immuneToAntipassback=og.immuneToAntipassback,
                        antipassbackResetTime=og.antipassbackResetTime,
                    ),
                )
            except Exception:
                pass
        await store.cache_del("group", str(target_group_id))

    async def step2_forward() -> None:
        cached = await store.cache_get("group", str(target_group_id), "members")
        if cached is not None:
            ctx["current_target_ids"] = set(cached)
        else:
            page = await client.list_group_users(target_group_id, page_size=200)
            ctx["current_target_ids"] = {u.id for u in page.data}

    async def step3_forward() -> None:
        for uid in new_set - ctx["current_target_ids"]:
            await client.add_user_to_group(target_group_id, uid)
            ctx["added"].append(uid)

    async def step3_rollback() -> None:
        for uid in reversed(ctx["added"]):
            try:
                await client.remove_user_from_group(target_group_id, uid)
            except Exception:
                pass

    async def step4_forward() -> None:
        for uid in ctx["current_target_ids"] - new_set:
            await client.remove_user_from_group(target_group_id, uid)
            ctx["removed"].append(uid)
        await store.cache_del("group", str(target_group_id), "members")

    async def step4_rollback() -> None:
        for uid in reversed(ctx["removed"]):
            try:
                await client.add_user_to_group(target_group_id, uid)
            except Exception:
                pass
        await store.cache_del("group", str(target_group_id), "members")

    await run_saga(
        [
            Step("update-name", step1_forward, step1_rollback),
            Step("fetch-members", step2_forward),
            Step("add-members", step3_forward, step3_rollback),
            Step("remove-stale", step4_forward, step4_rollback),
        ]
    )

    return ctx["updated_group"], scim_id
