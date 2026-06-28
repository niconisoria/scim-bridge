from unittest.mock import AsyncMock, patch

import pytest

from app.brivo.client import BrivoNotFoundError, BrivoRateLimitError, brivo_retry


@pytest.mark.asyncio
async def test_brivo_retry_retries_three_times_then_raises():
    call_count = 0

    @brivo_retry
    async def always_fails():
        nonlocal call_count
        call_count += 1
        raise BrivoRateLimitError(429, "rate limited")

    with patch("asyncio.sleep", new_callable=AsyncMock):
        with pytest.raises(BrivoRateLimitError):
            await always_fails()

    assert call_count == 4  # 1 original + 3 retries


@pytest.mark.asyncio
async def test_brivo_retry_succeeds_on_second_attempt():
    call_count = 0

    @brivo_retry
    async def fails_once():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise BrivoRateLimitError(429, "rate limited")
        return "ok"

    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await fails_once()

    assert result == "ok"
    assert call_count == 2


@pytest.mark.asyncio
async def test_brivo_retry_does_not_retry_on_not_found():
    call_count = 0

    @brivo_retry
    async def not_found():
        nonlocal call_count
        call_count += 1
        raise BrivoNotFoundError(404, "not found")

    with pytest.raises(BrivoNotFoundError):
        await not_found()

    assert call_count == 1  # no retries


@pytest.mark.asyncio
async def test_brivo_retry_does_not_catch_generic_exception():
    call_count = 0

    @brivo_retry
    async def generic_error():
        nonlocal call_count
        call_count += 1
        raise ValueError("unexpected")

    with pytest.raises(ValueError):
        await generic_error()

    assert call_count == 1  # no retries


@pytest.mark.asyncio
async def test_brivo_retry_returns_value_on_success():
    @brivo_retry
    async def success():
        return 42

    result = await success()
    assert result == 42
