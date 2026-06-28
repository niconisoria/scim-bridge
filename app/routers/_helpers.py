from datetime import datetime

from fastapi import Depends, Query
from typing import Annotated

from app.core.errors import ScimNotFound
from app.redis.store import RedisStore


class ScimListParams:
    def __init__(
        self,
        startIndex: int = Query(default=1, ge=1),
        count: int = Query(default=100, ge=0),
        filter: str | None = Query(default=None),
    ):
        self.startIndex = startIndex
        self.count = count
        self.filter = filter


Params = Annotated[ScimListParams, Depends(ScimListParams)]


async def resolve_or_404(
    rtype: str, scim_id: str, store: RedisStore
) -> tuple[str, datetime]:
    idmap = await store.get_by_scim(rtype, scim_id)
    if not idmap:
        raise ScimNotFound(f"{rtype.capitalize()} {scim_id!r} not found")
    return idmap["target_id"], datetime.fromisoformat(idmap["created_at"])
