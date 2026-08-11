from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, Date, Enum, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.enums import CalibrationMode
from app.models.base import Base
from app.models.common import RecordMixin


class CalibrationDataset(RecordMixin, Base):
    __tablename__ = "calibration_datasets"
    __table_args__ = (
        UniqueConstraint("code", "source_version", name="uq_calibration_dataset_code_version"),
    )

    code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    mode: Mapped[CalibrationMode] = mapped_column(
        Enum(CalibrationMode, native_enum=False, length=32), nullable=False, index=True
    )
    source: Mapped[str] = mapped_column(String(240), nullable=False)
    source_reference: Mapped[str] = mapped_column(String(600), nullable=False)
    population: Mapped[str] = mapped_column(String(240), nullable=False)
    sample_period: Mapped[str] = mapped_column(String(160), nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    source_version: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    license_or_access_note: Mapped[str] = mapped_column(Text, nullable=False)
    limitations: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    data_quality: Mapped[str] = mapped_column(String(100), nullable=False)


class CalibrationParameter(RecordMixin, Base):
    __tablename__ = "calibration_parameters"
    __table_args__ = (
        UniqueConstraint(
            "dataset_id",
            "parameter_code",
            "segment",
            "region",
            "effective_from",
            "parameter_version",
            name="uq_calibration_parameter_scope_version",
        ),
    )

    dataset_id: Mapped[str] = mapped_column(
        ForeignKey("calibration_datasets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parameter_code: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    value: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    lower_bound: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    upper_bound: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    estimation_method: Mapped[str] = mapped_column(String(240), nullable=False)
    segment: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    region: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    parameter_version: Mapped[str] = mapped_column(String(120), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    limitations: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    metadata_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
