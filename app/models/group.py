from pydantic import BaseModel, ConfigDict, Field

from app.models.user import ScimMeta

_SCIM_GROUP_URN = "urn:ietf:params:scim:schemas:core:2.0:Group"


class ScimMember(BaseModel):
    value: str
    display: str | None = None


class ScimGroup(BaseModel):
    model_config = ConfigDict(extra="ignore")

    schemas: list[str] = Field(default_factory=lambda: [_SCIM_GROUP_URN])
    displayName: str = Field(max_length=35)
    members: list[ScimMember] = Field(default_factory=list)
    externalId: str | None = None


class ScimGroupResponse(ScimGroup):
    id: str
    meta: ScimMeta
