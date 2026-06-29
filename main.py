from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request

from aiolimiter import AsyncLimiter

from app.brivo.client import BrivoClient, BrivoError
from app.core.auth import BearerTokenMiddleware
from app.core.config import settings
from app.core.logging import RequestLoggingMiddleware, configure_logging, get_logger
from app.core.errors import ScimBadRequest, ScimConflict, ScimNotFound, scim_error
from app.redis.store import get_redis
from app.routers.discovery import router as discovery_router
from app.routers.groups import router as groups_router
from app.routers.users import router as users_router
from app.services.saga import SagaError


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    http = httpx.AsyncClient(
        base_url=settings.brivo_base_url,
        headers={"api-key": "dev"},
    )
    app.state.brivo_client = BrivoClient(
        http, AsyncLimiter(max_rate=settings.brivo_rate_limit, time_period=1)
    )
    yield
    await http.aclose()
    await get_redis().aclose()


app = FastAPI(lifespan=lifespan)


app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(BearerTokenMiddleware)
app.include_router(discovery_router)
app.include_router(users_router)
app.include_router(groups_router)


@app.exception_handler(ScimNotFound)
async def _not_found(request: Request, exc: ScimNotFound):
    return scim_error(404, exc.detail)


@app.exception_handler(ScimBadRequest)
async def _bad_request(request: Request, exc: ScimBadRequest):
    return scim_error(400, exc.detail)


@app.exception_handler(ScimConflict)
async def _conflict(request: Request, exc: ScimConflict):
    return scim_error(409, exc.detail)


@app.exception_handler(SagaError)
async def _saga_error(request: Request, exc: SagaError):
    get_logger().error("saga.error", method=request.method, path=request.url.path, error=str(exc))
    return scim_error(500, str(exc))


@app.exception_handler(BrivoError)
async def _brivo_error(request: Request, exc: BrivoError):
    get_logger().error("brivo.error", method=request.method, path=request.url.path, brivo_status=exc.status_code, error=str(exc))
    return scim_error(502, str(exc))
