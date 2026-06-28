from app.brivo.client import BrivoClient
from app.brivo.fetch import fetch_group
from app.models.brivo import BrivoGroupWrite
from app.models.common import PatchOp
from app.redis.store import RedisStore


async def patch_replace_group(
    target_id: int, op: PatchOp, store: RedisStore, client: BrivoClient
) -> None:
    current = await fetch_group(str(target_id), store, client)

    if op.path == "displayName":
        new_name = op.value
    else:
        value = op.value or {}
        new_name = (
            value.get("displayName", current.name)
            if isinstance(value, dict)
            else current.name
        )

    write = BrivoGroupWrite(
        name=new_name,
        keypadUnlock=current.keypadUnlock,
        immuneToAntipassback=current.immuneToAntipassback,
        antipassbackResetTime=current.antipassbackResetTime,
    )
    await client.update_group(target_id, write)
    await store.cache_del("group", str(target_id))
