import json
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as aioredis

from app.core.config import settings

_TARGET = "brivo"
_CACHE_TTL = 300  # 5 minutes

_redis: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _redis


class RedisStore:
    def __init__(self, client: aioredis.Redis) -> None:
        self._r = client

    # --- key builders ---

    def _scim_key(self, rtype: str, scim_id: str) -> str:
        return f"idmap:{_TARGET}:scim:{rtype}:{scim_id}"

    def _ext_key(self, rtype: str, external_id: str) -> str:
        return f"idmap:{_TARGET}:ext:{rtype}:{external_id}"

    def _tid_key(self, rtype: str, target_id: str) -> str:
        return f"idmap:{_TARGET}:tid:{rtype}:{target_id}"

    def _lock_key(self, rtype: str, external_id: str) -> str:
        return f"lock:{_TARGET}:create:{rtype}:{external_id}"

    def _cache_key(self, *parts: str) -> str:
        return f"cache:{_TARGET}:{':'.join(parts)}"

    # --- ID mappings ---

    async def set_idmap(
        self,
        rtype: str,
        scim_id: str,
        target_id: str,
        external_id: str,
    ) -> None:
        created_at = datetime.now(timezone.utc).isoformat()
        async with self._r.pipeline(transaction=True) as pipe:
            pipe.set(
                self._scim_key(rtype, scim_id),
                json.dumps({"target_id": target_id, "external_id": external_id, "created_at": created_at}),
            )
            pipe.set(
                self._ext_key(rtype, external_id),
                json.dumps({"scim_id": scim_id, "target_id": target_id}),
            )
            pipe.set(
                self._tid_key(rtype, target_id),
                json.dumps({"scim_id": scim_id, "external_id": external_id}),
            )
            await pipe.execute()

    async def get_by_scim(self, rtype: str, scim_id: str) -> dict | None:
        v = await self._r.get(self._scim_key(rtype, scim_id))
        return json.loads(v) if v else None

    async def get_by_external(self, rtype: str, external_id: str) -> dict | None:
        v = await self._r.get(self._ext_key(rtype, external_id))
        return json.loads(v) if v else None

    async def get_by_target(self, rtype: str, target_id: str) -> dict | None:
        v = await self._r.get(self._tid_key(rtype, target_id))
        return json.loads(v) if v else None

    async def del_idmap(
        self, rtype: str, scim_id: str, target_id: str, external_id: str
    ) -> None:
        await self._r.delete(
            self._scim_key(rtype, scim_id),
            self._ext_key(rtype, external_id),
            self._tid_key(rtype, target_id),
        )

    # --- idempotency locks ---

    async def acquire_lock(self, rtype: str, external_id: str, saga_id: str) -> bool:
        result = await self._r.set(
            self._lock_key(rtype, external_id), saga_id, nx=True, ex=300
        )
        return result is not None

    async def release_lock(self, rtype: str, external_id: str) -> None:
        await self._r.delete(self._lock_key(rtype, external_id))

    # --- Brivo response cache ---

    async def cache_get(self, *key_parts: str) -> Any | None:
        v = await self._r.get(self._cache_key(*key_parts))
        return json.loads(v) if v else None

    async def cache_set(self, *key_parts: str, value: Any) -> None:
        await self._r.set(self._cache_key(*key_parts), json.dumps(value), ex=_CACHE_TTL)

    async def cache_del(self, *key_parts: str) -> None:
        await self._r.delete(self._cache_key(*key_parts))


async def get_store() -> RedisStore:
    return RedisStore(get_redis())
