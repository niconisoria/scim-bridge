from pydantic import BaseModel, ConfigDict, Field

_SCIM_USER_URN = "urn:ietf:params:scim:schemas:core:2.0:User"


class ScimEmail(BaseModel):
    value: str
    type: str = "work"
    primary: bool = False


class ScimPhone(BaseModel):
    value: str
    type: str = "work"
    primary: bool = False


class ScimName(BaseModel):
    givenName: str | None = None
    familyName: str | None = None


class ScimMeta(BaseModel):
    resourceType: str | None = None
    location: str | None = None
    created: str | None = None
    lastModified: str | None = None
    version: str | None = None


class ScimUser(BaseModel):
    model_config = ConfigDict(extra="ignore")

    schemas: list[str] = Field(default_factory=lambda: [_SCIM_USER_URN])
    userName: str
    name: ScimName | None = None
    emails: list[ScimEmail] = Field(min_length=1)
    phoneNumbers: list[ScimPhone] | None = None
    active: bool = True
    externalId: str | None = None


class ScimUserResponse(ScimUser):
    id: str
    meta: ScimMeta
