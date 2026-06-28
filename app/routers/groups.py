import re
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import JSONResponse

from app.brivo.client import BrivoClient, paginate_all
from app.brivo.dependencies import get_client
from app.core.errors import ScimNotFound
from app.models.brivo import BrivoGroup, BrivoGroupWrite
from app.models.common import ListResponse, PatchOp, PatchRequest
from app.models.group import ScimGroup, ScimGroupResponse
from app.redis.store import RedisStore, get_store
from app.services.add_members import add_members
from app.services.create_group import create_group
from app.services.delete_group import delete_group
from app.services.field_mapper import brivo_group_to_scim, hydrate_members
from app.services.remove_members import remove_members
from app.services.update_group import update_group

router = APIRouter(prefix="/scim/v2/Groups", tags=["groups"])

Store = Annotated[RedisStore, Depends(get_store)]
Client = Annotated[BrivoClient, Depends(get_client)]

_FILTER_RE = re.compile(r'displayName\s+eq\s+"([^"]*)"', re.IGNORECASE)


@router.post("", status_code=201)
async def post_group(
    body: ScimGroup, store: Store, client: Client, response: Response
) -> ScimGroupResponse:
    brivo_group, scim_id = await create_group(body, store, client)
    idmap = await store.get_by_scim("group", scim_id)
    created_at = datetime.fromisoformat(idmap["created_at"])
    location = f"/scim/v2/Groups/{scim_id}"
    response.headers["Location"] = location
    return brivo_group_to_scim(
        brivo_group, scim_id, list(body.members), created_at, location
    )


@router.get("")
async def list_groups(
    store: Store,
    client: Client,
    startIndex: int = Query(default=1, ge=1),
    count: int = Query(default=100, ge=0),
    filter: str | None = Query(default=None),
) -> JSONResponse:
    if filter:
        resources = await _apply_filter(filter, store, client)
        total = len(resources)
    else:
        page = await client.list_groups(offset=startIndex - 1, page_size=count)
        resources = []
        for bg in page.data:
            idmap = await store.get_by_target("group", str(bg.id))
            if not idmap:
                continue
            scim_id = idmap["scim_id"]
            rec = await store.get_by_scim("group", scim_id)
            created_at = (
                datetime.fromisoformat(rec["created_at"])
                if rec
                else datetime.now(timezone.utc)
            )
            location = f"/scim/v2/Groups/{scim_id}"
            cached_members = await store.cache_get("group", str(bg.id), "members")
            members = await hydrate_members(cached_members or [], store)
            resources.append(
                brivo_group_to_scim(bg, scim_id, members, created_at, location)
            )
        total = page.count

    resp = ListResponse[ScimGroupResponse](
        totalResults=total,
        startIndex=startIndex,
        itemsPerPage=len(resources),
        Resources=resources,
    )
    return JSONResponse(content=resp.model_dump(mode="json"))


@router.get("/{scim_id}")
async def get_group(scim_id: str, store: Store, client: Client) -> ScimGroupResponse:
    idmap = await store.get_by_scim("group", scim_id)
    if not idmap:
        raise ScimNotFound(f"Group {scim_id!r} not found")
    target_id = idmap["target_id"]
    created_at = datetime.fromisoformat(idmap["created_at"])
    return await _fetch_group_response(scim_id, target_id, created_at, store, client)


@router.put("/{scim_id}")
async def put_group(
    scim_id: str, body: ScimGroup, store: Store, client: Client
) -> ScimGroupResponse:
    idmap = await store.get_by_scim("group", scim_id)
    if not idmap:
        raise ScimNotFound(f"Group {scim_id!r} not found")
    target_id = idmap["target_id"]
    created_at = datetime.fromisoformat(idmap["created_at"])
    await update_group(int(target_id), scim_id, body, store, client)
    return await _fetch_group_response(scim_id, target_id, created_at, store, client)


@router.patch("/{scim_id}")
async def patch_group(
    scim_id: str, body: PatchRequest, store: Store, client: Client
) -> ScimGroupResponse:
    idmap = await store.get_by_scim("group", scim_id)
    if not idmap:
        raise ScimNotFound(f"Group {scim_id!r} not found")
    target_id = idmap["target_id"]
    created_at = datetime.fromisoformat(idmap["created_at"])

    for op in body.Operations:
        if op.op == "replace":
            await _patch_replace(int(target_id), op, store, client)
        elif op.op == "add":
            await add_members(
                int(target_id), _extract_member_ids(op.value), store, client
            )
        elif op.op == "remove":
            await remove_members(
                int(target_id), _extract_member_ids(op.value), store, client
            )

    return await _fetch_group_response(scim_id, target_id, created_at, store, client)


@router.delete("/{scim_id}", status_code=204)
async def delete_group_endpoint(scim_id: str, store: Store, client: Client) -> Response:
    await delete_group(scim_id, store, client)
    return Response(status_code=204)


async def _fetch_group_response(
    scim_id: str,
    target_id: str,
    created_at: datetime,
    store: RedisStore,
    client: BrivoClient,
) -> ScimGroupResponse:
    cached = await store.cache_get("group", target_id)
    if cached:
        brivo_group = BrivoGroup.model_validate(cached)
    else:
        brivo_group = await client.get_group(int(target_id))
        await store.cache_set(
            "group", target_id, value=brivo_group.model_dump(mode="json")
        )

    cached_members = await store.cache_get("group", target_id, "members")
    if cached_members is not None:
        target_ids = cached_members
    else:
        page = await client.list_group_users(int(target_id), page_size=200)
        target_ids = [u.id for u in page.data]
        await store.cache_set("group", target_id, "members", value=target_ids)

    members = await hydrate_members(target_ids, store)
    location = f"/scim/v2/Groups/{scim_id}"
    return brivo_group_to_scim(brivo_group, scim_id, members, created_at, location)


async def _patch_replace(
    target_id: int, op: PatchOp, store: RedisStore, client: BrivoClient
) -> None:
    cached = await store.cache_get("group", str(target_id))
    if cached:
        current = BrivoGroup.model_validate(cached)
    else:
        current = await client.get_group(target_id)

    if op.path == "displayName":
        new_name = op.value
    else:
        value = op.value or {}
        new_name = (
            value.get("displayName", current.name)
            if isinstance(value, dict)
            else current.name
        )

    write = BrivoGroupWrite(
        name=new_name,
        keypadUnlock=current.keypadUnlock,
        immuneToAntipassback=current.immuneToAntipassback,
        antipassbackResetTime=current.antipassbackResetTime,
    )
    await client.update_group(target_id, write)
    await store.cache_del("group", str(target_id))


def _extract_member_ids(value: Any) -> list[str]:
    if not value or not isinstance(value, list):
        return []
    return [
        item["value"] for item in value if isinstance(item, dict) and "value" in item
    ]


async def _apply_filter(
    filter_str: str, store: RedisStore, client: BrivoClient
) -> list[ScimGroupResponse]:
    m = _FILTER_RE.match(filter_str.strip())
    if not m:
        return []
    display_name = m.group(1).lower()

    all_groups: list[BrivoGroup] = await paginate_all(client.list_groups)

    results: list[ScimGroupResponse] = []
    for bg in all_groups:
        if bg.name.lower() != display_name:
            continue
        idmap = await store.get_by_target("group", str(bg.id))
        if not idmap:
            continue
        scim_id = idmap["scim_id"]
        rec = await store.get_by_scim("group", scim_id)
        created_at = (
            datetime.fromisoformat(rec["created_at"])
            if rec
            else datetime.now(timezone.utc)
        )
        cached_members = await store.cache_get("group", str(bg.id), "members")
        members = await hydrate_members(cached_members or [], store)
        location = f"/scim/v2/Groups/{scim_id}"
        results.append(brivo_group_to_scim(bg, scim_id, members, created_at, location))
    return results
