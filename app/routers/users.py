import re
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from fastapi.responses import JSONResponse

from app.brivo.client import BrivoClient, paginate_all
from app.brivo.dependencies import get_client
from app.models.common import ListResponse, PatchRequest
from app.models.user import ScimUser, ScimUserResponse
from app.brivo.fetch import fetch_user
from app.redis.store import RedisStore, get_store
from app.routers._helpers import Params, resolve_or_404
from app.services.create_user import create_user
from app.services.delete_user import delete_user
from app.services.field_mapper import brivo_user_to_scim
from app.services.update_user import update_user

router = APIRouter(prefix="/scim/v2/Users", tags=["users"])

Store = Annotated[RedisStore, Depends(get_store)]
Client = Annotated[BrivoClient, Depends(get_client)]

_FILTER_RE = re.compile(r'userName\s+eq\s+"([^"]*)"', re.IGNORECASE)


@router.post("", status_code=201)
async def post_user(
    body: ScimUser, store: Store, client: Client, response: Response
) -> ScimUserResponse:
    brivo_user, scim_id = await create_user(body, store, client)
    idmap = await store.get_by_scim("user", scim_id)
    created_at = datetime.fromisoformat(idmap["created_at"])
    location = f"/scim/v2/Users/{scim_id}"
    response.headers["Location"] = location
    return brivo_user_to_scim(brivo_user, scim_id, created_at, location)


@router.get("")
async def list_users(params: Params, store: Store, client: Client) -> JSONResponse:
    if params.filter:
        resources = await _apply_filter(params.filter, store, client)
        total = len(resources)
    else:
        page = await client.list_users(offset=params.startIndex - 1, page_size=params.count)
        resources = []
        for bu in page.data:
            if r := await _user_to_scim_response(bu, store):
                resources.append(r)
        total = page.count

    resp = ListResponse[ScimUserResponse](
        totalResults=total,
        startIndex=params.startIndex,
        itemsPerPage=len(resources),
        Resources=resources,
    )
    return JSONResponse(content=resp.model_dump(mode="json"))


@router.get("/{scim_id}")
async def get_user(scim_id: str, store: Store, client: Client) -> ScimUserResponse:
    target_id, created_at = await resolve_or_404("user", scim_id, store)

    brivo_user = await fetch_user(target_id, store, client)
    location = f"/scim/v2/Users/{scim_id}"
    return brivo_user_to_scim(brivo_user, scim_id, created_at, location)


@router.put("/{scim_id}")
async def put_user(
    scim_id: str, body: ScimUser, store: Store, client: Client
) -> ScimUserResponse:
    target_id_str, created_at = await resolve_or_404("user", scim_id, store)
    target_id = int(target_id_str)
    brivo_user = await update_user(
        target_id, body=body, patch_ops=None, store=store, client=client
    )
    location = f"/scim/v2/Users/{scim_id}"
    return brivo_user_to_scim(brivo_user, scim_id, created_at, location)


@router.patch("/{scim_id}")
async def patch_user(
    scim_id: str, body: PatchRequest, store: Store, client: Client
) -> ScimUserResponse:
    target_id_str, created_at = await resolve_or_404("user", scim_id, store)
    target_id = int(target_id_str)
    brivo_user = await update_user(
        target_id, body=None, patch_ops=body.Operations, store=store, client=client
    )
    location = f"/scim/v2/Users/{scim_id}"
    return brivo_user_to_scim(brivo_user, scim_id, created_at, location)


@router.delete("/{scim_id}", status_code=204)
async def delete_user_endpoint(scim_id: str, store: Store, client: Client) -> Response:
    await delete_user(scim_id, store, client)
    return Response(status_code=204)


async def _user_to_scim_response(bu, store: RedisStore) -> ScimUserResponse | None:
    idmap = await store.get_by_target("user", str(bu.id))
    if not idmap:
        return None
    scim_id = idmap["scim_id"]
    rec = await store.get_by_scim("user", scim_id)
    created_at = datetime.fromisoformat(rec["created_at"]) if rec else datetime.now(timezone.utc)
    return brivo_user_to_scim(bu, scim_id, created_at, f"/scim/v2/Users/{scim_id}")


async def _apply_filter(
    filter_str: str, store: RedisStore, client: BrivoClient
) -> list[ScimUserResponse]:
    m = _FILTER_RE.match(filter_str.strip())
    if not m:
        return []
    username = m.group(1).lower()
    results = []
    for bu in await paginate_all(client.list_users):
        if not bu.emails or bu.emails[0].address.lower() != username:
            continue
        if r := await _user_to_scim_response(bu, store):
            results.append(r)
    return results
