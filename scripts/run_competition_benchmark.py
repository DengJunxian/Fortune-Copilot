from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.services.competition.benchmark import run_competition_benchmark  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        type=Path,
        default=PROJECT_ROOT / "data/benchmarks/competition_personas_v1.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "output/competition_benchmark_results.json",
    )
    args = parser.parse_args()
    result = run_competition_benchmark(args.dataset)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "profile_count": result["profile_count"],
                "measured_systems": [
                    item["system_code"] for item in result["systems"] if item["measured"]
                ],
                "general_llm_measured": False,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
