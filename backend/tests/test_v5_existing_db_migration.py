from __future__ import annotations

import os
import subprocess
import sys
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from app.core.auth import ActorContext
from app.core.database import build_engine
from app.models.client_profile import ClientWealthProfile, WealthNeed
from app.models.family import Household
from app.services.financial.facts import load_household_facts
from app.services.financial_graph.projection import compare_legacy_projection
from app.services.financial_graph.repository import load_financial_graph
from app.services.seed import seed_synthetic_data
from app.services.wealth_needs.engine import recalculate_wealth_needs

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _actor() -> ActorContext:
    now = datetime.now(UTC)
    return ActorContext(
        actor_id="migration-e02",
        role="admin",
        household_ids=("*",),
        issued_at=now,
        expires_at=now + timedelta(hours=1),
        auth_source="demo_headers",
    )


def _alembic(database_url: str, *arguments: str) -> None:
    environment = {**os.environ, "APP_ENV": "test", "DATABASE_URL": database_url}
    subprocess.run(
        [sys.executable, "-m", "alembic", *arguments],
        cwd=BACKEND_ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )


def test_existing_0015_database_upgrades_backfills_and_downgrades(tmp_path: Path) -> None:
    database = tmp_path / "v4-fixture.sqlite"
    database_url = f"sqlite:///{database}"
    _alembic(database_url, "upgrade", "0015_fortune_copilot_v4")

    target = build_engine(database_url)
    with Session(target) as session:
        seed_synthetic_data(
            session,
            "../data/synthetic/families.json",
            rules_path="../data/rules/financial_health_v1.json",
            planning_rules_path="../data/rules/planning_waterfall_v1.json",
            methodology_rules_path="../data/rules/wealth_methodology_v3.json",
            portfolio_rules_path="../data/rules/portfolio_policy_v1.json",
            twin_rules_path="../data/rules/twin_simulation_v1.json",
            behavior_rules_path="../data/rules/behavior_finance_v1.json",
            knowledge_base_path="../data/knowledge/controlled_knowledge_v1.json",
        )
        household_ids = {item.code: item.id for item in session.scalars(select(Household)).all()}
        legacy_totals = {
            code: sum(
                (item.market_value for item in load_household_facts(session, household_id).assets),
                Decimal("0.00"),
            )
            for code, household_id in household_ids.items()
        }
    target.dispose()
    _alembic(database_url, "upgrade", "head")
    target = build_engine(database_url)
    assert {
        "financial_entities",
        "financial_accounts",
        "positions",
        "ownership_edges",
        "client_wealth_profiles",
        "client_profile_tags",
        "wealth_needs",
        "wealth_need_priorities",
    } <= set(inspect(target).get_table_names())
    with Session(target) as session:
        for code, household_id in household_ids.items():
            graph = load_financial_graph(session, household_id)
            assert graph.positions
            assert (
                sum((item.market_value for item in graph.positions), Decimal("0.00"))
                == (legacy_totals[code])
            )
            diagnostic = compare_legacy_projection(session, household_id, graph)
            assert diagnostic.status == "matched", diagnostic.details
            assert diagnostic.difference <= Decimal("0.01")
        result = recalculate_wealth_needs(
            session,
            household_ids["DEMO_B"],
            _actor(),
            "../data/rules/client_profile_v1.json",
            date(2026, 8, 10),
        )
        assert result.needs
        assert session.scalar(select(ClientWealthProfile.id)) is not None
        assert session.scalar(select(WealthNeed.id)) is not None
    target.dispose()

    _alembic(database_url, "downgrade", "0016_v5_financial_graph_core")
    target = build_engine(database_url)
    tables_after_e02_downgrade = set(inspect(target).get_table_names())
    assert "client_wealth_profiles" not in tables_after_e02_downgrade
    assert "wealth_needs" not in tables_after_e02_downgrade
    assert "positions" in tables_after_e02_downgrade
    with Session(target) as session:
        position_count = session.scalar(
            text("SELECT COUNT(*) FROM positions WHERE household_id = :household_id"),
            {"household_id": household_ids["DEMO_B"]},
        )
        assert position_count is not None and position_count > 0
    target.dispose()

    _alembic(database_url, "downgrade", "0015_fortune_copilot_v4")
    target = build_engine(database_url)
    assert "positions" not in inspect(target).get_table_names()
    with Session(target) as session:
        assert load_household_facts(session, household_ids["DEMO_B"]).assets
    target.dispose()


def test_0018_liability_migration_round_trip_preserves_legacy_contracts(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'e03-round-trip.sqlite'}"
    _alembic(database_url, "upgrade", "0017_v5_client_profile_and_needs")
    target = build_engine(database_url)
    tables_at_0017 = set(inspect(target).get_table_names())
    assert "financial_goals" in tables_at_0017
    assert "responsibilities" in tables_at_0017
    assert "wealth_needs" in tables_at_0017
    assert "liability_streams" not in tables_at_0017
    target.dispose()

    _alembic(database_url, "upgrade", "0018_v5_liability_streams_eltc")
    target = build_engine(database_url)
    tables_at_0018 = set(inspect(target).get_table_names())
    assert {"liability_streams", "liability_stream_cashflows"} <= tables_at_0018
    assert tables_at_0017 <= tables_at_0018
    target.dispose()

    _alembic(database_url, "downgrade", "0017_v5_client_profile_and_needs")
    target = build_engine(database_url)
    tables_after_downgrade = set(inspect(target).get_table_names())
    assert "liability_streams" not in tables_after_downgrade
    assert "liability_stream_cashflows" not in tables_after_downgrade
    assert "financial_goals" in tables_after_downgrade
    assert "responsibilities" in tables_after_downgrade
    assert "wealth_needs" in tables_after_downgrade
    target.dispose()


def test_0019_persistent_twin_round_trip_preserves_e03_and_simulation_contracts(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'e04-round-trip.sqlite'}"
    _alembic(database_url, "upgrade", "0018_v5_liability_streams_eltc")
    target = build_engine(database_url)
    tables_at_0018 = set(inspect(target).get_table_names())
    simulation_columns_at_0018 = {
        item["name"] for item in inspect(target).get_columns("simulation_runs")
    }
    assert "household_snapshots" not in tables_at_0018
    assert "household_snapshot_id" not in simulation_columns_at_0018
    target.dispose()

    _alembic(database_url, "upgrade", "0019_v5_persistent_financial_twin")
    target = build_engine(database_url)
    tables_at_0019 = set(inspect(target).get_table_names())
    simulation_columns_at_0019 = {
        item["name"] for item in inspect(target).get_columns("simulation_runs")
    }
    assert {"household_snapshots", "financial_events", "life_events"} <= tables_at_0019
    assert "household_snapshot_id" in simulation_columns_at_0019
    assert tables_at_0018 <= tables_at_0019
    target.dispose()

    _alembic(database_url, "downgrade", "0018_v5_liability_streams_eltc")
    target = build_engine(database_url)
    tables_after_downgrade = set(inspect(target).get_table_names())
    simulation_columns_after_downgrade = {
        item["name"] for item in inspect(target).get_columns("simulation_runs")
    }
    assert "household_snapshots" not in tables_after_downgrade
    assert "financial_events" not in tables_after_downgrade
    assert "life_events" not in tables_after_downgrade
    assert "household_snapshot_id" not in simulation_columns_after_downgrade
    assert "liability_streams" in tables_after_downgrade
    assert "snapshot_id" in simulation_columns_after_downgrade
    target.dispose()


def test_0020_family_enterprise_round_trip_preserves_twin_and_graph_contracts(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'e05-round-trip.sqlite'}"
    _alembic(database_url, "upgrade", "0019_v5_persistent_financial_twin")
    target = build_engine(database_url)
    tables_at_0019 = set(inspect(target).get_table_names())
    positions_at_0019 = {item["name"] for item in inspect(target).get_columns("positions")}
    assert "enterprise_profiles" not in tables_at_0019
    assert "enterprise_id" not in positions_at_0019
    assert "household_snapshots" in tables_at_0019
    target.dispose()

    _alembic(database_url, "upgrade", "0020_v5_family_enterprise")
    target = build_engine(database_url)
    tables_at_0020 = set(inspect(target).get_table_names())
    positions_at_0020 = {item["name"] for item in inspect(target).get_columns("positions")}
    assert {
        "enterprise_profiles",
        "enterprise_ownerships",
        "enterprise_valuations",
        "enterprise_cashflows",
        "enterprise_guarantees",
        "enterprise_liquidity_events",
    } <= tables_at_0020
    assert "enterprise_id" in positions_at_0020
    assert tables_at_0019 <= tables_at_0020
    target.dispose()

    _alembic(database_url, "downgrade", "0019_v5_persistent_financial_twin")
    target = build_engine(database_url)
    tables_after_downgrade = set(inspect(target).get_table_names())
    positions_after_downgrade = {item["name"] for item in inspect(target).get_columns("positions")}
    assert "enterprise_profiles" not in tables_after_downgrade
    assert "enterprise_liquidity_events" not in tables_after_downgrade
    assert "enterprise_id" not in positions_after_downgrade
    assert "household_snapshots" in tables_after_downgrade
    assert "financial_events" in tables_after_downgrade
    target.dispose()


def test_0021_cfs_round_trip_preserves_family_enterprise_contracts(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'e06-round-trip.sqlite'}"
    _alembic(database_url, "upgrade", "0020_v5_family_enterprise")
    target = build_engine(database_url)
    tables_at_0020 = set(inspect(target).get_table_names())
    assert "enterprise_profiles" in tables_at_0020
    assert "cfs_solutions" not in tables_at_0020
    target.dispose()

    _alembic(database_url, "upgrade", "0021_v5_cfs_orchestration")
    target = build_engine(database_url)
    tables_at_0021 = set(inspect(target).get_table_names())
    assert {
        "cfs_solutions",
        "cfs_solution_components",
        "professional_service_referrals",
    } <= tables_at_0021
    assert tables_at_0020 <= tables_at_0021
    target.dispose()

    _alembic(database_url, "downgrade", "0020_v5_family_enterprise")
    target = build_engine(database_url)
    tables_after_downgrade = set(inspect(target).get_table_names())
    assert "cfs_solutions" not in tables_after_downgrade
    assert "cfs_solution_components" not in tables_after_downgrade
    assert "professional_service_referrals" not in tables_after_downgrade
    assert "enterprise_profiles" in tables_after_downgrade
    assert "enterprise_ownerships" in tables_after_downgrade
    target.dispose()


def test_0022_product_ontology_extends_products_and_preserves_cfs_contracts(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'e07-round-trip.sqlite'}"
    _alembic(database_url, "upgrade", "0021_v5_cfs_orchestration")
    target = build_engine(database_url)
    product_columns_at_0021 = {item["name"] for item in inspect(target).get_columns("products")}
    assert "product_snapshots" not in inspect(target).get_table_names()
    assert "product_family" not in product_columns_at_0021
    with Session(target) as session:
        session.execute(
            text(
                "INSERT INTO products ("
                "code, name, product_type, risk_level, liquidity_level, minimum_investment, "
                "principal_guaranteed, is_simulated, terms, id, currency, data_source, "
                "is_user_confirmed, version, created_at, updated_at, is_deleted"
                ") VALUES ("
                "'LEGACY-E07', 'Legacy product', 'cash_management', 'R1', 'IMMEDIATE', 0, "
                "0, 1, '{}', 'legacy-e07-product', 'CNY', 'migration-test', 1, 1, "
                "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 0"
                ")"
            )
        )
        session.commit()
    target.dispose()
    _alembic(database_url, "upgrade", "0022_v5_product_ontology")
    target = build_engine(database_url)
    tables_at_0022 = set(inspect(target).get_table_names())
    product_columns_at_0022 = {item["name"] for item in inspect(target).get_columns("products")}
    assert "product_snapshots" in tables_at_0022
    assert {
        "issuer",
        "jurisdiction",
        "product_family",
        "product_subtype",
        "all_in_cost",
        "distribution_incentive_disclosure",
        "conflict_of_interest_flag",
        "professional_review_required",
        "client_role_in_cfs",
        "classification_version",
        "evidence_json",
    } <= product_columns_at_0022
    assert "cfs_solutions" in tables_at_0022
    with Session(target) as session:
        legacy = session.execute(
            text(
                "SELECT code, issuer, jurisdiction, product_family, classification_version "
                "FROM products WHERE id = 'legacy-e07-product'"
            )
        ).one()
        assert legacy.code == "LEGACY-E07"
        assert legacy.issuer == "unknown"
        assert legacy.jurisdiction == "CN"
        assert legacy.product_family == "CASH_MANAGEMENT"
        assert legacy.classification_version == "legacy-v1"
    target.dispose()

    _alembic(database_url, "downgrade", "0021_v5_cfs_orchestration")
    target = build_engine(database_url)
    tables_after_downgrade = set(inspect(target).get_table_names())
    product_columns_after_downgrade = {
        item["name"] for item in inspect(target).get_columns("products")
    }
    assert "product_snapshots" not in tables_after_downgrade
    assert "product_family" not in product_columns_after_downgrade
    assert "cfs_solutions" in tables_after_downgrade
    target.dispose()


def test_0023_decision_evidence_adds_searchable_bindings_and_round_trips(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'e08-round-trip.sqlite'}"
    _alembic(database_url, "upgrade", "0022_v5_product_ontology")
    target = build_engine(database_url)
    recommendation_columns = {
        item["name"] for item in inspect(target).get_columns("recommendations")
    }
    report_columns = {item["name"] for item in inspect(target).get_columns("plan_reports")}
    assert "client_profile_version" not in recommendation_columns
    assert "decision_evidence" not in report_columns
    target.dispose()

    _alembic(database_url, "upgrade", "0023_v5_decision_evidence_v2")
    target = build_engine(database_url)
    recommendation_columns = {
        item["name"] for item in inspect(target).get_columns("recommendations")
    }
    report_columns = {item["name"] for item in inspect(target).get_columns("plan_reports")}
    searchable = {
        "client_profile_version",
        "wealth_need_set_hash",
        "liability_version",
        "twin_snapshot_version",
        "enterprise_snapshot_version",
        "cfs_solution_id",
        "calibration_version",
        "monitoring_trigger_id",
    }
    assert searchable <= recommendation_columns
    assert searchable | {"decision_evidence"} <= report_columns
    target.dispose()

    _alembic(database_url, "downgrade", "0022_v5_product_ontology")
    target = build_engine(database_url)
    recommendation_columns = {
        item["name"] for item in inspect(target).get_columns("recommendations")
    }
    report_columns = {item["name"] for item in inspect(target).get_columns("plan_reports")}
    assert not searchable & recommendation_columns
    assert "decision_evidence" not in report_columns
    assert "product_snapshots" in inspect(target).get_table_names()
    target.dispose()


def test_0024_and_0025_specialized_cfs_tables_round_trip_without_touching_e08(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'e09-round-trip.sqlite'}"
    _alembic(database_url, "upgrade", "0023_v5_decision_evidence_v2")
    target = build_engine(database_url)
    tables_at_0023 = set(inspect(target).get_table_names())
    assert "product_snapshots" in tables_at_0023
    assert "institutional_entitlements" not in tables_at_0023
    assert "trust_succession_needs" not in tables_at_0023
    target.dispose()
    _alembic(database_url, "upgrade", "0024_v5_retirement_cross_border")
    target = build_engine(database_url)
    tables_at_0024 = set(inspect(target).get_table_names())
    assert {"institutional_entitlements", "currency_exposures"} <= tables_at_0024
    assert "trust_succession_needs" not in tables_at_0024
    assert tables_at_0023 <= tables_at_0024
    target.dispose()

    _alembic(database_url, "upgrade", "0025_v5_trust_philanthropy")
    target = build_engine(database_url)
    tables_at_0025 = set(inspect(target).get_table_names())
    assert {"trust_succession_needs", "philanthropy_goals"} <= tables_at_0025
    assert tables_at_0024 <= tables_at_0025
    target.dispose()

    _alembic(database_url, "downgrade", "0024_v5_retirement_cross_border")
    target = build_engine(database_url)
    tables_after_0025_downgrade = set(inspect(target).get_table_names())
    assert "trust_succession_needs" not in tables_after_0025_downgrade
    assert "philanthropy_goals" not in tables_after_0025_downgrade
    assert "institutional_entitlements" in tables_after_0025_downgrade
    assert "currency_exposures" in tables_after_0025_downgrade
    target.dispose()

    _alembic(database_url, "downgrade", "0023_v5_decision_evidence_v2")
    target = build_engine(database_url)
    tables_after_e09_downgrade = set(inspect(target).get_table_names())
    assert "institutional_entitlements" not in tables_after_e09_downgrade
    assert "currency_exposures" not in tables_after_e09_downgrade
    assert "product_snapshots" in tables_after_e09_downgrade
    assert "decision_evidence" in {
        item["name"] for item in inspect(target).get_columns("plan_reports")
    }
    target.dispose()


def test_0026_monitoring_tables_and_action_bindings_round_trip(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'e10-round-trip.sqlite'}"
    _alembic(database_url, "upgrade", "0025_v5_trust_philanthropy")
    target = build_engine(database_url)
    tables_at_0025 = set(inspect(target).get_table_names())
    action_columns_at_0025 = {item["name"] for item in inspect(target).get_columns("action_items")}
    assert "monitoring_policies" not in tables_at_0025
    assert "advisor_trigger_id" not in action_columns_at_0025
    target.dispose()

    _alembic(database_url, "upgrade", "0026_v5_monitoring_and_triggers")
    target = build_engine(database_url)
    tables_at_0026 = set(inspect(target).get_table_names())
    action_columns_at_0026 = {item["name"] for item in inspect(target).get_columns("action_items")}
    assert {
        "monitoring_policies",
        "monitoring_alerts",
        "advisor_triggers",
        "behavior_observations",
    } <= tables_at_0026
    assert {
        "advisor_trigger_id",
        "action_type",
        "do_not_sell_flag",
        "required_specialist",
    } <= action_columns_at_0026
    assert tables_at_0025 <= tables_at_0026
    target.dispose()

    _alembic(database_url, "downgrade", "0025_v5_trust_philanthropy")
    target = build_engine(database_url)
    tables_after_downgrade = set(inspect(target).get_table_names())
    action_columns_after_downgrade = {
        item["name"] for item in inspect(target).get_columns("action_items")
    }
    assert (
        not {
            "monitoring_policies",
            "monitoring_alerts",
            "advisor_triggers",
            "behavior_observations",
        }
        & tables_after_downgrade
    )
    assert "advisor_trigger_id" not in action_columns_after_downgrade
    assert "trust_succession_needs" in tables_after_downgrade
    target.dispose()


def test_0027_calibration_registry_round_trip_preserves_e12_tables(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'e13-round-trip.sqlite'}"
    _alembic(database_url, "upgrade", "0026_v5_monitoring_and_triggers")
    target = build_engine(database_url)
    tables_at_0026 = set(inspect(target).get_table_names())
    assert "agent_orchestration_runs" in tables_at_0026
    assert "calibration_datasets" not in tables_at_0026
    target.dispose()

    _alembic(database_url, "upgrade", "0027_v5_calibration_registry")
    target = build_engine(database_url)
    inspector = inspect(target)
    tables_at_0027 = set(inspector.get_table_names())
    assert {"calibration_datasets", "calibration_parameters"} <= tables_at_0027
    assert tables_at_0026 <= tables_at_0027
    assert {
        "code",
        "mode",
        "source",
        "population",
        "sample_period",
        "effective_date",
        "source_version",
        "license_or_access_note",
        "limitations",
    } <= {item["name"] for item in inspector.get_columns("calibration_datasets")}
    assert {
        "dataset_id",
        "parameter_code",
        "value",
        "lower_bound",
        "upper_bound",
        "estimation_method",
        "segment",
        "region",
        "effective_from",
        "effective_to",
        "parameter_version",
        "confidence",
    } <= {item["name"] for item in inspector.get_columns("calibration_parameters")}
    target.dispose()

    _alembic(database_url, "downgrade", "0026_v5_monitoring_and_triggers")
    target = build_engine(database_url)
    tables_after_downgrade = set(inspect(target).get_table_names())
    assert not {"calibration_datasets", "calibration_parameters"} & tables_after_downgrade
    assert tables_after_downgrade == tables_at_0026
    target.dispose()
