from app.brivo.client import BrivoClient, BrivoNotFoundError
from app.core.errors import ScimNotFound
from app.core.logging import get_logger
from app.redis.store import RedisStore
from app.services.saga import Step, run_saga


async def delete_group(scim_id: str, store: RedisStore, client: BrivoClient) -> None:
    record = await store.get_by_scim("group", scim_id)
    if record is None:
        raise ScimNotFound(f"Group {scim_id!r} not found")

    target_id: str = record["target_id"]
    external_id: str = record["external_id"]
    log = get_logger()

    async def step1_forward() -> None:
        try:
            await client.delete_group(int(target_id))
        except BrivoNotFoundError:
            pass

    async def step1_rollback() -> None:
        log.error(
            "rollback.delete_group.unrecoverable",
            scim_id=scim_id,
            target_id=target_id,
        )

    async def step2_forward() -> None:
        await store.del_idmap("group", scim_id, target_id, external_id)
        await store.cache_del("group", target_id)
        await store.cache_del("group", target_id, "members")

    async def step2_rollback() -> None:
        await store.set_idmap("group", scim_id, target_id, external_id)

    await run_saga(
        [
            Step("delete-brivo-group", step1_forward, step1_rollback),
            Step("del-idmap-cache", step2_forward, step2_rollback),
        ]
    )
