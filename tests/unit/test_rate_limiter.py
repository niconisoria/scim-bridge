from unittest.mock import AsyncMock, patch

import pytest
from aiolimiter import AsyncLimiter

from app.brivo.client import BrivoNotFoundError, BrivoRateLimitError
from app.brivo.rate_limiter import brivo_retry, make_limiter


def test_make_limiter_returns_async_limiter_with_correct_max_rate():
    limiter = make_limiter(15)
    assert isinstance(limiter, AsyncLimiter)
    assert limiter.max_rate == 15


def test_make_limiter_respects_different_rates():
    assert make_limiter(5).max_rate == 5
    assert make_limiter(20).max_rate == 20


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
