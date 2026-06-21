from app.brivo.client import BrivoClient, BrivoNotFoundError
from app.core.errors import ScimNotFound
from app.core.logging import get_logger
from app.models.brivo import BrivoUser, BrivoUserWrite
from app.redis.store import RedisStore
from app.services.saga import Step, run_saga


async def delete_user(scim_id: str, store: RedisStore, client: BrivoClient) -> None:
    record = await store.get_by_scim("user", scim_id)
    if record is None:
        raise ScimNotFound(f"User {scim_id!r} not found")

    target_id = int(record["target_id"])
    external_id: str = record["external_id"]
    log = get_logger()

    ctx: dict = {"groups": [], "removed_gids": [], "snapshot": None}

    async def step1_forward() -> None:
        ctx["groups"] = await client.list_user_groups(target_id)

    async def step2_forward() -> None:
        for group in ctx["groups"]:
            try:
                await client.remove_user_from_group(group.id, target_id)
                ctx["removed_gids"].append(group.id)
            except BrivoNotFoundError:
                pass

    async def step2_rollback() -> None:
        for gid in ctx["removed_gids"]:
            try:
                await client.add_user_to_group(gid, target_id)
            except Exception:
                log.error("rollback.add_group_member.failed", group_id=gid)

    async def step3_forward() -> None:
        try:
            ctx["snapshot"] = await client.get_user(target_id)
        except BrivoNotFoundError:
            return
        try:
            await client.delete_user(target_id)
        except BrivoNotFoundError:
            pass

    async def step3_rollback() -> None:
        snap: BrivoUser | None = ctx["snapshot"]
        if snap is None:
            return
        write = BrivoUserWrite(
            externalId=snap.externalId,
            firstName=snap.firstName,
            lastName=snap.lastName,
            emails=snap.emails,
            phoneNumbers=snap.phoneNumbers,
            suspended=snap.suspended,
        )
        try:
            await client.create_user(write)
        except Exception:
            log.warning("rollback.recreate_user.failed", target_id=target_id)

    async def step4_forward() -> None:
        await store.del_idmap("user", scim_id, record["target_id"], external_id)
        await store.cache_del("user", record["target_id"])

    async def step4_rollback() -> None:
        snap: BrivoUser | None = ctx["snapshot"]
        await store.set_idmap("user", scim_id, record["target_id"], external_id)
        if snap is not None:
            await store.cache_set(
                "user", record["target_id"], value=snap.model_dump(mode="json")
            )

    await run_saga(
        [
            Step("fetch-groups", step1_forward),
            Step("remove-from-groups", step2_forward, step2_rollback),
            Step("delete-brivo-user", step3_forward, step3_rollback),
            Step("del-idmap-cache", step4_forward, step4_rollback),
        ]
    )
