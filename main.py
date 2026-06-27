from fastapi import FastAPI, Request

from app.core.auth import BearerTokenMiddleware
from app.core.errors import ScimBadRequest, ScimConflict, ScimNotFound, scim_error
from app.routers.discovery import router as discovery_router
from app.routers.groups import router as groups_router
from app.routers.users import router as users_router
from app.services.saga import SagaError

app = FastAPI()
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
    return scim_error(500, str(exc))
