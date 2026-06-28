from datetime import datetime

from app.core.errors import ScimNotFound
from app.redis.store import RedisStore


async def resolve_or_404(
    rtype: str, scim_id: str, store: RedisStore
) -> tuple[str, datetime]:
    idmap = await store.get_by_scim(rtype, scim_id)
    if not idmap:
        raise ScimNotFound(f"{rtype.capitalize()} {scim_id!r} not found")
    return idmap["target_id"], datetime.fromisoformat(idmap["created_at"])
