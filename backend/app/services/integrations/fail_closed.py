from __future__ import annotations

from dataclasses import dataclass

from app.core.errors import AppError
from app.schemas.integrations import (
    IntegrationCapabilityCode,
    IntegrationRequest,
    IntegrationResult,
)


@dataclass(frozen=True)
class UnavailableProductionAdapter:
    """Default binding for every bank-private capability.

    It deliberately has no HTTP transport or credentials. A bank deployment
    must replace it with an independently reviewed adapter through the port.
    """

    capability: IntegrationCapabilityCode
    prerequisites: tuple[str, ...]
    adapter_id: str = "unavailable-production-adapter"
    adapter_version: str = "fail-closed-v1.0.0"
    is_live: bool = False

    def execute(self, request: IntegrationRequest) -> IntegrationResult:
        del request
        raise AppError(
            "external_integration_unavailable",
            "该能力需要银行授权系统或受控生产数据，当前未接入，禁止生成替代事实",
            status_code=503,
            details={
                "capability": self.capability,
                "adapter_id": self.adapter_id,
                "required_prerequisites": list(self.prerequisites),
                "mock_substitution_allowed": False,
            },
        )
