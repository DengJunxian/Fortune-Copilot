import asyncio
from collections.abc import Mapping
from typing import Any

from httpx import ASGITransport, AsyncClient, Response

from app.core.database import SessionLocal
from app.main import app
from app.models.family import Household
from app.models.finance import Asset
from app.services.seed import reset_synthetic_data


async def api_request(
    method: str,
    path: str,
    *,
    payload: Mapping[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
) -> Response:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, path, json=payload, headers=headers)


def call(
    method: str,
    path: str,
    *,
    payload: Mapping[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
) -> Response:
    return asyncio.run(api_request(method, path, payload=payload, headers=headers))


def household_payload(code: str = "TEST_HOUSEHOLD") -> dict[str, Any]:
    return {
        "code": code,
        "name": "接口测试家庭",
        "lifecycle_stage": "family_formation",
        "region": "上海市",
        "is_synthetic": True,
        "data_source": "test",
        "is_user_confirmed": True,
    }


def create_household(code: str = "TEST_HOUSEHOLD") -> dict[str, Any]:
    response = call("POST", "/api/v1/households", payload=household_payload(code))
    assert response.status_code == 201, response.text
    return response.json()


def create_member(household_id: str, name: str = "测试成员") -> dict[str, Any]:
    response = call(
        "POST",
        f"/api/v1/households/{household_id}/members",
        payload={
            "display_name": name,
            "relationship": "本人",
            "birth_date": "1990-01-01",
            "occupation": "测试职业",
            "employment_stability": "high",
            "expected_retirement_age": 60,
            "health_risk_level": "low",
            "data_source": "test",
            "is_user_confirmed": True,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_household_and_required_nested_resources_support_full_crud() -> None:
    household = create_household()
    household_id = household["id"]

    page = call("GET", "/api/v1/households?page=1&page_size=1")
    assert page.status_code == 200
    assert page.json()["pagination"] == {"page": 1, "page_size": 1, "total": 1, "pages": 1}

    updated_household = call(
        "PATCH",
        f"/api/v1/households/{household_id}",
        payload={"expected_version": 1, "name": "已更新测试家庭"},
    )
    assert updated_household.status_code == 200
    assert updated_household.json()["version"] == 2

    member = create_member(household_id)
    member_id = member["id"]
    asset_response = call(
        "POST",
        f"/api/v1/households/{household_id}/assets",
        payload={
            "owner_member_id": member_id,
            "name": "测试活期资产",
            "category": "demand_deposit",
            "subcategory": "测试",
            "acquisition_cost": "1000.01",
            "market_value": "1234.56",
            "liquidity_days": 0,
            "liquidity_level": "immediate",
            "risk_level": "low",
            "purpose": "接口测试",
            "pledged": False,
            "ownership": "本人",
            "property_use": "not_property",
        },
    )
    assert asset_response.status_code == 201, asset_response.text
    asset = asset_response.json()
    assert asset["market_value"] == "1234.56"

    resources: list[tuple[str, dict[str, Any], dict[str, Any], str, Any]] = [
        (
            "liabilities",
            {
                "borrower_member_id": member_id,
                "linked_asset_id": asset["id"],
                "name": "测试负债",
                "category": "consumer_loan",
                "outstanding_balance": "500.00",
                "annual_interest_rate": "0.12",
                "monthly_payment": "50.00",
                "maturity_date": "2027-01-01",
                "rate_type": "fixed",
                "prepayment_cost": "0.00",
                "is_high_interest": True,
            },
            {"name": "已更新负债"},
            "name",
            "已更新负债",
        ),
        (
            "incomes",
            {
                "member_id": member_id,
                "name": "测试收入",
                "amount": "120000.00",
                "frequency": "annual",
                "stability": "0.80",
                "volatility": "0.10",
                "interruption_probability": "0.10",
                "cycle_correlation": "0.20",
                "source_concentration": "1.00",
                "is_sustainable": True,
            },
            {"amount": "120001.23"},
            "amount",
            "120001.23",
        ),
        (
            "expenses",
            {
                "member_id": member_id,
                "name": "测试支出",
                "amount": "60000.00",
                "frequency": "annual",
                "necessity": "essential",
                "compressible_ratio": "0.10",
                "category": "basic_living",
            },
            {"amount": "59000.00"},
            "amount",
            "59000.00",
        ),
        (
            "insurance-policies",
            {
                "insured_member_id": member_id,
                "name": "模拟医疗险",
                "policy_type": "medical",
                "coverage_amount": "1000000.00",
                "annual_premium": "1000.00",
                "start_date": "2026-01-01",
                "end_date": "2026-12-31",
                "deductible": "10000.00",
                "waiting_period_days": 30,
                "guaranteed_benefit": "0.00",
                "non_guaranteed_benefit": "0.00",
                "cash_value": "0.00",
            },
            {"annual_premium": "1100.00"},
            "annual_premium",
            "1100.00",
        ),
        (
            "goals",
            {
                "name": "测试目标",
                "goal_type": "education",
                "target_amount": "300000.00",
                "target_date": "2036-01-01",
                "rigidity": "important",
                "priority": 1,
                "can_defer": True,
                "minimum_acceptable_amount": "200000.00",
                "prepared_amount": "10000.00",
                "annual_cost_growth_rate": "0.04",
            },
            {"priority": 2},
            "priority",
            2,
        ),
        (
            "risk-assessments",
            {
                "capacity_score": "0.60",
                "willingness_score": "0.70",
                "knowledge_score": "0.50",
                "behavior_score": "0.40",
                "final_risk_limit": "medium",
                "explanation": "测试风险解释",
            },
            {"final_risk_limit": "medium_low"},
            "final_risk_limit",
            "medium_low",
        ),
        (
            "consents",
            {
                "member_id": member_id,
                "scopes": ["finance"],
                "purpose": "接口测试",
                "granted_at": "2026-08-04T09:00:00+08:00",
                "consent_version": "v1",
                "metadata_json": {
                    "scenario": "core_planning",
                    "explicit": True,
                },
            },
            {"scopes": ["finance", "risk"]},
            "scopes",
            ["finance", "risk"],
        ),
    ]

    for slug, create_payload, patch_payload, field, expected in resources:
        base_path = f"/api/v1/households/{household_id}/{slug}"
        created = call("POST", base_path, payload=create_payload)
        assert created.status_code == 201, f"{slug}: {created.text}"
        record = created.json()
        record_id = record["id"]
        listed = call("GET", f"{base_path}?page=1&page_size=10")
        assert listed.status_code == 200
        assert listed.json()["pagination"]["total"] == 1
        assert call("GET", f"{base_path}/{record_id}").status_code == 200

        patch = {"expected_version": 1, **patch_payload}
        updated = call("PATCH", f"{base_path}/{record_id}", payload=patch)
        assert updated.status_code == 200, f"{slug}: {updated.text}"
        assert updated.json()[field] == expected
        assert updated.json()["version"] == 2

        stale = call("PATCH", f"{base_path}/{record_id}", payload=patch)
        assert stale.status_code == 409
        assert stale.json()["error"]["code"] == "version_conflict"

        deleted = call("DELETE", f"{base_path}/{record_id}?expected_version=2")
        assert deleted.status_code == 204
        assert call("GET", f"{base_path}/{record_id}").status_code == 404

    asset_path = f"/api/v1/households/{household_id}/assets/{asset['id']}"
    updated_asset = call(
        "PATCH",
        asset_path,
        payload={"expected_version": 1, "market_value": "1235.67"},
    )
    assert updated_asset.status_code == 200
    assert updated_asset.json()["market_value"] == "1235.67"
    assert call("DELETE", f"{asset_path}?expected_version=2").status_code == 204
    with SessionLocal() as session:
        deleted_asset = session.get(Asset, asset["id"])
        assert deleted_asset is not None
        assert deleted_asset.is_deleted is True
        assert deleted_asset.deleted_at is not None
        assert deleted_asset.version == 3

    member_path = f"/api/v1/households/{household_id}/members/{member_id}"
    updated_member = call(
        "PATCH",
        member_path,
        payload={"expected_version": 1, "occupation": "已更新职业"},
    )
    assert updated_member.status_code == 200
    assert call("DELETE", f"{member_path}?expected_version=2").status_code == 204

    deleted_household = call(
        "DELETE",
        f"/api/v1/households/{household_id}?expected_version=2",
        headers={"X-Confirm-Action": "legacy_soft_delete_household"},
    )
    assert deleted_household.status_code == 204
    assert call("GET", f"/api/v1/households/{household_id}").status_code == 404


def test_money_rejects_binary_float_and_references_are_household_scoped() -> None:
    first = create_household("HOUSEHOLD_ONE")
    second = create_household("HOUSEHOLD_TWO")
    second_member = create_member(second["id"], "第二家庭成员")
    payload = {
        "owner_member_id": second_member["id"],
        "name": "跨家庭资产",
        "category": "cash",
        "acquisition_cost": "0.10",
        "market_value": "0.10",
        "liquidity_days": 0,
        "liquidity_level": "immediate",
        "risk_level": "low",
        "purpose": "测试",
        "ownership": "本人",
        "property_use": "not_property",
    }
    cross_household = call(
        "POST",
        f"/api/v1/households/{first['id']}/assets",
        payload=payload,
    )
    assert cross_household.status_code == 404

    payload["owner_member_id"] = None
    payload["market_value"] = 0.1
    float_money = call(
        "POST",
        f"/api/v1/households/{first['id']}/assets",
        payload=payload,
    )
    assert float_money.status_code == 422
    assert float_money.json()["error"]["code"] == "validation_error"
    assert all("input" not in detail for detail in float_money.json()["error"]["details"])


def test_user_household_defaults_to_non_synthetic_and_survives_demo_reset() -> None:
    payload = household_payload("USER_HOUSEHOLD")
    payload.pop("is_synthetic")
    response = call("POST", "/api/v1/households", payload=payload)
    assert response.status_code == 201
    household = response.json()
    assert household["is_synthetic"] is False

    with SessionLocal() as session:
        assert reset_synthetic_data(session) == 0
        preserved = session.get(Household, household["id"])
        assert preserved is not None
        assert preserved.is_synthetic is False


def test_partial_updates_validate_complete_goal_and_insurance_state() -> None:
    household = create_household("PATCH_VALIDATION")
    household_id = household["id"]
    member = create_member(household_id)

    invalid_consent = call(
        "POST",
        f"/api/v1/households/{household_id}/consents",
        payload={
            "member_id": member["id"],
            "scopes": ["finance"],
            "purpose": "授权时间线验证",
            "granted_at": "2026-08-04T09:00:00+08:00",
            "withdrawn_at": "2026-08-03T09:00:00+08:00",
            "consent_version": "v1",
        },
    )
    assert invalid_consent.status_code == 422
    assert invalid_consent.json()["error"]["code"] == "validation_error"

    goal = call(
        "POST",
        f"/api/v1/households/{household_id}/goals",
        payload={
            "name": "目标整体验证",
            "goal_type": "education",
            "target_amount": "300000.00",
            "target_date": "2036-01-01",
            "rigidity": "important",
            "priority": 1,
            "can_defer": True,
            "minimum_acceptable_amount": "200000.00",
            "prepared_amount": "10000.00",
            "annual_cost_growth_rate": "0.04",
        },
    )
    assert goal.status_code == 201
    invalid_goal = call(
        "PATCH",
        f"/api/v1/households/{household_id}/goals/{goal.json()['id']}",
        payload={"expected_version": 1, "target_amount": "100000.00"},
    )
    assert invalid_goal.status_code == 422
    assert invalid_goal.json()["error"]["code"] == "validation_error"

    policy = call(
        "POST",
        f"/api/v1/households/{household_id}/insurance-policies",
        payload={
            "insured_member_id": member["id"],
            "name": "保单整体验证",
            "policy_type": "medical",
            "coverage_amount": "1000000.00",
            "annual_premium": "1000.00",
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "deductible": "10000.00",
            "waiting_period_days": 30,
            "guaranteed_benefit": "0.00",
            "non_guaranteed_benefit": "0.00",
            "cash_value": "0.00",
        },
    )
    assert policy.status_code == 201
    invalid_policy = call(
        "PATCH",
        f"/api/v1/households/{household_id}/insurance-policies/{policy.json()['id']}",
        payload={"expected_version": 1, "end_date": "2025-12-31"},
    )
    assert invalid_policy.status_code == 422
    assert invalid_policy.json()["error"]["code"] == "validation_error"

    current_goal = call("GET", f"/api/v1/households/{household_id}/goals/{goal.json()['id']}")
    current_policy = call(
        "GET",
        f"/api/v1/households/{household_id}/insurance-policies/{policy.json()['id']}",
    )
    assert current_goal.json()["version"] == 1
    assert current_policy.json()["version"] == 1


def test_permission_placeholder_rejects_unknown_roles() -> None:
    response = call(
        "GET",
        "/api/v1/households",
        headers={"X-Actor-Role": "unknown", "X-Actor-ID": "test"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden_role"
