from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

from sqlalchemy import Boolean, Date, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column


def new_id() -> str:
    return str(uuid4())


def utc_now() -> datetime:
    return datetime.now(UTC)


class RecordMixin:
    """Auditable fields shared by every stage-2 record."""

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    currency: Mapped[str] = mapped_column(String(3), default="CNY", nullable=False)
    valuation_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    data_source: Mapped[str] = mapped_column(String(64), default="user", nullable=False)
    is_user_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
