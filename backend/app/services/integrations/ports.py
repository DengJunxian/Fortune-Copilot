from __future__ import annotations

from typing import Protocol

from app.schemas.integrations import (
    IntegrationCapabilityCode,
    IntegrationRequest,
    IntegrationResult,
)


class ProductionIntegrationPort(Protocol):
    """Contract implemented only inside an authorized bank deployment."""

    @property
    def capability(self) -> IntegrationCapabilityCode: ...

    @property
    def adapter_id(self) -> str: ...

    @property
    def adapter_version(self) -> str: ...

    @property
    def is_live(self) -> bool: ...

    def execute(self, request: IntegrationRequest) -> IntegrationResult: ...


class IdentityAccessPort(ProductionIntegrationPort, Protocol):
    """Federated identity, entitlements and household-object grants."""


class CustomerConsentPort(ProductionIntegrationPort, Protocol):
    """Purpose-bound customer authorization and consent withdrawal."""


class CustomerDueDiligencePort(ProductionIntegrationPort, Protocol):
    """KYC, beneficial-owner, CDD/EDD and AML decision evidence."""


class BankFinancialDataPort(ProductionIntegrationPort, Protocol):
    """Authorized bank accounts, transactions, credit and loan facts."""


class InstitutionalDataPort(ProductionIntegrationPort, Protocol):
    """Authorized social security, provident fund and pension facts."""


class ProductMasterPort(ProductionIntegrationPort, Protocol):
    """Dated product facts, sale status, fees, inventory and channel rights."""


class TransactionExecutionPort(ProductionIntegrationPort, Protocol):
    """Transaction-time suitability, order, clearing and position writeback."""


class AdvisorCrmPort(ProductionIntegrationPort, Protocol):
    """Advisor cases, segregation of duties and accountable human nodes."""


class InvestmentCommitteePort(ProductionIntegrationPort, Protocol):
    """Approved Market/Property Regime snapshots from investment governance."""


class ChannelDeliveryPort(ProductionIntegrationPort, Protocol):
    """Authenticated delivery across bank-approved service channels."""
