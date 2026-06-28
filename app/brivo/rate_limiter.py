from aiolimiter import AsyncLimiter


def make_limiter(max_rate: int) -> AsyncLimiter:
    return AsyncLimiter(max_rate=max_rate, time_period=1)
