from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Generic, TypeVar

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# --- Inline models (no app/ imports) ---

class BrivoEmail(BaseModel):
    address: str
    type: str = "work"


class BrivoPhone(BaseModel):
    number: str
    type: str = "mobile"


class BrivoUser(BaseModel):
    id: int
    firstName: str
    lastName: str
    emails: list[BrivoEmail] = []
    phoneNumbers: list[BrivoPhone] = []
    suspended: bool = False
    created: datetime
    updated: datetime


class BrivoGroup(BaseModel):
    id: int
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
_counters: dict[str, int] = {"users": 0, "groups": 0}


def next_id(resource: str) -> int:
    _counters[resource] += 1
    return _counters[resource]


# --- App ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    users.clear()
    groups.clear()
    _counters["users"] = 0
    _counters["groups"] = 0
    yield


app = FastAPI(lifespan=lifespan)


# --- Auth middleware ---

@app.middleware("http")
async def require_api_key(request: Request, call_next):
    if request.url.path == "/health":
        return await call_next(request)
    if not request.headers.get("api-key"):
        return JSONResponse(status_code=403, content={"code": 403, "message": "Forbidden"})
    return await call_next(request)


# --- Endpoints ---

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/v1/api/users")
async def list_users(offset: int = 0, pageSize: int = 20):
    items = list(users.values())
    page = items[offset: offset + pageSize]
    return BrivoPage[BrivoUser](data=page, offset=offset, pageSize=pageSize, count=len(items))


@app.get("/v1/api/groups")
async def list_groups(offset: int = 0, pageSize: int = 20):
    items = list(groups.values())
    page = items[offset: offset + pageSize]
    return BrivoPage[BrivoGroup](data=page, offset=offset, pageSize=pageSize, count=len(items))
