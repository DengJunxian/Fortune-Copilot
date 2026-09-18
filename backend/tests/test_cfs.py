from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import func, select

from app.core.auth import ActorContext
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.domain.enums import AssetCategory, CFSComponentType, FinancialEntityType
from app.main import app
from app.models.cfs import CFSSolution, CFSSolutionComponent, ProfessionalServiceReferral
from app.models.family import Household
from app.models.finance import Asset, InsurancePolicy, Liability
from app.schemas.cfs import CFSComposeRequest
from app.schemas.family_enterprise import EnterpriseCreate, EnterpriseExposureCreate
from app.services.cfs_composer.engine import compose_cfs_solution
from app.services.family_enterprise.events import process_enterprise_exposures
from app.services.family_enterprise.repository import create_enterprise
from app.services.financial_graph.engine import build_financial_graph
from app.services.seed import seed_synthetic_data

DATASET_PATH = "../data/synthetic/families.json"
FINANCIAL_RULES_PATH = "../data/rules/financial_health_v1.json"
PLANNING_RULES_PATH = "../data/rules/planning_waterfall_v1.json"
METHODOLOGY_RULES_PATH = "../data/rules/wealth_methodology_v3.json"
PUBLIC_DATA_PATH = "../data/public/authoritative_public_snapshot_v1.json"
CLIENT_PROFILE_RULES_PATH = "../data/rules/client_profile_v1.json"
LIABILITY_RULES_PATH = "../data/rules/liability_engine_v1.json"
TWIN_RULES_PATH = "../data/rules/twin_simulation_v1.json"
FAMILY_ENTERPRISE_RULES_PATH = "../data/rules/family_enterprise_v1.json"
CFS_RULES_PATH = "../data/rules/cfs_composer_v1.json"
ANALYSIS_DATE = date(2026, 8, 10)


def _actor(role: str = "admin") -> ActorContext:
    now = datetime.now(UTC)
    return ActorContext(
        actor_id=f"cfs-{role}",
        role=role,  # type: ignore[arg-type]
        household_ids=("*",),
        issued_at=now,
        expires_at=now + timedelta(hours=1),
        auth_source="demo_headers",
    )


def _seed(code: str) -> str:
    with SessionLocal() as session:
        seed_synthetic_data(
            session,
            DATASET_PATH,
            rules_path=FINANCIAL_RULES_PATH,
            planning_rules_path=PLANNING_RULES_PATH,
            methodology_rules_path=METHODOLOGY_RULES_PATH,
            twin_rules_path=TWIN_RULES_PATH,
            reset=True,
        )
        household = session.scalar(select(Household).where(Household.code == code))
        assert household is not None
        return household.id


def _compose_kwargs() -> dict[str, Any]:
    return {
        "financial_rules_path": FINANCIAL_RULES_PATH,
        "planning_rules_path": PLANNING_RULES_PATH,
        "methodology_rules_path": METHODOLOGY_RULES_PATH,
        "public_data_snapshot_path": PUBLIC_DATA_PATH,
        "client_profile_rules_path": CLIENT_PROFILE_RULES_PATH,
        "liability_rules_path": LIABILITY_RULES_PATH,
        "family_enterprise_rules_path": FAMILY_ENTERPRISE_RULES_PATH,
        "cfs_rules_path": CFS_RULES_PATH,
        "analysis_date": ANALYSIS_DATE,
    }


def test_case_one_high_interest_debt_blocks_investment_and_records_no_action() -> None:
    household_id = _seed("DEMO_B")
    with SessionLocal() as session:
        result = compose_cfs_solution(
            session,
            household_id,
            CFSComposeRequest(is_user_confirmed=True),
            _actor(),
            **_compose_kwargs(),
        )
        component_types = {item.component_type for item in result.components}
        no_action = next(
            item
            for item in result.components
            if item.component_type == CFSComponentType.NO_ACTION
        )
        no_action_step = next(
            item for item in result.orchestration if item.component_id == no_action.id
        )
        assert CFSComponentType.DEBT in component_types
        assert CFSComponentType.INVESTMENT not in component_types
        assert no_action.status.value == "no_action_required"
        assert no_action.target_amount > 0
        assert "不新增投资" in no_action.recommended_action
        assert no_action.product_mapping_allowed is False
        assert no_action_step.deterministic_tool == "no_action"
        assert no_action_step.status == "blocked"
        assert result.risk_budget.decision == "repair_first"
        assert result.risk_budget.additional_risk_allowed is False
        risk_order = {
            "low": 0,
            "medium_low": 1,
            "medium": 2,
            "medium_high": 3,
            "high": 4,
        }
        final_level = risk_order[result.risk_budget.household_economic_risk_capacity.value]
        assert final_level <= risk_order[result.risk_budget.capacity.value]
        assert final_level <= risk_order[result.risk_budget.willingness.value]
        assert final_level <= risk_order[result.risk_budget.behavior.value]
        assert {item.code for item in result.risk_budget.factors} == {
            "capacity",
            "willingness",
            "behavior",
            "existing_economic_exposure",
            "liquidity",
            "liability_rigidity",
            "time_horizon",
        }

        replay = compose_cfs_solution(
            session,
            household_id,
            CFSComposeRequest(is_user_confirmed=True),
            _actor(),
            **_compose_kwargs(),
        )
        assert replay.meta.idempotent_replay is True
        assert replay.solution.id == result.solution.id
        assert session.scalar(select(func.count()).select_from(CFSSolution)) == 1
        assert session.scalar(select(func.count()).select_from(CFSSolutionComponent)) == len(
            result.components
        )


def test_case_two_open_budget_combines_protection_retirement_and_investment() -> None:
    household_id = _seed("DEMO_C")
    with SessionLocal() as session:
        for asset in session.scalars(
            select(Asset).where(Asset.household_id == household_id)
        ).all():
            if asset.category == AssetCategory.DEMAND_DEPOSIT:
                asset.market_value = Decimal("15000000.00")
                asset.acquisition_cost = Decimal("15000000.00")
                asset.version += 1
        for liability in session.scalars(
            select(Liability).where(Liability.household_id == household_id)
        ).all():
            liability.outstanding_balance = Decimal("0.00")
            liability.monthly_payment = Decimal("0.00")
            liability.version += 1
        for policy in session.scalars(
            select(InsurancePolicy).where(InsurancePolicy.household_id == household_id)
        ).all():
            policy.coverage_amount = Decimal("0.00")
            policy.version += 1
        session.commit()

        result = compose_cfs_solution(
            session,
            household_id,
            CFSComposeRequest(is_user_confirmed=True),
            _actor(),
            **_compose_kwargs(),
        )
        component_types = {item.component_type for item in result.components}
        assert {
            CFSComponentType.PROTECTION,
            CFSComponentType.RETIREMENT,
            CFSComponentType.INVESTMENT,
        } <= component_types
        assert CFSComponentType.NO_ACTION not in component_types
        investment = next(
            item
            for item in result.components
            if item.component_type == CFSComponentType.INVESTMENT
        )
        assert investment.target_amount > 0
        assert investment.product_mapping_allowed is True
        assert result.risk_budget.decision == "open"
        assert result.risk_budget.additional_risk_allowed is True
        assert result.solution.summary["headline"] == "保障、退休与长期配置按风险预算并行"


def test_case_three_routes_enterprise_cross_border_and_succession_specialists() -> None:
    household_id = _seed("DEMO_B")
    actor = _actor()
    with SessionLocal() as session:
        financial_set = False
        property_set = False
        for asset in session.scalars(
            select(Asset).where(Asset.household_id == household_id)
        ).all():
            if asset.category == AssetCategory.PRIMARY_RESIDENCE and not property_set:
                asset.market_value = Decimal("5000000.00")
                property_set = True
            elif asset.category == AssetCategory.DEMAND_DEPOSIT and not financial_set:
                asset.market_value = Decimal("3000000.00")
                asset.currency = "USD"
                financial_set = True
            else:
                asset.market_value = Decimal("0.00")
            asset.version += 1
        session.commit()
        graph = build_financial_graph(session, household_id, actor)
        owner = next(
            item for item in graph.entities if item.entity_type == FinancialEntityType.PERSON
        )
        enterprise, _entity = create_enterprise(
            session,
            household_id,
            EnterpriseCreate(
                name="景行智造科技",
                industry="高端制造",
                stage="mature",
                jurisdiction="CN",
                currency="CNY",
                listed_status="unlisted",
                enterprise_type="operating_company",
                valuation_date=ANALYSIS_DATE,
                data_source="cfs-acceptance",
                is_user_confirmed=True,
            ),
            actor,
        )
        exposure = EnterpriseExposureCreate.model_validate(
            {
                "enterprise_id": enterprise.id,
                "ownerships": [
                    {
                        "owner_entity_id": owner.id,
                        "ownership_ratio": "1.000000",
                        "voting_ratio": "1.000000",
                        "instrument_type": "common_equity",
                    }
                ],
                "valuations": [
                    {
                        "valuation_date": ANALYSIS_DATE.isoformat(),
                        "equity_value": "17000000.00",
                        "valuation_method": "user_estimate",
                        "confidence": "medium",
                        "source_kind": "client_financial_statement",
                        "currency": "CNY",
                    }
                ],
                "source_reference": "cfs-enterprise-acceptance",
                "is_user_confirmed": True,
            }
        )
        process_enterprise_exposures(
            session,
            household_id,
            exposure,
            actor,
            financial_rules_path=FINANCIAL_RULES_PATH,
            methodology_rules_path=METHODOLOGY_RULES_PATH,
            public_data_snapshot_path=PUBLIC_DATA_PATH,
            client_profile_rules_path=CLIENT_PROFILE_RULES_PATH,
            liability_rules_path=LIABILITY_RULES_PATH,
            family_enterprise_rules_path=FAMILY_ENTERPRISE_RULES_PATH,
            analysis_date=ANALYSIS_DATE,
        )
        result = compose_cfs_solution(
            session,
            household_id,
            CFSComposeRequest(is_user_confirmed=True),
            actor,
            **_compose_kwargs(),
        )
        component_types = {item.component_type for item in result.components}
        assert {
            CFSComponentType.ENTERPRISE_RISK,
            CFSComponentType.CROSS_BORDER,
            CFSComponentType.SUCCESSION,
        } <= component_types
        specialist_types = {item.specialist_type.value for item in result.referrals}
        assert {
            "private_banker",
            "cross_border_specialist",
            "legal_tax_professional",
        } <= specialist_types
        specialized_referrals = [
            item
            for item in result.referrals
            if item.specialist_type.value
            in {"cross_border_specialist", "legal_tax_professional"}
        ]
        assert all(
            item.evidence["complexity_gate"] == "professional_review_required"
            and item.evidence["advisor_workflow"] == "professional_referral"
            for item in specialized_referrals
        )
        enterprise_component = next(
            item
            for item in result.components
            if item.component_type == CFSComponentType.ENTERPRISE_RISK
        )
        assert enterprise_component.target_amount == Decimal("17000000.00")
        assert result.risk_budget.additional_risk_allowed is False
        assert result.risk_budget.existing_economic_exposure >= Decimal("17000000.00")


async def _api_request(
    method: str,
    path: str,
    *,
    role: str = "admin",
    payload: Mapping[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
) -> Response:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.request(
            method,
            path,
            json=payload,
            headers={
                "X-Actor-ID": f"cfs-{role}",
                "X-Actor-Role": role,
                **(dict(headers) if headers else {}),
            },
        )


def _call(
    method: str,
    path: str,
    *,
    role: str = "admin",
    payload: Mapping[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
) -> Response:
    return asyncio.run(_api_request(method, path, role=role, payload=payload, headers=headers))


def test_cfs_api_is_flagged_role_scoped_confirmed_and_idempotent(monkeypatch: Any) -> None:
    household_id = _seed("DEMO_B")
    base = f"/api/v1/households/{household_id}"
    monkeypatch.setenv("ENABLE_V5_CFS", "false")
    get_settings.cache_clear()
    disabled = _call(
        "POST",
        f"{base}/cfs-solutions",
        payload={"is_user_confirmed": True},
    )
    assert disabled.status_code == 404

    for key, value in {
        "ENABLE_V5_CFS": "true",
        "FINANCIAL_RULES_PATH": FINANCIAL_RULES_PATH,
        "PLANNING_RULES_PATH": PLANNING_RULES_PATH,
        "METHODOLOGY_RULES_PATH": METHODOLOGY_RULES_PATH,
        "PUBLIC_DATA_SNAPSHOT_PATH": PUBLIC_DATA_PATH,
        "CLIENT_PROFILE_RULES_PATH": CLIENT_PROFILE_RULES_PATH,
        "LIABILITY_RULES_PATH": LIABILITY_RULES_PATH,
        "FAMILY_ENTERPRISE_RULES_PATH": FAMILY_ENTERPRISE_RULES_PATH,
        "CFS_RULES_PATH": CFS_RULES_PATH,
    }.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    payload = {"is_user_confirmed": True}
    path = f"{base}/cfs-solutions?analysis_date={ANALYSIS_DATE}"
    denied = _call("POST", path, role="compliance", payload=payload)
    assert denied.status_code == 403
    unconfirmed = _call("POST", path, payload=payload)
    assert unconfirmed.status_code == 409
    created = _call(
        "POST",
        path,
        role="client",
        payload=payload,
        headers={"X-Confirm-Action": "create_cfs_solution"},
    )
    assert created.status_code == 201, created.text
    solution_id = created.json()["solution"]["id"]
    assert created.json()["meta"]["idempotent_replay"] is False
    fetched = _call("GET", f"{base}/cfs-solutions/{solution_id}", role="advisor")
    assert fetched.status_code == 200
    recalculate_path = (
        f"{base}/cfs-solutions/{solution_id}/recalculate?analysis_date={ANALYSIS_DATE}"
    )
    assert _call("POST", recalculate_path, payload=payload).status_code == 409
    replay = _call(
        "POST",
        recalculate_path,
        payload=payload,
        headers={"X-Confirm-Action": "recalculate_cfs_solution"},
    )
    assert replay.status_code == 200
    assert replay.json()["meta"]["idempotent_replay"] is True
    assert replay.json()["solution"]["id"] == solution_id

    debt_component = next(
        item for item in created.json()["components"] if item["component_type"] == "debt"
    )
    referral_payload = {
        "solution_id": solution_id,
        "component_id": debt_component["id"],
        "specialist_type": "private_banker",
        "trigger_reason": "客户确认由私行顾问协调负债优先顺序。",
        "urgency": "high",
        "evidence": {"client_requested": True},
        "is_user_confirmed": True,
    }
    referral = _call(
        "POST",
        f"{base}/professional-referrals",
        role="advisor",
        payload=referral_payload,
        headers={"X-Confirm-Action": "create_professional_referral"},
    )
    assert referral.status_code == 201, referral.text
    assert referral.json()["specialist_type"] == "private_banker"
    with SessionLocal() as session:
        assert session.scalar(select(func.count()).select_from(CFSSolution)) == 1
        assert session.scalar(select(func.count()).select_from(ProfessionalServiceReferral)) >= 1
    get_settings.cache_clear()
