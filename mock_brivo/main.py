import asyncio
import collections
import os
import random
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Generic, TypeVar

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


def _configure_logging() -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(20),
        logger_factory=structlog.PrintLoggerFactory(),
    )


_log = structlog.get_logger()


class _RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        if request.url.path != "/health":
            _log.info(
                "http.request",
                method=request.method,
                path=request.url.path,
                status=response.status_code,
            )
        return response


# --- Inline models (no app/ imports) ---


class BrivoEmail(BaseModel):
    address: str
    type: str = "work"


class BrivoPhone(BaseModel):
    number: str
    type: str = "mobile"


class BrivoUser(BaseModel):
    id: int
    externalId: str | None = None
    firstName: str
    lastName: str
    emails: list[BrivoEmail] = []
    phoneNumbers: list[BrivoPhone] = []
    suspended: bool = False
    created: datetime
    updated: datetime


class BrivoUserIn(BaseModel):
    externalId: str | None = None
    firstName: str
    lastName: str
    emails: list[BrivoEmail] = []
    phoneNumbers: list[BrivoPhone] = []
    suspended: bool = False


class BrivoGroup(BaseModel):
    id: int
    name: str
    keypadUnlock: bool = False
    immuneToAntipassback: bool = False
    antipassbackResetTime: int = 0


class BrivoGroupIn(BaseModel):
    name: str
    keypadUnlock: bool = False
    immuneToAntipassback: bool = False
    antipassbackResetTime: int = 0


class BrivoError(BaseModel):
    code: int
    message: str


T = TypeVar("T")


class BrivoPage(BaseModel, Generic[T]):
    data: list[T]
    offset: int
    pageSize: int
    count: int


# --- In-memory store ---

users: dict[int, BrivoUser] = {}
groups: dict[int, BrivoGroup] = {}
group_members: dict[int, set[int]] = {}
_counters: dict[str, int] = {"users": 0, "groups": 0}
_request_times: collections.deque = collections.deque()


def next_id(resource: str) -> int:
    _counters[resource] += 1
    return _counters[resource]


# --- App ---


@asynccontextmanager
async def lifespan(app: FastAPI):
    _configure_logging()
    users.clear()
    groups.clear()
    group_members.clear()
    _request_times.clear()
    _counters["users"] = 0
    _counters["groups"] = 0
    now = datetime.now(timezone.utc)
    seed = BrivoUser(
        id=next_id("users"),
        externalId="seed-user-1",
        firstName="Seed",
        lastName="User",
        emails=[BrivoEmail(address="seed@example.com")],
        created=now,
        updated=now,
    )
    users[seed.id] = seed
    yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(_RequestLoggingMiddleware)


# --- Auth middleware ---


@app.middleware("http")
async def require_api_key(request: Request, call_next):
    if request.url.path == "/health":
        return await call_next(request)
    if not request.headers.get("api-key"):
        return JSONResponse(
            status_code=403, content={"code": 403, "message": "Forbidden"}
        )
    return await call_next(request)


# --- Simulation middleware ---


@app.middleware("http")
async def simulate_brivo_behavior(request: Request, call_next):
    if request.url.path == "/health":
        return await call_next(request)

    rate_limit = int(os.getenv("BRIVO_RATE_LIMIT", "0") or "0")
    if rate_limit > 0:
        now = time.monotonic()
        while _request_times and _request_times[0] < now - 1.0:
            _request_times.popleft()
        if len(_request_times) >= rate_limit:
            return JSONResponse(
                status_code=429, content={"code": 429, "message": "Rate limit exceeded"}
            )
        _request_times.append(now)

    error_rate = float(os.getenv("BRIVO_ERROR_RATE", "0") or "0")
    if error_rate > 0 and random.random() < error_rate:
        status = random.choice([500, 503])
        return JSONResponse(
            status_code=status, content={"code": status, "message": "Simulated error"}
        )

    latency_ms = int(os.getenv("BRIVO_LATENCY_MS", "0") or "0")
    if latency_ms > 0:
        min_ms = min(50, latency_ms)
        await asyncio.sleep(random.randint(min_ms, latency_ms) / 1000)

    return await call_next(request)


# --- Endpoints ---


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/v1/api/users")
async def list_users(offset: int = 0, pageSize: int = 20):
    items = list(users.values())
    page = items[offset : offset + pageSize]
    return BrivoPage[BrivoUser](
        data=page, offset=offset, pageSize=pageSize, count=len(items)
    )


@app.post("/v1/api/users")
async def create_user(body: BrivoUserIn):
    now = datetime.now(timezone.utc)
    user = BrivoUser(id=next_id("users"), created=now, updated=now, **body.model_dump(mode="python"))
    users[user.id] = user
    return user


@app.get("/v1/api/users/{userId}")
async def get_user(userId: int):
    user = users.get(userId)
    if not user:
        return JSONResponse(
            status_code=404, content={"code": 404, "message": "Not found"}
        )
    if userId % 2 == 0:
        user = user.model_copy(update={"phoneNumbers": []})
    return user


@app.put("/v1/api/users/{userId}")
async def update_user(userId: int, body: BrivoUserIn):
    user = users.get(userId)
    if not user:
        return JSONResponse(
            status_code=404, content={"code": 404, "message": "Not found"}
        )
    updated = user.model_copy(
        update={**body.model_dump(mode="python"), "updated": datetime.now(timezone.utc)}
    )
    users[userId] = updated
    return updated


@app.delete("/v1/api/users/{userId}", status_code=204)
async def delete_user(userId: int):
    if userId not in users:
        return JSONResponse(
            status_code=404, content={"code": 404, "message": "Not found"}
        )
    del users[userId]


@app.get("/v1/api/users/{userId}/groups")
async def list_user_groups(userId: int):
    if userId not in users:
        return JSONResponse(
            status_code=404, content={"code": 404, "message": "Not found"}
        )
    user_group_ids = {
        gid for gid, members in group_members.items() if userId in members
    }
    data = [
        {"id": g.id, "name": g.name} for gid in user_group_ids if (g := groups.get(gid))
    ]
    return {"count": len(data), "data": data}


@app.get("/v1/api/groups")
async def list_groups(offset: int = 0, pageSize: int = 20):
    items = list(groups.values())
    page = items[offset : offset + pageSize]
    return BrivoPage[BrivoGroup](
        data=page, offset=offset, pageSize=pageSize, count=len(items)
    )


@app.post("/v1/api/groups")
async def create_group(body: BrivoGroupIn):
    if len(body.name) > 35:
        return JSONResponse(
            status_code=400,
            content={"code": 400, "message": "name exceeds 35 characters"},
        )
    group = BrivoGroup(id=next_id("groups"), **body.model_dump())
    groups[group.id] = group
    return group


@app.get("/v1/api/groups/{groupId}")
async def get_group(groupId: int):
    group = groups.get(groupId)
    if not group:
        return JSONResponse(
            status_code=404, content={"code": 404, "message": "Not found"}
        )
    return group


@app.put("/v1/api/groups/{groupId}")
async def update_group(groupId: int, body: BrivoGroupIn):
    if groupId not in groups:
        return JSONResponse(
            status_code=404, content={"code": 404, "message": "Not found"}
        )
    if len(body.name) > 35:
        return JSONResponse(
            status_code=400,
            content={"code": 400, "message": "name exceeds 35 characters"},
        )
    groups[groupId] = BrivoGroup(id=groupId, **body.model_dump())
    return groups[groupId]


@app.delete("/v1/api/groups/{groupId}", status_code=204)
async def delete_group(groupId: int):
    if groupId not in groups:
        return JSONResponse(
            status_code=404, content={"code": 404, "message": "Not found"}
        )
    del groups[groupId]
    group_members.pop(groupId, None)


@app.get("/v1/api/groups/{groupId}/users")
async def list_group_users(groupId: int, offset: int = 0, pageSize: int = 20):
    if groupId not in groups:
        return JSONResponse(
            status_code=404, content={"code": 404, "message": "Not found"}
        )
    member_ids = group_members.get(groupId, set())
    items = [users[uid] for uid in member_ids if uid in users]
    page = items[offset : offset + pageSize]
    return BrivoPage[BrivoUser](
        data=page, offset=offset, pageSize=pageSize, count=len(items)
    )


@app.put("/v1/api/groups/{groupId}/users/{userId}", status_code=204)
async def add_user_to_group(groupId: int, userId: int):
    if groupId not in groups:
        return JSONResponse(
            status_code=404, content={"code": 404, "message": "Not found"}
        )
    if userId not in users:
        return JSONResponse(
            status_code=404, content={"code": 404, "message": "Not found"}
        )
    group_members.setdefault(groupId, set()).add(userId)


@app.delete("/v1/api/groups/{groupId}/users/{userId}", status_code=204)
async def remove_user_from_group(groupId: int, userId: int):
    if groupId not in groups:
        return JSONResponse(
            status_code=404, content={"code": 404, "message": "Not found"}
        )
    if userId not in users:
        return JSONResponse(
            status_code=404, content={"code": 404, "message": "Not found"}
        )
    group_members.get(groupId, set()).discard(userId)
