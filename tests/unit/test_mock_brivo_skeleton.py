import pytest
from httpx import AsyncClient, ASGITransport
from mock_brivo.main import app


@pytest.mark.asyncio
async def test_health_no_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_missing_api_key_returns_403():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/v1/api/users")
    assert r.status_code == 403
    assert r.json() == {"code": 403, "message": "Forbidden"}


@pytest.mark.asyncio
async def test_api_key_header_accepted():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/v1/api/users", headers={"api-key": "any-value"})
    assert r.status_code != 403
