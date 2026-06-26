from uuid import uuid4

from app.brivo.client import BrivoClient, BrivoNotFoundError
from app.brivo.client import BrivoUser
from app.core.errors import ScimConflict
from app.models.user import ScimUser
from app.redis.store import RedisStore
from app.services.field_mapper import scim_user_to_brivo
from app.services.saga import Step, run_saga


async def create_user(
    body: ScimUser,
    store: RedisStore,
    client: BrivoClient,
) -> tuple[BrivoUser, str]:
    external_id = body.externalId or body.userName
    scim_id = str(uuid4())
    brivo_write = scim_user_to_brivo(body)

    if await store.get_by_external("user", external_id):
        raise ScimConflict("User already exists")

    if not await store.acquire_lock("user", external_id, scim_id):
        raise ScimConflict("User creation already in progress for this externalId")

    result: dict = {}

    async def step_create_forward() -> None:
        result["user"] = await client.create_user(brivo_write)

    async def step_create_rollback() -> None:
        if "user" in result:
            try:
                await client.delete_user(result["user"].id)
            except BrivoNotFoundError:
                pass
        await store.release_lock("user", external_id)

    async def step_idmap_forward() -> None:
        await store.set_idmap("user", scim_id, str(result["user"].id), external_id)
        await store.release_lock("user", external_id)

    async def step_idmap_rollback() -> None:
        if "user" in result:
            await store.del_idmap("user", scim_id, str(result["user"].id), external_id)

    await run_saga(
        [
            Step("create-brivo-user", step_create_forward, step_create_rollback),
            Step("write-idmap", step_idmap_forward, step_idmap_rollback),
        ]
    )

    return result["user"], scim_id
