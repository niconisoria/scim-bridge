from aiolimiter import AsyncLimiter
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from app.brivo.client import BrivoRateLimitError


def make_limiter(max_rate: int) -> AsyncLimiter:
    return AsyncLimiter(max_rate=max_rate, time_period=1)


brivo_retry = retry(
    retry=retry_if_exception_type(BrivoRateLimitError),
    wait=wait_fixed(1),
    stop=stop_after_attempt(4),
    reraise=True,
)
