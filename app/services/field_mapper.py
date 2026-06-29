import hashlib
import json
from datetime import datetime

from app.models.brivo import (
    BrivoEmail,
    BrivoGroup,
    BrivoGroupWrite,
    BrivoPhoneNumber,
    BrivoUser,
    BrivoUserWrite,
)
from app.models.common import ScimMeta
from app.models.group import ScimGroup, ScimGroupResponse, ScimMember
from app.models.user import ScimEmail, ScimName, ScimPhone, ScimUser, ScimUserResponse
from app.redis.store import RedisStore


def scim_user_to_brivo(user: ScimUser) -> BrivoUserWrite:
    primary_email = next((e for e in user.emails if e.primary), user.emails[0])
    phones = user.phoneNumbers or []
    primary_phone = next(
        (p for p in phones if p.primary), phones[0] if phones else None
    )

    return BrivoUserWrite(
        externalId=user.externalId,
        firstName=user.name.givenName if user.name else "",
        lastName=user.name.familyName if user.name else "",
        emails=[BrivoEmail(address=primary_email.value, type=primary_email.type)],
        phoneNumbers=(
            [BrivoPhoneNumber(number=primary_phone.value, type=primary_phone.type)]
            if primary_phone
            else []
        ),
        suspended=not user.active,
    )


def scim_group_to_brivo(group: ScimGroup) -> BrivoGroupWrite:
    if len(group.displayName) > 35:
        raise ValueError("Group displayName exceeds Brivo's 35-character limit")
    return BrivoGroupWrite(
        name=group.displayName,
        keypadUnlock=False,
        immuneToAntipassback=False,
        antipassbackResetTime=0,
    )


def _version_hash(model: BrivoUser | BrivoGroup) -> str:
    return hashlib.sha256(
        json.dumps(model.model_dump(mode="json"), sort_keys=True).encode()
    ).hexdigest()


def brivo_user_to_scim(
    user: BrivoUser,
    scim_id: str,
    created_at: datetime,
    location: str | None = None,
) -> ScimUserResponse:
    return ScimUserResponse(
        id=scim_id,
        userName=user.emails[0].address if user.emails else "",
        name=ScimName(givenName=user.firstName, familyName=user.lastName),
        emails=[
            ScimEmail(value=e.address, type=e.type, primary=(i == 0))
            for i, e in enumerate(user.emails)
        ],
        phoneNumbers=[
            ScimPhone(value=p.number, type=p.type, primary=(i == 0))
            for i, p in enumerate(user.phoneNumbers)
        ],
        active=not user.suspended,
        meta=ScimMeta(
            resourceType="User",
            location=location,
            created=created_at.isoformat(),
            lastModified=user.updated.isoformat(),
            version=_version_hash(user),
        ),
    )


async def hydrate_members(target_ids: list[int], store: RedisStore) -> list[ScimMember]:
    members = []
    for tid in target_ids:
        record = await store.get_by_target("user", str(tid))
        if record:
            members.append(ScimMember(value=record["scim_id"]))
    return members


def brivo_group_to_scim(
    group: BrivoGroup,
    scim_id: str,
    members: list[ScimMember],
    created_at: datetime,
    location: str | None = None,
) -> ScimGroupResponse:
    return ScimGroupResponse(
        id=scim_id,
        displayName=group.name,
        members=members,
        meta=ScimMeta(
            resourceType="Group",
            location=location,
            created=created_at.isoformat(),
            lastModified=None,
            version=_version_hash(group),
        ),
    )
