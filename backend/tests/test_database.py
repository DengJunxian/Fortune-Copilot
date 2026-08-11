from sqlalchemy import inspect

from app.core.database import build_engine, check_database
from app.domain.enums import PlanWorkflowState
from app.models.base import Base
from app.models.governance import PlanWorkflowVersion


def test_database_engine_supports_sqlite_without_external_service() -> None:
    target = build_engine("sqlite://")
    Base.metadata.create_all(target)
    status, _ = check_database(target)
    assert status == "ok"
    table_names = inspect(target).get_table_names()
    assert "households" in table_names
    assert "audit_events" in table_names
    assert len(table_names) == 80
    assert {
        "identity_access_grants",
        "privacy_requests",
        "quality_gate_runs",
        "evaluation_runs",
    } <= set(table_names)
    assert {
        "cfs_solutions",
        "cfs_solution_components",
        "professional_service_referrals",
    } <= set(table_names)
    assert {
        "financial_entities",
        "financial_accounts",
        "positions",
        "ownership_edges",
    } <= set(table_names)
    assert {
        "client_wealth_profiles",
        "client_profile_tags",
        "wealth_needs",
        "wealth_need_priorities",
    } <= set(table_names)
    assert {"household_snapshots", "financial_events", "life_events"} <= set(table_names)
    assert {
        "monitoring_policies",
        "monitoring_alerts",
        "advisor_triggers",
        "behavior_observations",
    } <= set(table_names)
    assert {
        "enterprise_profiles",
        "enterprise_ownerships",
        "enterprise_valuations",
        "enterprise_cashflows",
        "enterprise_guarantees",
        "enterprise_liquidity_events",
    } <= set(table_names)
    assert "enterprise_id" in {
        column["name"] for column in inspect(target).get_columns("positions")
    }


def test_workflow_state_uses_the_lowercase_values_enforced_by_the_migration() -> None:
    target = build_engine("sqlite://")
    state_type = PlanWorkflowVersion.__table__.c.state.type
    processor = state_type.bind_processor(target.dialect)

    assert processor is not None
    assert processor(PlanWorkflowState.DRAFT) == "draft"
    assert processor(PlanWorkflowState.COMPLIANCE_REVIEWED) == "compliance_reviewed"
