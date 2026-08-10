from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

IntegrationCapabilityCode = Literal[
    "identity_access_management",
    "customer_consent_authorization",
    "kyc_cdd_edd_aml",
    "bank_account_and_cashflow_data",
    "social_security_provident_pension_data",
    "product_master_and_channel_inventory",
    "transaction_suitability_order_settlement_positions",
    "advisor_crm_and_human_accountability",
    "market_property_regime_committee",
    "regional_public_data_pipeline",
    "model_independent_validation_monitoring",
    "sre_dr_multichannel",
]

IntegrationState = Literal[
    "available_public_snapshot",
    "implemented_local_only",
    "mock_only",
    "contract_required",
    "authorization_required",
    "governance_required",
    "operational_evidence_required",
]


class IntegrationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(min_length=1, max_length=80)
    purpose: str = Field(min_length=2, max_length=240)
    consent_reference: str | None = Field(default=None, max_length=160)
    payload_reference_hash: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )


class IntegrationResult(BaseModel):
    capability: IntegrationCapabilityCode
    adapter_id: str
    adapter_version: str
    executed_at: datetime
    source_kind: Literal["bank_fact", "authorized_external", "public_snapshot"]
    evidence_reference: str
    payload: dict[str, Any]


class CapabilityReadiness(BaseModel):
    capability: IntegrationCapabilityCode
    label: str
    state: IntegrationState
    adapter_id: str
    execution_allowed: bool
    production_blocking: bool
    current_implementation: str
    required_prerequisites: list[str]
    evidence: list[str]


class OperationalControlReadiness(BaseModel):
    code: str
    label: str
    state: Literal[
        "implemented_local_only",
        "design_complete",
        "requires_bank_platform",
        "requires_verified_drill",
    ]
    production_blocking: bool
    evidence: str


class AuthoritativeSourceReference(BaseModel):
    code: str
    title: str
    authority: str
    source_reference: str
    effective_from: date | None = None


class IntegrationReadinessResponse(BaseModel):
    assessment_version: str
    assessed_at: datetime
    runtime_mode: str
    production_ready: bool
    has_live_icbc_connection: Literal[False] = False
    has_live_government_connection: Literal[False] = False
    public_data_snapshot_version: str
    public_data_integrity_hash: str
    capabilities: list[CapabilityReadiness]
    operational_controls: list[OperationalControlReadiness]
    authoritative_sources: list[AuthoritativeSourceReference]
    boundary_note: str
