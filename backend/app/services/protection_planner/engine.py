from __future__ import annotations

from decimal import Decimal

from app.domain.enums import AssetCategory, InsuranceType
from app.domain.financial import HouseholdFacts
from app.schemas.financial_analysis import FinancialAnalysisResponse, ProtectionRisk
from app.schemas.methodology import ProtectionNeedLine, ProtectionPlan
from app.services.financial.utils import ZERO, money


def _coverage(facts: HouseholdFacts, policy_type: InsuranceType) -> Decimal:
    return money(
        sum(
            (
                policy.coverage_amount
                for policy in facts.insurance_policies
                if policy.policy_type == policy_type
            ),
            ZERO,
        )
    )


def _line(
    risk: ProtectionRisk,
    *,
    code: str | None = None,
    label: str | None = None,
    existing_coverage: Decimal | None = None,
) -> ProtectionNeedLine:
    coverage = risk.existing_coverage if existing_coverage is None else existing_coverage
    gap = money(max(ZERO, risk.required_amount - coverage))
    return ProtectionNeedLine(
        risk_code=code or risk.risk_code,
        label=label or risk.name,
        required_coverage=risk.required_amount,
        existing_coverage=coverage,
        coverage_gap=gap,
        annual_premium_cost=ZERO,
        status="covered" if gap == ZERO else "gap",
        quote_status="not_required" if gap == ZERO else "product_quote_required",
        explanation=(
            "保障需求和现有保额由确定性规则核对；"
            "未接入真实产品报价时不从保障缺口反推保费。"
        ),
    )


def build_protection_plan(
    facts: HouseholdFacts,
    financial: FinancialAnalysisResponse,
) -> ProtectionPlan:
    by_code = {item.risk_code: item for item in financial.protection.risks}
    needs = [
        _line(
            by_code["medical_self_pay"],
            code="medical",
            label="医疗自付风险",
            existing_coverage=_coverage(facts, InsuranceType.MEDICAL),
        ),
        ProtectionNeedLine(
            risk_code="critical_illness",
            label="重疾与收入中断风险",
            required_coverage=ZERO,
            existing_coverage=_coverage(facts, InsuranceType.CRITICAL_ILLNESS),
            coverage_gap=ZERO,
            annual_premium_cost=ZERO,
            status="needs_review",
            quote_status="product_quote_required",
            explanation=(
                "当前规则没有经过验证的重疾需求参数，不复用医疗储备或虚构统一倍数；"
                "需补充收入中断期、社保医疗与家庭照护责任后再计算。"
            ),
        ),
        _line(
            by_code["death_responsibility"],
            code="death_income_replacement",
            label="身故与收入替代",
        ),
        _line(by_code["accident_income_loss"], code="accident", label="意外风险"),
    ]
    has_property_or_vehicle = any(
        item.category
        in {
            AssetCategory.PRIMARY_RESIDENCE,
            AssetCategory.INVESTMENT_PROPERTY,
            AssetCategory.VEHICLE,
        }
        for item in facts.assets
    )
    if has_property_or_vehicle:
        property_coverage = _coverage(facts, InsuranceType.PROPERTY)
        needs.append(
            ProtectionNeedLine(
                risk_code="auto_property_liability",
                label="车险、财产与责任风险",
                required_coverage=ZERO,
                existing_coverage=property_coverage,
                coverage_gap=ZERO,
                annual_premium_cost=ZERO,
                status="needs_review",
                quote_status="product_quote_required",
                explanation="存在房产或车辆；需按标的、地区和责任条款询价，不使用统一保费。",
            )
        )
    annual_income = financial.statements.cash_flow.annual_income
    premium_ratio = (
        financial.protection.annual_premium / annual_income if annual_income > ZERO else None
    )
    split_required = any(
        policy.policy_type in {InsuranceType.ANNUITY, InsuranceType.WHOLE_LIFE}
        and (policy.cash_value > ZERO or policy.non_guaranteed_benefit > ZERO)
        for policy in facts.insurance_policies
    )
    return ProtectionPlan(
        version="protection-need-engine-v1.0.0",
        annual_premium_cost=financial.protection.annual_premium,
        premium_affordability_ratio=premium_ratio,
        needs=needs,
        savings_and_protection_split_required=split_required,
        explanation=(
            "保费作为年度消费流列示，保额不进入资产；"
            "年金或现金价值保险的保障与资金积累属性分开。"
        ),
    )
