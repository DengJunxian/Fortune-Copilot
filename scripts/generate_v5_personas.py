#!/usr/bin/env python3
"""Generate the deterministic Canonical V5 heterogeneous persona fixture."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/synthetic/v5_personas/personas_v2.json"
AS_OF = "2026-08-10"
SOURCE = "synthetic-v5-personas-v2.0.0"


def member(
    name: str,
    relationship: str,
    birth_date: str,
    occupation: str | None,
    *,
    stability: str = "high",
    retirement_age: int | None = 60,
    health: str = "low",
) -> dict[str, Any]:
    return {
        "display_name": name,
        "relationship": relationship,
        "birth_date": birth_date,
        "occupation": occupation,
        "employment_stability": stability,
        "expected_retirement_age": retirement_age,
        "health_risk_level": health,
    }


def consents(primary: str) -> list[dict[str, Any]]:
    base = {
        "member_id": primary,
        "granted_at": "2026-08-10T09:00:00+08:00",
        "withdrawn_at": None,
        "consent_version": "v5-persona-consent-v2",
    }
    return [
        {
            **base,
            "scopes": ["profile", "finance", "risk", "behavior"],
            "purpose": "V5 合成 Persona 的客户画像、财务诊断与风险预算验证",
            "metadata_json": {
                "synthetic": True,
                "scenario": "v5_profile_and_risk",
                "explicit": True,
            },
        },
        {
            **base,
            "granted_at": "2026-08-10T09:01:00+08:00",
            "scopes": ["identity_sensitive", "health_sensitive", "insurance"],
            "purpose": "V5 合成 Persona 的敏感字段与保障缺口验证",
            "metadata_json": {
                "synthetic": True,
                "scenario": "v5_protection_and_specialist_routing",
                "explicit": True,
                "sensitive_data_acknowledged": True,
            },
        },
        {
            **base,
            "granted_at": "2026-08-10T09:02:00+08:00",
            "scopes": ["simulation", "report"],
            "purpose": "V5 合成 Persona 的情景实验、CFS 与报告验证",
            "metadata_json": {
                "synthetic": True,
                "scenario": "v5_scenario_cfs_and_report",
                "explicit": True,
            },
        },
    ]


def income(
    owner: str,
    name: str,
    amount: str,
    *,
    income_type: str = "employment",
    currency: str = "CNY",
    stability: str = "0.85",
    volatility: str = "0.10",
    interruption: str = "0.10",
    concentration: str = "0.60",
    sustainable: bool = True,
) -> dict[str, Any]:
    return {
        "member_id": owner,
        "name": name,
        "income_type": income_type,
        "amount": amount,
        "frequency": "annual",
        "stability": stability,
        "volatility": volatility,
        "interruption_probability": interruption,
        "cycle_correlation": "0.30",
        "source_concentration": concentration,
        "is_sustainable": sustainable,
        "currency": currency,
    }


def expense(
    owner: str,
    name: str,
    amount: str,
    category: str,
    *,
    essential: bool = True,
) -> dict[str, Any]:
    return {
        "member_id": owner,
        "name": name,
        "amount": amount,
        "frequency": "annual",
        "necessity": "essential" if essential else "flexible",
        "compressible_ratio": "0.05" if essential else "0.50",
        "category": category,
    }


def asset(
    owner: str,
    name: str,
    category: str,
    value: str,
    *,
    currency: str = "CNY",
    liquidity_days: int = 1,
    liquidity_level: str = "within_7_days",
    risk: str = "low",
    purpose: str = "家庭财务安排",
    property_use: str = "not_property",
    pledged: bool = False,
    source_kind: str = "user_self_report",
    household_role: str = "household_shared",
    region_code: str | None = None,
) -> dict[str, Any]:
    return {
        "owner_member_id": owner,
        "name": name,
        "category": category,
        "subcategory": "V5 合成资产",
        "acquisition_cost": value,
        "market_value": value,
        "liquidity_days": liquidity_days,
        "liquidity_level": liquidity_level,
        "risk_level": risk,
        "purpose": purpose,
        "pledged": pledged,
        "ownership": owner,
        "property_use": property_use,
        "currency": currency,
        "source_kind": source_kind,
        "household_role": household_role,
        "region_code": region_code,
    }


def liability(
    owner: str,
    name: str,
    category: str,
    balance: str,
    payment: str,
    *,
    rate: str,
    maturity: str,
    linked_asset: str | None = None,
    currency: str = "CNY",
    high_interest: bool = False,
) -> dict[str, Any]:
    return {
        "borrower_member_id": owner,
        "linked_asset_id": linked_asset,
        "name": name,
        "category": category,
        "outstanding_balance": balance,
        "annual_interest_rate": rate,
        "monthly_payment": payment,
        "maturity_date": maturity,
        "rate_type": "floating",
        "prepayment_cost": "0.00",
        "is_high_interest": high_interest,
        "currency": currency,
    }


def policy(
    insured: str,
    name: str,
    policy_type: str,
    coverage: str,
    premium: str,
) -> dict[str, Any]:
    return {
        "insured_member_id": insured,
        "name": name,
        "policy_type": policy_type,
        "coverage_amount": coverage,
        "annual_premium": premium,
        "start_date": "2026-01-01",
        "end_date": "2026-12-31" if policy_type in {"medical", "accident"} else None,
        "deductible": "10000.00" if policy_type == "medical" else "0.00",
        "waiting_period_days": 30
        if policy_type in {"medical", "critical_illness"}
        else 0,
        "guaranteed_benefit": "0.00",
        "non_guaranteed_benefit": "0.00",
        "cash_value": "0.00",
    }


def social_security(owner: str, balance: str, region: str) -> dict[str, Any]:
    return {
        "member_id": owner,
        "account_type": "城镇职工基本养老保险",
        "balance": balance,
        "annual_personal_contribution": "24000.00",
        "annual_employer_contribution": "48000.00",
        "benefit_region": region,
    }


def goal(
    name: str,
    goal_type: str,
    target: str,
    target_date: str,
    *,
    priority: int,
    prepared: str = "0.00",
    minimum: str | None = None,
    rigidity: str = "important",
    can_defer: bool = False,
    currency: str = "CNY",
    growth: str = "0.03",
) -> dict[str, Any]:
    return {
        "name": name,
        "goal_type": goal_type,
        "target_amount": target,
        "target_date": target_date,
        "rigidity": rigidity,
        "priority": priority,
        "can_defer": can_defer,
        "minimum_acceptable_amount": minimum or target,
        "prepared_amount": prepared,
        "annual_cost_growth_rate": growth,
        "currency": currency,
    }


def assessments(
    *,
    capacity: str = "0.70",
    willingness: str = "0.65",
    behavior: str = "0.60",
    risk_limit: str = "medium",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    risk = [
        {
            "capacity_score": capacity,
            "willingness_score": willingness,
            "knowledge_score": "0.70",
            "behavior_score": behavior,
            "final_risk_limit": risk_limit,
            "explanation": "按合成家庭现金流、责任期限与行为承受力取审慎风险上限。",
        }
    ]
    behavior_rows = [
        {
            "questionnaire_score": willingness,
            "experiment_score": behavior,
            "final_behavior_limit": risk_limit,
            "detected_biases": ["loss_aversion"] if behavior < willingness else [],
            "experiment_answers": {},
            "explanation": "合成行为记录只用于验证风险预算约束，不代表真实客户测评。",
        }
    ]
    return risk, behavior_rows


def bundle(
    code: str,
    title: str,
    stage: str,
    region: str,
    members: list[dict[str, Any]],
    incomes: list[dict[str, Any]],
    expenses: list[dict[str, Any]],
    assets: list[dict[str, Any]],
    liabilities: list[dict[str, Any]],
    policies: list[dict[str, Any]],
    security: list[dict[str, Any]],
    goals: list[dict[str, Any]],
    *,
    preferences: dict[str, Any] | None = None,
    capacity: str = "0.70",
    willingness: str = "0.65",
    behavior: str = "0.60",
    risk_limit: str = "medium",
) -> dict[str, Any]:
    risk_rows, behavior_rows = assessments(
        capacity=capacity,
        willingness=willingness,
        behavior=behavior,
        risk_limit=risk_limit,
    )
    return {
        "household": {
            "code": code,
            "name": title,
            "lifecycle_stage": stage,
            "region": region,
            "demo_profile": code.removeprefix("DEMO_"),
            "is_synthetic": True,
            "planning_preferences": preferences or {},
        },
        "members": members,
        "consents": consents(members[0]["display_name"]),
        "incomes": incomes,
        "expenses": expenses,
        "assets": assets,
        "liabilities": liabilities,
        "insurance_policies": policies,
        "social_security_accounts": security,
        "goals": goals,
        "risk_assessments": risk_rows,
        "behavior_assessments": behavior_rows,
    }


def enterprise(
    household_code: str,
    name: str,
    owner: str,
    *,
    industry: str,
    stage: str,
    jurisdiction: str,
    listed_status: str,
    enterprise_type: str,
    value: str,
    ownership_ratio: str,
    instrument_type: str,
    cashflows: list[dict[str, Any]] | None = None,
    guarantees: list[dict[str, Any]] | None = None,
    events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "household_code": household_code,
        "enterprise": {
            "name": name,
            "industry": industry,
            "stage": stage,
            "jurisdiction": jurisdiction,
            "listed_status": listed_status,
            "enterprise_type": enterprise_type,
            "currency": "CNY",
            "valuation_date": AS_OF,
            "data_source": SOURCE,
            "is_user_confirmed": True,
        },
        "ownerships": [
            {
                "owner_entity_id": owner,
                "ownership_ratio": ownership_ratio,
                "voting_ratio": ownership_ratio,
                "instrument_type": instrument_type,
                "vesting_date": "2020-01-01",
                "lockup_end_date": "2028-12-31"
                if instrument_type != "common_equity"
                else None,
            }
        ],
        "valuations": [
            {
                "valuation_date": AS_OF,
                "equity_value": value,
                "valuation_method": "user_estimate",
                "confidence": "medium",
                "source_kind": "synthetic_client_statement",
                "evidence": {"synthetic": True, "amount_is_not_bank_verified": True},
                "currency": "CNY",
            }
        ],
        "cashflows": cashflows or [],
        "guarantees": guarantees or [],
        "liquidity_events": events or [],
        "source_reference": f"{SOURCE}:{household_code}:{name}",
    }


def build_dataset() -> dict[str, Any]:
    descriptors = [
        (
            "DEMO_A",
            "刚工作的个人 / 新市民",
            [
                "小额现金",
                "租房",
                "信用卡",
                "应急",
                "保障",
                "首套房",
                "养老金",
                "ELTC",
                "投资教育",
            ],
        ),
        (
            "DEMO_B",
            "上海双职工中产家庭",
            ["房贷", "教育", "赡养", "保险", "个人养老金", "养老", "目标冲突", "投资"],
        ),
        (
            "DEMO_C",
            "高收入专业人士",
            ["高现金流", "碎片化资产", "多目标", "低效现金", "保险", "养老金", "CFS"],
        ),
        (
            "DEMO_D",
            "科创企业创始人",
            [
                "未上市企业股权",
                "个人担保",
                "企业收入依赖",
                "跨境收入",
                "国际教育",
                "财富传承",
            ],
        ),
        (
            "DEMO_E",
            "科创专家 / 科学家",
            [
                "股权激励",
                "限制性股票",
                "海外合作收入",
                "教育",
                "创业可能",
                "隐性集中风险",
            ],
        ),
        (
            "DEMO_F",
            "多代际高净值家族",
            [
                "multiple generations",
                "enterprise",
                "succession",
                "trust need",
                "philanthropy",
                "professional routing",
            ],
        ),
        (
            "DEMO_G",
            "跨境家庭",
            [
                "CNY income",
                "USD/HKD assets",
                "foreign education liability",
                "currency matching",
                "professional routing",
            ],
        ),
        (
            "DEMO_H",
            "临近退休 / 退休家庭",
            [
                "property concentration",
                "social security",
                "pension",
                "medical",
                "long-term care",
                "longevity",
                "withdrawal",
                "legacy",
            ],
        ),
    ]
    personas = [
        {"code": code, "title": title, "archetype": title, "validation_focus": focus}
        for code, title, focus in descriptors
    ]

    a_member = member("陈晨", "本人", "2002-10-12", "软件工程师", retirement_age=60)
    a = bundle(
        "DEMO_A",
        "家庭 A｜新市民职场起步",
        "early_career",
        "浙江省杭州市",
        [a_member],
        [income("陈晨", "税后工资", "180000.00", concentration="1.00")],
        [
            expense("陈晨", "租房与基本生活", "84000.00", "basic_living"),
            expense("陈晨", "可选消费", "24000.00", "discretionary", essential=False),
        ],
        [
            asset(
                "陈晨",
                "工资活期",
                "demand_deposit",
                "25000.00",
                liquidity_days=0,
                liquidity_level="immediate",
                purpose="日用与应急",
            ),
            asset("陈晨", "货币基金", "money_market", "10000.00", purpose="应急储备"),
            asset(
                "陈晨",
                "宽基学习仓",
                "equity_fund",
                "5000.00",
                risk="high",
                liquidity_days=3,
                purpose="投资教育",
            ),
        ],
        [
            liability(
                "陈晨",
                "信用卡未还款",
                "credit_card_unpaid",
                "12000.00",
                "3000.00",
                rate="0.180000",
                maturity="2026-12-31",
                high_interest=True,
            )
        ],
        [
            policy("陈晨", "合成医疗险", "medical", "1000000.00", "1200.00"),
            policy("陈晨", "合成意外险", "accident", "500000.00", "600.00"),
        ],
        [social_security("陈晨", "20000.00", "浙江省杭州市")],
        [
            goal(
                "补足应急储备",
                "emergency_fund",
                "60000.00",
                "2027-08-10",
                priority=1,
                prepared="35000.00",
                minimum="48000.00",
                rigidity="rigid",
            ),
            goal(
                "首套房首付",
                "home",
                "600000.00",
                "2032-08-10",
                priority=2,
                minimum="400000.00",
                can_defer=True,
            ),
            goal(
                "长期养老起步",
                "retirement",
                "2500000.00",
                "2062-08-10",
                priority=3,
                prepared="20000.00",
                minimum="1500000.00",
            ),
        ],
        capacity="0.45",
        willingness="0.65",
        behavior="0.40",
        risk_limit="medium_low",
    )

    b_members = [
        member("李先生", "本人", "1991-05-20", "制造业项目经理"),
        member("王女士", "配偶", "1993-09-08", "公立学校教师"),
        member(
            "李小朋友", "子女", "2021-03-15", None, stability="low", retirement_age=None
        ),
    ]
    b = bundle(
        "DEMO_B",
        "家庭 B｜上海双职工育儿家庭",
        "parenting",
        "上海市",
        b_members,
        [
            income("李先生", "本人税后收入", "360000.00"),
            income("王女士", "配偶税后收入", "240000.00", concentration="0.40"),
        ],
        [
            expense("李先生", "家庭基本生活", "180000.00", "basic_living"),
            expense("王女士", "子女教育", "60000.00", "child_education"),
            expense("李先生", "父母赡养", "48000.00", "parent_support"),
        ],
        [
            asset(
                "李先生",
                "家庭活期",
                "demand_deposit",
                "50000.00",
                liquidity_days=0,
                liquidity_level="immediate",
            ),
            asset(
                "王女士",
                "定期存款",
                "time_deposit",
                "150000.00",
                liquidity_days=180,
                liquidity_level="within_1_year",
            ),
            asset(
                "李先生",
                "宽基基金",
                "equity_fund",
                "120000.00",
                risk="high",
                liquidity_days=3,
            ),
            asset(
                "王女士",
                "个人养老金",
                "pension_account",
                "30000.00",
                liquidity_days=3650,
                liquidity_level="illiquid",
                purpose="养老",
            ),
            asset(
                "李先生",
                "上海自住房",
                "primary_residence",
                "2400000.00",
                liquidity_days=180,
                liquidity_level="illiquid",
                property_use="primary_residence",
                risk="medium",
                region_code="310000",
            ),
            asset(
                "李先生",
                "家庭车辆",
                "vehicle",
                "100000.00",
                liquidity_days=30,
                liquidity_level="within_30_days",
            ),
        ],
        [
            liability(
                "李先生",
                "住房按揭",
                "mortgage",
                "1200000.00",
                "7500.00",
                rate="0.035000",
                maturity="2046-08-10",
                linked_asset="上海自住房",
            ),
            liability(
                "李先生",
                "信用卡未还款",
                "credit_card_unpaid",
                "8000.00",
                "8000.00",
                rate="0.180000",
                maturity="2026-09-10",
                high_interest=True,
            ),
        ],
        [
            policy("李先生", "定期寿险", "term_life", "1500000.00", "4200.00"),
            policy("王女士", "医疗险", "medical", "1000000.00", "1800.00"),
        ],
        [
            social_security("李先生", "180000.00", "上海市"),
            social_security("王女士", "160000.00", "上海市"),
        ],
        [
            goal(
                "子女教育",
                "education",
                "1000000.00",
                "2039-08-10",
                priority=1,
                prepared="120000.00",
                minimum="700000.00",
                rigidity="rigid",
            ),
            goal(
                "夫妻退休养老",
                "retirement",
                "6000000.00",
                "2051-08-10",
                priority=2,
                prepared="370000.00",
                minimum="4000000.00",
            ),
            goal(
                "父母赡养储备",
                "family_support",
                "600000.00",
                "2036-08-10",
                priority=3,
                prepared="50000.00",
                minimum="400000.00",
            ),
        ],
        preferences={"personal_pension_review_requested": True},
    )
    legacy = json.loads((ROOT / "data/synthetic/families.json").read_text(encoding="utf-8"))
    b = next(
        item for item in legacy["households"] if item["household"]["code"] == "DEMO_B"
    )
    b["household"].update(
        {
            "name": "家庭 B｜上海双职工育儿家庭",
            "region": "上海市",
            "planning_preferences": {"personal_pension_review_requested": True},
        }
    )

    c_members = [
        member("许医生", "本人", "1985-04-18", "三甲医院主任医师"),
        member("林女士", "配偶", "1987-07-02", "律师"),
    ]
    c = bundle(
        "DEMO_C",
        "家庭 C｜高收入专业人士",
        "mature_family",
        "北京市",
        c_members,
        [
            income("许医生", "专业服务收入", "1200000.00", concentration="0.70"),
            income("林女士", "律师收入", "600000.00", concentration="0.30"),
        ],
        [
            expense("许医生", "家庭基本生活", "300000.00", "basic_living"),
            expense(
                "林女士", "品质消费", "180000.00", "discretionary", essential=False
            ),
        ],
        [
            asset(
                "许医生",
                "活期一",
                "demand_deposit",
                "900000.00",
                liquidity_days=0,
                liquidity_level="immediate",
                purpose="低效现金",
            ),
            asset(
                "林女士",
                "活期二",
                "demand_deposit",
                "600000.00",
                liquidity_days=0,
                liquidity_level="immediate",
                purpose="低效现金",
            ),
            asset(
                "许医生",
                "定期一",
                "time_deposit",
                "800000.00",
                liquidity_days=180,
                liquidity_level="within_1_year",
            ),
            asset("林女士", "债券基金", "bond_fund", "500000.00", risk="medium_low"),
            asset(
                "许医生",
                "宽基基金组合",
                "public_fund",
                "700000.00",
                risk="medium_high",
                liquidity_days=3,
            ),
            asset(
                "林女士",
                "个人养老金",
                "pension_account",
                "180000.00",
                liquidity_days=3650,
                liquidity_level="illiquid",
                purpose="养老",
            ),
            asset(
                "许医生",
                "北京自住房",
                "primary_residence",
                "7000000.00",
                liquidity_days=180,
                liquidity_level="illiquid",
                property_use="primary_residence",
                risk="medium",
                region_code="110000",
            ),
        ],
        [],
        [
            policy("许医生", "高额医疗险", "medical", "3000000.00", "6800.00"),
            policy("林女士", "定期寿险", "term_life", "3000000.00", "8200.00"),
        ],
        [
            social_security("许医生", "500000.00", "北京市"),
            social_security("林女士", "420000.00", "北京市"),
        ],
        [
            goal(
                "子女国际课程",
                "education",
                "1500000.00",
                "2036-08-10",
                priority=1,
                prepared="400000.00",
                minimum="1000000.00",
            ),
            goal(
                "职业降速准备",
                "retirement",
                "9000000.00",
                "2048-08-10",
                priority=2,
                prepared="2500000.00",
                minimum="6000000.00",
            ),
            goal(
                "家庭旅行",
                "travel",
                "500000.00",
                "2030-08-10",
                priority=4,
                prepared="100000.00",
                minimum="250000.00",
                can_defer=True,
                rigidity="flexible",
            ),
        ],
        capacity="0.90",
        willingness="0.75",
        behavior="0.70",
        risk_limit="medium_high",
    )

    d_members = [
        member("沈先生", "本人", "1982-06-16", "科创企业创始人", stability="medium"),
        member("顾女士", "配偶", "1984-11-03", "品牌顾问"),
        member(
            "沈同学", "子女", "2012-05-09", None, stability="low", retirement_age=None
        ),
    ]
    d = bundle(
        "DEMO_D",
        "家庭 D｜科创企业创始人 Hero",
        "mature_family",
        "上海市",
        d_members,
        [
            income(
                "沈先生",
                "企业经营分配",
                "1600000.00",
                income_type="business",
                stability="0.45",
                volatility="0.55",
                interruption="0.35",
                concentration="0.70",
            ),
            income(
                "沈先生",
                "海外顾问收入",
                "250000.00",
                income_type="business",
                currency="USD",
                stability="0.55",
                volatility="0.40",
                concentration="0.20",
            ),
            income("顾女士", "顾问收入", "400000.00", concentration="0.10"),
        ],
        [
            expense("沈先生", "家庭基本生活", "420000.00", "basic_living"),
            expense("顾女士", "国际教育支出", "180000.00", "child_education"),
        ],
        [
            asset(
                "沈先生",
                "家庭隔离现金",
                "demand_deposit",
                "1000000.00",
                liquidity_days=0,
                liquidity_level="immediate",
                purpose="家庭与企业流动性隔离",
            ),
            asset(
                "沈先生",
                "美元存款",
                "time_deposit",
                "300000.00",
                currency="USD",
                liquidity_days=90,
                liquidity_level="within_1_year",
            ),
            asset(
                "顾女士",
                "港币存款",
                "demand_deposit",
                "500000.00",
                currency="HKD",
                liquidity_days=0,
                liquidity_level="immediate",
            ),
            asset(
                "沈先生",
                "公开市场基金",
                "public_fund",
                "1200000.00",
                risk="medium_high",
                liquidity_days=3,
            ),
            asset(
                "沈先生",
                "上海自住房",
                "primary_residence",
                "12000000.00",
                liquidity_days=180,
                liquidity_level="illiquid",
                property_use="primary_residence",
                risk="medium",
                region_code="310000",
            ),
        ],
        [
            liability(
                "沈先生",
                "自住房按揭",
                "mortgage",
                "2000000.00",
                "18000.00",
                rate="0.034000",
                maturity="2041-08-10",
                linked_asset="上海自住房",
            )
        ],
        [
            policy("沈先生", "创始人定期寿险", "term_life", "5000000.00", "18000.00"),
            policy("顾女士", "家庭医疗险", "medical", "3000000.00", "6500.00"),
        ],
        [
            social_security("沈先生", "480000.00", "上海市"),
            social_security("顾女士", "360000.00", "上海市"),
        ],
        [
            goal(
                "国际教育",
                "education",
                "3500000.00",
                "2031-08-10",
                priority=1,
                prepared="800000.00",
                minimum="2500000.00",
                currency="USD",
                growth="0.05",
            ),
            goal(
                "家庭财富传承",
                "wealth_transfer",
                "20000000.00",
                "2045-08-10",
                priority=2,
                prepared="1000000.00",
                minimum="10000000.00",
            ),
            goal(
                "家庭独立养老",
                "retirement",
                "12000000.00",
                "2047-08-10",
                priority=3,
                prepared="1800000.00",
                minimum="8000000.00",
            ),
        ],
        preferences={
            "trust_review_requested": True,
            "family_liquidity_isolation_target": "3000000.00",
        },
        capacity="0.85",
        willingness="0.80",
        behavior="0.65",
        risk_limit="medium_high",
    )

    e_members = [
        member("陆博士", "本人", "1988-01-20", "人工智能科学家"),
        member("周先生", "配偶", "1987-03-12", "产品负责人"),
    ]
    e = bundle(
        "DEMO_E",
        "家庭 E｜科创专家与科学家",
        "family_formation",
        "北京市",
        e_members,
        [
            income("陆博士", "科研岗位收入", "900000.00", concentration="0.65"),
            income(
                "陆博士",
                "海外合作收入",
                "150000.00",
                income_type="other",
                currency="USD",
                stability="0.55",
                volatility="0.35",
                concentration="0.15",
            ),
            income("周先生", "产品岗位收入", "500000.00", concentration="0.20"),
        ],
        [
            expense("陆博士", "家庭基本生活", "260000.00", "basic_living"),
            expense("周先生", "学习与会议", "100000.00", "other", essential=False),
        ],
        [
            asset(
                "陆博士",
                "活期存款",
                "demand_deposit",
                "500000.00",
                liquidity_days=0,
                liquidity_level="immediate",
            ),
            asset("周先生", "稳健基金", "bond_fund", "400000.00", risk="medium_low"),
            asset(
                "陆博士",
                "限制性股票",
                "stock",
                "6000000.00",
                risk="high",
                liquidity_days=1095,
                liquidity_level="illiquid",
                purpose="股权激励",
                source_kind="equity_incentive",
                household_role="employment_concentration",
            ),
            asset(
                "陆博士",
                "美元科研结余",
                "demand_deposit",
                "120000.00",
                currency="USD",
                liquidity_days=0,
                liquidity_level="immediate",
            ),
        ],
        [],
        [
            policy("陆博士", "科研人才医疗险", "medical", "2000000.00", "4200.00"),
            policy("周先生", "定期寿险", "term_life", "2000000.00", "5600.00"),
        ],
        [
            social_security("陆博士", "300000.00", "北京市"),
            social_security("周先生", "280000.00", "北京市"),
        ],
        [
            goal(
                "未来子女教育",
                "education",
                "1800000.00",
                "2040-08-10",
                priority=2,
                prepared="300000.00",
                minimum="1200000.00",
            ),
            goal(
                "创业选择权",
                "other",
                "2000000.00",
                "2032-08-10",
                priority=1,
                prepared="500000.00",
                minimum="1000000.00",
                can_defer=True,
            ),
            goal(
                "长期养老",
                "retirement",
                "8000000.00",
                "2053-08-10",
                priority=3,
                prepared="980000.00",
                minimum="5000000.00",
            ),
        ],
        preferences={
            "equity_incentive_holder": True,
            "entrepreneurship_possible": True,
        },
        capacity="0.80",
        willingness="0.75",
        behavior="0.70",
        risk_limit="medium_high",
    )

    f_members = [
        member(
            "郑先生",
            "本人",
            "1968-09-01",
            "家族企业董事长",
            stability="medium",
            retirement_age=65,
        ),
        member(
            "何女士",
            "配偶",
            "1970-02-12",
            "家族公益事务负责人",
            stability="medium",
            retirement_age=60,
        ),
        member(
            "郑父",
            "父亲",
            "1942-04-03",
            "退休",
            stability="low",
            retirement_age=60,
            health="medium_high",
        ),
        member("郑女儿", "子女", "1996-07-19", "企业管理人员"),
        member(
            "郑外孙", "孙辈", "2022-10-21", None, stability="low", retirement_age=None
        ),
    ]
    f = bundle(
        "DEMO_F",
        "家庭 F｜多代际高净值家族",
        "retirement_and_legacy",
        "广东省深圳市",
        f_members,
        [
            income(
                "郑先生",
                "企业分红",
                "3500000.00",
                income_type="business",
                stability="0.55",
                volatility="0.40",
                concentration="0.75",
            ),
            income(
                "何女士",
                "投资收入",
                "900000.00",
                income_type="investment",
                concentration="0.15",
            ),
            income(
                "郑父",
                "养老金",
                "120000.00",
                income_type="pension",
                stability="0.95",
                volatility="0.02",
                interruption="0.01",
                concentration="0.10",
            ),
        ],
        [
            expense("郑先生", "多代际家庭支出", "900000.00", "basic_living"),
            expense("何女士", "医疗照护", "300000.00", "medical"),
            expense("何女士", "年度公益预算", "600000.00", "other", essential=False),
        ],
        [
            asset(
                "郑先生",
                "家族现金池",
                "demand_deposit",
                "5000000.00",
                liquidity_days=0,
                liquidity_level="immediate",
            ),
            asset(
                "何女士",
                "债券组合",
                "bond",
                "8000000.00",
                risk="medium_low",
                liquidity_days=30,
                liquidity_level="within_30_days",
            ),
            asset(
                "郑先生",
                "公开市场权益",
                "public_fund",
                "12000000.00",
                risk="high",
                liquidity_days=3,
            ),
            asset(
                "郑先生",
                "深圳主宅",
                "primary_residence",
                "30000000.00",
                risk="medium",
                liquidity_days=180,
                liquidity_level="illiquid",
                property_use="primary_residence",
                region_code="440300",
            ),
            asset(
                "何女士",
                "家族信托观察资产",
                "trust",
                "10000000.00",
                risk="medium",
                liquidity_days=3650,
                liquidity_level="illiquid",
                purpose="传承安排",
            ),
        ],
        [],
        [
            policy("郑先生", "终身寿险", "whole_life", "15000000.00", "280000.00"),
            policy("郑父", "长期医疗险", "medical", "2000000.00", "26000.00"),
        ],
        [
            social_security("郑先生", "800000.00", "广东省深圳市"),
            social_security("何女士", "760000.00", "广东省深圳市"),
            social_security("郑父", "500000.00", "广东省深圳市"),
        ],
        [
            goal(
                "企业与家族传承",
                "wealth_transfer",
                "60000000.00",
                "2040-08-10",
                priority=1,
                prepared="10000000.00",
                minimum="30000000.00",
            ),
            goal(
                "多代际照护",
                "medical",
                "8000000.00",
                "2045-08-10",
                priority=2,
                prepared="2000000.00",
                minimum="5000000.00",
            ),
            goal(
                "家族养老",
                "retirement",
                "18000000.00",
                "2033-08-10",
                priority=3,
                prepared="5000000.00",
                minimum="12000000.00",
            ),
        ],
        preferences={
            "trust_review_requested": True,
            "philanthropy_target_amount": "6000000.00",
            "philanthropy_annual_budget": "600000.00",
            "philanthropy_target_cause": "科技教育与乡村医疗",
            "philanthropy_family_participation": "三代家庭共同参与年度复核",
            "philanthropy_governance_preference": "预算、用途、受益人与年度报告分层治理",
        },
        capacity="0.90",
        willingness="0.65",
        behavior="0.60",
        risk_limit="medium",
    )

    g_members = [
        member("唐先生", "本人", "1984-05-14", "跨国企业财务负责人"),
        member("袁女士", "配偶", "1986-08-08", "大学教师"),
        member(
            "唐同学", "子女", "2011-01-30", None, stability="low", retirement_age=None
        ),
    ]
    g = bundle(
        "DEMO_G",
        "家庭 G｜跨境资产与教育责任",
        "parenting",
        "上海市",
        g_members,
        [
            income("唐先生", "人民币工资", "900000.00", concentration="0.70"),
            income("袁女士", "人民币工资", "360000.00", concentration="0.30"),
        ],
        [
            expense("唐先生", "家庭基本生活", "300000.00", "basic_living"),
            expense("袁女士", "教育准备支出", "120000.00", "child_education"),
        ],
        [
            asset(
                "唐先生",
                "人民币活期",
                "demand_deposit",
                "600000.00",
                liquidity_days=0,
                liquidity_level="immediate",
            ),
            asset(
                "唐先生",
                "美元存款",
                "time_deposit",
                "800000.00",
                currency="USD",
                liquidity_days=180,
                liquidity_level="within_1_year",
            ),
            asset(
                "袁女士",
                "港币存款",
                "demand_deposit",
                "1200000.00",
                currency="HKD",
                liquidity_days=0,
                liquidity_level="immediate",
            ),
            asset(
                "唐先生",
                "全球指数基金",
                "public_fund",
                "1000000.00",
                currency="USD",
                risk="high",
                liquidity_days=3,
            ),
            asset(
                "唐先生",
                "上海自住房",
                "primary_residence",
                "8000000.00",
                risk="medium",
                liquidity_days=180,
                liquidity_level="illiquid",
                property_use="primary_residence",
                region_code="310000",
            ),
        ],
        [
            liability(
                "唐先生",
                "住房按揭",
                "mortgage",
                "1800000.00",
                "14000.00",
                rate="0.034000",
                maturity="2042-08-10",
                linked_asset="上海自住房",
            )
        ],
        [
            policy("唐先生", "定期寿险", "term_life", "4000000.00", "12000.00"),
            policy("袁女士", "医疗险", "medical", "2000000.00", "4800.00"),
        ],
        [
            social_security("唐先生", "420000.00", "上海市"),
            social_security("袁女士", "360000.00", "上海市"),
        ],
        [
            goal(
                "海外本科教育",
                "education",
                "500000.00",
                "2029-08-10",
                priority=1,
                prepared="150000.00",
                minimum="400000.00",
                rigidity="rigid",
                currency="USD",
                growth="0.05",
            ),
            goal(
                "家庭养老",
                "retirement",
                "10000000.00",
                "2049-08-10",
                priority=2,
                prepared="2000000.00",
                minimum="6500000.00",
            ),
        ],
        capacity="0.80",
        willingness="0.70",
        behavior="0.65",
        risk_limit="medium_high",
    )

    h_members = [
        member(
            "周先生",
            "本人",
            "1963-02-18",
            "退休工程师",
            stability="low",
            retirement_age=60,
            health="medium",
        ),
        member(
            "赵女士",
            "配偶",
            "1965-06-26",
            "退休会计师",
            stability="low",
            retirement_age=60,
            health="medium_high",
        ),
    ]
    h = bundle(
        "DEMO_H",
        "家庭 H｜退休与长寿责任",
        "retirement_and_legacy",
        "广东省广州市",
        h_members,
        [
            income(
                "周先生",
                "基本养老金",
                "180000.00",
                income_type="pension",
                stability="0.95",
                volatility="0.02",
                interruption="0.01",
                concentration="0.55",
            ),
            income(
                "赵女士",
                "基本养老金",
                "150000.00",
                income_type="pension",
                stability="0.95",
                volatility="0.02",
                interruption="0.01",
                concentration="0.45",
            ),
            income(
                "周先生",
                "租金收入",
                "120000.00",
                income_type="rental",
                stability="0.70",
                volatility="0.15",
                concentration="0.20",
            ),
        ],
        [
            expense("周先生", "退休基本生活", "240000.00", "basic_living"),
            expense("赵女士", "医疗与照护", "100000.00", "medical"),
            expense("周先生", "旅行支出", "60000.00", "discretionary", essential=False),
        ],
        [
            asset(
                "周先生",
                "退休活期",
                "demand_deposit",
                "500000.00",
                liquidity_days=0,
                liquidity_level="immediate",
            ),
            asset(
                "赵女士",
                "养老定期",
                "time_deposit",
                "800000.00",
                liquidity_days=180,
                liquidity_level="within_1_year",
            ),
            asset(
                "周先生", "稳健债券基金", "bond_fund", "600000.00", risk="medium_low"
            ),
            asset(
                "周先生",
                "广州自住房",
                "primary_residence",
                "6000000.00",
                risk="medium",
                liquidity_days=180,
                liquidity_level="illiquid",
                property_use="primary_residence",
                region_code="440100",
            ),
            asset(
                "赵女士",
                "出租物业",
                "investment_property",
                "2500000.00",
                risk="medium_high",
                liquidity_days=180,
                liquidity_level="illiquid",
                property_use="investment_property",
                region_code="440100",
            ),
            asset(
                "周先生",
                "个人养老金",
                "pension_account",
                "600000.00",
                liquidity_days=365,
                liquidity_level="within_1_year",
                purpose="退休提取",
            ),
        ],
        [],
        [
            policy("周先生", "退休医疗险", "medical", "1000000.00", "16000.00"),
            policy("赵女士", "长期护理观察保单", "other", "500000.00", "18000.00"),
        ],
        [
            social_security("周先生", "900000.00", "广东省广州市"),
            social_security("赵女士", "820000.00", "广东省广州市"),
        ],
        [
            goal(
                "退休现金流",
                "retirement",
                "5000000.00",
                "2035-08-10",
                priority=1,
                prepared="2500000.00",
                minimum="3500000.00",
                rigidity="rigid",
            ),
            goal(
                "医疗与长期照护",
                "medical",
                "3000000.00",
                "2040-08-10",
                priority=2,
                prepared="800000.00",
                minimum="2000000.00",
                rigidity="rigid",
            ),
            goal(
                "代际传承",
                "wealth_transfer",
                "4000000.00",
                "2045-08-10",
                priority=3,
                prepared="1000000.00",
                minimum="2500000.00",
            ),
        ],
        preferences={
            "retirement_withdrawal_review_requested": True,
            "long_term_care_review_requested": True,
        },
        capacity="0.55",
        willingness="0.45",
        behavior="0.40",
        risk_limit="medium_low",
    )

    d_enterprise = enterprise(
        "DEMO_D",
        "澄明科技",
        "沈先生",
        industry="人工智能基础设施",
        stage="growth",
        jurisdiction="CN",
        listed_status="unlisted",
        enterprise_type="operating_company",
        value="30000000.00",
        ownership_ratio="0.800000",
        instrument_type="common_equity",
        cashflows=[
            {
                "member_id": "沈先生",
                "cashflow_type": "salary",
                "amount": "1200000.00",
                "currency": "CNY",
                "frequency": "annual",
                "stability": "medium",
            },
            {
                "member_id": "沈先生",
                "cashflow_type": "business_distribution",
                "amount": "250000.00",
                "currency": "USD",
                "frequency": "annual",
                "stability": "low",
            },
        ],
        guarantees=[
            {
                "member_id": "沈先生",
                "guarantee_type": "personal",
                "guaranteed_amount": "10000000.00",
                "outstanding_exposure": "8000000.00",
                "expiry_date": "2029-12-31",
                "currency": "CNY",
            }
        ],
        events=[
            {
                "event_type": "funding",
                "expected_date": "2027-03-31",
                "estimated_value": "20000000.00",
                "probability": "0.70",
                "lockup": True,
                "currency": "CNY",
                "status": "planned",
            }
        ],
    )
    e_enterprise = enterprise(
        "DEMO_E",
        "北辰智能",
        "陆博士",
        industry="人工智能",
        stage="pre_ipo",
        jurisdiction="CN",
        listed_status="unlisted",
        enterprise_type="operating_company",
        value="6000000.00",
        ownership_ratio="0.015000",
        instrument_type="restricted_stock",
        events=[
            {
                "event_type": "lockup_expiry",
                "expected_date": "2028-12-31",
                "estimated_value": "6000000.00",
                "probability": "0.50",
                "lockup": True,
                "currency": "CNY",
                "status": "planned",
            }
        ],
    )
    f_enterprise = enterprise(
        "DEMO_F",
        "鹏远实业集团",
        "郑先生",
        industry="高端制造",
        stage="mature",
        jurisdiction="CN",
        listed_status="unlisted",
        enterprise_type="family_business",
        value="80000000.00",
        ownership_ratio="0.700000",
        instrument_type="common_equity",
        cashflows=[
            {
                "member_id": "郑先生",
                "cashflow_type": "dividend",
                "amount": "3500000.00",
                "currency": "CNY",
                "frequency": "annual",
                "stability": "medium",
            }
        ],
    )
    return {
        "schema_version": "canonical-v5-persona-v2",
        "dataset_version": SOURCE,
        "as_of_date": AS_OF,
        "personas": personas,
        "households": [a, b, c, d, e, f, g, h],
        "enterprise_extensions": [d_enterprise, e_enterprise, f_enterprise],
    }


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(build_dataset(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(OUTPUT)


if __name__ == "__main__":
    main()
