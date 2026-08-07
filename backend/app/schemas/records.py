from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field


def reject_binary_float(value: object) -> object:
    if isinstance(value, float):
        raise ValueError("货币金额必须使用十进制字符串或整数，不能使用二进制浮点数")
    return value


Money = Annotated[
    Decimal,
    BeforeValidator(reject_binary_float),
    Field(ge=0, max_digits=20, decimal_places=2),
]
Ratio = Annotated[Decimal, Field(ge=0, le=1, max_digits=9, decimal_places=6)]
SignedRatio = Annotated[Decimal, Field(ge=-1, le=1, max_digits=9, decimal_places=6)]


class RecordInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    currency: str = Field(default="CNY", pattern=r"^[A-Z]{3}$")
    valuation_date: date | None = None
    data_source: str = Field(default="user", min_length=1, max_length=64)
    is_user_confirmed: bool = False


class RecordUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    valuation_date: date | None = None
    data_source: str | None = Field(default=None, min_length=1, max_length=64)
    is_user_confirmed: bool | None = None


class RecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    currency: str
    valuation_date: date | None
    data_source: str
    is_user_confirmed: bool
    version: int
    created_at: datetime
    updated_at: datetime
    is_deleted: bool
    deleted_at: datetime | None


class Pagination(BaseModel):
    page: int
    page_size: int
    total: int
    pages: int


class PageResponse[PageItem](BaseModel):
    items: list[PageItem]
    pagination: Pagination
