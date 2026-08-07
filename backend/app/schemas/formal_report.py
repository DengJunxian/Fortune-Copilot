from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.trust import KnowledgeCitation

FORMAL_CHAPTER_TITLES = (
    "家庭基础情况",
    "理财目标",
    "大额支出计划",
    "理财假设",
    "家庭财务报表",
    "家庭财务比率分析",
    "投资规划建议",
    "免责声明",
)

ReportStatus = Literal["draft_requires_human_review", "workflow_linked", "client_ready"]
ReportTrigger = Literal["manual", "monthly_review", "major_event", "action_status_change"]
ReportActionStatus = Literal["open", "completed", "deferred", "not_applicable"]


class ReportTable(BaseModel):
    title: str
    columns: list[str] = Field(min_length=1)
    rows: list[list[str]]
    note: str = ""
    calculation_source: str

    @model_validator(mode="after")
    def rows_match_columns(self) -> ReportTable:
        if any(len(row) != len(self.columns) for row in self.rows):
            raise ValueError("报告表格每行必须与列数一致")
        return self


class ReportAdvice(BaseModel):
    code: str
    title: str
    reason: str
    priority: int = Field(ge=1)
    action: str
    completion_criteria: str
    review_cycle: str
    status: ReportActionStatus = "open"
    due_date: date | None = None
    citation_ids: list[str] = Field(default_factory=list)
    calculation_source: str


class ReportSection(BaseModel):
    code: str
    title: str
    narratives: list[str] = Field(default_factory=list)
    tables: list[ReportTable] = Field(default_factory=list)
    advice: list[ReportAdvice] = Field(default_factory=list)
    citation_ids: list[str] = Field(default_factory=list)


class FormalReportChapter(BaseModel):
    number: int = Field(ge=1, le=8)
    title: str
    summary: str
    sections: list[ReportSection] = Field(min_length=1)


class ReportAppendix(BaseModel):
    code: str
    title: str
    tables: list[ReportTable] = Field(default_factory=list)
    narratives: list[str] = Field(default_factory=list)


class ReportSourceClaim(BaseModel):
    text: str
    citation_ids: list[str] = Field(min_length=1)


class ReportNumericClaim(BaseModel):
    code: str
    label: str
    raw_value: str
    display_value: str
    unit: str
    source_path: str
    calculation_source: Literal[
        "deterministic_tools",
        "deterministic_simulation_engine",
        "deterministic_review_schedule",
    ]


class ReportVersionLedger(BaseModel):
    report_version: str
    input_version: str
    formula_version: str
    planning_rule_version: str
    portfolio_rule_version: str
    twin_result_version: str
    model_version: str
    prompt_version: str
    knowledge_version: str
    product_catalog_version: str
    fund_advisory_catalog_version: str | None = None
    workflow_version: str | None


class ReportExecutionMetrics(BaseModel):
    total: int = Field(ge=0)
    open: int = Field(ge=0)
    completed: int = Field(ge=0)
    deferred: int = Field(ge=0)
    not_applicable: int = Field(ge=0)
    completion_ratio: str

    @model_validator(mode="after")
    def counts_balance(self) -> ReportExecutionMetrics:
        if self.total != self.open + self.completed + self.deferred + self.not_applicable:
            raise ValueError("行动状态合计必须等于行动总数")
        return self


class ReportConsistencyCheck(BaseModel):
    code: str
    status: Literal["passed", "needs_review"]
    explanation: str


class FormalReportDocument(BaseModel):
    report_id: str
    household_id: str
    household_code: str
    household_name: str
    sequence: int = Field(ge=1)
    parent_report_id: str | None
    workflow_id: str | None
    workflow_version_id: str | None
    workflow_state: str | None
    status: ReportStatus
    title: str
    subtitle: str
    watermark: str
    chapter_count: Literal[8] = 8
    chapters: list[FormalReportChapter] = Field(min_length=8, max_length=8)
    appendices: list[ReportAppendix]
    citations: list[KnowledgeCitation]
    sourced_claims: list[ReportSourceClaim]
    numeric_ledger: list[ReportNumericClaim]
    versions: ReportVersionLedger
    execution_metrics: ReportExecutionMetrics
    consistency_checks: list[ReportConsistencyCheck]
    consistency_status: Literal["passed", "needs_review"]
    generation_trigger: ReportTrigger
    generation_reason: str
    generated_at: datetime
    analysis_date: date
    data_as_of: date
    report_hash: str
    mock_mode_supported: Literal[True] = True
    boundary_note: str

    @model_validator(mode="after")
    def enforce_structure_and_sources(self) -> FormalReportDocument:
        numbers = [chapter.number for chapter in self.chapters]
        titles = [chapter.title for chapter in self.chapters]
        if numbers != list(range(1, 9)):
            raise ValueError("正式规划书必须按 1 至 8 顺序排列")
        if tuple(titles) != FORMAL_CHAPTER_TITLES:
            raise ValueError("正式规划书一级目录必须严格保持指定八章")
        citation_ids = {item.citation_id for item in self.citations}
        referenced = {
            citation_id
            for chapter in self.chapters
            for section in chapter.sections
            for citation_id in section.citation_ids
        }
        referenced.update(
            citation_id for claim in self.sourced_claims for citation_id in claim.citation_ids
        )
        if not referenced <= citation_ids:
            raise ValueError("报告包含无法追溯的引用编号")
        if len(citation_ids) != len(self.citations):
            raise ValueError("报告引用编号不得重复")
        return self


class FormalReportSummary(BaseModel):
    report_id: str
    household_id: str
    sequence: int
    report_version: str
    parent_report_id: str | None
    workflow_id: str | None
    workflow_version_id: str | None
    status: ReportStatus
    consistency_status: Literal["passed", "needs_review"]
    generation_trigger: ReportTrigger
    generated_at: datetime
    data_as_of: date
    report_hash: str
    watermark: str
    html_url: str
    pdf_url: str


class ReportGenerationRequest(BaseModel):
    analysis_date: date | None = None
    trigger: ReportTrigger = "manual"
    reason: str = Field(default="一键生成正式八章规划书", min_length=2, max_length=500)
    expected_report_sequence: int | None = Field(default=None, ge=1)


class ReportRecalculationRequest(BaseModel):
    analysis_date: date | None = None
    trigger: Literal["monthly_review", "major_event"]
    reason: str = Field(min_length=2, max_length=500)
    expected_report_sequence: int = Field(ge=1)


class ReportActionOut(BaseModel):
    id: str
    action_code: str
    group_code: str
    title: str
    detail: str
    why: str
    completion_criteria: str
    review_cycle: str
    amount: str
    due_date: date | None
    priority: int
    status: ReportActionStatus
    completed_at: datetime | None
    deferred_until: date | None
    status_reason: str | None
    record_version: int
    calculation_source: str


class ReportActionList(BaseModel):
    household_id: str
    report_id: str | None
    report_sequence: int | None
    items: list[ReportActionOut]
    metrics: ReportExecutionMetrics


class ReportActionUpdateRequest(BaseModel):
    status: ReportActionStatus
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=2, max_length=500)
    deferred_until: date | None = None

    @model_validator(mode="after")
    def validate_deferred_date(self) -> ReportActionUpdateRequest:
        if self.status == "deferred" and self.deferred_until is None:
            raise ValueError("延期状态必须提供新的复盘日期")
        if self.status != "deferred" and self.deferred_until is not None:
            raise ValueError("只有延期状态可以提供 deferred_until")
        return self


class ReportActionUpdateResponse(BaseModel):
    action: ReportActionOut
    metrics: ReportExecutionMetrics
    report: FormalReportSummary


class ReportGenerationChain(BaseModel):
    household_id: str
    current_report_id: str | None
    chain_verified: bool
    items: list[FormalReportSummary]
    audit_event_ids: list[str]
    boundary_note: str
