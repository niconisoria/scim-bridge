from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class BrivoEmail(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    address: str
    type: str


class BrivoPhoneNumber(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    number: str
    type: str


class BrivoUser(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: int
    externalId: str | None = None
    firstName: str
    lastName: str
    emails: list[BrivoEmail]
    phoneNumbers: list[BrivoPhoneNumber]
    suspended: bool
    created: datetime
    updated: datetime


class BrivoUserWrite(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    externalId: str | None = None
    firstName: str
    lastName: str
    emails: list[BrivoEmail]
    phoneNumbers: list[BrivoPhoneNumber]
    suspended: bool


class BrivoGroup(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: int
    name: str = Field(max_length=35)
    keypadUnlock: bool
    immuneToAntipassback: bool
    antipassbackResetTime: int


class BrivoGroupWrite(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(max_length=35)
    keypadUnlock: bool
    immuneToAntipassback: bool
    antipassbackResetTime: int


class BrivoGroupRef(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: int
    name: str


class BrivoPaginatedList(BaseModel, Generic[T]):
    model_config = ConfigDict(populate_by_name=True)

    data: list[T]
    offset: int
    pageSize: int
    count: int
