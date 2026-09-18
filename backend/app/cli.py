from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.services.calibration.registry import (
    ensure_calibration_registry,
    load_calibration_registry,
)
from app.services.demo_backup import backup_demo_database, restore_demo_database
from app.services.public_data.rules import build_public_data_response
from app.services.seed import seed_synthetic_data


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fortune Copilot maintenance commands")
    subparsers = parser.add_subparsers(dest="command", required=True)
    seed_parser = subparsers.add_parser("seed", help="load the configured synthetic personas")
    seed_parser.add_argument("--reset", action="store_true", help="replace synthetic households")
    seed_parser.add_argument(
        "--if-empty",
        action="store_true",
        help="load only when the database has no active household",
    )
    seed_parser.add_argument("--path", help="override the synthetic dataset path")
    backup_parser = subparsers.add_parser(
        "backup-demo", help="create a verified SQLite backup containing synthetic demo data only"
    )
    backup_parser.add_argument("--output", type=Path, required=True)
    backup_parser.add_argument("--overwrite", action="store_true")
    restore_parser = subparsers.add_parser(
        "restore-demo", help="restore a verified synthetic-only SQLite demo backup"
    )
    restore_parser.add_argument("--input", type=Path, required=True)
    restore_parser.add_argument("--confirm", required=True)
    public_data_parser = subparsers.add_parser(
        "validate-public-data",
        help="validate governed public sources and print the immutable snapshot hash",
    )
    public_data_parser.add_argument("--path", help="override the public-data snapshot path")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    settings = get_settings()
    if args.command == "backup-demo":
        print(
            json.dumps(
                asdict(backup_demo_database(settings, args.output, overwrite=args.overwrite)),
                ensure_ascii=False,
            )
        )
        return
    if args.command == "restore-demo":
        print(
            json.dumps(
                asdict(restore_demo_database(settings, args.input, confirmation=args.confirm)),
                ensure_ascii=False,
            )
        )
        return
    if args.command == "validate-public-data":
        response = build_public_data_response(args.path or settings.public_data_snapshot_path)
        print(
            json.dumps(
                {
                    "snapshot_version": response.snapshot.snapshot_version,
                    "publication_cutoff": response.snapshot.publication_cutoff.isoformat(),
                    "integrity_hash": response.integrity_hash,
                    "source_count": (
                        2
                        + len(response.snapshot.regional_living_cost_observations)
                        + len(response.snapshot.policy_sources)
                        + len(response.snapshot.integration_access_boundaries)
                        + sum(
                            1 + len(series.values)
                            for series in response.snapshot.regional_minimum_wages.values()
                        )
                    ),
                    "is_live": False,
                },
                ensure_ascii=False,
            )
        )
        return
    if args.command != "seed":
        raise SystemExit(2)
    with SessionLocal() as session:
        result = seed_synthetic_data(
            session,
            args.path or settings.synthetic_data_path,
            rules_path=settings.financial_rules_path,
            planning_rules_path=settings.planning_rules_path,
            methodology_rules_path=settings.methodology_rules_path,
            portfolio_rules_path=settings.portfolio_rules_path,
            product_catalog_path=settings.product_catalog_path,
            twin_rules_path=settings.twin_rules_path,
            behavior_rules_path=settings.behavior_rules_path,
            knowledge_base_path=settings.knowledge_base_path,
            reset=args.reset,
            if_empty=args.if_empty,
        )
        if settings.enable_v5_calibration:
            ensure_calibration_registry(
                session,
                load_calibration_registry(settings.calibration_registry_path),
            )
            session.commit()
    print(
        json.dumps(
            {
                "dataset_version": result.dataset_version,
                "loaded": result.loaded,
                "skipped": result.skipped,
                "reset_removed": result.reset_removed,
                "household_codes": result.household_codes,
                "product_count": result.product_count,
                "scenario_count": result.scenario_count,
                "behavior_rule_version": result.behavior_rule_version,
                "behavior_inputs_refreshed": result.behavior_inputs_refreshed,
                "knowledge_document_count": result.knowledge_document_count,
                "knowledge_chunk_count": result.knowledge_chunk_count,
                "knowledge_quarantined_chunk_count": (result.knowledge_quarantined_chunk_count),
                "knowledge_documents_changed": result.knowledge_documents_changed,
                "knowledge_chunks_changed": result.knowledge_chunks_changed,
                "enterprise_profiles_loaded": result.enterprise_profiles_loaded,
                "enterprise_exposures_refreshed": result.enterprise_exposures_refreshed,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
