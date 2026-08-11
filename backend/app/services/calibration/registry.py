from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import date
from functools import lru_cache
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.domain.enums import CalibrationMode
from app.models.calibration import CalibrationDataset, CalibrationParameter
from app.schemas.calibration import (
    CalibrationCatalogResponse,
    CalibrationDatasetOut,
    CalibrationModeAvailability,
    CalibrationParameterResolution,
    CalibrationRegistrySeed,
)

_MODE_PRIORITY = {
    CalibrationMode.CONTROLLED_DEMO: 1,
    CalibrationMode.EMPIRICALLY_CALIBRATED: 2,
    CalibrationMode.BANK_AUTHORIZED: 3,
}


def resolve_calibration_registry_path(configured_path: str) -> Path:
    configured = Path(configured_path)
    candidates = [configured]
    if not configured.is_absolute():
        candidates.append(
            Path(__file__).resolve().parents[4] / "data/calibration/china_purchasing_power_v1.json"
        )
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise AppError(
        "calibration_registry_missing",
        "找不到中国本地化校准注册表",
        status_code=500,
        details={"configured_path": configured_path},
    )


@lru_cache(maxsize=8)
def load_calibration_registry(configured_path: str) -> CalibrationRegistrySeed:
    path = resolve_calibration_registry_path(configured_path)
    try:
        return CalibrationRegistrySeed.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise AppError(
            "calibration_registry_invalid",
            "校准注册表未通过结构、边界或唯一性校验",
            status_code=500,
        ) from exc


def ensure_calibration_registry(
    session: Session,
    registry: CalibrationRegistrySeed,
) -> list[CalibrationDataset]:
    existing_datasets = {
        (item.code, item.source_version): item
        for item in session.scalars(
            select(CalibrationDataset).where(CalibrationDataset.is_deleted.is_(False))
        )
    }
    records: list[CalibrationDataset] = []
    for dataset_seed in registry.datasets:
        key = (dataset_seed.code, dataset_seed.version)
        dataset = existing_datasets.get(key)
        values = {
            "code": dataset_seed.code,
            "mode": dataset_seed.mode,
            "source": dataset_seed.source,
            "source_reference": dataset_seed.source_reference,
            "population": dataset_seed.population,
            "sample_period": dataset_seed.sample_period,
            "effective_date": dataset_seed.effective_date,
            "source_version": dataset_seed.version,
            "license_or_access_note": dataset_seed.license_or_access_note,
            "limitations": dataset_seed.limitations,
            "data_quality": dataset_seed.data_quality,
            "valuation_date": dataset_seed.effective_date,
            "data_source": f"calibration:{dataset_seed.mode.value}",
            "is_user_confirmed": dataset_seed.mode == CalibrationMode.BANK_AUTHORIZED,
        }
        if dataset is None:
            dataset = CalibrationDataset(**values)
            session.add(dataset)
            session.flush()
        else:
            changed = any(getattr(dataset, name) != value for name, value in values.items())
            if changed:
                for name, value in values.items():
                    setattr(dataset, name, value)
                dataset.version += 1
        records.append(dataset)

        existing_parameters = {
            (
                item.parameter_code,
                item.segment,
                item.region,
                item.effective_from,
                item.parameter_version,
            ): item
            for item in session.scalars(
                select(CalibrationParameter).where(
                    CalibrationParameter.dataset_id == dataset.id,
                    CalibrationParameter.is_deleted.is_(False),
                )
            )
        }
        for parameter_seed in dataset_seed.parameters:
            parameter_key = (
                parameter_seed.code,
                parameter_seed.segment,
                parameter_seed.region,
                parameter_seed.effective_from,
                parameter_seed.version,
            )
            parameter = existing_parameters.get(parameter_key)
            parameter_values = {
                "dataset_id": dataset.id,
                "parameter_code": parameter_seed.code,
                "value": parameter_seed.value,
                "lower_bound": parameter_seed.lower_bound,
                "upper_bound": parameter_seed.upper_bound,
                "estimation_method": parameter_seed.estimation_method,
                "segment": parameter_seed.segment,
                "region": parameter_seed.region,
                "effective_from": parameter_seed.effective_from,
                "effective_to": parameter_seed.effective_to,
                "parameter_version": parameter_seed.version,
                "confidence": parameter_seed.confidence,
                "limitations": parameter_seed.limitations,
                "metadata_snapshot": parameter_seed.metadata,
                "valuation_date": parameter_seed.effective_from,
                "data_source": f"calibration:{dataset_seed.mode.value}",
                "is_user_confirmed": dataset_seed.mode == CalibrationMode.BANK_AUTHORIZED,
            }
            if parameter is None:
                session.add(CalibrationParameter(**parameter_values))
            else:
                changed = any(
                    getattr(parameter, name) != value for name, value in parameter_values.items()
                )
                if changed:
                    for name, value in parameter_values.items():
                        setattr(parameter, name, value)
                    parameter.version += 1
    session.flush()
    return records


def _unresolved(
    code: str,
    segment: str,
    region: str,
    on_date: date,
    allowed_modes: tuple[CalibrationMode, ...],
) -> CalibrationParameterResolution:
    mode_names = ", ".join(item.value for item in allowed_modes)
    return CalibrationParameterResolution(
        parameter_id=f"unresolved:{code}:{segment}:{region}:{on_date.isoformat()}",
        code=code,
        value=None,
        segment=segment,
        region=region,
        mode=None,
        status="needs_review",
        source="not_available",
        source_reference="not_available",
        version="unresolved",
        method="none",
        confidence=0,
        limitations=[
            f"在 {on_date.isoformat()} 未找到模式 [{mode_names}] 下有效且口径匹配的参数。",
            "必须补充经验证参数或显式保留降级状态，禁止静默猜测。",
        ],
        reason="missing_verified_parameter",
    )


class DatabaseCalibrationPort:
    def __init__(
        self,
        session: Session,
        registry_version: str,
        *,
        allowed_modes: Iterable[CalibrationMode] | None = None,
    ) -> None:
        self.session = session
        self.registry_version = registry_version
        self.allowed_modes = tuple(allowed_modes or tuple(CalibrationMode))

    def get_parameter(
        self,
        code: str,
        segment: str,
        region: str,
        on_date: date,
    ) -> CalibrationParameterResolution:
        rows = (
            self.session.execute(
                select(CalibrationParameter, CalibrationDataset)
                .join(
                    CalibrationDataset,
                    CalibrationDataset.id == CalibrationParameter.dataset_id,
                )
                .where(
                    CalibrationParameter.parameter_code == code,
                    CalibrationParameter.is_deleted.is_(False),
                    CalibrationDataset.is_deleted.is_(False),
                    CalibrationDataset.mode.in_(self.allowed_modes),
                    CalibrationDataset.effective_date <= on_date,
                    CalibrationParameter.effective_from <= on_date,
                    (
                        CalibrationParameter.effective_to.is_(None)
                        | (CalibrationParameter.effective_to >= on_date)
                    ),
                    CalibrationParameter.segment.in_((segment, "all")),
                    CalibrationParameter.region.in_((region, "CN", "all")),
                )
            )
            .tuples()
            .all()
        )
        if not rows:
            return _unresolved(code, segment, region, on_date, self.allowed_modes)

        def rank(
            row: tuple[CalibrationParameter, CalibrationDataset],
        ) -> tuple[int, int, int, date, str]:
            parameter, dataset = row
            return (
                _MODE_PRIORITY[dataset.mode],
                int(parameter.region == region),
                int(parameter.segment == segment),
                parameter.effective_from,
                parameter.parameter_version,
            )

        parameter, dataset = max(rows, key=rank)
        controlled = dataset.mode == CalibrationMode.CONTROLLED_DEMO
        limitations = [*dataset.limitations, *parameter.limitations]
        return CalibrationParameterResolution(
            parameter_id=parameter.id,
            code=parameter.parameter_code,
            value=parameter.value,
            lower_bound=parameter.lower_bound,
            upper_bound=parameter.upper_bound,
            segment=parameter.segment,
            region=parameter.region,
            mode=dataset.mode,
            status="degraded" if controlled else "available",
            source=dataset.source,
            source_reference=dataset.source_reference,
            version=parameter.parameter_version,
            method=parameter.estimation_method,
            confidence=parameter.confidence,
            limitations=limitations,
            effective_from=parameter.effective_from,
            effective_to=parameter.effective_to,
            dataset_code=dataset.code,
            reason=(
                "controlled_demo_parameter_requires_review"
                if controlled
                else "verified_parameter_resolved"
            ),
        )


def build_database_calibration_port(
    session: Session,
    configured_path: str,
    *,
    allowed_modes: Iterable[CalibrationMode] | None = None,
) -> DatabaseCalibrationPort:
    registry = load_calibration_registry(configured_path)
    ensure_calibration_registry(session, registry)
    return DatabaseCalibrationPort(
        session,
        registry.registry_version,
        allowed_modes=allowed_modes,
    )


def build_calibration_catalog(
    session: Session,
    configured_path: str,
) -> CalibrationCatalogResponse:
    registry = load_calibration_registry(configured_path)
    datasets = ensure_calibration_registry(session, registry)
    parameters = list(
        session.scalars(
            select(CalibrationParameter).where(CalibrationParameter.is_deleted.is_(False))
        )
    )
    counts_by_dataset: dict[str, int] = {}
    for item in parameters:
        counts_by_dataset[item.dataset_id] = counts_by_dataset.get(item.dataset_id, 0) + 1
    dataset_out = [
        CalibrationDatasetOut(
            id=item.id,
            code=item.code,
            mode=item.mode,
            source=item.source,
            source_reference=item.source_reference,
            population=item.population,
            sample_period=item.sample_period,
            effective_date=item.effective_date,
            version=item.source_version,
            license_or_access_note=item.license_or_access_note,
            limitations=item.limitations,
            data_quality=item.data_quality,
            parameter_count=counts_by_dataset.get(item.id, 0),
        )
        for item in sorted(datasets, key=lambda value: (value.mode.value, value.code))
    ]
    modes: list[CalibrationModeAvailability] = []
    for mode in CalibrationMode:
        matching = [item for item in dataset_out if item.mode == mode]
        available = bool(matching)
        note = {
            CalibrationMode.CONTROLLED_DEMO: "仅用于受控演示，所有输出均标记降级。",
            CalibrationMode.EMPIRICALLY_CALIBRATED: "来自已验证公开快照，仍受样本期与口径限制。",
            CalibrationMode.BANK_AUTHORIZED: (
                "需银行合同、客户授权与生产凭据；当前没有可用数据。"
                if not available
                else "已绑定银行授权数据。"
            ),
        }[mode]
        modes.append(
            CalibrationModeAvailability(
                mode=mode,
                available=available,
                dataset_count=len(matching),
                parameter_count=sum(item.parameter_count for item in matching),
                note=note,
            )
        )
    return CalibrationCatalogResponse(
        registry_version=registry.registry_version,
        datasets=dataset_out,
        modes=modes,
    )
