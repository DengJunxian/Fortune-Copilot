from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import func, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, engine
from app.domain.enums import EmploymentStability, LifecycleStage, RiskLevel
from app.models import Base
from app.models.assessment import BehaviorAssessment, RiskAssessment
from app.models.family import ConsentRecord, Household, HouseholdMember
from app.models.finance import (
    Asset,
    ExpenseItem,
    FinancialGoal,
    IncomeSource,
    InsurancePolicy,
    Liability,
    SocialSecurityAccount,
)
from app.models.governance import PlanReport
from app.services.seed import seed_synthetic_data


def test_all_required_entities_have_auditable_versioned_fields() -> None:
    domain_tables = set(Base.metadata.tables) - {"runtime_metadata"}
    assert len(domain_tables) == 45
    for table_name in domain_tables:
        columns = set(Base.metadata.tables[table_name].columns.keys())
        assert {
            "id",
            "currency",
            "valuation_date",
            "data_source",
            "is_user_confirmed",
            "version",
            "updated_at",
            "is_deleted",
        } <= columns
    member_columns = {column["name"] for column in inspect(engine).get_columns("household_members")}
    assert "health_risk_level" in member_columns
    assert "diagnosis" not in Base.metadata.tables["household_members"].columns
    report_constraints = {
        constraint.name for constraint in Base.metadata.tables["plan_reports"].constraints
    }
    assert "ck_plan_reports_chapter_count_eight" in report_constraints


def test_seed_loads_three_distinct_families_and_exact_main_demo_inputs() -> None:
    with SessionLocal() as session:
        result = seed_synthetic_data(
            session,
            "../data/synthetic/families.json",
            reset=True,
        )
        assert result.loaded == 3
        assert result.household_codes == ("DEMO_A", "DEMO_B", "DEMO_C")

        households = list(session.scalars(select(Household).order_by(Household.code)).all())
        assert {household.lifecycle_stage for household in households} == {
            LifecycleStage.EARLY_CAREER,
            LifecycleStage.PARENTING,
            LifecycleStage.RETIREMENT_PREPARATION,
        }
        complete_fact_models = (
            HouseholdMember,
            ConsentRecord,
            IncomeSource,
            ExpenseItem,
            Asset,
            InsurancePolicy,
            SocialSecurityAccount,
            FinancialGoal,
            RiskAssessment,
            BehaviorAssessment,
        )
        for household in households:
            for model in complete_fact_models:
                count = session.scalar(
                    select(func.count())
                    .select_from(model)
                    .where(model.household_id == household.id)
                )
                assert count is not None and count > 0, (household.code, model.__name__)

        main_demo = session.scalar(select(Household).where(Household.code == "DEMO_B"))
        assert main_demo is not None
        assert len(main_demo.members) == 3
        total_assets = session.scalar(
            select(func.sum(Asset.market_value)).where(Asset.household_id == main_demo.id)
        )
        total_liabilities = session.scalar(
            select(func.sum(Liability.outstanding_balance)).where(
                Liability.household_id == main_demo.id
            )
        )
        total_income = session.scalar(
            select(func.sum(IncomeSource.amount)).where(IncomeSource.household_id == main_demo.id)
        )
        total_expense = session.scalar(
            select(func.sum(ExpenseItem.amount)).where(ExpenseItem.household_id == main_demo.id)
        )
        assert total_assets == Decimal("2850000.00")
        assert total_liabilities == Decimal("1208000.00")
        assert total_income == Decimal("360000.00")
        assert total_expense == Decimal("288000.00")
        credit_card = session.scalar(
            select(Liability).where(
                Liability.household_id == main_demo.id,
                Liability.category == "credit_card_unpaid",
            )
        )
        assert credit_card is not None
        assert credit_card.outstanding_balance == Decimal("8000.00")
        assert all(asset.category.value != "credit_card_unpaid" for asset in _assets(session))

        second = seed_synthetic_data(session, "../data/synthetic/families.json")
        assert second.loaded == 0
        assert second.skipped == 3
        reset_result = seed_synthetic_data(
            session,
            "../data/synthetic/families.json",
            reset=True,
        )
        assert reset_result.reset_removed == 3
        assert reset_result.loaded == 3
        assert session.scalar(select(func.count()).select_from(Household)) == 3


def _assets(session: Session) -> list[Asset]:
    return list(session.scalars(select(Asset)).all())


def test_hard_delete_cascades_to_household_children() -> None:
    with SessionLocal() as session:
        household = Household(
            code="CASCADE_TEST",
            name="级联测试家庭",
            lifecycle_stage=LifecycleStage.FAMILY_FORMATION,
            region="北京市",
            is_synthetic=True,
        )
        session.add(household)
        session.flush()
        member = HouseholdMember(
            household_id=household.id,
            display_name="级联成员",
            relationship="本人",
            birth_date=date(1990, 1, 1),
            employment_stability=EmploymentStability.HIGH,
            health_risk_level=RiskLevel.LOW,
        )
        session.add(member)
        session.commit()
        member_id = member.id
        session.delete(household)
        session.commit()
        session.expunge_all()
        assert session.get(HouseholdMember, member_id) is None


def test_plan_report_database_rejects_non_eight_chapter_structure() -> None:
    with SessionLocal() as session:
        household = Household(
            code="REPORT_CONSTRAINT",
            name="规划书约束测试家庭",
            lifecycle_stage=LifecycleStage.FAMILY_FORMATION,
            region="北京市",
            is_synthetic=True,
        )
        session.add(household)
        session.flush()
        session.add(
            PlanReport(
                household_id=household.id,
                report_version="invalid-seven-chapters",
                chapter_count=7,
                structured_report={},
                generated_at=datetime.now(UTC),
                consistency_status="invalid",
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
