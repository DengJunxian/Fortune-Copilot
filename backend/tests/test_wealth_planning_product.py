from decimal import Decimal

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.wealth_planning import RATIO_METRIC_IDS

client = TestClient(app)


def test_client_intake_creates_normalized_case_and_six_ratio_explanations() -> None:
    response = client.post(
        "/api/v1/wealth-planning/cases",
        headers={"X-Actor-ID": "client-intake-test", "X-Actor-Role": "client"},
        json={
            "planning_scope": "family",
            "case_name": "周先生家庭财富规划",
            "region": "上海市",
            "kyc": {
                "city_tier": "tier_one_or_new_tier_one",
                "growth_entry_threshold": "700000.00",
                "investment_experience": "experienced",
                "risk_preference": "balanced",
                "loss_tolerance": "medium",
                "investment_horizon_years": 10,
                "funds_sources": ["salary", "accumulated_savings"],
                "personal_pension_status": "opened",
            },
            "members": [
                {
                    "display_name": "周先生",
                    "relationship": "本人",
                    "birth_date": "1989-04-12",
                    "occupation": "工程师",
                    "employment_stability": "high",
                    "expected_retirement_age": 60,
                },
                {
                    "display_name": "林女士",
                    "relationship": "配偶",
                    "birth_date": "1990-11-03",
                    "occupation": "会计",
                    "employment_stability": "high",
                    "expected_retirement_age": 55,
                },
                {
                    "display_name": "周同学",
                    "relationship": "子女",
                    "birth_date": "2019-08-20",
                    "occupation": None,
                    "employment_stability": "low",
                    "expected_retirement_age": None,
                },
            ],
            "assets": [
                {
                    "category": "cash_and_equivalents",
                    "label": "现金、活期存款及货币基金",
                    "amount": "180000.00",
                },
                {
                    "category": "time_deposit_and_bank_wealth",
                    "label": "定期存款及银行理财",
                    "amount": "260000.00",
                },
                {
                    "category": "non_bank_financial",
                    "label": "基金及其他金融资产",
                    "amount": "160000.00",
                },
                {
                    "category": "primary_residence",
                    "label": "家庭自住房",
                    "amount": "3200000.00",
                },
            ],
            "liabilities": [
                {
                    "category": "mortgage",
                    "label": "住房贷款余额",
                    "balance": "1450000.00",
                    "monthly_payment": "9800.00",
                    "annual_interest_rate": "0.032000",
                },
                {
                    "category": "credit_card_unpaid",
                    "label": "信用卡本期未付",
                    "balance": "8600.00",
                    "monthly_payment": "8600.00",
                    "annual_interest_rate": "0.000000",
                },
            ],
            "incomes": [
                {
                    "category": "self_employment",
                    "label": "本人税后年收入",
                    "annual_amount": "360000.00",
                },
                {
                    "category": "spouse_employment",
                    "label": "配偶税后年收入",
                    "annual_amount": "240000.00",
                },
                {
                    "category": "asset_income",
                    "label": "资产生息收入",
                    "annual_amount": "18000.00",
                },
            ],
            "expenses": [
                {
                    "category": "living",
                    "label": "家庭生活费",
                    "annual_amount": "168000.00",
                },
                {
                    "category": "child_education",
                    "label": "子女教养费",
                    "annual_amount": "72000.00",
                },
                {
                    "category": "insurance_premium",
                    "label": "家庭保费",
                    "annual_amount": "24000.00",
                },
                {
                    "category": "debt_service",
                    "label": "年度还贷支出",
                    "annual_amount": "126200.00",
                },
                {
                    "category": "other",
                    "label": "其他支出",
                    "annual_amount": "48000.00",
                },
            ],
        },
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    household_id = payload["household_id"]
    analysis = payload["analysis"]
    assert analysis["profile"]["lifecycle_stage"] == "parenting"
    assert analysis["statements"]["balance_sheet"]["total_assets"] == "3800000.00"
    assert analysis["statements"]["balance_sheet"]["total_liabilities"] == "1458600.00"
    assert analysis["statements"]["balance_sheet"]["net_worth"] == "2341400.00"
    assert any(
        item["category"] == "credit_card_unpaid"
        for item in analysis["statements"]["balance_sheet"]["liabilities"]
    )
    assert not any("credit_limit" in str(item) for item in analysis["metrics"])

    explanation = client.post(
        f"/api/v1/households/{household_id}/ratio-explanations",
        headers={"X-Actor-ID": "client-intake-test", "X-Actor-Role": "client"},
        json={"question": "请逐项说明家庭目前最需要关注什么。"},
    )
    assert explanation.status_code == 200, explanation.text
    explained = explanation.json()
    assert explained["provider"] == "mock"
    assert explained["calculation_source"] == "deterministic_tools"
    assert {item["metric_id"] for item in explained["items"]} == set(RATIO_METRIC_IDS)
    assert len(explained["items"]) == 6

    narrative = client.post(
        f"/api/v1/households/{household_id}/plan-narrative",
        headers={"X-Actor-ID": "client-intake-test", "X-Actor-Role": "client"},
        json={
            "goals": [
                {
                    "name": "子女教育准备",
                    "goal_type": "education",
                    "target_amount": "600000.00",
                    "target_date": "2035-09-01",
                    "prepared_amount": "80000.00",
                    "rigidity": "important",
                }
            ],
            "major_expenses": [
                {
                    "name": "车辆更新",
                    "target_amount": "180000.00",
                    "target_date": "2029-06-01",
                    "prepared_amount": "30000.00",
                    "planned_source": "年度结余",
                }
            ],
        },
    )
    assert narrative.status_code == 200, narrative.text
    plan_payload = narrative.json()
    assert plan_payload["provider"] == "mock"
    assert (
        plan_payload["planning"]["methodology"]["regional_threshold"]
        ["customer_selected_threshold"]
        == "700000.00"
    )
    assert plan_payload["planning"]["denominators"]["growth_entry_threshold"] == "735000.00"
    assert (
        plan_payload["planning"]["denominators"]["growth_entry_threshold"]
        == plan_payload["planning"]["methodology"]["regional_threshold"]
        ["effective_threshold"]
    )
    assert (
        plan_payload["planning"]["denominators"]["net_financial_assets_after_debt"]
        == "-858600.00"
    )
    assert plan_payload["planning"]["accounts"][2]["name"] == "保本的钱"
    learning = plan_payload["planning"]["investment_learning"]
    assert learning["applicable"] is True
    assert learning["eligible"] is True
    assert Decimal(learning["recommended_ratio"]) <= Decimal("0.100000")
    assert (
        plan_payload["planning"]["accounts"][3]["recommended_amount"]
        == learning["recommended_amount"]
    )
    assert "宽基指数基金" in plan_payload["narrative"]["four_account_analysis"]
    assert "认识真实波动" in plan_payload["narrative"]["four_account_analysis"]
    assert plan_payload["planning"]["growth_benchmark"]["minimum_wage_is_cpi"] is False
    assert plan_payload["planning"]["growth_benchmark"]["is_return_guarantee"] is False
    assert plan_payload["narrative"]["family_analysis"]
    assert len(plan_payload["narrative"]["review_triggers"]) >= 3
    assert (
        "地区长期资金启动门槛或个人风险承受能力变化"
        in plan_payload["narrative"]["review_triggers"]
    )
    assert (
        "市场环境和长期资金参考条件发生明显变化"
        in plan_payload["narrative"]["review_triggers"]
    )
