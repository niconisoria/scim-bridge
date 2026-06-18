from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

_LIST_RESPONSE_URN = "urn:ietf:params:scim:api:messages:2.0:ListResponse"
_PATCH_URN = "urn:ietf:params:scim:api:messages:2.0:PatchOp"
_ERROR_URN = "urn:ietf:params:scim:api:messages:2.0:Error"

T = TypeVar("T")


class ScimMeta(BaseModel):
    resourceType: str | None = None
    location: str | None = None
    created: str | None = None
    lastModified: str | None = None
    version: str | None = None


class ListResponse(BaseModel, Generic[T]):
    model_config = ConfigDict(extra="ignore")

    schemas: list[str] = Field(default_factory=lambda: [_LIST_RESPONSE_URN])
    totalResults: int
    startIndex: int = 1
    itemsPerPage: int
    Resources: list[T] = Field(default_factory=list)


class PatchOp(BaseModel):
    model_config = ConfigDict(extra="ignore")

    op: str
    path: str | None = None
    value: Any = None

    @field_validator("op", mode="before")
    @classmethod
    def normalize_op(cls, v: Any) -> str:
        return str(v).lower()


class PatchRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    schemas: list[str] = Field(default_factory=lambda: [_PATCH_URN])
    Operations: list[PatchOp]


class ScimError(BaseModel):
    schemas: list[str] = Field(default_factory=lambda: [_ERROR_URN])
    status: str
    detail: str | None = None
    scimType: str | None = None
