from app.models.brivo import (
    BrivoEmail,
    BrivoGroupWrite,
    BrivoPhoneNumber,
    BrivoUserWrite,
)
from app.models.group import ScimGroup
from app.models.user import ScimUser


def scim_user_to_brivo(user: ScimUser) -> BrivoUserWrite:
    primary_email = next((e for e in user.emails if e.primary), user.emails[0])
    phones = user.phoneNumbers or []
    primary_phone = next(
        (p for p in phones if p.primary), phones[0] if phones else None
    )

    return BrivoUserWrite(
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
