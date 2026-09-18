from __future__ import annotations

import argparse
import json
from pathlib import Path

SEGMENTS = [
    (
        "young_professional",
        "年轻职场人士",
        25,
        220000,
        0,
        180000,
        30000,
        7000,
        0,
        0.82,
        0.62,
        0.15,
        0.58,
        96,
    ),
    (
        "middle_class_family",
        "中产家庭",
        38,
        420000,
        220000,
        1800000,
        1800000,
        23000,
        1,
        0.86,
        0.66,
        0.18,
        0.68,
        144,
    ),
    (
        "high_net_worth",
        "高净值客户",
        46,
        1200000,
        500000,
        12000000,
        2500000,
        65000,
        2,
        0.78,
        0.70,
        0.22,
        0.80,
        180,
    ),
    (
        "business_owner",
        "企业主",
        43,
        900000,
        180000,
        8000000,
        4200000,
        48000,
        2,
        0.48,
        0.72,
        0.25,
        0.76,
        156,
    ),
    (
        "tech_founder",
        "科技创业者",
        34,
        650000,
        260000,
        6000000,
        1600000,
        35000,
        1,
        0.42,
        0.78,
        0.28,
        0.82,
        180,
    ),
    (
        "retiree",
        "退休人士",
        66,
        210000,
        100000,
        3500000,
        200000,
        15000,
        0,
        0.92,
        0.38,
        0.10,
        0.52,
        60,
    ),
]


def build_profiles() -> list[dict[str, object]]:
    profiles: list[dict[str, object]] = []
    for segment_index, segment in enumerate(SEGMENTS):
        (
            code,
            label,
            age,
            income,
            spouse_income,
            financial_assets,
            liabilities,
            monthly_expense,
            dependents,
            stability,
            tolerance,
            max_loss,
            knowledge,
            horizon_months,
        ) = segment
        for case_index in range(10):
            scale = 0.82 + case_index * 0.04
            annual_income = round((income + spouse_income) * scale, 2)
            assets = round(financial_assets * (0.75 + case_index * 0.055), 2)
            debt = round(liabilities * max(0.25, 1.05 - case_index * 0.07), 2)
            expenses = round(monthly_expense * (0.88 + case_index * 0.03), 2)
            target = round(max(300000, annual_income * (2.0 + case_index * 0.12)), 2)
            current = round(target * (0.12 + case_index * 0.035), 2)
            profiles.append(
                {
                    "profile_id": f"BENCH-{segment_index + 1:02d}-{case_index + 1:02d}",
                    "segment": code,
                    "segment_label": label,
                    "age": age + (case_index % 5) - 2,
                    "annual_income": annual_income,
                    "financial_assets": assets,
                    "liabilities": debt,
                    "essential_monthly_expense": expenses,
                    "dependents": max(0, dependents + (1 if case_index in {7, 8} else 0)),
                    "income_stability": round(
                        max(0.20, min(0.98, stability - case_index * 0.012)), 4
                    ),
                    "risk_tolerance": round(
                        max(0.15, min(0.95, tolerance + (case_index - 4) * 0.018)), 4
                    ),
                    "maximum_acceptable_loss": round(
                        max(0.05, min(0.35, max_loss + (case_index - 4) * 0.008)), 4
                    ),
                    "knowledge_score": round(
                        max(0.10, min(0.95, knowledge + (case_index - 4) * 0.015)), 4
                    ),
                    "goal": {
                        "target_amount": target,
                        "current_assets": current,
                        "horizon_months": max(12, horizon_months + (case_index - 4) * 6),
                        "expected_return": round(0.035 + segment_index * 0.004, 4),
                        "inflation_rate": 0.03 if code != "middle_class_family" else 0.05,
                    },
                    "behavior_signals": [
                        "recent_return_anchor" if case_index % 2 == 0 else "excessive_trading",
                        "chase_top_performer" if case_index in {2, 5, 8} else "hold_loser",
                    ],
                    "expected_escalation": code
                    in {"high_net_worth", "business_owner", "tech_founder"},
                    "required_knowledge_categories": [
                        "product_suitability",
                        "consumer_protection",
                        "personal_pension"
                        if code in {"young_professional", "retiree"}
                        else "insurance_disclosure",
                    ],
                }
            )
    return profiles


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/benchmarks/competition_personas_v1.json"),
    )
    args = parser.parse_args()
    payload = {
        "schema_version": "fortune-copilot-competition-benchmark-v1",
        "dataset_version": "synthetic-competition-personas-v1.0.0",
        "as_of_date": "2026-09-01",
        "synthetic": True,
        "real_customer_data": False,
        "generator": "scripts/generate_competition_benchmark.py",
        "profiles": build_profiles(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {"output": str(args.output), "profile_count": len(payload["profiles"])},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
