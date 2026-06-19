import os
import time
from unittest.mock import patch

import pytest
from httpx import AsyncClient, ASGITransport
from mock_brivo.main import app, users, groups, group_members, _counters, _request_times

HEADERS = {"api-key": "test-key"}


@pytest.fixture(autouse=True)
def reset_store():
    users.clear()
    groups.clear()
    group_members.clear()
    _counters["users"] = 0
    _counters["groups"] = 0
    _request_times.clear()
    yield
    _request_times.clear()


async def _create_user(client, first="Jane", last="Smith", phones=None):
    body = {"firstName": first, "lastName": last}
    if phones:
        body["phoneNumbers"] = phones
    r = await client.post("/v1/api/users", json=body, headers=HEADERS)
    return r.json()


@pytest.mark.asyncio
async def test_latency_applied():
    with patch.dict(os.environ, {"BRIVO_LATENCY_MS": "100"}):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            start = time.monotonic()
            await c.get("/v1/api/groups", headers=HEADERS)
            elapsed = time.monotonic() - start
    assert elapsed >= 0.05


@pytest.mark.asyncio
async def test_no_latency_when_unset():
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("BRIVO_LATENCY_MS", None)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            start = time.monotonic()
            await c.get("/v1/api/groups", headers=HEADERS)
            elapsed = time.monotonic() - start
    assert elapsed < 0.05


@pytest.mark.asyncio
async def test_error_rate_1_always_returns_5xx():
    with patch.dict(os.environ, {"BRIVO_ERROR_RATE": "1.0"}):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.get("/v1/api/groups", headers=HEADERS)
    assert r.status_code in (500, 503)


@pytest.mark.asyncio
async def test_error_rate_zero_no_errors():
    with patch.dict(os.environ, {"BRIVO_ERROR_RATE": "0.0"}):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.get("/v1/api/groups", headers=HEADERS)
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_rate_limit_returns_429():
    with patch.dict(os.environ, {"BRIVO_RATE_LIMIT": "1"}):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            await c.get("/v1/api/groups", headers=HEADERS)
            r = await c.get("/v1/api/groups", headers=HEADERS)
    assert r.status_code == 429
    assert r.json()["code"] == 429


@pytest.mark.asyncio
async def test_rate_limit_unset_no_429():
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("BRIVO_RATE_LIMIT", None)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            for _ in range(5):
                r = await c.get("/v1/api/groups", headers=HEADERS)
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_partial_response_even_userid_omits_phone_numbers():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        # create two users so second has id=2 (even)
        await _create_user(
            c,
            first="A",
            last="B",
            phones=[{"number": "+15550001111", "type": "mobile"}],
        )
        await _create_user(
            c,
            first="C",
            last="D",
            phones=[{"number": "+15550002222", "type": "mobile"}],
        )
        r = await c.get("/v1/api/users/2", headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["phoneNumbers"] == []


@pytest.mark.asyncio
async def test_partial_response_odd_userid_keeps_phone_numbers():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        await _create_user(
            c,
            first="A",
            last="B",
            phones=[{"number": "+15550001111", "type": "mobile"}],
        )
        r = await c.get("/v1/api/users/1", headers=HEADERS)
    assert r.status_code == 200
    assert len(r.json()["phoneNumbers"]) == 1


@pytest.mark.asyncio
async def test_health_exempt_from_error_simulation():
    with patch.dict(os.environ, {"BRIVO_ERROR_RATE": "1.0"}):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.get("/health")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_health_exempt_from_rate_limit():
    with patch.dict(os.environ, {"BRIVO_RATE_LIMIT": "1"}):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            for _ in range(5):
                r = await c.get("/health")
    assert r.status_code == 200
