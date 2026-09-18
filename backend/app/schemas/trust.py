from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class KnowledgeChunkSeed(BaseModel):
    code: str = Field(min_length=3, max_length=120)
    page_ref: str | None = Field(default=None, max_length=80)
    paragraph_ref: str = Field(min_length=1, max_length=160)
    content: str = Field(min_length=20, max_length=4000)
    keywords: list[str] = Field(min_length=1, max_length=30)


class PolicyDocumentSeed(BaseModel):
    code: str = Field(min_length=3, max_length=80)
    title: str = Field(min_length=3, max_length=300)
    issuing_authority: str = Field(min_length=2, max_length=200)
    category: str = Field(min_length=3, max_length=80)
    document_version: str = Field(min_length=2, max_length=64)
    publication_date: date
    effective_date: date
    expiry_date: date | None = None
    source_uri: str = Field(min_length=8, max_length=500)
    source_type: str = Field(min_length=3, max_length=40)
    applicable_audiences: list[str] = Field(min_length=1)
    applicable_regions: list[str] = Field(min_length=1)
    last_verified_date: date
    controlled_snapshot: bool
    metadata: dict[str, Any] = Field(default_factory=dict)
    chunks: list[KnowledgeChunkSeed] = Field(min_length=1)

    @field_validator("expiry_date")
    @classmethod
    def validate_expiry(cls, value: date | None, info: Any) -> date | None:
        effective = info.data.get("effective_date")
        if value is not None and effective is not None and value < effective:
            raise ValueError("expiry_date must not precede effective_date")
        return value


class ControlledKnowledgeDataset(BaseModel):
    dataset_version: str = Field(min_length=3, max_length=64)
    updated_at: date
    vectorizer_version: str = Field(min_length=3, max_length=64)
    source_summary: str = Field(min_length=10, max_length=800)
    documents: list[PolicyDocumentSeed] = Field(min_length=6)


class KnowledgeCatalogDocument(BaseModel):
    code: str
    title: str
    issuing_authority: str
    category: str
    document_version: str
    publication_date: date
    effective_date: date
    expiry_date: date | None
    applicable_audiences: list[str]
    applicable_regions: list[str]
    source_type: str
    source_uri: str
    last_verified_date: date | None
    content_hash: str
    chunk_count: int
    status: Literal["active", "expired", "not_yet_effective"]


class KnowledgeCatalogResponse(BaseModel):
    dataset_version: str
    updated_at: date
    retrieval_version: str
    vectorizer_version: str
    source_summary: str
    document_count: int
    active_document_count: int
    chunk_count: int
    quarantined_chunk_count: int
    categories: list[str]
    documents: list[KnowledgeCatalogDocument]
    runtime_network_required: Literal[False] = False


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    as_of_date: date | None = None
    categories: list[str] = Field(default_factory=list, max_length=12)
    audiences: list[str] = Field(default_factory=list, max_length=12)
    regions: list[str] = Field(default_factory=list, max_length=12)
    limit: int = Field(default=5, ge=1, le=10)


class KnowledgeCitation(BaseModel):
    citation_id: str
    chunk_id: str
    chunk_code: str
    document_code: str
    title: str
    issuing_authority: str
    category: str
    source_uri: str
    source_type: str
    publication_date: date
    effective_date: date
    expiry_date: date | None
    last_verified_date: date | None
    applicable_audiences: list[str]
    applicable_regions: list[str]
    page_ref: str | None
    paragraph_ref: str
    document_version: str
    content_hash: str


class KnowledgeMatch(BaseModel):
    chunk_id: str
    chunk_code: str
    excerpt: str
    keyword_score: Decimal
    vector_score: Decimal
    metadata_score: Decimal
    combined_score: Decimal
    citation_id: str


class KnowledgeClaim(BaseModel):
    text: str
    citation_ids: list[str] = Field(min_length=1)


class KnowledgeSearchResponse(BaseModel):
    query: str
    as_of_date: date
    answer: str
    claims: list[KnowledgeClaim]
    matches: list[KnowledgeMatch]
    citations: list[KnowledgeCitation]
    insufficient_information: bool
    filtered_expired_count: int
    filtered_not_yet_effective_count: int
    filtered_quarantined_count: int
    retrieval_version: str
    vectorizer_version: str
    calculation_source: Literal["deterministic_hybrid_retrieval"] = "deterministic_hybrid_retrieval"
    limitations: list[str]


class GraphNode(BaseModel):
    id: str
    node_type: str
    label: str
    lane: Literal["family", "facts", "goals", "controls", "knowledge"]
    properties: dict[str, str | int | bool | None] = Field(default_factory=dict)
    source_entity_type: str
    source_entity_id: str | None = None
    calculation_source: str


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    relation: str
    label: str
    evidence: list[str]


class GraphInference(BaseModel):
    code: str
    title: str
    conclusion: str
    evidence_node_ids: list[str] = Field(min_length=1)
    rule: str
    human_review_required: bool = False


class HouseholdGraphResponse(BaseModel):
    graph_id: str
    graph_version: str
    title: str
    subtitle: str
    as_of_date: date
    synthetic: bool
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    inferences: list[GraphInference]
    node_type_coverage: list[str]
    calculation_source: Literal["deterministic_relational_graph_service"] = (
        "deterministic_relational_graph_service"
    )
    limitations: list[str]


class IntakeDraftRequest(BaseModel):
    text: str = Field(min_length=2, max_length=2000)
    household_id: str | None = None


class ExtractedDraftField(BaseModel):
    code: str
    label: str
    value: str
    value_type: Literal["money", "count", "stage", "relationship", "text"]
    unit: str | None = None
    evidence: str
    confidence: Decimal
    confirmed: bool


class MissingDraftField(BaseModel):
    code: str
    label: str
    reason: str
    required_for: list[str]
    priority: int = Field(default=3, ge=1, le=5)
    follow_up_question: str = "请补充这一信息。"


class IntakeDraftResponse(BaseModel):
    draft_id: str
    household_id: str | None
    status: Literal["pending_confirmation", "partially_confirmed", "confirmed"]
    parser_version: str
    source_text_hash: str
    redacted_preview: str
    extracted_fields: list[ExtractedDraftField]
    missing_fields: list[MissingDraftField]
    confirmed_values: dict[str, str]
    contains_untrusted_instruction: bool
    confirmation_required: bool
    created_at: datetime
    confirmed_at: datetime | None
    boundary_note: str


class ConfirmIntakeDraftRequest(BaseModel):
    confirmed_values: dict[str, str] = Field(min_length=1, max_length=30)


class AgentSpecOut(BaseModel):
    code: str
    name: str
    purpose: str
    sequence: int
    input_schema_name: str
    input_json_schema: dict[str, Any]
    output_schema_name: str
    output_json_schema: dict[str, Any]
    allowed_tools: list[str] = Field(min_length=1)
    prohibited_actions: list[str] = Field(min_length=1)
    timeout_seconds: int
    failure_fallback: str
    audit_event: str


class AgentCatalogResponse(BaseModel):
    orchestrator_version: str
    state_machine: list[str]
    agent_count: Literal[9] = 9
    agents: list[AgentSpecOut]
    hard_gates: list[str]


class OrchestrationRequest(BaseModel):
    request_kind: Literal["trusted_plan_explanation", "policy_and_plan_review"] = (
        "trusted_plan_explanation"
    )
    policy_query: str = Field(
        default="个人养老金与家庭适配需要核对什么?", min_length=2, max_length=500
    )
    analysis_date: date | None = None


class ToolCallEvidence(BaseModel):
    tool: str
    status: Literal["completed", "degraded", "blocked"]
    input_reference: str
    output_reference: str
    calculation_source: str


class AgentStepOut(BaseModel):
    step_id: str
    agent_code: str
    agent_name: str
    sequence: int
    status: Literal["pending", "running", "completed", "degraded", "blocked"]
    input_schema_name: str
    output_schema_name: str
    tool_calls: list[ToolCallEvidence]
    structured_output: dict[str, Any]
    citations: list[str]
    prohibitions_checked: list[str]
    timeout_seconds: int
    failure_code: str | None
    degraded: bool
    started_at: datetime
    completed_at: datetime | None


class NumericLedgerEntry(BaseModel):
    code: str
    value: str
    unit: str
    source_tool: str
    source_path: str
    value_hash: str


class GovernanceIssue(BaseModel):
    code: str
    severity: Literal["info", "warning", "block"]
    message: str
    claim_index: int | None = None
    evidence: list[str] = Field(default_factory=list)


class OrchestrationResponse(BaseModel):
    run_id: str
    household_id: str
    request_kind: str
    status: Literal["running", "completed", "degraded", "blocked"]
    current_state: str
    orchestrator_version: str
    provider_mode: str
    steps: list[AgentStepOut]
    numeric_ledger: list[NumericLedgerEntry]
    citation_chunk_ids: list[str]
    structured_output: dict[str, Any]
    blocked_issues: list[GovernanceIssue]
    requires_human_review: bool
    degraded: bool
    started_at: datetime
    completed_at: datetime | None
    boundary_note: str


class GovernanceClaim(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    claim_type: Literal["numeric", "policy", "product", "general"]
    value: str | None = None
    tool_reference: str | None = None
    citation_chunk_ids: list[str] = Field(default_factory=list)
    product_code: str | None = None
    product_catalog_version: str | None = None


class GovernanceValidationRequest(BaseModel):
    claims: list[GovernanceClaim] = Field(min_length=1, max_length=30)
    numeric_ledger: list[NumericLedgerEntry] = Field(default_factory=list, max_length=100)
    as_of_date: date | None = None
    ordinary_household_path: bool = True


class GovernanceValidationResponse(BaseModel):
    passed: bool
    blocked: bool
    requires_human_review: bool
    issues: list[GovernanceIssue]
    validated_claim_count: int
    calculation_source: Literal["deterministic_governance_validator"] = (
        "deterministic_governance_validator"
    )
