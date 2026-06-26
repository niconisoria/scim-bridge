import httpx

from app.brivo.client import BrivoClient
from app.brivo.rate_limiter import make_limiter
from app.core.config import settings


async def get_client() -> BrivoClient:
    http = httpx.AsyncClient(
        base_url=settings.brivo_base_url,
        headers={"api-key": "dev"},
    )
    return BrivoClient(http, make_limiter(settings.brivo_rate_limit))
