from app.brivo.client import BrivoClient
from app.models.brivo import BrivoEmail, BrivoUser, BrivoUserWrite
from app.models.common import PatchOp
from app.models.user import ScimUser
from app.redis.store import RedisStore
from app.services.field_mapper import scim_user_to_brivo


async def update_user(
    target_id: int,
    body: ScimUser | None,
    patch_ops: list[PatchOp] | None,
    store: RedisStore,
    client: BrivoClient,
) -> BrivoUser:
    cached = await store.cache_get("user", str(target_id))
    if cached:
        current = BrivoUser.model_validate(cached)
    else:
        current = await client.get_user(target_id)

    if body is not None:
        write = scim_user_to_brivo(body)
        write = write.model_copy(update={"externalId": current.externalId})
    else:
        write = _apply_patch_ops(current, patch_ops or [])

    updated = await client.update_user(target_id, write)
    await store.cache_del("user", str(target_id))
    return updated


def _apply_patch_ops(current: BrivoUser, ops: list[PatchOp]) -> BrivoUserWrite:
    first_name = current.firstName
    last_name = current.lastName
    suspended = current.suspended
    emails = list(current.emails)
    phone_numbers = list(current.phoneNumbers)

    for op in ops:
        if op.op != "replace":
            continue
        if op.path == "active":
            suspended = not op.value
        elif op.path == "name.givenName":
            first_name = op.value
        elif op.path == "name.familyName":
            last_name = op.value
        elif op.path == "userName" and emails:
            emails[0] = BrivoEmail(address=op.value, type=emails[0].type)

    return BrivoUserWrite(
        externalId=current.externalId,
        firstName=first_name,
        lastName=last_name,
        emails=emails,
        phoneNumbers=phone_numbers,
        suspended=suspended,
    )
