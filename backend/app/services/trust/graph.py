from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.governance import PolicyDocument, Product, ScenarioDefinition
from app.schemas.trust import GraphEdge, GraphInference, GraphNode, HouseholdGraphResponse
from app.services.financial.engine import analyze_household
from app.services.financial.facts import load_household_facts

GRAPH_VERSION = "relational-household-graph-v1.0.0"
GraphLane = Literal["family", "facts", "goals", "controls", "knowledge"]
REQUIRED_NODE_TYPES = [
    "household_member",
    "lifecycle",
    "income",
    "expense",
    "asset",
    "liability",
    "insurance",
    "social_security",
    "personal_pension",
    "goal",
    "product",
    "risk",
    "policy",
    "regional_cost",
    "behavior_bias",
    "restriction",
    "market_scenario",
]


def _node(
    node_id: str,
    node_type: str,
    label: str,
    lane: GraphLane,
    properties: dict[str, str | int | bool | None],
    *,
    source_entity_type: str,
    source_entity_id: str | None = None,
    calculation_source: str = "confirmed_relational_fact",
) -> GraphNode:
    return GraphNode(
        id=node_id,
        node_type=node_type,
        label=label,
        lane=lane,
        properties=properties,
        source_entity_type=source_entity_type,
        source_entity_id=source_entity_id,
        calculation_source=calculation_source,
    )


def _edge(
    edge_id: str,
    source: str,
    target: str,
    relation: str,
    label: str,
    *evidence: str,
) -> GraphEdge:
    return GraphEdge(
        id=edge_id,
        source=source,
        target=target,
        relation=relation,
        label=label,
        evidence=list(evidence),
    )


def shanghai_demo_graph(*, as_of: date) -> HouseholdGraphResponse:
    property_value = Decimal("3200000.00")
    total_assets = Decimal("4000000.00")
    property_ratio = (property_value / total_assets).quantize(
        Decimal("0.000001"), rounding=ROUND_HALF_UP
    )
    nodes = [
        _node(
            "demo-household",
            "household",
            "上海双收入育儿家庭",
            "family",
            {"region": "上海市", "synthetic": True},
            source_entity_type="ControlledGraphFixture",
        ),
        _node(
            "member-primary",
            "household_member",
            "本人 · 35岁",
            "family",
            {"age": 35, "income_earner": True},
            source_entity_type="ControlledGraphFixture",
        ),
        _node(
            "member-spouse",
            "household_member",
            "配偶 · 34岁",
            "family",
            {"age": 34, "income_earner": True},
            source_entity_type="ControlledGraphFixture",
        ),
        _node(
            "member-child",
            "household_member",
            "子女 · 5岁",
            "family",
            {"age": 5, "dependent": True},
            source_entity_type="ControlledGraphFixture",
        ),
        _node(
            "member-parents",
            "household_member",
            "双方父母",
            "family",
            {"protection_information": "insufficient"},
            source_entity_type="ControlledGraphFixture",
        ),
        _node(
            "lifecycle-parenting",
            "lifecycle",
            "家庭责任期",
            "controls",
            {"detected_stage": "parenting"},
            source_entity_type="DeterministicLifecycleRule",
            calculation_source="deterministic_graph_rule",
        ),
        _node(
            "income-dual",
            "income",
            "双收入现金流",
            "facts",
            {"earner_count": 2, "amount_status": "user_confirmation_required"},
            source_entity_type="ControlledGraphFixture",
        ),
        _node(
            "expense-core",
            "expense",
            "育儿与基本生活支出",
            "facts",
            {"amount_status": "user_confirmation_required"},
            source_entity_type="ControlledGraphFixture",
        ),
        _node(
            "asset-home",
            "asset",
            "上海自住房",
            "facts",
            {"market_value": "3200000.00", "currency": "CNY", "property_use": "primary_residence"},
            source_entity_type="ControlledGraphFixture",
        ),
        _node(
            "liability-mortgage",
            "liability",
            "住房按揭",
            "facts",
            {"outstanding_balance": "1800000.00", "currency": "CNY"},
            source_entity_type="ControlledGraphFixture",
        ),
        _node(
            "insurance-parents",
            "insurance",
            "父母保障事实",
            "facts",
            {"status": "insufficient_information"},
            source_entity_type="ControlledGraphFixture",
        ),
        _node(
            "social-security",
            "social_security",
            "夫妻基本社保",
            "facts",
            {"status": "reported_not_verified"},
            source_entity_type="ControlledGraphFixture",
        ),
        _node(
            "personal-pension",
            "personal_pension",
            "个人养老金适配核对",
            "knowledge",
            {"participation": "unknown", "tax_status": "unknown"},
            source_entity_type="ControlledGraphFixture",
        ),
        _node(
            "goal-education",
            "goal",
            "子女教育目标",
            "goals",
            {"horizon_years": 13, "amount_status": "user_confirmation_required"},
            source_entity_type="ControlledGraphFixture",
        ),
        _node(
            "goal-retirement",
            "goal",
            "夫妻退休目标",
            "goals",
            {"horizon": "long_term"},
            source_entity_type="ControlledGraphFixture",
        ),
        _node(
            "product-controlled",
            "product",
            "受控产品类型目录",
            "knowledge",
            {"mode": "mock_only", "recommendation": "none"},
            source_entity_type="MockProductCatalog",
        ),
        _node(
            "risk-medium",
            "risk",
            "客观承受能力待核对",
            "controls",
            {"maximum": "not_above_objective_capacity"},
            source_entity_type="DeterministicRiskRule",
            calculation_source="deterministic_graph_rule",
        ),
        _node(
            "policy-pension",
            "policy",
            "个人养老金全国实施规则",
            "knowledge",
            {"source_required": True, "effective_date_required": True},
            source_entity_type="ControlledKnowledgeBase",
        ),
        _node(
            "regional-shanghai",
            "regional_cost",
            "上海生活成本内部诊断口径",
            "knowledge",
            {"source_type": "internal_demo", "not_cpi": True},
            source_entity_type="ControlledKnowledgeBase",
        ),
        _node(
            "bias-loss",
            "behavior_bias",
            "损失厌恶待实验核验",
            "controls",
            {"status": "not_assumed"},
            source_entity_type="BehaviorExperiment",
        ),
        _node(
            "restriction-safety",
            "restriction",
            "安全层优先",
            "controls",
            {"fixed_four_account_ratio": False, "credit_limit_is_asset": False},
            source_entity_type="PlanningGuardrail",
            calculation_source="deterministic_graph_rule",
        ),
        _node(
            "scenario-job",
            "market_scenario",
            "单收入中断压力",
            "controls",
            {"scenario_type": "income_shock", "result_status": "not_run"},
            source_entity_type="ScenarioCatalog",
        ),
    ]
    edges = [
        _edge("e1", "member-primary", "demo-household", "member_of", "家庭成员", "年龄35岁"),
        _edge("e2", "member-spouse", "demo-household", "member_of", "家庭成员", "双收入"),
        _edge("e3", "member-child", "demo-household", "dependent_of", "受抚养", "年龄5岁"),
        _edge(
            "e4",
            "member-parents",
            "demo-household",
            "support_responsibility",
            "赡养责任",
            "保障信息不足",
        ),
        _edge("e5", "income-dual", "demo-household", "supports", "双收入支持家庭", "金额待确认"),
        _edge(
            "e6",
            "liability-mortgage",
            "asset-home",
            "finances",
            "按揭关联自住房",
            "余额为合成图谱输入",
        ),
        _edge(
            "e7",
            "asset-home",
            "restriction-safety",
            "creates_concentration",
            "房产集中限制流动性",
            f"住房资产占比 {property_ratio}",
        ),
        _edge("e8", "member-child", "goal-education", "drives", "形成教育期限", "5岁至18岁为13年"),
        _edge(
            "e9",
            "demo-household",
            "lifecycle-parenting",
            "classified_as",
            "进入家庭责任期",
            "育儿、按揭、赡养并存",
        ),
        _edge(
            "e10",
            "insurance-parents",
            "restriction-safety",
            "limits",
            "保障信息不足限制增长",
            "不猜测父母保额",
        ),
        _edge(
            "e11",
            "social-security",
            "personal-pension",
            "complements",
            "基本养老与第三支柱分开",
            "个人养老金不替代基本养老",
        ),
        _edge(
            "e12",
            "policy-pension",
            "personal-pension",
            "governs",
            "政策约束参加与领取",
            "来源和有效期必填",
        ),
        _edge(
            "e13",
            "personal-pension",
            "goal-retirement",
            "may_support",
            "需确认后才可纳入养老",
            "税务和参与状态未知",
        ),
        _edge(
            "e14", "risk-medium", "product-controlled", "caps", "风险上限约束产品", "适当性不得绕过"
        ),
        _edge(
            "e15",
            "bias-loss",
            "risk-medium",
            "may_downshift",
            "行为只可维持或下调",
            "不得提高客观能力",
        ),
        _edge(
            "e16", "scenario-job", "income-dual", "stresses", "检验单收入中断", "尚未运行不生成结果"
        ),
        _edge(
            "e17",
            "regional-shanghai",
            "expense-core",
            "contextualizes",
            "只做地区语境分类",
            "不是CPI或最低工资",
        ),
        _edge(
            "e18",
            "restriction-safety",
            "product-controlled",
            "gates",
            "安全层先于产品映射",
            "动态金额而非固定比例",
        ),
    ]
    inferences = [
        GraphInference(
            code="responsibility_period",
            title="家庭责任期",
            conclusion="育儿、住房按揭与父母赡养并存，当前处于家庭责任期。",
            evidence_node_ids=["member-child", "liability-mortgage", "member-parents"],
            rule="存在未成年子女且承担长期负债或赡养责任",
        ),
        GraphInference(
            code="protection_focus",
            title="保障重点",
            conclusion="先核对双收入中断风险和父母保障缺口；信息不足时不推断保额。",
            evidence_node_ids=["income-dual", "insurance-parents", "restriction-safety"],
            rule="收入责任与未确认保障事实优先于增长配置",
            human_review_required=True,
        ),
        GraphInference(
            code="education_horizon",
            title="教育期限",
            conclusion="5岁子女距18岁约13年；具体入学目标日和金额仍需用户确认。",
            evidence_node_ids=["member-child", "goal-education"],
            rule="合成图谱年龄差计算，不替代用户目标日期",
        ),
        GraphInference(
            code="property_concentration",
            title="房产集中",
            conclusion=f"合成图谱住房资产占总资产 {property_ratio:.2%}，流动性与集中风险需单列。",
            evidence_node_ids=["asset-home", "liability-mortgage"],
            rule="3200000 ÷ 4000000，由确定性图谱工具计算",
        ),
        GraphInference(
            code="growth_ceiling",
            title="增长上限",
            conclusion="增长空间必须先通过流动性、债务、保障、期限、适当性和行为约束，不能从家庭总资产套用统一70%。",
            evidence_node_ids=["restriction-safety", "risk-medium", "bias-loss"],
            rule="五硬一软及行为不得上调客观能力",
        ),
        GraphInference(
            code="pension_fit",
            title="养老金适配",
            conclusion="夫妻可核对个人养老金资格，但参与状态、税务事实、产品目录和流动性需求未确认前不生成产品建议。",
            evidence_node_ids=["social-security", "personal-pension", "policy-pension"],
            rule="结构化事实与有效政策同时满足后才可解释适配",
            human_review_required=True,
        ),
    ]
    return HouseholdGraphResponse(
        graph_id="shanghai-dual-income-demo",
        graph_version=GRAPH_VERSION,
        title="35岁上海双收入家庭关系推导图",
        subtitle="5岁子女 · 有房贷 · 父母保障信息不足 · 完全合成示例",
        as_of_date=as_of,
        synthetic=True,
        nodes=nodes,
        edges=edges,
        inferences=inferences,
        node_type_coverage=sorted({node.node_type for node in nodes}),
        limitations=[
            "这是独立合成图谱示例，不是家庭 A／B／C 的事实，也不是工商银行客户数据。",
            "图中金额只用于演示关系推导；未确认字段不会被补全。",
            "个人养老金、社保与产品结论仍需按来源有效期和用户事实复核。",
        ],
    )


def household_graph(
    session: Session,
    household_id: str,
    *,
    analysis_date: date,
    financial_rules_path: str,
) -> HouseholdGraphResponse:
    facts = load_household_facts(session, household_id)
    financial = analyze_household(session, household_id, financial_rules_path, analysis_date)
    nodes: list[GraphNode] = [
        _node(
            f"household:{facts.id}",
            "household",
            facts.name,
            "family",
            {"region": facts.region, "synthetic": facts.is_synthetic},
            source_entity_type="Household",
            source_entity_id=facts.id,
        ),
        _node(
            f"lifecycle:{facts.id}",
            "lifecycle",
            f"生命周期 · {facts.lifecycle_stage.value}",
            "controls",
            {"recorded_stage": facts.lifecycle_stage.value},
            source_entity_type="Household",
            source_entity_id=facts.id,
        ),
        _node(
            f"regional:{facts.region}",
            "regional_cost",
            f"{facts.region}生活成本语境",
            "knowledge",
            {"status": "requires_confirmed_expenses", "not_cpi": True},
            source_entity_type="RegionalContextRule",
            calculation_source="deterministic_graph_rule",
        ),
        _node(
            f"restriction:{facts.id}",
            "restriction",
            "家庭安全与适当性约束",
            "controls",
            {"fixed_ratio": False, "credit_limit_is_asset": False},
            source_entity_type="PlanningGuardrail",
            calculation_source="deterministic_graph_rule",
        ),
        _node(
            f"risk:{facts.id}",
            "risk",
            "客观与行为风险上限",
            "controls",
            {
                "objective": (
                    facts.risk_assessments[-1].final_risk_limit.value
                    if facts.risk_assessments
                    else "missing"
                ),
                "behavior": (
                    facts.behavior_assessments[-1].final_behavior_limit.value
                    if facts.behavior_assessments
                    else "missing"
                ),
            },
            source_entity_type="RiskAssessment",
            source_entity_id=facts.risk_assessments[-1].id if facts.risk_assessments else None,
        ),
        _node(
            f"personal-pension:{facts.id}",
            "personal_pension",
            "个人养老金参加事实",
            "knowledge",
            {"status": "not_separately_reported"},
            source_entity_type="SocialSecurityAccount",
        ),
    ]
    edges: list[GraphEdge] = []
    household_node = f"household:{facts.id}"

    def add_fact_nodes(
        items: tuple[tuple[str, str, int, str], ...],
        node_type: str,
        prefix: str,
        lane: GraphLane,
    ) -> None:
        for item_id, label, item_version, source_type in items:
            nodes.append(
                _node(
                    f"{prefix}:{item_id}",
                    node_type,
                    label,
                    lane,
                    {"version": item_version},
                    source_entity_type=source_type,
                    source_entity_id=item_id,
                )
            )
            edges.append(
                _edge(
                    f"edge:{prefix}:{item_id}",
                    f"{prefix}:{item_id}",
                    household_node,
                    "belongs_to",
                    "属于该家庭",
                    f"source_record_id={item_id}",
                )
            )

    for member in facts.members:
        age = (
            analysis_date.year
            - member.birth_date.year
            - (
                (analysis_date.month, analysis_date.day)
                < (member.birth_date.month, member.birth_date.day)
            )
        )
        nodes.append(
            _node(
                f"member:{member.id}",
                "household_member",
                member.display_name,
                "family",
                {"relationship": member.relationship, "age": age},
                source_entity_type="HouseholdMember",
                source_entity_id=member.id,
            )
        )
        edges.append(
            _edge(
                f"edge:member:{member.id}",
                f"member:{member.id}",
                household_node,
                "member_of",
                "家庭成员",
                f"source_record_id={member.id}",
            )
        )
    add_fact_nodes(
        tuple((item.id, item.name, item.version, type(item).__name__) for item in facts.incomes),
        "income",
        "income",
        "facts",
    )
    add_fact_nodes(
        tuple((item.id, item.name, item.version, type(item).__name__) for item in facts.expenses),
        "expense",
        "expense",
        "facts",
    )
    add_fact_nodes(
        tuple((item.id, item.name, item.version, type(item).__name__) for item in facts.assets),
        "asset",
        "asset",
        "facts",
    )
    add_fact_nodes(
        tuple(
            (item.id, item.name, item.version, type(item).__name__) for item in facts.liabilities
        ),
        "liability",
        "liability",
        "facts",
    )
    add_fact_nodes(
        tuple(
            (item.id, item.name, item.version, type(item).__name__)
            for item in facts.insurance_policies
        ),
        "insurance",
        "insurance",
        "facts",
    )
    add_fact_nodes(
        tuple(
            (item.id, item.account_type, item.version, type(item).__name__)
            for item in facts.social_security_accounts
        ),
        "social_security",
        "social",
        "facts",
    )
    add_fact_nodes(
        tuple((item.id, item.name, item.version, type(item).__name__) for item in facts.goals),
        "goal",
        "goal",
        "goals",
    )
    for assessment in facts.behavior_assessments[-1:]:
        for bias in assessment.detected_biases:
            node_id = f"bias:{assessment.id}:{bias}"
            nodes.append(
                _node(
                    node_id,
                    "behavior_bias",
                    bias,
                    "controls",
                    {"assessment_version": assessment.version},
                    source_entity_type="BehaviorAssessment",
                    source_entity_id=assessment.id,
                )
            )
            edges.append(
                _edge(
                    f"edge:{node_id}",
                    node_id,
                    f"risk:{facts.id}",
                    "may_downshift",
                    "行为只可下调风险上限",
                    f"source_record_id={assessment.id}",
                )
            )
    products = list(
        session.scalars(
            select(Product)
            .where(Product.enabled.is_(True), Product.is_deleted.is_(False))
            .order_by(Product.code)
            .limit(3)
        ).all()
    )
    for product in products:
        node_id = f"product:{product.id}"
        nodes.append(
            _node(
                node_id,
                "product",
                product.name,
                "knowledge",
                {
                    "code": product.code,
                    "catalog_version": product.catalog_version,
                    "simulated": product.is_simulated,
                },
                source_entity_type="Product",
                source_entity_id=product.id,
            )
        )
        edges.append(
            _edge(
                f"edge:{node_id}",
                f"risk:{facts.id}",
                node_id,
                "gates",
                "需通过适当性",
                f"product_code={product.code}",
            )
        )
    active_policies = list(
        session.scalars(
            select(PolicyDocument)
            .where(
                PolicyDocument.effective_date <= analysis_date,
                (
                    PolicyDocument.expiry_date.is_(None)
                    | (PolicyDocument.expiry_date >= analysis_date)
                ),
                PolicyDocument.is_deleted.is_(False),
            )
            .order_by(PolicyDocument.category)
            .limit(5)
        ).all()
    )
    for policy in active_policies:
        node_id = f"policy:{policy.id}"
        nodes.append(
            _node(
                node_id,
                "policy",
                policy.title,
                "knowledge",
                {
                    "category": policy.category,
                    "effective_date": policy.effective_date.isoformat(),
                    "last_verified_date": policy.last_verified_date.isoformat()
                    if policy.last_verified_date
                    else None,
                },
                source_entity_type="PolicyDocument",
                source_entity_id=policy.id,
            )
        )
        edges.append(
            _edge(
                f"edge:{node_id}",
                node_id,
                household_node,
                "may_apply",
                "按对象和地区过滤后解释",
                f"document_version={policy.document_version}",
            )
        )
    scenario = session.scalar(
        select(ScenarioDefinition)
        .where(ScenarioDefinition.enabled.is_(True))
        .order_by(ScenarioDefinition.code)
    )
    nodes.append(
        _node(
            f"scenario:{scenario.id if scenario else 'none'}",
            "market_scenario",
            scenario.name if scenario else "市场情景待加载",
            "controls",
            {"status": "available_not_run" if scenario else "missing"},
            source_entity_type="ScenarioDefinition",
            source_entity_id=scenario.id if scenario else None,
        )
    )
    if not any(node.node_type == "behavior_bias" for node in nodes):
        nodes.append(
            _node(
                f"bias:{facts.id}:missing",
                "behavior_bias",
                "行为偏差信息不足",
                "controls",
                {"status": "missing"},
                source_entity_type="BehaviorAssessment",
            )
        )
    if not any(node.node_type == "product" for node in nodes):
        nodes.append(
            _node(
                f"product:{facts.id}:missing",
                "product",
                "Mock产品目录未加载",
                "knowledge",
                {"status": "missing"},
                source_entity_type="Product",
            )
        )
    if not any(node.node_type == "policy" for node in nodes):
        nodes.append(
            _node(
                f"policy:{facts.id}:missing",
                "policy",
                "受控政策未加载",
                "knowledge",
                {"status": "missing"},
                source_entity_type="PolicyDocument",
            )
        )

    property_assets = sum(
        (
            asset.market_value
            for asset in facts.assets
            if asset.property_use.value != "not_property"
        ),
        Decimal("0"),
    )
    property_ratio = (
        property_assets / financial.statements.balance_sheet.total_assets
        if financial.statements.balance_sheet.total_assets > 0
        else None
    )
    children = [member for member in facts.members if member.relationship in {"子女", "child"}]
    education_goals = [goal for goal in facts.goals if goal.goal_type.value == "education"]
    inferences = [
        GraphInference(
            code="responsibility_period",
            title="家庭责任期",
            conclusion=(
                "存在子女、长期目标或负债，家庭责任约束优先。"
                if children or facts.liabilities
                else "未识别子女或负债，仍需按完整事实核对责任期。"
            ),
            evidence_node_ids=[household_node, f"lifecycle:{facts.id}"],
            rule="关系表事实驱动，不用模型猜测",
        ),
        GraphInference(
            code="protection_focus",
            title="保障重点",
            conclusion=(
                "确定性财务工具测得最大保障缺口 "
                f"{financial.protection.protection_gap:.2f} 元；具体产品仍需人工与适当性复核。"
            ),
            evidence_node_ids=[household_node, f"restriction:{facts.id}"],
            rule="financial_analysis.protection.protection_gap",
        ),
        GraphInference(
            code="education_horizon",
            title="教育期限",
            conclusion=(
                "最近教育目标日为 "
                f"{min(goal.target_date for goal in education_goals).isoformat()}。"
                if education_goals
                else "未提供教育目标日期，不生成期限。"
            ),
            evidence_node_ids=[
                f"goal:{education_goals[0].id}" if education_goals else household_node
            ],
            rule="只读取用户确认目标日期",
        ),
        GraphInference(
            code="property_concentration",
            title="房产集中",
            conclusion=(
                f"住房类资产占总资产 {property_ratio:.2%}，该比率由关系表金额计算。"
                if property_ratio is not None
                else "总资产为零或无住房资产，房产集中率不适用。"
            ),
            evidence_node_ids=[household_node],
            rule="住房类市场价值 ÷ 总资产",
        ),
        GraphInference(
            code="growth_ceiling",
            title="增长上限",
            conclusion="增长账户必须经过安全层与客观／行为风险上限，70%不是家庭总资产统一比例。",
            evidence_node_ids=[f"risk:{facts.id}", f"restriction:{facts.id}"],
            rule="动态四账户与五硬一软",
        ),
        GraphInference(
            code="pension_fit",
            title="养老金适配",
            conclusion="社保记录可作为养老事实；个人养老金参与、税务状态和产品选择仍需单独确认并引用有效政策。",
            evidence_node_ids=[f"personal-pension:{facts.id}"],
            rule="政策有效性与结构化事实双门禁",
            human_review_required=True,
        ),
    ]
    return HouseholdGraphResponse(
        graph_id=f"household-{facts.id}",
        graph_version=GRAPH_VERSION,
        title=f"{facts.name}关系图谱",
        subtitle=f"{facts.region} · 关系表实时推导",
        as_of_date=analysis_date,
        synthetic=facts.is_synthetic,
        nodes=nodes,
        edges=edges,
        inferences=inferences,
        node_type_coverage=sorted({node.node_type for node in nodes}),
        limitations=[
            "图谱关系来自当前数据库事实和确定性规则，不等于法律或产品结论。",
            "缺失的个人养老金、父母保障和地区参数保持缺失。",
            "产品节点只来自受控 Mock 目录，不代表真实在售。",
        ],
    )
