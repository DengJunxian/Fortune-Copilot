from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Mapping
from datetime import date
from decimal import Decimal
from time import monotonic
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import ActorContext
from app.core.config import Settings
from app.core.errors import AppError
from app.domain.enums import AgentStepStatus, AuditEventType, OrchestrationStatus
from app.models.cfs import CFSSolution
from app.models.common import utc_now
from app.models.financial_twin import FinancialEvent
from app.models.governance import AuditEvent, PlanReport, Recommendation
from app.models.trust import AgentOrchestrationRun, AgentStepRun
from app.schemas.agents import (
    AgentGuardrailIssue,
    AgentToolRegistryResponse,
    BoundedAgentCode,
    BoundedAgentRunRequest,
    BoundedAgentRunResponse,
)
from app.schemas.trust import (
    IntakeDraftRequest,
    KnowledgeSearchRequest,
    ToolCallEvidence,
)
from app.services.agents.guardrails import evaluate_agent_guardrails
from app.services.agents.tool_registry import (
    REGISTRY_VERSION,
    AgentToolRegistry,
    ToolContext,
    ToolResult,
)
from app.services.cfs_composer.engine import get_cfs_solution
from app.services.client_profile.engine import get_client_profile
from app.services.crud import ensure_household
from app.services.financial.engine import analyze_household
from app.services.financial.facts import load_household_facts
from app.services.monitoring.engine import list_monitoring_alerts
from app.services.next_best_action.engine import get_next_best_actions
from app.services.product_ontology.adapter import ensure_verified_fund_ontology
from app.services.trust.intake import (
    MONEY_TOKEN,
    create_intake_draft,
    extract_intake_fields,
    parse_money,
)
from app.services.trust.knowledge import ensure_knowledge_base, search_knowledge
from app.services.twin.engine import scenario_catalog
from app.services.twin.rules import load_twin_rules
from app.services.wealth_needs.engine import get_wealth_needs

BOUNDARY_NOTE = (
    "Agent 只能整理确定性工具结果和受控证据；不得执行交易、覆盖适当性、提高风险等级，"
    "也不得把候选草稿直接写入客户事实。"
)


def _value(value: object) -> object:
    return getattr(value, "value", value)


def _year_offset(value: date, years: int) -> date:
    try:
        return value.replace(year=value.year + years)
    except ValueError:
        return value.replace(month=2, day=28, year=value.year + years)


def _goal_parse(message: str, analysis_date: date) -> dict[str, Any]:
    horizon_match = re.search(rf"(?P<years>{MONEY_TOKEN})\s*年(?:后|内)", message)
    horizon_years: int | None = None
    if horizon_match is not None:
        try:
            parsed = int(parse_money(horizon_match.group("years")))
            horizon_years = parsed if 1 <= parsed <= 60 else None
        except (ArithmeticError, ValueError):
            horizon_years = None

    goal_type = (
        "education"
        if any(term in message for term in ("教育", "留学", "大学", "读书"))
        else "retirement"
        if "退休" in message
        else "housing"
        if any(term in message for term in ("买房", "住房", "首付"))
        else "other"
    )
    amount_match = re.search(
        rf"(?:预算|目标|准备|学费|费用|需要).{{0,8}}(?P<amount>{MONEY_TOKEN})(?:元)?",
        message,
    )
    target_amount: str | None = None
    if amount_match is not None:
        try:
            target_amount = f"{parse_money(amount_match.group('amount')):.2f}"
        except (ArithmeticError, ValueError):
            target_amount = None
    inflation_match = re.search(
        r"(?:教育成本增长率|教育通胀率|通胀率).{0,8}(?P<rate>\d+(?:\.\d+)?)\s*%",
        message,
    )
    fx_match = re.search(r"(?:汇率).{0,8}(?P<rate>\d+(?:\.\d+)?)", message)
    currency = (
        "USD"
        if any(term in message.casefold() for term in ("美元", "usd"))
        else "GBP"
        if any(term in message.casefold() for term in ("英镑", "gbp"))
        else "EUR"
        if any(term in message.casefold() for term in ("欧元", "eur"))
        else None
    )
    user_assumptions = {
        "target_amount": target_amount,
        "target_currency": currency,
        "education_cost_growth_rate": (
            str(
                (Decimal(inflation_match.group("rate")) / Decimal("100")).quantize(
                    Decimal("0.000001")
                )
            )
            if inflation_match is not None
            else None
        ),
        "fx_rate": fx_match.group("rate") if fx_match is not None else None,
    }
    missing = [
        code
        for code, value in (
            ("target_amount_or_tuition_source", target_amount),
            ("education_cost_growth_rate", user_assumptions["education_cost_growth_rate"]),
            ("target_currency", currency),
            ("fx_rate", user_assumptions["fx_rate"]),
        )
        if goal_type == "education" and value is None
    ]
    if horizon_years is None:
        missing.insert(0, "target_horizon_or_date")
    return {
        "goal_type": goal_type,
        "beneficiary": "child" if any(term in message for term in ("孩子", "子女")) else None,
        "horizon_years": horizon_years,
        "target_date": (
            _year_offset(analysis_date, horizon_years).isoformat()
            if horizon_years is not None
            else None
        ),
        "user_provided_assumptions": user_assumptions,
        "assumptions_requiring_confirmation": missing,
        "evidence": {
            "horizon_text": horizon_match.group(0) if horizon_match is not None else None,
            "amount_text": amount_match.group(0) if amount_match is not None else None,
            "inflation_text": inflation_match.group(0) if inflation_match is not None else None,
            "fx_text": fx_match.group(0) if fx_match is not None else None,
        },
    }


def _guardrail_tool(_context: ToolContext, payload: Mapping[str, Any]) -> ToolResult:
    findings = evaluate_agent_guardrails(str(payload.get("message", "")))
    return ToolResult(
        data={
            "passed": not findings,
            "issues": [
                {"code": item.code, "message": item.message, "action": item.action}
                for item in findings
            ],
        },
        output_reference="guardrail.findings",
        calculation_source="deterministic_agent_guardrail_v1",
    )


def _parse_document_tool(_context: ToolContext, payload: Mapping[str, Any]) -> ToolResult:
    extracted, missing = extract_intake_fields(str(payload.get("message", "")))
    return ToolResult(
        data={
            "candidate_facts": [item.model_dump(mode="json") for item in extracted],
            "missing_facts": [item.model_dump(mode="json") for item in missing],
        },
        output_reference="intake.candidate_facts",
        calculation_source="deterministic_zh_intake_parser",
    )


def _current_profile_tool(context: ToolContext, _payload: Mapping[str, Any]) -> ToolResult:
    facts = load_household_facts(context.session, context.household_id)
    profile: dict[str, Any]
    try:
        current = get_client_profile(context.session, context.household_id)
        profile = {
            "status": current.profile.status.value,
            "profile_id": current.profile.id,
            "profile_version": current.profile.profile_version,
            "lifecycle_stage": current.profile.lifecycle_stage.value,
            "wealth_tier": current.profile.wealth_tier.value,
            "risk_capacity": current.profile.risk_capacity.value,
            "risk_willingness": current.profile.risk_willingness.value,
            "behavior_limit": current.profile.behavior_limit.value,
            "completeness_score": str(current.profile.completeness_score),
        }
    except AppError as exc:
        if exc.code != "client_profile_not_calculated":
            raise
        profile = {"status": "not_calculated"}
    return ToolResult(
        data={
            "household_code": facts.code,
            "confirmed": facts.is_user_confirmed,
            "confirmed_fact_version": f"{facts.id}:v{facts.version}",
            "fact_counts": {
                "members": len(facts.members),
                "incomes": len(facts.incomes),
                "expenses": len(facts.expenses),
                "assets": len(facts.assets),
                "liabilities": len(facts.liabilities),
                "goals": len(facts.goals),
            },
            "profile": profile,
        },
        output_reference="household.current_profile",
        calculation_source="confirmed_relational_facts",
    )


def _create_intake_draft_tool(context: ToolContext, payload: Mapping[str, Any]) -> ToolResult:
    draft = create_intake_draft(
        context.session,
        IntakeDraftRequest(
            household_id=context.household_id,
            text=str(payload.get("message", "")),
        ),
        context.actor,
    )
    return ToolResult(
        data=draft.model_dump(mode="json"),
        output_reference=f"intake_draft:{draft.draft_id}",
        calculation_source=draft.parser_version,
    )


def _parse_goal_tool(context: ToolContext, payload: Mapping[str, Any]) -> ToolResult:
    return ToolResult(
        data=_goal_parse(str(payload.get("message", "")), context.analysis_date),
        output_reference="goal.candidate_draft",
        calculation_source="deterministic_goal_parser_v1",
    )


def _current_goals_tool(context: ToolContext, _payload: Mapping[str, Any]) -> ToolResult:
    facts = load_household_facts(context.session, context.household_id)
    return ToolResult(
        data={
            "goals": [
                {
                    "goal_id": item.id,
                    "name": item.name,
                    "goal_type": item.goal_type.value,
                    "target_amount": str(item.target_amount),
                    "target_date": item.target_date.isoformat(),
                    "annual_cost_growth_rate": str(item.annual_cost_growth_rate),
                    "confirmed_fact_version": item.version,
                }
                for item in facts.goals
            ]
        },
        output_reference="household.confirmed_goals",
        calculation_source="confirmed_relational_facts",
    )


def _liability_assumptions_tool(context: ToolContext, _payload: Mapping[str, Any]) -> ToolResult:
    rules = load_twin_rules(context.settings.twin_rules_path)
    return ToolResult(
        data={
            "controlled_candidates": {
                "general_inflation_rate": str(rules.base_inflation_rate),
                "rule_version": rules.semantic_version,
                "effective_from": rules.effective_from.isoformat(),
            },
            "limitations": [
                "一般通胀不能自动替代教育成本增长率。",
                "受控规则未提供学费或汇率时，必须由数据工具或用户确认。",
            ],
        },
        output_reference="goal.controlled_assumption_sources",
        calculation_source=rules.semantic_version,
    )


def _financial_diagnosis_tool(context: ToolContext, _payload: Mapping[str, Any]) -> ToolResult:
    result = analyze_household(
        context.session,
        context.household_id,
        context.settings.financial_rules_path,
        context.analysis_date,
    )
    return ToolResult(
        data={
            "input_version": result.meta.input_version,
            "calculation_source": result.meta.calculation_source,
            "health": {
                "score": str(result.health_assessment.overall_score),
                "status": result.health_assessment.status,
                "hard_gate_triggered": result.health_assessment.hard_gate_triggered,
                "priority_action": result.health_assessment.priority_action.model_dump(mode="json"),
            },
            "statements": {
                "net_worth": str(result.statements.balance_sheet.net_worth),
                "annual_surplus": str(result.statements.cash_flow.annual_surplus),
                "currency": result.meta.currency,
            },
            "diagnostics": [item.model_dump(mode="json") for item in result.diagnostics.issues],
            "protection": {
                "gap": str(result.protection.protection_gap),
                "most_significant_risk": result.protection.most_significant_risk,
                "payment_pressure": result.protection.payment_pressure,
            },
        },
        output_reference="financial.deterministic_diagnosis",
        calculation_source=result.meta.calculation_source,
    )


def _wealth_needs_tool(context: ToolContext, _payload: Mapping[str, Any]) -> ToolResult:
    try:
        result = get_wealth_needs(context.session, context.household_id)
    except AppError as exc:
        if exc.code not in {"client_profile_not_calculated", "wealth_needs_not_calculated"}:
            raise
        return ToolResult(
            data={"status": "not_calculated", "needs": [], "priorities": []},
            output_reference="wealth_needs.unavailable",
            calculation_source="deterministic_wealth_needs_engine",
        )
    return ToolResult(
        data={
            "status": "available",
            "need_set_hash": result.meta.profile_hash,
            "needs": [
                {
                    "need_id": item.id,
                    "need_type": item.need_type.value,
                    "target_amount": str(item.target_amount),
                    "status": item.status.value,
                    "professional_review_required": item.professional_review_required,
                }
                for item in result.needs
            ],
            "priorities": [item.model_dump(mode="json") for item in result.priorities],
        },
        output_reference="wealth_needs.current",
        calculation_source=result.meta.calculation_source,
    )


def _cfs_tool(context: ToolContext, _payload: Mapping[str, Any]) -> ToolResult:
    solution = context.session.scalar(
        select(CFSSolution)
        .where(
            CFSSolution.household_id == context.household_id,
            CFSSolution.is_deleted.is_(False),
        )
        .order_by(CFSSolution.solution_version.desc(), CFSSolution.created_at.desc())
        .limit(1)
    )
    if solution is None:
        return ToolResult(
            data={"status": "not_composed", "components": [], "referrals": []},
            output_reference="cfs.unavailable",
            calculation_source="deterministic_cfs_composer",
        )
    result = get_cfs_solution(
        context.session,
        context.household_id,
        solution.id,
        context.settings.cfs_rules_path,
    )
    return ToolResult(
        data={
            "status": result.solution.status.value,
            "solution_id": result.solution.id,
            "solution_version": result.solution.solution_version,
            "decision_hash": result.solution.decision_hash,
            "summary": result.solution.summary,
            "components": [
                {
                    "component_id": item.id,
                    "component_type": item.component_type.value,
                    "priority": item.priority,
                    "recommended_action": item.recommended_action,
                    "professional_review_required": item.professional_review_required,
                    "required_specialist": _value(item.required_specialist),
                    "status": item.status.value,
                }
                for item in result.components
            ],
            "referrals": [item.model_dump(mode="json") for item in result.referrals],
        },
        output_reference=f"cfs_solution:{solution.id}",
        calculation_source="deterministic_cfs_composer",
    )


def _scenario_catalog_tool(context: ToolContext, _payload: Mapping[str, Any]) -> ToolResult:
    result = scenario_catalog(context.session, context.settings.twin_rules_path)
    return ToolResult(
        data=result.model_dump(mode="json"),
        output_reference=f"scenario_catalog:{result.scenario_version}",
        calculation_source="controlled_scenario_catalog",
    )


_SCENARIO_KEYWORDS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("失业", "收入中断"), "primary_income_interruption_6m"),
    (("医疗", "大病", "住院"), "medical_out_of_pocket"),
    (("教育", "学费", "留学"), "education_overrun"),
    (("提前退休",), "early_retirement"),
    (("长寿", "寿命"), "longevity"),
    (("房贷", "利率"), "mortgage_rate_up"),
    (("房价", "住房价值"), "housing_value_down_20"),
    (("权益", "股市", "市场下跌"), "equity_down_30"),
    (("通胀", "成本上涨"), "cost_inflation_up"),
)


def _select_scenarios_tool(_context: ToolContext, payload: Mapping[str, Any]) -> ToolResult:
    message = str(payload.get("message", ""))
    catalog_items = list(payload.get("scenarios", []))
    by_code = {
        str(item.get("code")): item
        for item in catalog_items
        if isinstance(item, Mapping) and item.get("enabled") is True
    }
    maximum = max(1, min(int(payload.get("maximum_results", 3)), 5))
    requested = [
        code
        for keywords, code in _SCENARIO_KEYWORDS
        if code in by_code and any(term in message for term in keywords)
    ]
    if not requested:
        requested = [
            code
            for code in (
                "primary_income_interruption_6m",
                "medical_out_of_pocket",
                "cost_inflation_up",
            )
            if code in by_code
        ]
    selected: list[dict[str, Any]] = []
    for code in requested:
        if code in {item["code"] for item in selected}:
            continue
        item = by_code[code]
        selected.append(
            {
                "code": code,
                "name": item.get("name"),
                "category": item.get("category"),
                "description": item.get("description"),
                "scenario_version": item.get("scenario_version"),
                "selection_reason": f"客户问题包含与 {item.get('name')} 对应的压力主题。",
            }
        )
        if len(selected) >= maximum:
            break
    return ToolResult(
        data={
            "selected_scenarios": selected,
            "catalog_codes_checked": sorted(by_code),
            "arbitrary_forecast_generated": False,
        },
        output_reference="scenario.selected_catalog_entries",
        calculation_source="deterministic_scenario_selector_v1",
    )


def _product_ontology_tool(context: ToolContext, payload: Mapping[str, Any]) -> ToolResult:
    catalog, products, _snapshots = ensure_verified_fund_ontology(
        context.session, context.settings.fund_advisory_catalog_path
    )
    requested = {str(code).casefold() for code in payload.get("product_codes", [])}
    maximum = max(1, min(int(payload.get("maximum_results", 3)), 5))
    filtered = [item for item in products if not requested or item.code.casefold() in requested]
    filtered.sort(key=lambda item: item.code)
    selected = filtered[:maximum]
    return ToolResult(
        data={
            "catalog_version": catalog.catalog_version,
            "catalog_as_of": catalog.verified_on.isoformat(),
            "selection_method": "exact_product_code" if requested else "neutral_code_order",
            "products": [
                {
                    "product_id": item.id,
                    "code": item.code,
                    "name": item.name,
                    "issuer": item.issuer,
                    "product_family": item.product_family.value,
                    "risk_level": item.risk_level.value,
                    "liquidity_level": item.liquidity_level.value,
                    "minimum_investment": str(item.minimum_investment),
                    "minimum_holding_months": item.minimum_holding_months,
                    "all_in_cost": str(item.all_in_cost) if item.all_in_cost is not None else None,
                    "principal_loss_possible": item.principal_loss_possible,
                    "professional_review_required": item.professional_review_required,
                    "classification_version": item.classification_version,
                    "evidence": item.evidence_json,
                }
                for item in selected
            ],
            "recommendation_generated": False,
        },
        output_reference=f"product_ontology:{catalog.catalog_version}",
        calculation_source="verified_product_ontology",
    )


def _product_snapshot_tool(context: ToolContext, payload: Mapping[str, Any]) -> ToolResult:
    _catalog, _products, snapshots = ensure_verified_fund_ontology(
        context.session, context.settings.fund_advisory_catalog_path
    )
    requested_ids = {str(item) for item in payload.get("product_ids", [])}
    selected = [item for item in snapshots if item.product_id in requested_ids]
    selected.sort(key=lambda item: (item.product_id, item.as_of_date), reverse=True)
    return ToolResult(
        data={
            "snapshots": [
                {
                    "snapshot_id": item.id,
                    "product_id": item.product_id,
                    "as_of_date": item.as_of_date.isoformat(),
                    "sale_status": item.sale_status,
                    "risk_level": item.risk_level.value,
                    "fee_snapshot": item.fee_snapshot,
                    "liquidity_snapshot": item.liquidity_snapshot,
                    "terms_snapshot": item.terms_snapshot,
                    "source_reference": item.source_reference,
                    "snapshot_hash": item.snapshot_hash,
                    "snapshot_version": item.snapshot_version,
                    "evidence": item.evidence,
                }
                for item in selected
            ]
        },
        output_reference="product_snapshots.versioned",
        calculation_source="verified_product_snapshot",
    )


def _approved_knowledge_tool(context: ToolContext, payload: Mapping[str, Any]) -> ToolResult:
    ensure_knowledge_base(context.session, context.settings.knowledge_base_path)
    result = search_knowledge(
        context.session,
        context.settings.knowledge_base_path,
        KnowledgeSearchRequest(
            query=str(payload.get("message", "")),
            as_of_date=context.analysis_date,
            limit=max(1, min(int(payload.get("maximum_results", 3)), 5)),
        ),
        actor=context.actor,
    )
    return ToolResult(
        data={
            "answer": result.answer,
            "insufficient_information": result.insufficient_information,
            "claims": [item.model_dump(mode="json") for item in result.claims],
            "citations": [item.model_dump(mode="json") for item in result.citations],
            "limitations": result.limitations,
        },
        output_reference="approved_knowledge.matches",
        calculation_source=result.calculation_source,
        citations=tuple(item.chunk_id for item in result.citations),
    )


def _monitoring_trigger_tool(context: ToolContext, _payload: Mapping[str, Any]) -> ToolResult:
    result = get_next_best_actions(context.session, context.household_id, context.analysis_date)
    alerts = list_monitoring_alerts(
        context.session,
        context.household_id,
        context.settings.monitoring_rules_path,
    )
    return ToolResult(
        data={
            "outcome": result.outcome,
            "actions": [item.model_dump(mode="json") for item in result.actions],
            "alerts": [item.model_dump(mode="json") for item in alerts.alerts],
            "boundary": result.boundary,
        },
        output_reference="monitoring.next_best_actions",
        calculation_source="deterministic_monitoring_and_nba",
    )


def _profile_changes_tool(context: ToolContext, _payload: Mapping[str, Any]) -> ToolResult:
    events = list(
        context.session.scalars(
            select(FinancialEvent)
            .where(
                FinancialEvent.household_id == context.household_id,
                FinancialEvent.is_deleted.is_(False),
            )
            .order_by(FinancialEvent.effective_at.desc(), FinancialEvent.id.desc())
            .limit(10)
        ).all()
    )
    return ToolResult(
        data={
            "changes": [
                {
                    "event_id": item.id,
                    "event_domain": item.event_domain.value,
                    "event_type": item.event_type,
                    "effective_at": item.effective_at.isoformat(),
                    "confirmation_status": item.confirmation_status.value,
                    "source_reference": item.source_reference,
                    "changed_fields": sorted(item.payload),
                }
                for item in events
            ]
        },
        output_reference="financial_twin.confirmed_changes",
        calculation_source="persistent_financial_event_ledger",
    )


def _decision_evidence_tool(context: ToolContext, _payload: Mapping[str, Any]) -> ToolResult:
    recommendation = context.session.scalar(
        select(Recommendation)
        .where(
            Recommendation.household_id == context.household_id,
            Recommendation.is_deleted.is_(False),
        )
        .order_by(Recommendation.created_at.desc(), Recommendation.id.desc())
        .limit(1)
    )
    report = context.session.scalar(
        select(PlanReport)
        .where(
            PlanReport.household_id == context.household_id,
            PlanReport.is_deleted.is_(False),
        )
        .order_by(PlanReport.sequence.desc(), PlanReport.created_at.desc())
        .limit(1)
    )
    evidence = (
        recommendation.decision_evidence
        if recommendation is not None and recommendation.decision_evidence
        else report.decision_evidence
        if report is not None
        else {}
    )
    return ToolResult(
        data={
            "evidence": evidence,
            "decision_hash": (
                recommendation.decision_hash
                if recommendation is not None
                else report.decision_hash
                if report is not None
                else None
            ),
            "report_chapter_count": report.chapter_count if report is not None else None,
            "source_type": (
                "recommendation"
                if recommendation is not None and recommendation.decision_evidence
                else "plan_report"
                if report is not None
                else "none"
            ),
        },
        output_reference="decision_evidence.latest",
        calculation_source="frozen_decision_evidence_v2",
    )


_HANDLERS: dict[str, Callable[[ToolContext, Mapping[str, Any]], ToolResult]] = {
    "guardrail_check": _guardrail_tool,
    "parse_document": _parse_document_tool,
    "read_current_profile": _current_profile_tool,
    "create_intake_draft": _create_intake_draft_tool,
    "parse_goal_request": _parse_goal_tool,
    "read_current_goals": _current_goals_tool,
    "read_liability_assumption_sources": _liability_assumptions_tool,
    "read_financial_diagnosis": _financial_diagnosis_tool,
    "read_wealth_needs": _wealth_needs_tool,
    "read_cfs": _cfs_tool,
    "read_scenario_catalog": _scenario_catalog_tool,
    "select_scenarios": _select_scenarios_tool,
    "read_product_ontology": _product_ontology_tool,
    "read_product_snapshot": _product_snapshot_tool,
    "search_approved_knowledge": _approved_knowledge_tool,
    "read_monitoring_trigger": _monitoring_trigger_tool,
    "read_profile_changes": _profile_changes_tool,
    "read_decision_evidence": _decision_evidence_tool,
}


def build_tool_registry() -> AgentToolRegistry:
    registry = AgentToolRegistry()
    for code, handler in _HANDLERS.items():
        registry.register(code, handler)
    return registry


def agent_tool_catalog() -> AgentToolRegistryResponse:
    return build_tool_registry().catalog()


class _InvocationLedger:
    def __init__(
        self,
        registry: AgentToolRegistry,
        agent_code: BoundedAgentCode,
        context: ToolContext,
    ) -> None:
        self.registry = registry
        self.agent_code = agent_code
        self.context = context
        self.tool_calls: list[ToolCallEvidence] = []
        self.citations: list[str] = []

    def invoke(
        self,
        tool_code: str,
        payload: Mapping[str, Any],
        *,
        blocked: bool = False,
    ) -> dict[str, Any]:
        result = self.registry.invoke(self.agent_code, tool_code, self.context, payload)
        self.tool_calls.append(
            ToolCallEvidence(
                tool=tool_code,
                status="blocked" if blocked else "completed",
                input_reference="redacted_agent_request_or_prior_tool_output",
                output_reference=result.output_reference,
                calculation_source=result.calculation_source,
            )
        )
        for citation in result.citations:
            if citation not in self.citations:
                self.citations.append(citation)
        return result.data


def _intake_output(
    ledger: _InvocationLedger, request: BoundedAgentRunRequest
) -> tuple[dict[str, Any], bool, bool]:
    parsed = ledger.invoke("parse_document", {"message": request.message})
    profile = ledger.invoke("read_current_profile", {})
    draft = ledger.invoke("create_intake_draft", {"message": request.message})
    return (
        {
            "candidate_facts": parsed["candidate_facts"],
            "missing_facts": parsed["missing_facts"],
            "current_profile_reference": profile,
            "intake_draft": draft,
            "canonical_write_status": "pending_user_confirmation",
            "facts_written": False,
        },
        True,
        bool(draft.get("contains_untrusted_instruction")),
    )


def _goal_output(
    ledger: _InvocationLedger, request: BoundedAgentRunRequest
) -> tuple[dict[str, Any], bool, bool]:
    draft = ledger.invoke("parse_goal_request", {"message": request.message})
    goals = ledger.invoke("read_current_goals", {})
    sources = ledger.invoke("read_liability_assumption_sources", {})
    return (
        {
            "goal_draft": draft,
            "current_goals": goals["goals"],
            "liability_assumption_sources": sources,
            "confirmation_required_for": draft["assumptions_requiring_confirmation"],
            "canonical_goal_written": False,
        },
        True,
        False,
    )


def _household_output(
    ledger: _InvocationLedger, _request: BoundedAgentRunRequest
) -> tuple[dict[str, Any], bool, bool]:
    diagnosis = ledger.invoke("read_financial_diagnosis", {})
    needs = ledger.invoke("read_wealth_needs", {})
    cfs = ledger.invoke("read_cfs", {})
    priority = diagnosis["health"]["priority_action"]
    explanation = (
        f"确定性家庭财务健康分为 {diagnosis['health']['score']}，"
        f"当前优先事项是{priority['title']}。"
        f"该说明引用输入版本 {diagnosis['input_version']}，没有重新计算或补造数字。"
    )
    return (
        {
            "explanation": explanation,
            "deterministic_diagnosis": diagnosis,
            "wealth_needs": needs,
            "cfs": cfs,
            "new_numeric_claims_generated": False,
        },
        False,
        any(item.get("professional_review_required") for item in needs.get("needs", [])),
    )


def _scenario_output(
    ledger: _InvocationLedger, request: BoundedAgentRunRequest
) -> tuple[dict[str, Any], bool, bool]:
    catalog = ledger.invoke("read_scenario_catalog", {})
    selection = ledger.invoke(
        "select_scenarios",
        {
            "message": request.message,
            "scenarios": catalog["scenarios"],
            "maximum_results": request.maximum_results,
        },
    )
    return (
        {
            "scenario_catalog_version": catalog["scenario_version"],
            "selected_scenarios": selection["selected_scenarios"],
            "all_selected_from_catalog": all(
                item["code"] in selection["catalog_codes_checked"]
                for item in selection["selected_scenarios"]
            ),
            "arbitrary_forecast_generated": False,
            "next_step": "客户确认后才能调用确定性情景模拟器。",
        },
        True,
        False,
    )


def _product_output(
    ledger: _InvocationLedger, request: BoundedAgentRunRequest
) -> tuple[dict[str, Any], bool, bool]:
    ontology = ledger.invoke(
        "read_product_ontology",
        {
            "product_codes": request.product_codes,
            "maximum_results": request.maximum_results,
        },
    )
    product_ids = [item["product_id"] for item in ontology["products"]]
    snapshots = ledger.invoke("read_product_snapshot", {"product_ids": product_ids})
    knowledge = ledger.invoke(
        "search_approved_knowledge",
        {"message": request.message, "maximum_results": request.maximum_results},
    )
    comparison_fields = (
        "risk_level",
        "liquidity_level",
        "minimum_investment",
        "minimum_holding_months",
        "all_in_cost",
        "principal_loss_possible",
    )
    differences = [
        {
            "field": field,
            "values": {item["code"]: item[field] for item in ontology["products"]},
        }
        for field in comparison_fields
        if len({str(item[field]) for item in ontology["products"]}) > 1
    ]
    return (
        {
            "facts": ontology["products"],
            "differences": differences,
            "evidence": {
                "catalog_version": ontology["catalog_version"],
                "catalog_as_of": ontology["catalog_as_of"],
                "snapshots": snapshots["snapshots"],
                "approved_knowledge": knowledge,
            },
            "eligibility_engine_invoked": False,
            "recommendation_generated": False,
            "execution_allowed": False,
        },
        False,
        any(item["professional_review_required"] for item in ontology["products"]),
    )


def _advisor_output(
    ledger: _InvocationLedger, _request: BoundedAgentRunRequest
) -> tuple[dict[str, Any], bool, bool]:
    monitoring = ledger.invoke("read_monitoring_trigger", {})
    changes = ledger.invoke("read_profile_changes", {})
    profile = ledger.invoke("read_current_profile", {})
    needs = ledger.invoke("read_wealth_needs", {})
    cfs = ledger.invoke("read_cfs", {})
    evidence = ledger.invoke("read_decision_evidence", {})
    actions = monitoring["actions"]
    top_action = actions[0] if actions else None
    questions = [
        "请确认本次会谈前是否还有未记录的收入、责任或保障变化。",
        "请确认当前目标期限和刚性是否仍与上次记录一致。",
    ]
    if changes["changes"]:
        questions.append("请逐项确认最近事件的实际影响和生效时间。")
    specialist_set = {
        str(item["required_specialist"]) for item in actions if item.get("required_specialist")
    }
    specialist_set.update(
        str(item["required_specialist"])
        for item in cfs.get("components", [])
        if item.get("required_specialist")
    )
    headline = (
        top_action["recommended_action"]
        if top_action is not None
        else "当前无新增行动，按既定节奏复核。"
    )
    return (
        {
            "meeting_brief": {
                "headline": headline,
                "monitoring_outcome": monitoring["outcome"],
                "profile_version": profile["confirmed_fact_version"],
                "changed_fact_count": len(changes["changes"]),
                "need_count": len(needs.get("needs", [])),
                "cfs_solution_id": cfs.get("solution_id"),
                "decision_hash": evidence.get("decision_hash"),
            },
            "questions_to_verify": questions,
            "client_friendly_explanation": (
                "本次会谈先核对家庭变化和目标，再复核现有方案是否仍适用；"
                "不会因监控提醒直接推送产品。"
            ),
            "risk_warnings": [
                "行动中心不是 Next Best Sale，禁止直接转化为销售动作。",
                "风险等级、金额和适当性结论必须来自确定性工具及客户确认。",
            ],
            "specialist_handoff_summary": {
                "required": bool(specialist_set),
                "specialists": sorted(specialist_set),
                "evidence_reference": evidence.get("source_type"),
            },
            "source_evidence": {
                "monitoring": monitoring,
                "profile_changes": changes,
                "needs": needs,
                "cfs": cfs,
                "decision_evidence": evidence,
            },
        },
        False,
        bool(specialist_set),
    )


_OUTPUT_BUILDERS: dict[
    BoundedAgentCode,
    Callable[[_InvocationLedger, BoundedAgentRunRequest], tuple[dict[str, Any], bool, bool]],
] = {
    "intake": _intake_output,
    "goal": _goal_output,
    "household_analyst": _household_output,
    "scenario": _scenario_output,
    "product_research": _product_output,
    "advisor_copilot": _advisor_output,
}


def _run_response(
    run: AgentOrchestrationRun,
    step: AgentStepRun,
) -> BoundedAgentRunResponse:
    spec = build_tool_registry().spec(step.agent_code)  # type: ignore[arg-type]
    completed_at = step.completed_at or run.completed_at or utc_now()
    issues = [AgentGuardrailIssue.model_validate(item) for item in run.blocked_issues]
    return BoundedAgentRunResponse(
        run_id=run.id,
        step_id=step.id,
        household_id=run.household_id,
        agent_code=step.agent_code,
        status=run.status.value,
        registry_version=REGISTRY_VERSION,
        allowed_tools=list(spec.allowed_tools),
        tool_calls=[ToolCallEvidence.model_validate(item) for item in step.tool_calls],
        output=step.structured_output,
        guardrail_issues=issues,
        requires_confirmation=bool(run.structured_output.get("requires_confirmation")),
        requires_human_review=run.requires_human_review,
        started_at=run.started_at,
        completed_at=completed_at,
        boundary_note=BOUNDARY_NOTE,
    )


def run_bounded_agent(
    session: Session,
    household_id: str,
    request: BoundedAgentRunRequest,
    actor: ActorContext,
    settings: Settings,
) -> BoundedAgentRunResponse:
    ensure_household(session, household_id)
    analysis_date = request.analysis_date or date.today()
    registry = build_tool_registry()
    spec = registry.spec(request.agent_code)
    started_at = utc_now()
    query_hash = hashlib.sha256(request.message.encode("utf-8")).hexdigest()
    run = AgentOrchestrationRun(
        household_id=household_id,
        request_kind=f"bounded_agent:{request.agent_code}",
        status=OrchestrationStatus.RUNNING,
        current_state=request.agent_code,
        query_hash=query_hash,
        redacted_input={
            "message_hash": query_hash,
            "message_length": len(request.message),
            "analysis_date": analysis_date.isoformat(),
            "requested_product_code_count": len(request.product_codes),
        },
        structured_output={},
        numeric_ledger=[],
        citation_chunk_ids=[],
        blocked_issues=[],
        requires_human_review=False,
        degraded=False,
        orchestrator_version=REGISTRY_VERSION,
        started_at=started_at,
        valuation_date=analysis_date,
        data_source="bounded_agent_tool_registry",
        is_user_confirmed=False,
    )
    session.add(run)
    session.flush()
    session.add(
        AuditEvent(
            household_id=household_id,
            event_type=AuditEventType.ORCHESTRATION_STARTED,
            actor_id=actor.actor_id,
            actor_role=actor.role,
            entity_type="AgentOrchestrationRun",
            entity_id=run.id,
            event_version=run.version,
            summary=f"启动受限 {spec.name}",
            evidence={
                "agent_code": request.agent_code,
                "registry_version": REGISTRY_VERSION,
                "allowed_tools": list(spec.allowed_tools),
                "query_hash": query_hash,
            },
            occurred_at=started_at,
            valuation_date=analysis_date,
            data_source="bounded_agent_tool_registry",
            is_user_confirmed=True,
        )
    )
    session.flush()

    context = ToolContext(
        session=session,
        household_id=household_id,
        actor=actor,
        settings=settings,
        analysis_date=analysis_date,
    )
    ledger = _InvocationLedger(registry, request.agent_code, context)
    guardrail = ledger.invoke("guardrail_check", {"message": request.message})
    issues = [
        AgentGuardrailIssue(
            code=item["code"],
            message=item["message"],
            action=item["action"],
        )
        for item in guardrail["issues"]
    ]
    failure_code: str | None = None
    requires_confirmation = False
    requires_human_review = False
    degraded = False
    output: dict[str, Any]
    timer = monotonic()
    if issues:
        ledger.tool_calls[-1].status = "blocked"
        output = {
            "outcome": "blocked",
            "reason": "agent_guardrail_failed",
            "safe_next_step": (
                "删除越权指令后重新提交；金额、风险等级和适当性必须使用确定性工具。"
            ),
        }
        run.status = OrchestrationStatus.BLOCKED
        step_status = AgentStepStatus.BLOCKED
        requires_human_review = True
        failure_code = "agent_guardrail_failed"
    else:
        try:
            output, requires_confirmation, requires_human_review = _OUTPUT_BUILDERS[
                request.agent_code
            ](ledger, request)
            if monotonic() - timer > spec.timeout_seconds:
                failure_code = "step_timeout_budget_exceeded"
                degraded = True
        except Exception as exc:  # fail-safe persistence mirrors the existing state machine
            failure_code = type(exc).__name__
            degraded = True
            requires_human_review = True
            output = {
                "outcome": "degraded",
                "reason": "bounded_agent_tool_failure",
                "safe_fallback": spec.failure_fallback,
                "financial_output_generated": False,
            }
        run.status = OrchestrationStatus.DEGRADED if degraded else OrchestrationStatus.COMPLETED
        step_status = AgentStepStatus.DEGRADED if degraded else AgentStepStatus.COMPLETED

    completed_at = utc_now()
    step = AgentStepRun(
        run_id=run.id,
        household_id=household_id,
        agent_code=request.agent_code,
        sequence=1,
        status=step_status,
        input_schema_name="BoundedAgentRunRequest",
        output_schema_name=f"{request.agent_code}_bounded_output_v1",
        tool_calls=[item.model_dump(mode="json") for item in ledger.tool_calls],
        structured_output=output,
        citations=ledger.citations,
        prohibitions_checked=list(spec.prohibited_actions),
        timeout_seconds=spec.timeout_seconds,
        failure_code=failure_code,
        degraded=degraded,
        started_at=started_at,
        completed_at=completed_at,
        valuation_date=analysis_date,
        data_source="bounded_agent_tool_registry",
        is_user_confirmed=False,
    )
    session.add(step)
    session.flush()
    run.current_state = "finished"
    run.structured_output = {
        "agent_code": request.agent_code,
        "output": output,
        "requires_confirmation": requires_confirmation,
        "registry_version": REGISTRY_VERSION,
    }
    run.citation_chunk_ids = ledger.citations
    run.blocked_issues = [item.model_dump(mode="json") for item in issues]
    run.requires_human_review = requires_human_review
    run.degraded = degraded
    run.completed_at = completed_at
    run.version += 1
    session.add_all(
        [
            AuditEvent(
                household_id=household_id,
                event_type=(
                    AuditEventType.AGENT_STEP_DEGRADED
                    if degraded or issues
                    else AuditEventType.AGENT_STEP_COMPLETED
                ),
                actor_id=actor.actor_id,
                actor_role=actor.role,
                entity_type="AgentStepRun",
                entity_id=step.id,
                event_version=step.version,
                summary=f"{spec.name}{'已阻断' if issues else '降级完成' if degraded else '完成'}",
                evidence={
                    "agent_code": request.agent_code,
                    "tool_calls": [item.tool for item in ledger.tool_calls],
                    "failure_code": failure_code,
                    "guardrail_issue_codes": [item.code for item in issues],
                },
                occurred_at=completed_at,
                valuation_date=analysis_date,
                data_source="bounded_agent_tool_registry",
                is_user_confirmed=True,
            ),
            AuditEvent(
                household_id=household_id,
                event_type=AuditEventType.ORCHESTRATION_COMPLETED,
                actor_id=actor.actor_id,
                actor_role=actor.role,
                entity_type="AgentOrchestrationRun",
                entity_id=run.id,
                event_version=run.version,
                summary=f"受限 {spec.name} 运行结束：{run.status.value}",
                evidence={
                    "agent_code": request.agent_code,
                    "registry_version": REGISTRY_VERSION,
                    "blocked": bool(issues),
                    "degraded": degraded,
                    "requires_confirmation": requires_confirmation,
                },
                occurred_at=completed_at,
                valuation_date=analysis_date,
                data_source="bounded_agent_tool_registry",
                is_user_confirmed=True,
            ),
        ]
    )
    session.commit()
    session.refresh(run)
    session.refresh(step)
    return _run_response(run, step)


def get_bounded_agent_run(
    session: Session,
    household_id: str,
    run_id: str,
) -> BoundedAgentRunResponse:
    run = session.scalar(
        select(AgentOrchestrationRun).where(
            AgentOrchestrationRun.id == run_id,
            AgentOrchestrationRun.household_id == household_id,
            AgentOrchestrationRun.orchestrator_version == REGISTRY_VERSION,
            AgentOrchestrationRun.is_deleted.is_(False),
        )
    )
    if run is None:
        raise AppError("bounded_agent_run_not_found", "找不到该受限 Agent 运行", status_code=404)
    step = session.scalar(
        select(AgentStepRun).where(
            AgentStepRun.run_id == run.id,
            AgentStepRun.is_deleted.is_(False),
        )
    )
    if step is None:
        raise AppError("bounded_agent_step_not_found", "受限 Agent 步骤证据不完整", status_code=409)
    return _run_response(run, step)
