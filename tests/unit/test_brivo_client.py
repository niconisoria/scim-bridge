import pytest
import respx
import httpx

from app.brivo.client import (
    BrivoClient,
    BrivoError,
    BrivoNotFoundError,
    BrivoRateLimitError,
)
from app.brivo.rate_limiter import make_limiter
from app.models.brivo import (
    BrivoUser,
    BrivoGroup,
    BrivoGroupRef,
    BrivoPaginatedList,
)

BASE = "http://brivo-test"

USER_JSON = {
    "id": 1,
    "externalId": None,
    "firstName": "Jane",
    "lastName": "Smith",
    "emails": [],
    "phoneNumbers": [],
    "suspended": False,
    "created": "2024-01-01T00:00:00Z",
    "updated": "2024-01-01T00:00:00Z",
}

GROUP_JSON = {
    "id": 1,
    "name": "Engineering",
    "keypadUnlock": False,
    "immuneToAntipassback": False,
    "antipassbackResetTime": 0,
}

PAGE_USERS = {"data": [USER_JSON], "offset": 0, "pageSize": 20, "count": 1}
PAGE_GROUPS = {"data": [GROUP_JSON], "offset": 0, "pageSize": 20, "count": 1}

USER_WRITE = {
    "firstName": "Jane",
    "lastName": "Smith",
    "emails": [],
    "phoneNumbers": [],
    "suspended": False,
}

GROUP_WRITE = {
    "name": "Engineering",
    "keypadUnlock": False,
    "immuneToAntipassback": False,
    "antipassbackResetTime": 0,
}


def make_client(http):
    return BrivoClient(http, make_limiter(1000))


@pytest.mark.asyncio
async def test_list_users():
    async with respx.mock:
        respx.get(f"{BASE}/v1/api/users").mock(
            return_value=httpx.Response(200, json=PAGE_USERS)
        )
        async with httpx.AsyncClient(base_url=BASE) as http:
            result = await make_client(http).list_users()
    assert isinstance(result, BrivoPaginatedList)
    assert result.count == 1
    assert isinstance(result.data[0], BrivoUser)


@pytest.mark.asyncio
async def test_create_user():
    async with respx.mock:
        respx.post(f"{BASE}/v1/api/users").mock(
            return_value=httpx.Response(200, json=USER_JSON)
        )
        async with httpx.AsyncClient(base_url=BASE) as http:
            result = await make_client(http).create_user(_user_write())
    assert isinstance(result, BrivoUser)
    assert result.id == 1


@pytest.mark.asyncio
async def test_get_user():
    async with respx.mock:
        respx.get(f"{BASE}/v1/api/users/1").mock(
            return_value=httpx.Response(200, json=USER_JSON)
        )
        async with httpx.AsyncClient(base_url=BASE) as http:
            result = await make_client(http).get_user(1)
    assert result.firstName == "Jane"


@pytest.mark.asyncio
async def test_update_user():
    async with respx.mock:
        respx.put(f"{BASE}/v1/api/users/1").mock(
            return_value=httpx.Response(200, json=USER_JSON)
        )
        async with httpx.AsyncClient(base_url=BASE) as http:
            result = await make_client(http).update_user(1, _user_write())
    assert isinstance(result, BrivoUser)


@pytest.mark.asyncio
async def test_delete_user():
    async with respx.mock:
        respx.delete(f"{BASE}/v1/api/users/1").mock(return_value=httpx.Response(204))
        async with httpx.AsyncClient(base_url=BASE) as http:
            result = await make_client(http).delete_user(1)
    assert result is None


@pytest.mark.asyncio
async def test_list_user_groups():
    payload = {"count": 1, "data": [{"id": 1, "name": "Engineering"}]}
    async with respx.mock:
        respx.get(f"{BASE}/v1/api/users/1/groups").mock(
            return_value=httpx.Response(200, json=payload)
        )
        async with httpx.AsyncClient(base_url=BASE) as http:
            result = await make_client(http).list_user_groups(1)
    assert isinstance(result, list)
    assert isinstance(result[0], BrivoGroupRef)
    assert result[0].id == 1


@pytest.mark.asyncio
async def test_list_groups():
    async with respx.mock:
        respx.get(f"{BASE}/v1/api/groups").mock(
            return_value=httpx.Response(200, json=PAGE_GROUPS)
        )
        async with httpx.AsyncClient(base_url=BASE) as http:
            result = await make_client(http).list_groups()
    assert isinstance(result, BrivoPaginatedList)
    assert isinstance(result.data[0], BrivoGroup)


@pytest.mark.asyncio
async def test_create_group():
    async with respx.mock:
        respx.post(f"{BASE}/v1/api/groups").mock(
            return_value=httpx.Response(200, json=GROUP_JSON)
        )
        async with httpx.AsyncClient(base_url=BASE) as http:
            result = await make_client(http).create_group(_group_write())
    assert isinstance(result, BrivoGroup)
    assert result.name == "Engineering"


@pytest.mark.asyncio
async def test_get_group():
    async with respx.mock:
        respx.get(f"{BASE}/v1/api/groups/1").mock(
            return_value=httpx.Response(200, json=GROUP_JSON)
        )
        async with httpx.AsyncClient(base_url=BASE) as http:
            result = await make_client(http).get_group(1)
    assert result.id == 1


@pytest.mark.asyncio
async def test_update_group():
    async with respx.mock:
        respx.put(f"{BASE}/v1/api/groups/1").mock(
            return_value=httpx.Response(200, json=GROUP_JSON)
        )
        async with httpx.AsyncClient(base_url=BASE) as http:
            result = await make_client(http).update_group(1, _group_write())
    assert isinstance(result, BrivoGroup)


@pytest.mark.asyncio
async def test_delete_group():
    async with respx.mock:
        respx.delete(f"{BASE}/v1/api/groups/1").mock(return_value=httpx.Response(204))
        async with httpx.AsyncClient(base_url=BASE) as http:
            result = await make_client(http).delete_group(1)
    assert result is None


@pytest.mark.asyncio
async def test_list_group_users():
    async with respx.mock:
        respx.get(f"{BASE}/v1/api/groups/1/users").mock(
            return_value=httpx.Response(200, json=PAGE_USERS)
        )
        async with httpx.AsyncClient(base_url=BASE) as http:
            result = await make_client(http).list_group_users(1)
    assert isinstance(result, BrivoPaginatedList)
    assert isinstance(result.data[0], BrivoUser)


@pytest.mark.asyncio
async def test_add_user_to_group():
    async with respx.mock:
        respx.put(f"{BASE}/v1/api/groups/1/users/2").mock(
            return_value=httpx.Response(204)
        )
        async with httpx.AsyncClient(base_url=BASE) as http:
            result = await make_client(http).add_user_to_group(1, 2)
    assert result is None


@pytest.mark.asyncio
async def test_remove_user_from_group():
    async with respx.mock:
        respx.delete(f"{BASE}/v1/api/groups/1/users/2").mock(
            return_value=httpx.Response(204)
        )
        async with httpx.AsyncClient(base_url=BASE) as http:
            result = await make_client(http).remove_user_from_group(1, 2)
    assert result is None


@pytest.mark.asyncio
async def test_not_found_raises_brivo_not_found_error():
    async with respx.mock:
        respx.get(f"{BASE}/v1/api/users/999").mock(
            return_value=httpx.Response(404, json={"code": 404, "message": "Not found"})
        )
        async with httpx.AsyncClient(base_url=BASE) as http:
            with pytest.raises(BrivoNotFoundError):
                await make_client(http).get_user(999)


@pytest.mark.asyncio
async def test_rate_limit_raises_brivo_rate_limit_error():
    async with respx.mock:
        respx.get(f"{BASE}/v1/api/users/1").mock(
            return_value=httpx.Response(
                429, json={"code": 429, "message": "Rate limit exceeded"}
            )
        )
        async with httpx.AsyncClient(base_url=BASE) as http:
            with pytest.raises(BrivoRateLimitError):
                await make_client(http).get_user(1)


@pytest.mark.asyncio
async def test_server_error_raises_brivo_error():
    async with respx.mock:
        respx.get(f"{BASE}/v1/api/users/1").mock(
            return_value=httpx.Response(
                503, json={"code": 503, "message": "Service unavailable"}
            )
        )
        async with httpx.AsyncClient(base_url=BASE) as http:
            with pytest.raises(BrivoError):
                await make_client(http).get_user(1)


@pytest.mark.asyncio
async def test_limiter_called_before_request():
    class _Limiter:
        entered = False

        async def __aenter__(self):
            self.entered = True
            return self

        async def __aexit__(self, *_):
            pass

    limiter = _Limiter()
    async with respx.mock:
        respx.get(f"{BASE}/v1/api/users/1").mock(
            return_value=httpx.Response(200, json=USER_JSON)
        )
        async with httpx.AsyncClient(base_url=BASE) as http:
            await BrivoClient(http, limiter=limiter).get_user(1)
    assert limiter.entered


# --- helpers ---


def _user_write():
    from app.models.brivo import BrivoUserWrite

    return BrivoUserWrite(**USER_WRITE)


def _group_write():
    from app.models.brivo import BrivoGroupWrite

    return BrivoGroupWrite(**GROUP_WRITE)
