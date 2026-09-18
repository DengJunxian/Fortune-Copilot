from __future__ import annotations

from datetime import date
from typing import Protocol

from app.schemas.calibration import CalibrationParameterResolution


class CalibrationPort(Protocol):
    registry_version: str

    def get_parameter(
        self,
        code: str,
        segment: str,
        region: str,
        on_date: date,
    ) -> CalibrationParameterResolution: ...


class UnavailableCalibrationPort:
    registry_version = "calibration-not-enabled"

    def get_parameter(
        self,
        code: str,
        segment: str,
        region: str,
        on_date: date,
    ) -> CalibrationParameterResolution:
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
            version=self.registry_version,
            method="none",
            confidence=0,
            limitations=[
                "校准功能未启用或未绑定参数。",
                "当前结果只能保留为明确降级状态，禁止解释为经验校准或银行授权。",
            ],
            reason="calibration_not_enabled",
        )
