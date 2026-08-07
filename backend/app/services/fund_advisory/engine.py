from __future__ import annotations

import hashlib
import json
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.domain.enums import AccountBucket, AssetCategory, ProductRiskLevel, RiskLevel
from app.domain.financial import HouseholdFacts
from app.schemas.fund_advisory import (
    AdvisoryAllocation,
    AdvisoryCandidate,
    AdvisorySleeve,
    FundAdvisoryMeta,
    FundAdvisoryResponse,
    VerifiedFundCatalogResponse,
    VerifiedFundProduct,
)
from app.schemas.planning import PlanningResponse
from app.schemas.portfolio import PortfolioResponse
from app.services.financial.facts import load_household_facts
from app.services.financial.utils import ZERO, money
from app.services.fund_advisory.catalog import build_fund_catalog_response
from app.services.planning.engine import empty_counterfactual, plan_facts
from app.services.planning.rules import PlanningRules, load_planning_rules
from app.services.portfolio.engine import portfolio_household

ENGINE_VERSION = "fund_advisory_engine_v1.0.0"
ONE = Decimal("1")

PRODUCT_TO_RISK = {
    ProductRiskLevel.R1: RiskLevel.LOW,
    ProductRiskLevel.R2: RiskLevel.MEDIUM_LOW,
    ProductRiskLevel.R3: RiskLevel.MEDIUM,
    ProductRiskLevel.R4: RiskLevel.MEDIUM_HIGH,
    ProductRiskLevel.R5: RiskLevel.HIGH,
}


def _input_version(
    planning: PlanningResponse,
    portfolio: PortfolioResponse,
    catalog: VerifiedFundCatalogResponse,
    icbc_only: bool,
) -> str:
    canonical = json.dumps(
        {
            "planning_input_version": planning.meta.input_version,
            "portfolio_input_version": portfolio.meta.input_version,
            "catalog_version": catalog.catalog_version,
            "catalog_verified_on": catalog.verified_on.isoformat(),
            "engine_version": ENGINE_VERSION,
            "icbc_only": icbc_only,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def _account_amount(planning: PlanningResponse, bucket: AccountBucket) -> Decimal:
    account = next(item for item in planning.accounts if item.bucket == bucket)
    return money(account.recommended_amount)


def _personal_pension_amount(facts: HouseholdFacts) -> tuple[Decimal, bool]:
    exact = [
        item
        for item in facts.assets
        if item.category == AssetCategory.PENSION_ACCOUNT
        and (item.subcategory or "").strip() in {"个人养老金", "个人养老金账户"}
    ]
    mixed_exists = any(
        item.category == AssetCategory.PENSION_ACCOUNT
        and "个人养老金" in (item.subcategory or "")
        and item not in exact
        for item in facts.assets
    )
    return money(sum((item.market_value for item in exact), ZERO)), mixed_exists


def _product_map(catalog: VerifiedFundCatalogResponse) -> dict[str, VerifiedFundProduct]:
    return {item.code: item for item in catalog.products}


def _allocation(
    allocation_type: str,
    ratio: Decimal,
    amount: Decimal,
    *,
    product: VerifiedFundProduct | None = None,
    unallocated_reason: str | None = None,
) -> AdvisoryAllocation:
    if allocation_type == "fund" and product is not None:
        reason_by_category = {
            "money_market": (
                "适合承接暂时不需要当日支付的短期资金，重点是方便取用，不是追求高收益。"
            ),
            "short_bond": "可用于部分中短期资金安排，持有时间应与家庭目标日期相匹配。",
            "pure_bond": "可用于距离目标较远的稳健资金，但需要接受净值会随市场变化。",
            "domestic_broad_index": "通过宽基指数分散投资，适合长期不用的资金和分批投入。",
            "pension_bond_fof": "用于个人养老金账户内的长期养老准备，需同时接受账户和持有期限制。",
            "pension_broad_index": (
                "用于个人养老金账户内的长期权益投资，只适合能够承受市场波动的投资者。"
            ),
        }
        warning_by_category = {
            "money_market": "货币基金不等同于银行存款，快速赎回额度和到账安排也可能变化。",
            "short_bond": "短债基金仍有利率、信用和净值波动风险，赎回金额可能低于买入金额。",
            "pure_bond": "债券基金不保证本金，利率和信用变化都可能造成阶段性亏损。",
            "domestic_broad_index": (
                "宽基指数基金会随市场明显涨跌，不应使用五年内要用的钱，"
                "也不要因为短期行情频繁追涨杀跌。"
            ),
            "pension_bond_fof": "养老基金仍有净值波动，并受个人养老金账户和最短持有期约束。",
            "pension_broad_index": (
                "养老宽基基金可能出现较大回撤，并受个人养老金账户和最短持有期约束。"
            ),
        }
        route = (
            f"工行手机银行搜索六位代码 {product.code}，以当日可售状态和交易确认页为准"
            if product.icbc_publicly_listed
            else f"通过具备基金销售资质且当前可售的渠道搜索代码 {product.code}，不视为工行可售"
        )
        return AdvisoryAllocation(
            allocation_type="fund",
            ratio=ratio,
            amount=amount,
            product_code=product.code,
            product_name=product.name,
            product_risk_level=product.internal_risk_level,
            icbc_publicly_listed=product.icbc_publicly_listed,
            purchase_route=route,
            reasons=[reason_by_category[product.category]],
            warnings=[
                warning_by_category[product.category],
                "页面列示不代表当前账户一定可以购买，请以交易当日结果为准。",
            ],
            evidence_urls=list(dict.fromkeys(item.url for item in product.evidence)),
        )
    if allocation_type == "bank_cash_reserve":
        return AdvisoryAllocation(
            allocation_type="bank_cash_reserve",
            ratio=ratio,
            amount=amount,
            purchase_route="保留在工行活期/支付侧现金账户（非基金）",
            reasons=["保留随时可用于日常支付、应急或近期目标的钱。"],
            warnings=["现金部分不追求基金净值收益。"],
        )
    return AdvisoryAllocation(
        allocation_type="unallocated_guardrail",
        ratio=ratio,
        amount=amount,
        purchase_route="资金先留在原账户，等购买渠道、风险测评和家庭资金安排都确认后再决定",
        reasons=[unallocated_reason or "当前条件还不适合购买基金，资金先留在原账户。"],
        warnings=["不必为了把资金全部投出去而降低对风险、期限或购买渠道的要求。"],
    )


def _weighted_allocations(
    source_amount: Decimal,
    weights: list[tuple[str, Decimal]],
    products: dict[str, VerifiedFundProduct],
) -> list[AdvisoryAllocation]:
    if source_amount == 0:
        return []
    allocations: list[AdvisoryAllocation] = []
    allocated = ZERO
    for index, (key, weight) in enumerate(weights):
        amount = (
            money(source_amount - allocated)
            if index == len(weights) - 1
            else money(source_amount * weight)
        )
        allocated = money(allocated + amount)
        if key == "cash":
            allocations.append(_allocation("bank_cash_reserve", weight, amount))
        elif key == "guardrail":
            allocations.append(
                _allocation(
                    "unallocated_guardrail",
                    weight,
                    amount,
                    unallocated_reason="目前没有同时符合这笔钱用途、您的风险范围和指定购买渠道的基金。",
                )
            )
        else:
            allocations.append(
                _allocation("fund", weight, amount, product=products[key])
            )
    return allocations


def _daily_sleeve(
    amount: Decimal,
    products: dict[str, VerifiedFundProduct],
    catalog_stale: bool,
) -> AdvisorySleeve:
    if amount == 0:
        return AdvisorySleeve(
            sleeve_code="daily_liquidity",
            name="要花的钱",
            source_amount=amount,
            status="not_applicable",
            objective="日常支付与即时应急",
            allocations=[],
            guardrails=["不使用债券基金、权益基金或有持有期产品替代支付现金。"],
            explanation="当前规划未产生可用于此用途的建议金额。",
        )
    weights = (
        [("cash", ONE)]
        if catalog_stale
        else [("cash", Decimal("0.70")), ("482002", Decimal("0.30"))]
    )
    return AdvisorySleeve(
        sleeve_code="daily_liquidity",
        name="要花的钱",
        source_amount=amount,
        status="channel_verification_required" if catalog_stale else "recommended",
        objective="日常支付保留在活期账户，暂时不用的小部分资金可了解货币基金",
        allocations=_weighted_allocations(amount, weights, products),
        guardrails=[
            "支付侧现金不得低于70%。",
            "快速赎回存在限额和服务变更风险，不将货币基金等同活期存款。",
        ],
        explanation=(
            "产品资料已超过复核日期，暂时全部保留现金，更新后再考虑购买。"
            if catalog_stale
            else "只把暂时不用的小部分资金用于货币基金，日常支付和灵活取用仍放在第一位。"
        ),
    )


def _stable_sleeve(
    amount: Decimal,
    planning: PlanningResponse,
    planning_rules: PlanningRules,
    products: dict[str, VerifiedFundProduct],
    catalog_stale: bool,
) -> AdvisorySleeve:
    if amount == 0:
        return AdvisorySleeve(
            sleeve_code="stable_capital",
            name="保本的钱",
            source_amount=amount,
            status="not_applicable",
            objective="五年内刚性目标与家庭稳定层",
            allocations=[],
            guardrails=["“保本的钱”是资金用途名称，不代表债券基金或货币基金保本。"],
            explanation="当前规划未产生可用于此用途的建议金额。",
        )
    stable_months = [
        item.months_remaining
        for item in planning.goals
        if 0 < item.months_remaining <= planning_rules.goals.stable_goal_months
        and item.funding_gap > 0
    ]
    nearest = min(stable_months, default=planning_rules.goals.stable_goal_months)
    if catalog_stale:
        weights = [("cash", ONE)]
    elif nearest <= 3:
        weights = [("cash", Decimal("0.70")), ("482002", Decimal("0.30"))]
    elif nearest <= 12:
        weights = [
            ("cash", Decimal("0.40")),
            ("482002", Decimal("0.30")),
            ("006834", Decimal("0.30")),
        ]
    else:
        weights = [
            ("cash", Decimal("0.10")),
            ("482002", Decimal("0.30")),
            ("006834", Decimal("0.30")),
            ("000402", Decimal("0.30")),
        ]
    return AdvisorySleeve(
        sleeve_code="stable_capital",
        name="保本的钱",
        source_amount=amount,
        status="channel_verification_required" if catalog_stale else "recommended",
        objective=f"最近一项目标约在{nearest}个月后，按使用日期安排现金、货币基金和债券基金",
        allocations=_weighted_allocations(amount, weights, products),
        guardrails=[
            "所有基金都不保本；刚性支出时点越近，现金比例越高。",
            "单只基金上限30%，不使用二级债、可转债或含权益的固收+替代稳定层。",
        ],
        explanation=(
            "目录核验已过期，暂时100%保留现金。"
            if catalog_stale
            else "先看最近一次用钱日期，再决定是否使用债券基金，不能拿必须完成的支出去追求收益。"
        ),
    )


def _pension_candidates(
    products: dict[str, VerifiedFundProduct],
    icbc_only: bool,
) -> list[AdvisoryCandidate]:
    bond = products["020189"]
    return [
        AdvisoryCandidate(
            product_code=bond.code,
            product_name=bond.name,
            role="个人养老金账户内偏稳健的养老基金备选",
            status=(
                "channel_verification_required"
                if icbc_only or not bond.icbc_publicly_listed
                else "eligible"
            ),
            reason=(
                "当前还不能确认工行渠道是否可购买，因此本次不安排金额。"
                if icbc_only
                else "已进入个人养老金基金名录，购买前仍需确认当前渠道和本人适当性。"
            ),
        ),
        AdvisoryCandidate(
            product_code="022935",
            product_name=products["022935"].name,
            role="个人养老金账户内的沪深300宽基基金备选",
            status="eligible",
            reason="已进入个人养老金基金名录，但波动高于稳健类产品，本次不作为优先安排。",
        ),
        AdvisoryCandidate(
            product_code="022982",
            product_name=products["022982"].name,
            role="个人养老金账户内的中证A500宽基基金备选",
            status="eligible",
            reason="已进入个人养老金基金名录，但波动高于稳健类产品，本次不作为优先安排。",
        ),
    ]


def _pension_sleeve(
    amount: Decimal,
    mixed_record_exists: bool,
    effective_risk: RiskLevel,
    products: dict[str, VerifiedFundProduct],
    catalog_stale: bool,
    icbc_only: bool,
) -> AdvisorySleeve:
    candidates = _pension_candidates(products, icbc_only)
    if amount == 0:
        explanation = "未发现可与企业年金分开计量的“个人养老金”资产记录。"
        if mixed_record_exists:
            explanation += " 已发现混合标记的企业年金/个人养老金，未猜测可支配金额。"
        return AdvisorySleeve(
            sleeve_code="personal_pension",
            name="个人养老金投资",
            source_amount=amount,
            status="not_applicable",
            objective="仅对已确认的个人养老金资金账户做投资建议",
            allocations=[],
            candidate_products=candidates,
            guardrails=[
                "不将企业年金、基本养老金或普通账户资产冒充个人养老金。",
                "普通货币/债券基金不在官方个人养老金基金名录时，不得推荐到该账户。",
            ],
            explanation=explanation,
        )
    can_use_bond = (
        not catalog_stale
        and not icbc_only
        and effective_risk != RiskLevel.LOW
    )
    weights = (
        [("020189", Decimal("0.30")), ("guardrail", Decimal("0.70"))]
        if can_use_bond
        else [("guardrail", ONE)]
    )
    reason = (
        "个人养老金基金名录中没有货币基金，目前也无法确认偏稳健备选在工行渠道可购买，因此资金暂时保留。"
        if icbc_only
        else "偏稳健的养老基金最多使用这笔资金的30%，其余资金等待更合适的产品。"
    )
    return AdvisorySleeve(
        sleeve_code="personal_pension",
        name="个人养老金投资",
        source_amount=amount,
        status="recommended" if can_use_bond else "channel_verification_required",
        objective="个人养老金需要长期持有，先确认产品名录和本人能够承受的风险",
        allocations=_weighted_allocations(amount, weights, products),
        candidate_products=candidates,
        guardrails=[
            "个人养老金基金必须在购买当日的官方产品名录内。",
            "如果工行渠道无法确认购买状态，本次就不安排该产品。",
            "购买前还要确认Y类份额、账户取用限制和最短持有期。",
        ],
        explanation=reason,
    )


def _growth_sleeve(
    amount: Decimal,
    effective_risk: RiskLevel,
    portfolio: PortfolioResponse,
    products: dict[str, VerifiedFundProduct],
    catalog_stale: bool,
) -> AdvisorySleeve:
    if amount == 0:
        return AdvisorySleeve(
            sleeve_code="long_term_growth",
            name="生钱的钱",
            source_amount=amount,
            status="not_applicable",
            objective="长期购买力与长期目标",
            allocations=[],
            guardrails=["只使用动态四账户确认的长期金额，不挪用要花、保本或保障的钱。"],
            explanation="当前没有可用于新增长期投资的资金，先完成日常生活、保障、近期目标和债务安排。",
        )
    blocked = portfolio.family_safety_gate.status.value != "pass"
    if catalog_stale or blocked or effective_risk == RiskLevel.LOW:
        reason = (
                "产品资料已经超过复核日期，更新前不安排购买。"
                if catalog_stale
                else "生活、保障或近期目标还没有安排好，长期资金先保留。"
                if blocked
                else "您当前适合的风险范围较低，不适合权益类宽基指数基金。"
        )
        allocations = [
            _allocation(
                "unallocated_guardrail",
                ONE,
                amount,
                unallocated_reason=reason,
            )
        ]
        status = "education_only"
    else:
        if effective_risk == RiskLevel.MEDIUM_LOW:
            weights = [
                ("482002", Decimal("0.30")),
                ("006834", Decimal("0.30")),
                ("000402", Decimal("0.30")),
                ("005102", Decimal("0.10")),
            ]
        elif effective_risk == RiskLevel.MEDIUM:
            weights = [
                ("482002", Decimal("0.20")),
                ("006834", Decimal("0.15")),
                ("000402", Decimal("0.25")),
                ("005102", Decimal("0.30")),
                ("164809", Decimal("0.10")),
            ]
        else:
            weights = [
                ("482002", Decimal("0.25")),
                ("006834", Decimal("0.10")),
                ("000402", Decimal("0.15")),
                ("005102", Decimal("0.30")),
                ("164809", Decimal("0.20")),
            ]
        allocations = _weighted_allocations(amount, weights, products)
        status = "recommended"
    return AdvisorySleeve(
        sleeve_code="long_term_growth",
        name="生钱的钱",
        source_amount=amount,
        status=status,
        objective="只使用长期不用的资金，通过宽基指数分散投资，并保留稳健资金降低整体波动",
        allocations=allocations,
        guardrails=[
            "不推荐个股、行业、主题、杠杆或反向产品。",
            "单只基金最高30%，权益比例不能超过本人的风险承受范围。",
            "不按短期收益、历史排名或市场热点追涨，通常每年复核一次。",
        ],
        explanation=(
            "当前只说明可以学习的方向，资金仍留在原账户，不安排购买。"
            if status == "education_only"
            else "权益部分只选择国内宽基指数基金，并通过货币基金和债券基金控制整体波动。"
        ),
    )


def advise_household(
    session: Session,
    household_id: str,
    financial_rules_path: str,
    planning_rules_path: str,
    portfolio_rules_path: str,
    product_catalog_path: str,
    fund_advisory_catalog_path: str,
    analysis_date: date,
    *,
    icbc_only: bool = True,
) -> FundAdvisoryResponse:
    facts = load_household_facts(session, household_id)
    planning_rules = load_planning_rules(planning_rules_path)
    planning = plan_facts(
        facts,
        financial_rules_path,
        planning_rules,
        analysis_date,
        empty_counterfactual(),
    )
    portfolio = portfolio_household(
        session,
        household_id,
        financial_rules_path,
        planning_rules_path,
        portfolio_rules_path,
        product_catalog_path,
        analysis_date,
    )
    catalog = build_fund_catalog_response(fund_advisory_catalog_path, analysis_date)
    products = _product_map(catalog)
    effective_product_risk = (
        portfolio.customer_suitability_gate.effective_risk_limit or ProductRiskLevel.R1
    )
    effective_risk = PRODUCT_TO_RISK[effective_product_risk]
    pension_amount, mixed_pension = _personal_pension_amount(facts)
    sleeves = [
        _daily_sleeve(
            _account_amount(planning, AccountBucket.DAILY_LIQUIDITY),
            products,
            catalog.catalog_stale,
        ),
        _stable_sleeve(
            _account_amount(planning, AccountBucket.STABLE_GOALS),
            planning,
            planning_rules,
            products,
            catalog.catalog_stale,
        ),
        _pension_sleeve(
            pension_amount,
            mixed_pension,
            effective_risk,
            products,
            catalog.catalog_stale,
            icbc_only,
        ),
        _growth_sleeve(
            money(portfolio.context.eligible_long_term_amount),
            effective_risk,
            portfolio,
            products,
            catalog.catalog_stale,
        ),
    ]
    return FundAdvisoryResponse(
        meta=FundAdvisoryMeta(
            household_id=facts.id,
            household_code=facts.code,
            analysis_date=analysis_date,
            data_as_of=portfolio.meta.data_as_of,
            input_version=_input_version(planning, portfolio, catalog, icbc_only),
            engine_version=ENGINE_VERSION,
            catalog_version=catalog.catalog_version,
            catalog_data_date=catalog.data_date,
            catalog_stale=catalog.catalog_stale,
            icbc_only=icbc_only,
            currency=facts.currency,
            synthetic_data=facts.is_synthetic,
        ),
        effective_customer_risk=effective_risk,
        family_safety_status=portfolio.family_safety_gate.status,
        sleeves=sleeves,
        catalog=catalog,
        hard_boundaries=[
            "本页只细分第七章已经确定的金额，不会额外增加投资本金。",
            "个人养老金是现有专项账户资金，不能与其他账户重复计算。",
            "基金代码、风险等级和购买渠道需要逐项确认，无法确认时先保留资金。",
            "货币基金、债券基金和养老基金都不保证本金或收益。",
            "权益投资只考虑宽基指数基金，不建议个股、行业主题、杠杆或反向产品。",
        ],
        execution_checklist=[
            "在工行手机银行输入六位基金代码，确认基金全称、份额类别和基金管理人。",
            "重点查看风险等级、申购赎回费用、到账时间、最短持有期和最新公告。",
            "按购买当日的银行风险测评结果选择产品；银行给出的可买范围更低时，以银行结果为准。",
            "个人养老金产品还要确认最新官方名录、Y类份额和账户取用限制。",
        ],
        disclaimer=(
            "本页根据您确认的家庭资料和当前公开产品资料形成。金额沿用第七章的家庭规划，"
            "不承诺收益，也不替代购买当日的风险测评和产品确认。"
        ),
    )
