from __future__ import annotations

from calendar import monthrange
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import ActorContext
from app.core.errors import AppError
from app.core.privacy import stable_hash
from app.domain.enums import AuditEventType, PlanWorkflowState
from app.models.assessment import BehaviorAssessment
from app.models.common import utc_now
from app.models.family import ConsentRecord
from app.models.governance import AuditEvent, PlanReport, PlanWorkflowVersion
from app.schemas.client_experience import (
    ActionCalendarGroup,
    ActionCalendarItem,
    ClientDataExport,
    ClientDeliveryState,
    ClientExperienceResponse,
    ClientJourneyStep,
    ClientPrivacySummary,
    ClientReportChapter,
    ClientReportPreview,
    ConsentWithdrawRequest,
    HumanReviewRequest,
    HumanReviewResponse,
    PrivacyConsentItem,
)
from app.schemas.financial_analysis import FinancialAnalysisResponse
from app.schemas.planning import PlanningResponse
from app.schemas.trust import KnowledgeSearchRequest
from app.services.crud import ensure_household, get_active
from app.services.financial.engine import analyze_household
from app.services.planning.engine import plan_household
from app.services.trust.knowledge import search_knowledge

EXPERIENCE_VERSION = "client-experience-v1.0.0"
REPORT_VERSION = "client-report-preview-v1.0.0"
STATE_CATALOG = [
    "loading",
    "skeleton",
    "empty",
    "first_use",
    "missing_data",
    "data_conflict",
    "calculation_failed",
    "model_degraded",
    "permission_denied",
    "offline",
    "stale_data",
    "no_suitable_product",
    "compliance_blocked",
    "report_failed",
]
CLIENT_READY_WORKFLOW_STATES = {
    PlanWorkflowState.COMPLIANCE_REVIEWED,
    PlanWorkflowState.CUSTOMER_CONFIRMED,
    PlanWorkflowState.ACTIVE,
    PlanWorkflowState.SUPERSEDED,
}


def _add_months(value: date, months: int) -> date:
    index = (value.month - 1) + months
    year = value.year + index // 12
    month = (index % 12) + 1
    day = min(value.day, monthrange(year, month)[1])
    return date(year, month, day)


def _privacy_summary(session: Session, household_id: str) -> ClientPrivacySummary:
    records = list(
        session.scalars(
            select(ConsentRecord)
            .where(
                ConsentRecord.household_id == household_id,
                ConsentRecord.is_deleted.is_(False),
            )
            .order_by(ConsentRecord.granted_at, ConsentRecord.id)
        ).all()
    )
    scenario_scopes = {
        "core_planning": {"profile", "finance", "risk"},
        "protection_review": {"identity_sensitive", "health_sensitive", "insurance"},
        "simulation_and_report": {"simulation", "report"},
        "behavior_experiment": {"behavior"},
    }
    sensitive_scopes = {"identity_sensitive", "health_sensitive", "insurance"}
    consents = [
        PrivacyConsentItem(
            id=item.id,
            scopes=item.scopes,
            purpose=item.purpose,
            granted_at=item.granted_at,
            withdrawn_at=item.withdrawn_at,
            consent_version=item.consent_version,
            record_version=item.version,
            status="withdrawn" if item.withdrawn_at is not None else "active",
            withdrawal_allowed=item.withdrawn_at is None,
            scenario=str(item.metadata_json.get("scenario", "unspecified")),
            sensitive=bool(set(item.scopes) & sensitive_scopes),
            explicit=item.metadata_json.get("explicit") is True,
            minimum_necessary=set(item.scopes).issubset(
                scenario_scopes.get(str(item.metadata_json.get("scenario", "")), set())
            ),
        )
        for item in records
    ]
    active = sum(item.status == "active" for item in consents)
    return ClientPrivacySummary(
        active_consent_count=active,
        withdrawn_consent_count=len(consents) - active,
        consents=consents,
        export_path=f"/api/v1/households/{household_id}/privacy/exports",
        delete_path=f"/api/v1/households/{household_id}/privacy/deletion-requests",
        human_review_path=f"/api/v1/households/{household_id}/privacy/human-review-requests",
        boundary_note=(
            "撤回授权后不再把对应范围用于新计算；删除采用带版本、操作头和家庭代码"
            "三重确认的逻辑擦除与去标识。"
            "竞赛 Mock 数据不连接真实银行账户。"
        ),
    )


def _delivery_state(session: Session, household_id: str) -> ClientDeliveryState:
    """Expose only whether client-facing artifacts may be requested, never draft details."""

    workflow = session.scalar(
        select(PlanWorkflowVersion)
        .where(
            PlanWorkflowVersion.household_id == household_id,
            PlanWorkflowVersion.is_current.is_(True),
            PlanWorkflowVersion.is_deleted.is_(False),
        )
        .order_by(PlanWorkflowVersion.created_at.desc(), PlanWorkflowVersion.id.desc())
    )
    report = session.scalar(
        select(PlanReport)
        .where(
            PlanReport.household_id == household_id,
            PlanReport.is_current.is_(True),
            PlanReport.is_deleted.is_(False),
        )
        .order_by(PlanReport.sequence.desc(), PlanReport.id.desc())
    )
    workflow_ready = workflow is not None and workflow.state in CLIENT_READY_WORKFLOW_STATES
    workflow_state = (
        "not_created" if workflow is None else "client_ready" if workflow_ready else "under_review"
    )
    if report is None:
        report_state = "under_review" if workflow_state == "under_review" else "not_generated"
    elif report.publication_status == "published" or workflow is None or workflow_ready:
        report_state = "client_ready"
    else:
        report_state = "under_review"
    explanation = {
        "client_ready": "客户可读取当前正式报告、行动账本和可见审核版本。",
        "under_review": "内部草稿仍在顾问或合规审核中；客户端只显示确定性预览。",
        "not_generated": "尚未生成正式报告；客户端可从确定性预览创建新快照。",
    }[report_state]
    return ClientDeliveryState(
        report=report_state,
        workflow=workflow_state,
        actions=report_state,
        explanation=explanation,
    )


def build_action_calendar(
    plan: PlanningResponse,
    analysis_date: date,
) -> list[ActionCalendarGroup]:
    buckets: dict[str, list[ActionCalendarItem]] = {
        "immediate": [],
        "three_months": [],
        "one_year": [],
        "long_term": [],
        "next_12_months": [],
    }
    for item in plan.actions:
        if item.due_date is not None:
            days = (item.due_date - analysis_date).days
            code = (
                "immediate"
                if days <= 14
                else "three_months"
                if days <= 90
                else "one_year"
                if days <= 365
                else "long_term"
            )
        else:
            code = (
                "immediate"
                if item.priority <= 2
                else "three_months"
                if item.priority <= 4
                else "one_year"
                if item.priority <= 6
                else "long_term"
            )
        buckets[code].append(
            ActionCalendarItem(
                code=item.action_code,
                title=item.title,
                detail=item.detail,
                why=(
                    f"规划服务按七步资金瀑布、目标期限与安全约束生成；"
                    f"当前确定性优先级为 {item.priority}。"
                ),
                constraint_or_formula=(
                    f"{item.action_code}: PlanningResponse.actions.amount = {item.amount}; "
                    f"规则 {plan.meta.rule_version}"
                ),
                change_trigger="家庭收入、支出、目标期限、已准备金额或安全约束变化后重新计算。",
                risk_and_assumptions="未经家庭确认不执行；不代表保本、收益承诺或具体产品推荐。",
                amount=str(item.amount),
                due_date=item.due_date,
                priority=item.priority,
                source_record_ids=item.source_record_ids,
                calculation_source="deterministic_planning_rules",
            )
        )

    review_titles = {
        1: ("核对本月现金流", "确认收入、必要支出和债务偿付是否与家庭事实一致。"),
        3: ("复盘目标准备率", "核对目标金额、期限、准备率和冲突是否变化。"),
        6: ("复核保障与应急层", "检查家庭责任、保障缺口和流动性安全期。"),
        9: ("检查组合偏离", "只在安全闸门通过后核对长期资金的再平衡条件。"),
        12: ("完成年度家庭体检", "使用新数据日重算财务健康、四账户和数字孪生。"),
    }
    for month in range(1, 13):
        title, detail = review_titles.get(
            month,
            ("月度行动复盘", "记录行动完成情况和家庭事实变化；不自动交易或调仓。"),
        )
        buckets["next_12_months"].append(
            ActionCalendarItem(
                code=f"monthly_review_{month:02d}",
                title=title,
                detail=detail,
                why="固定复盘节奏用于发现家庭事实变化，不根据市场涨跌催促交易。",
                constraint_or_formula=(
                    f"复盘日 = 分析日 {analysis_date.isoformat()} + {month} 个自然月"
                ),
                change_trigger="复盘发现收入、支出、家庭成员、目标或风险承受能力变化时触发重算。",
                risk_and_assumptions="任务金额为 0；只核对事实与方案，不自动交易、调仓或保证改善。",
                amount="0.00",
                due_date=_add_months(analysis_date, month),
                priority=month,
                source_record_ids=[],
                calculation_source="deterministic_review_schedule",
            )
        )
    labels = {
        "immediate": ("立即处理", "先处理会影响家庭安全或后续计算的事项。"),
        "three_months": ("未来三个月", "补齐安全层、资料和近期目标动作。"),
        "one_year": ("一年内", "按目标期限持续投入并核对约束。"),
        "long_term": ("长期", "只有长期资金才进入长期增长讨论。"),
        "next_12_months": ("未来 12 个月复盘", "每个月均有可核验任务，不以倒计时制造紧迫感。"),
    }
    return [
        ActionCalendarGroup(
            code=code,
            label=labels[code][0],
            description=labels[code][1],
            items=buckets[code],
        )
        for code in ("immediate", "three_months", "one_year", "long_term", "next_12_months")
    ]


def _report(
    session: Session,
    knowledge_path: str | Path,
    analysis: FinancialAnalysisResponse,
    plan: PlanningResponse,
    *,
    analysis_date: date,
) -> ClientReportPreview:
    knowledge = search_knowledge(
        session,
        str(knowledge_path),
        KnowledgeSearchRequest(
            query="家庭财富规划需要核对个人养老金、消费者权益、风险适当性和保险披露哪些边界",
            as_of_date=analysis_date,
            audiences=["普通家庭"],
            regions=[analysis.profile.region],
            limit=5,
        ),
    )
    citations = knowledge.citations
    citation_ids = [item.citation_id for item in citations]
    balance = analysis.statements.balance_sheet
    cashflow = analysis.statements.cash_flow
    protection = analysis.protection
    profile = analysis.profile
    chapters = [
        ClientReportChapter(
            number=1,
            title="家庭画像与生命周期",
            summary=(
                f"{profile.name}当前按{plan.lifecycle.effective_stage.value}阶段计算，"
                f"家庭成员 {len(profile.members)} 人。"
            ),
            calculation_basis=[plan.lifecycle.formula, plan.lifecycle.substitution],
            citation_ids=[],
            status="ready",
        ),
        ClientReportChapter(
            number=2,
            title="资产负债与现金流",
            summary=(
                f"总资产 {balance.total_assets} 元，总负债 {balance.total_liabilities} 元，"
                f"年度结余 {cashflow.annual_surplus} 元。"
            ),
            calculation_basis=[balance.accounting_identity, "现金流记录按频率年化并按用途互斥归类"],
            citation_ids=[],
            status="ready",
        ),
        ClientReportChapter(
            number=3,
            title="财务健康与家庭保障",
            summary=(
                f"当前最大保障缺口为 {protection.protection_gap} 元；"
                "该数值是责任测算，不是产品推荐。"
            ),
            calculation_basis=[protection.counting_note, "财务健康维度来源于版本化确定性规则"],
            citation_ids=citation_ids[:1],
            status="ready",
        ),
        ClientReportChapter(
            number=4,
            title="家庭目标与冲突",
            summary=f"已识别 {len(plan.goals)} 个目标与 {len(plan.conflicts)} 组资金冲突。",
            calculation_basis=[item.formula for item in plan.goals[:3]],
            citation_ids=[],
            status="ready",
        ),
        ClientReportChapter(
            number=5,
            title="四账户动态规划",
            summary="四账户按七步资金瀑布动态生成，不使用固定比例；每个结果保留三种分母。",
            calculation_basis=[item.formula for item in plan.accounts],
            citation_ids=citation_ids[1:2],
            status="ready",
        ),
        ClientReportChapter(
            number=6,
            title="方案比较与数字孪生",
            summary="方案比较必须使用相同输入版本；数字孪生运行后补入路径区间、目标失败顺序和压力影响。",
            calculation_basis=[
                "确定性候选方案 + 共同随机数路径模拟",
                "单根向上曲线不得替代分位数区间",
            ],
            citation_ids=[],
            status="pending_twin",
        ),
        ClientReportChapter(
            number=7,
            title="行动日历与复盘",
            summary=f"当前生成 {len(plan.actions)} 项规则行动，并附未来 12 个月复盘节奏。",
            calculation_basis=["行动来自规划约束与目标冲突，未经确认不自动执行"],
            citation_ids=[],
            status="ready",
        ),
        ClientReportChapter(
            number=8,
            title="计算依据、引用与风险边界",
            summary=f"报告引用 {len(citations)} 个受控知识切片；来源不足时必须转人工核验。",
            calculation_basis=[
                f"财务公式 {analysis.meta.formula_version}",
                f"规划规则 {plan.meta.rule_version}",
                f"知识检索 {knowledge.retrieval_version}",
            ],
            citation_ids=citation_ids,
            status="needs_review" if knowledge.insufficient_information else "ready",
        ),
    ]
    return ClientReportPreview(
        report_version=REPORT_VERSION,
        knowledge_retrieval_version=knowledge.retrieval_version,
        title=f"{profile.name}家庭财富规划书",
        subtitle="比赛版确定性预览，待顾问和合规人员复核",
        chapters=chapters,
        citations=citations,
        generated_at=utc_now(),
        data_as_of=analysis.meta.data_as_of,
        boundary_note=(
            "本预览严格保持八章。金额、比例和配置来自确定性工具；"
            "语言模型不得改写数字，正式版式与签署流程在后续阶段完成。"
        ),
    )


def _journey(
    *,
    active_consent_count: int,
    member_count: int,
    completeness: float,
    goal_count: int,
    behavior_ready: bool,
) -> list[ClientJourneyStep]:
    definitions = [
        (
            "privacy",
            "隐私授权",
            "completed" if active_consent_count else "needs_action",
            "已有有效授权" if active_consent_count else "尚无有效授权",
            "核对授权范围",
            "privacy",
        ),
        ("quick", "快速体验", "completed", "合成演示家庭可直接体验", "查看家庭结论", "health"),
        ("deep", "深度规划", "ready", "确定性引擎和资料确认流程可用", "进入家庭建档", "family"),
        (
            "profile",
            "家庭建档",
            "completed" if member_count else "needs_action",
            f"已记录 {member_count} 名家庭成员",
            "核对责任关系",
            "family",
        ),
        (
            "checkup",
            "财务体检",
            "completed" if completeness >= 80 else "needs_action",
            f"数据完整度 {completeness:.0f}%",
            "查看诊断",
            "health",
        ),
        (
            "goals",
            "家庭目标",
            "completed" if goal_count else "needs_action",
            f"已记录 {goal_count} 个目标",
            "核对期限和冲突",
            "goals",
        ),
        (
            "behavior",
            "风险与行为测评",
            "completed" if behavior_ready else "ready",
            "已有行为证据" if behavior_ready else "可开始受控实验",
            "查看双画像",
            "behavior",
        ),
        ("accounts", "四账户", "completed", "已按家庭约束动态计算", "核对三种分母", "accounts"),
        (
            "comparison",
            "方案对比",
            "ready",
            "三套确定性候选与适当性闸门可用",
            "比较方案",
            "accounts",
        ),
        ("twin", "数字孪生", "ready", "可运行版本化压力场景", "运行路径模拟", "twin"),
        ("report", "规划书", "completed", "八章确定性预览已生成", "核对计算和引用", "report"),
        (
            "calendar",
            "行动日历",
            "completed",
            "规则行动与未来 12 个月复盘已生成",
            "查看行动",
            "actions",
        ),
        ("review", "持续复盘", "ready", "家庭事实变化后可用同一规则重算", "安排复盘", "actions"),
    ]
    return [
        ClientJourneyStep(
            code=code, label=label, status=status, reason=reason, action=action, view=view
        )
        for code, label, status, reason, action, view in definitions
    ]


def build_client_experience(
    session: Session,
    household_id: str,
    *,
    financial_rules_path: str | Path,
    planning_rules_path: str | Path,
    knowledge_path: str | Path,
    analysis_date: date,
) -> ClientExperienceResponse:
    household = ensure_household(session, household_id)
    analysis = analyze_household(session, household_id, str(financial_rules_path), analysis_date)
    plan = plan_household(
        session,
        household_id,
        str(financial_rules_path),
        str(planning_rules_path),
        analysis_date,
    )
    privacy = _privacy_summary(session, household_id)
    report = _report(session, knowledge_path, analysis, plan, analysis_date=analysis_date)
    behavior_ready = (
        session.scalar(
            select(BehaviorAssessment.id).where(
                BehaviorAssessment.household_id == household_id,
                BehaviorAssessment.is_deleted.is_(False),
            )
        )
        is not None
    )
    return ClientExperienceResponse(
        household_id=household.id,
        household_code=household.code,
        household_name=household.name,
        household_version=household.version,
        synthetic_data=household.is_synthetic,
        analysis_date=analysis.meta.analysis_date,
        data_as_of=analysis.meta.data_as_of,
        journey=_journey(
            active_consent_count=privacy.active_consent_count,
            member_count=len(analysis.profile.members),
            completeness=float(analysis.diagnostics.completeness_score),
            goal_count=len(plan.goals),
            behavior_ready=behavior_ready,
        ),
        privacy=privacy,
        action_calendar=build_action_calendar(plan, analysis_date),
        report=report,
        delivery=_delivery_state(session, household_id),
        calculation_versions={
            "experience": EXPERIENCE_VERSION,
            "financial_formula": analysis.meta.formula_version,
            "financial_rule": analysis.meta.rule_version,
            "planning_formula": plan.meta.formula_version,
            "planning_rule": plan.meta.rule_version,
            "knowledge_retrieval": report.knowledge_retrieval_version,
            "report": report.report_version,
        },
        state_catalog=STATE_CATALOG,
    )


def build_client_data_export(
    session: Session,
    household_id: str,
    *,
    financial_rules_path: str | Path,
    planning_rules_path: str | Path,
    knowledge_path: str | Path,
    analysis_date: date,
) -> ClientDataExport:
    experience = build_client_experience(
        session,
        household_id,
        financial_rules_path=financial_rules_path,
        planning_rules_path=planning_rules_path,
        knowledge_path=knowledge_path,
        analysis_date=analysis_date,
    )
    analysis = analyze_household(session, household_id, str(financial_rules_path), analysis_date)
    plan = plan_household(
        session,
        household_id,
        str(financial_rules_path),
        str(planning_rules_path),
        analysis_date,
    )
    return ClientDataExport(
        package_version=EXPERIENCE_VERSION,
        exported_at=utc_now(),
        household_id=household_id,
        financial_analysis=analysis,
        planning=plan,
        client_experience=experience,
        boundary_note="仅包含当前家庭的已授权或合成数据，不包含信用卡额度资产化结果。",
    )


def withdraw_consent(
    session: Session,
    household_id: str,
    consent_id: str,
    request: ConsentWithdrawRequest,
    actor: ActorContext,
) -> PrivacyConsentItem:
    ensure_household(session, household_id)
    consent = get_active(session, ConsentRecord, consent_id, household_id=household_id)
    if consent.version != request.expected_version:
        raise AppError(
            "version_conflict",
            "授权记录已变化，请刷新后再撤回",
            status_code=409,
            details={"expected": request.expected_version, "current": consent.version},
        )
    if consent.withdrawn_at is None:
        now = utc_now()
        consent.withdrawn_at = now
        consent.version += 1
        consent.updated_at = now
        consent.metadata_json = {**consent.metadata_json, "withdrawal_reason": request.reason}
        event = AuditEvent(
            household_id=household_id,
            event_type=AuditEventType.CONSENT_WITHDRAWN,
            actor_id=actor.actor_id,
            actor_role=actor.role,
            entity_type="ConsentRecord",
            entity_id=consent.id,
            event_version=consent.version,
            summary="客户从隐私中心撤回授权",
            evidence={"reason_hash": stable_hash(request.reason), "scopes": consent.scopes},
            occurred_at=now,
            data_source="client_confirmed_input",
            is_user_confirmed=True,
        )
        session.add(event)
        session.commit()
        session.refresh(consent)
    return PrivacyConsentItem(
        id=consent.id,
        scopes=consent.scopes,
        purpose=consent.purpose,
        granted_at=consent.granted_at,
        withdrawn_at=consent.withdrawn_at,
        consent_version=consent.consent_version,
        record_version=consent.version,
        status="withdrawn",
        withdrawal_allowed=False,
        scenario=str(consent.metadata_json.get("scenario", "unspecified")),
        sensitive=bool(
            set(consent.scopes) & {"identity_sensitive", "health_sensitive", "insurance"}
        ),
        explicit=consent.metadata_json.get("explicit") is True,
        minimum_necessary=True,
    )


def request_human_review(
    session: Session,
    household_id: str,
    request: HumanReviewRequest,
    actor: ActorContext,
) -> HumanReviewResponse:
    ensure_household(session, household_id)
    now = utc_now()
    event = AuditEvent(
        household_id=household_id,
        event_type=AuditEventType.REVIEW_RECORDED,
        actor_id=actor.actor_id,
        actor_role=actor.role,
        entity_type="HumanDecisionRequest",
        entity_id=None,
        event_version=1,
        summary="客户请求人工解释或决策",
        evidence={"reason": request.reason, "context": request.context},
        occurred_at=now,
        data_source="client_confirmed_input",
        is_user_confirmed=True,
    )
    session.add(event)
    session.flush()
    event.entity_id = event.id
    session.commit()
    return HumanReviewResponse(
        request_id=event.id,
        household_id=household_id,
        created_at=now,
        message="人工复核请求已写入演示顾问队列；系统不会替代人工作出最终决定。",
    )
