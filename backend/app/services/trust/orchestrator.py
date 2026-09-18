from __future__ import annotations

import hashlib
from datetime import date
from time import monotonic
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import ActorContext
from app.core.config import Settings
from app.core.errors import AppError
from app.domain.enums import (
    AccountBucket,
    AgentStepStatus,
    AuditEventType,
    OrchestrationStatus,
)
from app.models.common import utc_now
from app.models.governance import AuditEvent
from app.models.trust import AgentOrchestrationRun, AgentStepRun
from app.schemas.trust import (
    AgentStepOut,
    GovernanceClaim,
    GovernanceIssue,
    GovernanceValidationRequest,
    KnowledgeSearchRequest,
    NumericLedgerEntry,
    OrchestrationRequest,
    OrchestrationResponse,
    ToolCallEvidence,
)
from app.services.behavior.engine import behavior_overview
from app.services.financial.engine import analyze_household
from app.services.financial.facts import load_household_facts
from app.services.planning.engine import plan_household
from app.services.portfolio.engine import portfolio_household
from app.services.security.model_risk import record_orchestration_model_ledger
from app.services.trust.agents import (
    AGENT_SPECS,
    ORCHESTRATOR_VERSION,
    AgentSpec,
    validate_agent_output,
)
from app.services.trust.governance import validate_governed_output
from app.services.trust.knowledge import search_knowledge


def _hash_value(code: str, value: str, source_path: str) -> str:
    return hashlib.sha256(f"{code}|{value}|{source_path}".encode()).hexdigest()


def _numeric(
    code: str,
    value: Any,
    unit: str,
    source_tool: str,
    source_path: str,
) -> NumericLedgerEntry:
    rendered = str(value)
    return NumericLedgerEntry(
        code=code,
        value=rendered,
        unit=unit,
        source_tool=source_tool,
        source_path=source_path,
        value_hash=_hash_value(code, rendered, source_path),
    )


def _fallback_output(code: str) -> dict[str, Any]:
    outputs: dict[str, dict[str, Any]] = {
        "information_collection": {
            "household_code": "unavailable",
            "synthetic": False,
            "confirmed": False,
            "fact_counts": {},
            "missing_information": ["结构化家庭事实暂不可用"],
        },
        "financial_statement": {
            "input_version": "unavailable",
            "net_worth": "unavailable",
            "annual_income": "unavailable",
            "annual_expenses": "unavailable",
            "annual_surplus": "unavailable",
            "accounting_identity": "未生成估算金额",
        },
        "financial_diagnosis": {
            "completeness_score": "unavailable",
            "diagnostic_codes": ["tool_unavailable"],
            "protection_gap": "unavailable",
            "most_significant_risk": "requires_review",
            "calculation_source": "none",
        },
        "goal_planning": {
            "lifecycle_stage": "unavailable",
            "goal_count": 0,
            "conflict_count": 0,
            "available_planning_resources": "unavailable",
            "eligible_long_term_amount": "unavailable",
            "growth_70_eligible": False,
            "failed_growth_conditions": ["deterministic_planning_unavailable"],
        },
        "behavior_finance": {
            "information_status": "insufficient",
            "effective_risk_limit": None,
            "risk_downshifted": None,
            "bias_codes": [],
            "intervention_codes": [],
        },
        "asset_allocation": {
            "catalog_version": "unavailable",
            "product_source_type": "mock",
            "eligible_long_term_amount": "unavailable",
            "candidate_decisions": {},
            "family_gate": "blocked",
            "customer_gate": "blocked",
        },
        "policy_knowledge": {
            "answer": "没有足够受控依据，需人工核对。",
            "insufficient_information": True,
            "citation_chunk_ids": [],
            "citation_titles": [],
            "as_of_date": "unavailable",
        },
        "report_generation": {
            "summary": "确定性工具或受控知识不可用，本地模板不生成财务结论。",
            "numeric_reference_codes": [],
            "citation_chunk_ids": [],
            "missing_information": ["至少一个上游步骤降级"],
            "template_fallback_used": True,
        },
        "compliance_audit": {
            "passed": False,
            "blocked": True,
            "requires_human_review": True,
            "issues": [
                {
                    "code": "compliance_tool_unavailable",
                    "severity": "block",
                    "message": "合规终检不可用，输出已阻断。",
                    "claim_index": None,
                    "evidence": [],
                }
            ],
            "checked_numeric_reference_count": 0,
            "checked_citation_count": 0,
        },
    }
    return outputs[code]


def _tool(
    name: str,
    output_reference: str,
    calculation_source: str,
    *,
    status: Literal["completed", "degraded", "blocked"] = "completed",
) -> ToolCallEvidence:
    return ToolCallEvidence(
        tool=name,
        status=status,
        input_reference="confirmed_database_state",
        output_reference=output_reference,
        calculation_source=calculation_source,
    )


def _execute_step(
    spec: AgentSpec,
    session: Session,
    household_id: str,
    request: OrchestrationRequest,
    settings: Settings,
    context: dict[str, Any],
    numeric_ledger: list[NumericLedgerEntry],
) -> tuple[dict[str, Any], list[ToolCallEvidence], list[str]]:
    analysis_date = request.analysis_date or date.today()
    citations: list[str] = []
    if spec.code == "information_collection":
        facts = load_household_facts(session, household_id)
        context["facts"] = facts
        output = {
            "household_code": facts.code,
            "synthetic": facts.is_synthetic,
            "confirmed": facts.is_user_confirmed,
            "fact_counts": {
                "members": len(facts.members),
                "incomes": len(facts.incomes),
                "expenses": len(facts.expenses),
                "assets": len(facts.assets),
                "liabilities": len(facts.liabilities),
                "insurance": len(facts.insurance_policies),
                "social_security": len(facts.social_security_accounts),
                "goals": len(facts.goals),
            },
            "missing_information": [
                item
                for item, missing in (
                    ("家庭成员", not facts.members),
                    ("收入", not facts.incomes),
                    ("支出", not facts.expenses),
                    ("资产", not facts.assets),
                    ("保障", not facts.insurance_policies),
                )
                if missing
            ],
        }
        return (
            output,
            [_tool("load_household_facts", "context.facts", "confirmed_relational_facts")],
            citations,
        )

    if spec.code in {"financial_statement", "financial_diagnosis"}:
        financial = context.get("financial")
        if financial is None:
            financial = analyze_household(
                session, household_id, settings.financial_rules_path, analysis_date
            )
            context["financial"] = financial
        if spec.code == "financial_statement":
            balance = financial.statements.balance_sheet
            cashflow = financial.statements.cash_flow
            entries = [
                _numeric(
                    "net_worth",
                    balance.net_worth,
                    "CNY",
                    "analyze_household",
                    "financial.statements.balance_sheet.net_worth",
                ),
                _numeric(
                    "annual_income",
                    cashflow.annual_income,
                    "CNY/year",
                    "analyze_household",
                    "financial.statements.cash_flow.annual_income",
                ),
                _numeric(
                    "annual_expenses",
                    cashflow.annual_expenses,
                    "CNY/year",
                    "analyze_household",
                    "financial.statements.cash_flow.annual_expenses",
                ),
                _numeric(
                    "annual_surplus",
                    cashflow.annual_surplus,
                    "CNY/year",
                    "analyze_household",
                    "financial.statements.cash_flow.annual_surplus",
                ),
            ]
            numeric_ledger.extend(
                entry
                for entry in entries
                if entry.code not in {item.code for item in numeric_ledger}
            )
            output = {
                "input_version": financial.meta.input_version,
                "net_worth": str(balance.net_worth),
                "annual_income": str(cashflow.annual_income),
                "annual_expenses": str(cashflow.annual_expenses),
                "annual_surplus": str(cashflow.annual_surplus),
                "accounting_identity": balance.accounting_identity,
            }
            return (
                output,
                [
                    _tool(
                        "analyze_household",
                        "context.financial.statements",
                        financial.meta.calculation_source,
                    )
                ],
                citations,
            )
        protection_entry = _numeric(
            "protection_gap",
            financial.protection.protection_gap,
            "CNY",
            "analyze_household",
            "financial.protection.protection_gap",
        )
        if protection_entry.code not in {item.code for item in numeric_ledger}:
            numeric_ledger.append(protection_entry)
        output = {
            "completeness_score": str(financial.diagnostics.completeness_score),
            "diagnostic_codes": [item.code for item in financial.diagnostics.issues],
            "protection_gap": str(financial.protection.protection_gap),
            "most_significant_risk": financial.protection.most_significant_risk,
            "calculation_source": financial.meta.calculation_source,
        }
        return (
            output,
            [
                _tool(
                    "financial_diagnostics",
                    "context.financial.diagnostics",
                    financial.meta.calculation_source,
                ),
                _tool(
                    "protection_assessment",
                    "context.financial.protection",
                    financial.meta.calculation_source,
                ),
            ],
            citations,
        )

    if spec.code == "goal_planning":
        planning = plan_household(
            session,
            household_id,
            settings.financial_rules_path,
            settings.planning_rules_path,
            analysis_date,
        )
        context["planning"] = planning
        growth = next(
            account
            for account in planning.accounts
            if account.bucket == AccountBucket.LONG_TERM_GROWTH
        )
        for entry in (
            _numeric(
                "available_planning_resources",
                planning.denominators.available_planning_resources,
                "CNY",
                "plan_household",
                "planning.denominators.available_planning_resources",
            ),
            _numeric(
                "eligible_long_term_amount",
                growth.recommended_amount,
                "CNY",
                "plan_household",
                "planning.accounts.long_term_growth.recommended_amount",
            ),
        ):
            if entry.code not in {item.code for item in numeric_ledger}:
                numeric_ledger.append(entry)
        output = {
            "lifecycle_stage": planning.lifecycle.effective_stage.value,
            "goal_count": len(planning.goals),
            "conflict_count": len(planning.conflicts),
            "available_planning_resources": str(planning.denominators.available_planning_resources),
            "eligible_long_term_amount": str(growth.recommended_amount),
            "growth_70_eligible": planning.growth_70.eligible,
            "failed_growth_conditions": planning.growth_70.failed_conditions,
        }
        return (
            output,
            [_tool("plan_household", "context.planning", planning.meta.calculation_source)],
            citations,
        )

    if spec.code == "behavior_finance":
        behavior = behavior_overview(session, household_id, settings.behavior_rules_path)
        context["behavior"] = behavior
        profile = behavior.profile
        output = {
            "information_status": behavior.information_status,
            "effective_risk_limit": (
                profile.dual_profile.effective_risk_limit.value if profile else None
            ),
            "risk_downshifted": profile.dual_profile.risk_downshifted if profile else None,
            "bias_codes": [item.code for item in profile.biases] if profile else [],
            "intervention_codes": [item.code for item in profile.interventions] if profile else [],
        }
        return (
            output,
            [_tool("behavior_overview", "context.behavior", "deterministic_behavior_engine")],
            citations,
        )

    if spec.code == "asset_allocation":
        portfolio = portfolio_household(
            session,
            household_id,
            settings.financial_rules_path,
            settings.planning_rules_path,
            settings.portfolio_rules_path,
            settings.product_catalog_path,
            analysis_date,
        )
        context["portfolio"] = portfolio
        output = {
            "catalog_version": portfolio.meta.catalog_version,
            "product_source_type": portfolio.catalog.source_type,
            "eligible_long_term_amount": str(portfolio.context.eligible_long_term_amount),
            "candidate_decisions": {
                candidate.candidate_type.value: candidate.decision.value
                for candidate in portfolio.candidates
            },
            "family_gate": portfolio.family_safety_gate.status.value,
            "customer_gate": portfolio.customer_suitability_gate.status.value,
        }
        return (
            output,
            [
                _tool(
                    "portfolio_household", "context.portfolio", portfolio.meta.calculation_source
                ),
                _tool(
                    "controlled_product_catalog",
                    "context.portfolio.catalog",
                    "mock_controlled_catalog",
                ),
            ],
            citations,
        )

    if spec.code == "policy_knowledge":
        result = search_knowledge(
            session,
            settings.knowledge_base_path,
            KnowledgeSearchRequest(query=request.policy_query, as_of_date=analysis_date),
        )
        context["knowledge"] = result
        citations = [citation.chunk_id for citation in result.citations]
        output = {
            "answer": result.answer,
            "insufficient_information": result.insufficient_information,
            "citation_chunk_ids": citations,
            "citation_titles": [citation.title for citation in result.citations],
            "as_of_date": result.as_of_date.isoformat(),
        }
        return (
            output,
            [_tool("hybrid_knowledge_search", "context.knowledge", result.calculation_source)],
            citations,
        )

    if spec.code == "report_generation":
        report_facts = context.get("facts")
        knowledge = context.get("knowledge")
        net_worth = next((item for item in numeric_ledger if item.code == "net_worth"), None)
        annual_surplus = next(
            (item for item in numeric_ledger if item.code == "annual_surplus"), None
        )
        missing: list[str] = []
        if report_facts is None:
            missing.append("家庭事实")
        if knowledge is None or knowledge.insufficient_information:
            missing.append("政策依据")
        summary_parts = ["以下解释只复述已验证工具账本和受控来源。"]
        if net_worth is not None:
            summary_parts.append(f"净资产账本值为 {net_worth.value} 元。")
        if annual_surplus is not None:
            summary_parts.append(f"年度结余账本值为 {annual_surplus.value} 元。")
        if knowledge is not None and not knowledge.insufficient_information:
            summary_parts.append("政策说明已附受控来源和有效期。")
        report_citations = (
            [citation.chunk_id for citation in knowledge.citations] if knowledge else []
        )
        output = {
            "summary": "".join(summary_parts),
            "numeric_reference_codes": [item.code for item in numeric_ledger],
            "citation_chunk_ids": report_citations,
            "missing_information": missing,
            "template_fallback_used": True,
        }
        context["report"] = output
        return (
            output,
            [
                _tool("template_explanation", "context.report", "local_template_provider"),
                _tool("numeric_ledger", "run.numeric_ledger", "deterministic_tools_only"),
                _tool("citation_ledger", "run.citation_chunk_ids", "controlled_knowledge_only"),
            ],
            report_citations,
        )

    if spec.code == "compliance_audit":
        knowledge = context.get("knowledge")
        report = context.get("report", {})
        claims = [
            GovernanceClaim(
                text=f"工具账本 {entry.code} 的值为 {entry.value}。",
                claim_type="numeric",
                value=entry.value,
                tool_reference=entry.code,
            )
            for entry in numeric_ledger
        ]
        if knowledge is not None and knowledge.citations:
            claims.append(
                GovernanceClaim(
                    text="政策解释仅来自受控知识切片并带有效期。",
                    claim_type="policy",
                    citation_chunk_ids=[citation.chunk_id for citation in knowledge.citations],
                )
            )
        report_portfolio = context.get("portfolio")
        if report_portfolio is not None:
            mapped = next(
                (
                    mapping
                    for candidate in report_portfolio.candidates
                    for mapping in candidate.product_mappings
                    if mapping.product_code is not None
                ),
                None,
            )
            if mapped is not None:
                claims.append(
                    GovernanceClaim(
                        text="组合映射仅引用当前受控 Mock 产品目录。",
                        claim_type="product",
                        product_code=mapped.product_code,
                        product_catalog_version=report_portfolio.meta.catalog_version,
                    )
                )
        validation = validate_governed_output(
            session,
            GovernanceValidationRequest(
                claims=claims,
                numeric_ledger=numeric_ledger,
                as_of_date=analysis_date,
                ordinary_household_path=True,
            ),
        )
        context["governance"] = validation
        output = {
            "passed": validation.passed,
            "blocked": validation.blocked,
            "requires_human_review": validation.requires_human_review,
            "issues": [issue.model_dump(mode="json") for issue in validation.issues],
            "checked_numeric_reference_count": len(numeric_ledger),
            "checked_citation_count": len(report.get("citation_chunk_ids", [])),
        }
        return (
            output,
            [
                _tool(
                    "deterministic_governance_validator",
                    "context.governance",
                    validation.calculation_source,
                )
            ],
            list(report.get("citation_chunk_ids", [])),
        )

    raise KeyError(spec.code)


def _step_out(step: AgentStepRun) -> AgentStepOut:
    spec = next(item for item in AGENT_SPECS if item.code == step.agent_code)
    return AgentStepOut(
        step_id=step.id,
        agent_code=step.agent_code,
        agent_name=spec.name,
        sequence=step.sequence,
        status=step.status.value,
        input_schema_name=step.input_schema_name,
        output_schema_name=step.output_schema_name,
        tool_calls=[ToolCallEvidence.model_validate(item) for item in step.tool_calls],
        structured_output=step.structured_output,
        citations=step.citations,
        prohibitions_checked=step.prohibitions_checked,
        timeout_seconds=step.timeout_seconds,
        failure_code=step.failure_code,
        degraded=step.degraded,
        started_at=step.started_at,
        completed_at=step.completed_at,
    )


def _run_out(
    session: Session, run: AgentOrchestrationRun, provider_mode: str
) -> OrchestrationResponse:
    steps = list(
        session.scalars(
            select(AgentStepRun)
            .where(AgentStepRun.run_id == run.id, AgentStepRun.is_deleted.is_(False))
            .order_by(AgentStepRun.sequence)
        ).all()
    )
    return OrchestrationResponse(
        run_id=run.id,
        household_id=run.household_id,
        request_kind=run.request_kind,
        status=run.status.value,
        current_state=run.current_state,
        orchestrator_version=run.orchestrator_version,
        provider_mode=provider_mode,
        steps=[_step_out(step) for step in steps],
        numeric_ledger=[NumericLedgerEntry.model_validate(item) for item in run.numeric_ledger],
        citation_chunk_ids=run.citation_chunk_ids,
        structured_output=run.structured_output,
        blocked_issues=[GovernanceIssue.model_validate(item) for item in run.blocked_issues],
        requires_human_review=run.requires_human_review,
        degraded=run.degraded,
        started_at=run.started_at,
        completed_at=run.completed_at,
        boundary_note=(
            "九个步骤均受状态机和工具白名单约束；模型只可理解与解释，"
            "任何数字、政策和产品声明必须通过终检。"
        ),
    )


def run_orchestration(
    session: Session,
    household_id: str,
    request: OrchestrationRequest,
    actor: ActorContext,
    settings: Settings,
) -> OrchestrationResponse:
    facts = load_household_facts(session, household_id)
    analysis_date = request.analysis_date or date.today()
    started_at = utc_now()
    run = AgentOrchestrationRun(
        household_id=household_id,
        request_kind=request.request_kind,
        status=OrchestrationStatus.RUNNING,
        current_state=AGENT_SPECS[0].code,
        query_hash=hashlib.sha256(request.policy_query.encode("utf-8")).hexdigest(),
        redacted_input={
            "policy_query_hash": hashlib.sha256(request.policy_query.encode("utf-8")).hexdigest(),
            "query_length": len(request.policy_query),
            "analysis_date": analysis_date.isoformat(),
            "household_input_version": f"{facts.id}:v{facts.version}",
        },
        structured_output={},
        numeric_ledger=[],
        citation_chunk_ids=[],
        blocked_issues=[],
        requires_human_review=False,
        degraded=False,
        orchestrator_version=ORCHESTRATOR_VERSION,
        started_at=started_at,
        valuation_date=analysis_date,
        data_source="deterministic_agent_orchestrator",
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
            summary="启动九智能体可信编排状态机",
            evidence={
                "state_machine": [spec.code for spec in AGENT_SPECS],
                "query_hash": run.query_hash,
            },
            occurred_at=started_at,
            valuation_date=analysis_date,
            data_source="deterministic_agent_orchestrator",
            is_user_confirmed=True,
        )
    )
    session.commit()

    context: dict[str, Any] = {"facts": facts}
    numeric_ledger: list[NumericLedgerEntry] = []
    citation_ids: list[str] = []
    any_degraded = False
    model_ledger_outputs: dict[str, dict[str, Any]] = {}
    for spec in AGENT_SPECS:
        run.current_state = spec.code
        step_started = utc_now()
        timer = monotonic()
        failure_code: str | None = None
        degraded = False
        try:
            output, tool_calls, citations = _execute_step(
                spec,
                session,
                household_id,
                request,
                settings,
                context,
                numeric_ledger,
            )
            output = validate_agent_output(spec.code, output)
            elapsed = monotonic() - timer
            if elapsed > spec.timeout_seconds:
                failure_code = "step_timeout_budget_exceeded"
                degraded = True
        except Exception as exc:  # safe per-step fallback is part of the state machine contract
            failure_code = type(exc).__name__
            degraded = True
            output = validate_agent_output(spec.code, _fallback_output(spec.code))
            tool_calls = [
                _tool(
                    spec.allowed_tools[0],
                    "fallback_output",
                    "local_safe_fallback",
                    status="degraded",
                )
            ]
            citations = []
        any_degraded = any_degraded or degraded
        model_ledger_outputs[spec.code] = output
        citation_ids.extend(item for item in citations if item not in citation_ids)
        step = AgentStepRun(
            run_id=run.id,
            household_id=household_id,
            agent_code=spec.code,
            sequence=spec.sequence,
            status=AgentStepStatus.DEGRADED if degraded else AgentStepStatus.COMPLETED,
            input_schema_name=spec.input_model.__name__,
            output_schema_name=spec.output_model.__name__,
            tool_calls=[item.model_dump(mode="json") for item in tool_calls],
            structured_output=output,
            citations=citations,
            prohibitions_checked=list(spec.prohibited_actions),
            timeout_seconds=spec.timeout_seconds,
            failure_code=failure_code,
            degraded=degraded,
            started_at=step_started,
            completed_at=utc_now(),
            valuation_date=analysis_date,
            data_source="deterministic_agent_orchestrator",
            is_user_confirmed=False,
        )
        session.add(step)
        session.flush()
        session.add(
            AuditEvent(
                household_id=household_id,
                event_type=(
                    AuditEventType.AGENT_STEP_DEGRADED
                    if degraded
                    else AuditEventType.AGENT_STEP_COMPLETED
                ),
                actor_id=actor.actor_id,
                actor_role=actor.role,
                entity_type="AgentStepRun",
                entity_id=step.id,
                event_version=step.version,
                summary=f"{spec.name}{'降级完成' if degraded else '完成'}",
                evidence={
                    "agent_code": spec.code,
                    "tool_calls": [item.tool for item in tool_calls],
                    "failure_code": failure_code,
                    "prohibitions_checked": list(spec.prohibited_actions),
                },
                occurred_at=step.completed_at or utc_now(),
                valuation_date=analysis_date,
                data_source="deterministic_agent_orchestrator",
                is_user_confirmed=True,
            )
        )
        session.commit()

    governance = context.get("governance")
    blocked = bool(governance and governance.blocked)
    run.status = (
        OrchestrationStatus.BLOCKED
        if blocked
        else OrchestrationStatus.DEGRADED
        if any_degraded
        else OrchestrationStatus.COMPLETED
    )
    run.current_state = "finished"
    run.numeric_ledger = [item.model_dump(mode="json") for item in numeric_ledger]
    run.citation_chunk_ids = citation_ids
    run.blocked_issues = (
        [item.model_dump(mode="json") for item in governance.issues] if governance else []
    )
    run.requires_human_review = bool(governance and governance.requires_human_review)
    run.degraded = any_degraded
    run.structured_output = {
        "report": context.get("report", _fallback_output("report_generation")),
        "governance": (
            governance.model_dump(mode="json")
            if governance is not None
            else _fallback_output("compliance_audit")
        ),
        "completion_rule": "all_nine_steps_persisted_and_governance_checked",
    }
    run.completed_at = utc_now()
    run.version += 1
    record_orchestration_model_ledger(
        session,
        household_id=household_id,
        actor=actor,
        provider="mock_template" if settings.is_mock_mode else settings.llm_provider,
        model_name=settings.llm_model or "fortune-copilot-template-v1",
        prompt_version=ORCHESTRATOR_VERSION,
        started_at=started_at,
        outputs=model_ledger_outputs,
        degraded=any_degraded,
        human_review_required=run.requires_human_review,
    )
    session.add(
        AuditEvent(
            household_id=household_id,
            event_type=AuditEventType.ORCHESTRATION_COMPLETED,
            actor_id=actor.actor_id,
            actor_role=actor.role,
            entity_type="AgentOrchestrationRun",
            entity_id=run.id,
            event_version=run.version,
            summary=f"九智能体可信编排结束：{run.status.value}",
            evidence={
                "step_count": len(AGENT_SPECS),
                "numeric_reference_count": len(numeric_ledger),
                "citation_count": len(citation_ids),
                "blocked": blocked,
                "degraded": any_degraded,
            },
            occurred_at=run.completed_at,
            valuation_date=analysis_date,
            data_source="deterministic_agent_orchestrator",
            is_user_confirmed=True,
        )
    )
    session.commit()
    session.refresh(run)
    return _run_out(
        session, run, "mock_template" if settings.is_mock_mode else settings.llm_provider
    )


def get_orchestration(
    session: Session,
    household_id: str,
    run_id: str,
    settings: Settings,
) -> OrchestrationResponse:
    run = session.scalar(
        select(AgentOrchestrationRun).where(
            AgentOrchestrationRun.id == run_id,
            AgentOrchestrationRun.household_id == household_id,
            AgentOrchestrationRun.orchestrator_version == ORCHESTRATOR_VERSION,
            AgentOrchestrationRun.is_deleted.is_(False),
        )
    )
    if run is None:
        raise AppError("orchestration_not_found", "可信编排记录不存在", status_code=404)
    return _run_out(
        session, run, "mock_template" if settings.is_mock_mode else settings.llm_provider
    )


def latest_orchestration(
    session: Session,
    household_id: str,
    settings: Settings,
) -> OrchestrationResponse | None:
    run = session.scalar(
        select(AgentOrchestrationRun)
        .where(
            AgentOrchestrationRun.household_id == household_id,
            AgentOrchestrationRun.orchestrator_version == ORCHESTRATOR_VERSION,
            AgentOrchestrationRun.is_deleted.is_(False),
        )
        .order_by(AgentOrchestrationRun.created_at.desc(), AgentOrchestrationRun.id.desc())
    )
    if run is None:
        return None
    return _run_out(
        session, run, "mock_template" if settings.is_mock_mode else settings.llm_provider
    )
