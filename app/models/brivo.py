from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class BrivoEmail(BaseModel):
    address: str
    type: str


class BrivoPhoneNumber(BaseModel):
    number: str
    type: str


class BrivoUser(BaseModel):
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
    externalId: str | None = None
    firstName: str
    lastName: str
    emails: list[BrivoEmail]
    phoneNumbers: list[BrivoPhoneNumber]
    suspended: bool


class BrivoGroup(BaseModel):
    id: int
    name: str = Field(max_length=35)
    keypadUnlock: bool
    immuneToAntipassback: bool
    antipassbackResetTime: int


class BrivoGroupWrite(BaseModel):
    name: str = Field(max_length=35)
    keypadUnlock: bool
    immuneToAntipassback: bool
    antipassbackResetTime: int


class BrivoGroupRef(BaseModel):
    id: int
    name: str


class BrivoPaginatedList(BaseModel, Generic[T]):
    data: list[T]
    offset: int
    pageSize: int
    count: int
