from typing import Any

import httpx

from app.models.brivo import (
    BrivoGroup,
    BrivoGroupRef,
    BrivoGroupWrite,
    BrivoPaginatedList,
    BrivoUser,
    BrivoUserWrite,
)


class BrivoError(Exception):
    def __init__(self, status_code: int, message: str = ""):
        self.status_code = status_code
        super().__init__(f"{status_code}: {message}")


class BrivoNotFoundError(BrivoError):
    pass


class BrivoRateLimitError(BrivoError):
    pass


class BrivoClient:
    def __init__(self, http: httpx.AsyncClient, limiter: Any = None):
        self._http = http
        self._limiter = limiter

    def _check(self, r: httpx.Response) -> httpx.Response:
        if r.status_code == 404:
            raise BrivoNotFoundError(404, r.json().get("message", "Not found"))
        if r.status_code == 429:
            raise BrivoRateLimitError(
                429, r.json().get("message", "Rate limit exceeded")
            )
        if not r.is_success:
            msg = r.json().get("message", "Brivo error") if r.content else "Brivo error"
            raise BrivoError(r.status_code, msg)
        return r

    async def _call(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        if self._limiter:
            async with self._limiter:
                r = await self._http.request(method, url, **kwargs)
        else:
            r = await self._http.request(method, url, **kwargs)
        return self._check(r)

    # --- Users ---

    async def list_users(
        self, offset: int = 0, page_size: int = 20
    ) -> BrivoPaginatedList[BrivoUser]:
        r = await self._call(
            "GET", "/v1/api/users", params={"offset": offset, "pageSize": page_size}
        )
        return BrivoPaginatedList[BrivoUser].model_validate(r.json())

    async def create_user(self, body: BrivoUserWrite) -> BrivoUser:
        r = await self._call("POST", "/v1/api/users", json=body.model_dump())
        return BrivoUser.model_validate(r.json())

    async def get_user(self, user_id: int) -> BrivoUser:
        r = await self._call("GET", f"/v1/api/users/{user_id}")
        return BrivoUser.model_validate(r.json())

    async def update_user(self, user_id: int, body: BrivoUserWrite) -> BrivoUser:
        r = await self._call("PUT", f"/v1/api/users/{user_id}", json=body.model_dump())
        return BrivoUser.model_validate(r.json())

    async def delete_user(self, user_id: int) -> None:
        await self._call("DELETE", f"/v1/api/users/{user_id}")

    async def list_user_groups(self, user_id: int) -> list[BrivoGroupRef]:
        r = await self._call("GET", f"/v1/api/users/{user_id}/groups")
        return [BrivoGroupRef.model_validate(g) for g in r.json()["data"]]

    # --- Groups ---

    async def list_groups(
        self, offset: int = 0, page_size: int = 20
    ) -> BrivoPaginatedList[BrivoGroup]:
        r = await self._call(
            "GET", "/v1/api/groups", params={"offset": offset, "pageSize": page_size}
        )
        return BrivoPaginatedList[BrivoGroup].model_validate(r.json())

    async def create_group(self, body: BrivoGroupWrite) -> BrivoGroup:
        r = await self._call("POST", "/v1/api/groups", json=body.model_dump())
        return BrivoGroup.model_validate(r.json())

    async def get_group(self, group_id: int) -> BrivoGroup:
        r = await self._call("GET", f"/v1/api/groups/{group_id}")
        return BrivoGroup.model_validate(r.json())

    async def update_group(self, group_id: int, body: BrivoGroupWrite) -> BrivoGroup:
        r = await self._call(
            "PUT", f"/v1/api/groups/{group_id}", json=body.model_dump()
        )
        return BrivoGroup.model_validate(r.json())

    async def delete_group(self, group_id: int) -> None:
        await self._call("DELETE", f"/v1/api/groups/{group_id}")

    async def list_group_users(
        self, group_id: int, offset: int = 0, page_size: int = 20
    ) -> BrivoPaginatedList[BrivoUser]:
        r = await self._call(
            "GET",
            f"/v1/api/groups/{group_id}/users",
            params={"offset": offset, "pageSize": page_size},
        )
        return BrivoPaginatedList[BrivoUser].model_validate(r.json())

    async def add_user_to_group(self, group_id: int, user_id: int) -> None:
        await self._call("PUT", f"/v1/api/groups/{group_id}/users/{user_id}")

    async def remove_user_from_group(self, group_id: int, user_id: int) -> None:
        await self._call("DELETE", f"/v1/api/groups/{group_id}/users/{user_id}")
