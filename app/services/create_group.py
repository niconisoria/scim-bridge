from uuid import uuid4

from app.brivo.client import BrivoClient, BrivoNotFoundError
from app.core.errors import ScimBadRequest, ScimConflict
from app.models.brivo import BrivoGroup
from app.models.group import ScimGroup
from app.redis.store import RedisStore
from app.services.field_mapper import scim_group_to_brivo
from app.services.saga import Step, run_saga


async def create_group(
    body: ScimGroup,
    store: RedisStore,
    client: BrivoClient,
) -> tuple[BrivoGroup, str]:
    if not body.externalId:
        raise ScimBadRequest("externalId is required")

    # Resolve all members pre-saga (before lock) for clean 400 semantics
    resolved: list[int] = []
    for member in body.members:
        record = await store.get_by_scim("user", member.value)
        if record is None:
            raise ScimBadRequest(f"Member {member.value!r} not found in idmap")
        resolved.append(int(record["target_id"]))

    scim_id = str(uuid4())
    if not await store.acquire_lock("group", body.externalId, scim_id):
        raise ScimConflict("Group creation already in progress for this externalId")

    brivo_write = scim_group_to_brivo(body)
    result: dict = {"group": None, "added": []}

    async def step1_forward() -> None:
        result["group"] = await client.create_group(brivo_write)

    async def step1_rollback() -> None:
        if result["group"] is not None:
            try:
                await client.delete_group(result["group"].id)
            except BrivoNotFoundError:
                pass
        await store.release_lock("group", body.externalId)

    async def step2_forward() -> None:
        await store.set_idmap(
            "group", scim_id, str(result["group"].id), body.externalId
        )
        await store.release_lock("group", body.externalId)

    async def step2_rollback() -> None:
        if result["group"] is not None:
            await store.del_idmap(
                "group", scim_id, str(result["group"].id), body.externalId
            )

    async def step3_forward() -> None:
        group_id = result["group"].id
        for target_user_id in resolved:
            await client.add_user_to_group(group_id, target_user_id)
            result["added"].append(target_user_id)
        await store.cache_del("group", str(group_id), "members")

    async def step3_rollback() -> None:
        group_id = result["group"].id
        for uid in reversed(result["added"]):
            try:
                await client.remove_user_from_group(group_id, uid)
            except Exception:
                pass
        await store.cache_del("group", str(group_id), "members")

    steps: list[Step] = [
        Step("create-brivo-group", step1_forward, step1_rollback),
        Step("write-idmap", step2_forward, step2_rollback),
    ]
    if resolved:
        steps.append(Step("add-members", step3_forward, step3_rollback))

    await run_saga(steps)
    return result["group"], scim_id
