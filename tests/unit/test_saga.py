from unittest.mock import AsyncMock

import pytest

from app.services.saga import SagaError, Step, run_saga


@pytest.mark.asyncio
async def test_all_steps_called_in_order():
    calls = []

    async def s1():
        calls.append(1)

    async def s2():
        calls.append(2)

    async def s3():
        calls.append(3)

    await run_saga([Step("s1", s1), Step("s2", s2), Step("s3", s3)])
    assert calls == [1, 2, 3]


@pytest.mark.asyncio
async def test_success_returns_none():
    result = await run_saga([Step("s1", AsyncMock())])
    assert result is None


@pytest.mark.asyncio
async def test_failure_triggers_reverse_rollback():
    rollbacks = []

    async def rb1():
        rollbacks.append("rb1")

    async def rb2():
        rollbacks.append("rb2")

    async def fail():
        raise ValueError("boom")

    with pytest.raises(SagaError):
        await run_saga(
            [
                Step("s1", AsyncMock(), rb1),
                Step("s2", AsyncMock(), rb2),
                Step("s3", fail),
            ]
        )

    assert rollbacks == ["rb2", "rb1"]


@pytest.mark.asyncio
async def test_none_rollback_skipped():
    rollbacks = []

    async def rb():
        rollbacks.append("rb")

    async def fail():
        raise ValueError("boom")

    with pytest.raises(SagaError):
        await run_saga(
            [
                Step("s1", AsyncMock(), rb),
                Step("s2", AsyncMock()),
                Step("s3", fail),
            ]
        )

    assert rollbacks == ["rb"]


@pytest.mark.asyncio
async def test_rollback_error_continues_remaining():
    rollbacks = []

    async def rb_fail():
        raise RuntimeError("rollback crash")

    async def rb_ok():
        rollbacks.append("ok")

    async def fail():
        raise ValueError("boom")

    with pytest.raises(SagaError):
        await run_saga(
            [
                Step("s1", AsyncMock(), rb_ok),
                Step("s2", AsyncMock(), rb_fail),
                Step("s3", fail),
            ]
        )

    assert rollbacks == ["ok"]


@pytest.mark.asyncio
async def test_failed_step_rollback_is_called():
    rollbacks = []

    async def rb():
        rollbacks.append("rb")

    async def fail():
        raise ValueError("boom")

    with pytest.raises(SagaError):
        await run_saga([Step("s1", fail, rb)])

    assert rollbacks == ["rb"]


@pytest.mark.asyncio
async def test_saga_error_carries_saga_id_and_step_name():
    async def fail():
        raise ValueError("boom")

    with pytest.raises(SagaError) as exc_info:
        await run_saga([Step("my-step", fail)])

    err = exc_info.value
    assert err.failed_step == "my-step"
    assert err.saga_id is not None
    assert len(err.saga_id) == 36
