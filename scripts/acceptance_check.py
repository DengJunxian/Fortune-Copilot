#!/usr/bin/env python3
"""Black-box acceptance gate for the offline Fortune Copilot release Demo."""

from __future__ import annotations

import argparse
import ipaddress
import json
import sys
from dataclasses import dataclass, field
from time import monotonic
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen


def local_base_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise argparse.ArgumentTypeError("必须提供有效的 HTTP(S) 地址")
    host = parsed.hostname.casefold()
    if host != "localhost":
        try:
            if not ipaddress.ip_address(host).is_loopback:
                raise argparse.ArgumentTypeError("验收脚本只允许访问本机回环地址")
        except ValueError as exc:
            raise argparse.ArgumentTypeError("验收脚本只允许访问 localhost 或回环 IP") from exc
    return value.rstrip("/") + "/"


@dataclass
class AcceptanceLedger:
    started: float = field(default_factory=monotonic)
    checks: list[dict[str, Any]] = field(default_factory=list)

    def check(self, code: str, condition: bool, evidence: Any) -> None:
        self.checks.append({"code": code, "passed": condition, "evidence": evidence})
        if not condition:
            raise AssertionError(f"{code}: {evidence}")

    def output(self) -> dict[str, Any]:
        return {
            "status": "passed",
            "checks_passed": len(self.checks),
            "runtime_ms": int((monotonic() - self.started) * 1000),
            "external_network_calls": 0,
            "checks": self.checks,
        }


def request(
    base_url: str,
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    role: str = "admin",
    confirm: str | None = None,
    timeout: int = 300,
    accept: str = "application/json",
) -> tuple[int, bytes, str]:
    headers = {
        "Accept": accept,
        "X-Actor-ID": f"acceptance-{role}",
        "X-Actor-Role": role,
    }
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if confirm:
        headers["X-Confirm-Action"] = confirm
    target = urljoin(base_url, path.lstrip("/"))
    request_value = Request(
        target,
        data=json.dumps(payload).encode("utf-8") if payload is not None else None,
        method=method,
        headers=headers,
    )
    try:
        with urlopen(request_value, timeout=timeout) as response:
            return response.status, response.read(), response.headers.get_content_type()
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise AssertionError(f"{method} {path} -> HTTP {exc.code}: {detail[:500]}") from exc
    except (URLError, TimeoutError) as exc:
        raise AssertionError(f"{method} {path} 无法访问：{exc}") from exc


def json_request(base_url: str, path: str, **kwargs: Any) -> Any:
    status, body, content_type = request(base_url, path, **kwargs)
    if not 200 <= status < 300 or content_type != "application/json":
        raise AssertionError(f"{path}: status={status}, content_type={content_type}")
    return json.loads(body.decode("utf-8"))


def run_acceptance(api_url: str, web_url: str, *, reset_demo: bool) -> dict[str, Any]:
    ledger = AcceptanceLedger()

    health = json_request(api_url, "/api/v1/health")
    ledger.check(
        "service_health",
        health.get("status") == "ok" and health.get("database", {}).get("status") == "ok",
        health,
    )
    ledger.check("mock_default", health.get("mock_mode") is True, health.get("mock_mode"))

    if reset_demo:
        reset = json_request(
            api_url,
            "/api/v1/demo/reset",
            method="POST",
            payload={},
            confirm="reset_synthetic_demo",
        )
        ledger.check("synthetic_reset", reset.get("loaded") == 8, reset)
    loaded = json_request(api_url, "/api/v1/demo/load", method="POST", payload={})
    ledger.check(
        "seed_data",
        loaded.get("action") == "load"
        and loaded.get("loaded", 0) + loaded.get("skipped", 0) == 8
        and (
            loaded.get("loaded") == 0
            or set(loaded.get("household_codes", []))
            == {f"DEMO_{letter}" for letter in "ABCDEFGH"}
        ),
        loaded,
    )

    preheat = json_request(api_url, "/api/v1/demo/preheat", method="POST", payload={})
    ledger.check(
        "offline_preheat",
        preheat.get("status") == "ready" and preheat.get("external_network_calls") == 0,
        preheat,
    )
    manifest = json_request(api_url, "/api/v1/demo/manifest")
    ledger.check(
        "release_manifest",
        manifest.get("ready") is True
        and manifest.get("seeded_household_count") == 8
        and manifest.get("external_network_required") is False
        and all(manifest.get("release_assets", {}).values()),
        manifest,
    )

    v5_release = json_request(
        api_url,
        "/api/v1/demo/v5/release-benchmark",
        method="POST",
        payload={},
        confirm="run_v5_release_benchmark",
        timeout=300,
    )
    ledger.check(
        "v5_heterogeneous_persona_release",
        v5_release.get("passed") is True
        and len(v5_release.get("personas", [])) == 8
        and len(v5_release.get("metrics", [])) == 9
        and all(item.get("passed") for item in v5_release.get("metrics", [])),
        {
            "benchmark_version": v5_release.get("benchmark_version"),
            "persona_count": len(v5_release.get("personas", [])),
            "metrics": {
                item.get("code"): item.get("value")
                for item in v5_release.get("metrics", [])
            },
        },
    )

    founder_story = json_request(
        api_url,
        "/api/v1/demo/v5/founder-story",
        method="POST",
        payload={},
        confirm="run_founder_story",
        timeout=300,
    )
    ledger.check(
        "v5_founder_funding_e2e",
        founder_story.get("passed") is True
        and len(founder_story.get("stages", [])) == 14
        and all(item.get("passed") for item in founder_story.get("stages", []))
        and founder_story.get("initial_snapshot_id")
        != founder_story.get("funding_snapshot_id")
        and founder_story.get("funding_snapshot_id")
        != founder_story.get("confirmed_snapshot_id"),
        {
            "story_version": founder_story.get("story_version"),
            "stage_count": len(founder_story.get("stages", [])),
            "workflow_id": founder_story.get("workflow_id"),
        },
    )

    comparison = json_request(api_url, "/api/v1/demo/families/comparison")
    rows = comparison.get("rows", [])
    ledger.check(
        "three_family_dynamic_configuration",
        len(rows) == 3
        and comparison.get("unique_configuration_count") == 3
        and comparison.get("fixed_ratio_model") is False
        and len({row.get("configuration_signature") for row in rows}) == 3,
        {"rows": len(rows), "unique": comparison.get("unique_configuration_count")},
    )
    main_family = next((row for row in rows if row.get("code") == "DEMO_B"), None)
    ledger.check("main_family_present", main_family is not None, main_family)
    household_id = str(main_family["household_id"])

    analysis = json_request(api_url, f"/api/v1/households/{household_id}/financial-analysis")
    balance_sheet = analysis.get("statements", {}).get("balance_sheet", {})
    asset_lines = balance_sheet.get("assets", [])
    ledger.check(
        "main_calculation",
        balance_sheet.get("total_assets") == "2850000.00"
        and balance_sheet.get("net_worth") == "1642000.00"
        and all(item.get("category") != "credit_card_unpaid" for item in asset_lines),
        {
            "total_assets": balance_sheet.get("total_assets"),
            "net_worth": balance_sheet.get("net_worth"),
        },
    )

    suitability = json_request(
        api_url,
        f"/api/v1/households/{household_id}/portfolio/suitability-check",
        method="POST",
        payload={
            "analysis_date": "2026-08-04",
            "investment_amount": "500000.00",
            "target_horizon_months": 6,
            "requested_high_risk_ratio": "1.000000",
            "leverage_ratio": "1.000000",
            "concentration_ratio": "1.000000",
            "requested_product_codes": ["MOCK-FUTURES-LAB-001"],
            "purpose": "tuition",
        },
    )
    ledger.check(
        "suitability_rejection",
        suitability.get("decision") == "reject"
        and suitability.get("failed_check_codes")
        and suitability.get("calculation_source") == "deterministic_tools",
        suitability,
    )

    demo = json_request(
        api_url,
        "/api/v1/demo/runs",
        method="POST",
        payload={"path_count": 100},
        timeout=300,
    )
    ledger.check(
        "complete_demo",
        demo.get("status") == "completed"
        and demo.get("progress_percent") == 100
        and len(demo.get("stages", [])) == 10
        and demo.get("external_network_required") is False,
        {
            "status": demo.get("status"),
            "stages": len(demo.get("stages", [])),
            "error": demo.get("error_code"),
        },
    )
    targets = demo.get("metrics", {}).get("target_results", {})
    ledger.check("performance_targets", bool(targets) and all(targets.values()), targets)

    artifacts = demo.get("artifacts", {})
    twin = artifacts.get("twin", {})
    twin_run = json_request(
        api_url,
        f"/api/v1/households/{household_id}/twin/runs/{twin.get('run_id')}",
    )
    ledger.check(
        "twin_result",
        twin_run.get("status") == "completed"
        and twin_run.get("result") is not None
        and "unemployment_equity_down_30" in twin_run.get("scenario_codes", []),
        {"run_id": twin.get("run_id"), "status": twin_run.get("status")},
    )

    report = json_request(api_url, f"/api/v1/households/{household_id}/reports/current")
    ledger.check(
        "strict_eight_chapter_report",
        report.get("chapter_count") == 8 and len(report.get("chapters", [])) == 8,
        {"report_id": report.get("report_id"), "chapters": len(report.get("chapters", []))},
    )
    gate = json_request(
        api_url,
        f"/api/v1/reports/{report.get('report_id')}/quality-gate",
        method="POST",
        payload={"human_review_completed": True, "reason": "本地发布验收：人工核对合成报告"},
        role="compliance",
    )
    ledger.check(
        "report_quality_gate",
        gate.get("passed") is True
        and len(gate.get("gates", [])) == 10
        and all(item.get("status") == "pass" for item in gate.get("gates", [])),
        {"passed": gate.get("passed"), "gate_count": len(gate.get("gates", []))},
    )

    evaluation = json_request(
        api_url,
        "/api/v1/security/evaluations/run",
        method="POST",
        payload={},
        role="compliance",
    )
    metrics = evaluation.get("metrics", {})
    ledger.check(
        "security_adversarial_suite",
        evaluation.get("passed") is True
        and metrics.get("adversarial_passed") == 8
        and metrics.get("adversarial_total") == 8,
        metrics,
    )

    experiments = json_request(
        api_url,
        "/api/v1/demo/experiments/run",
        method="POST",
        payload={},
        role="compliance",
    )
    ledger.check(
        "seven_release_experiments",
        experiments.get("passed") is True
        and len(experiments.get("cases", [])) == 7
        and experiments.get("real_bank_results_claimed") is False,
        {
            "cases": len(experiments.get("cases", [])),
            "real_bank_results_claimed": experiments.get("real_bank_results_claimed"),
        },
    )

    for path in ("/", "/demo", "/client", "/advisor", "/risk"):
        status, body, content_type = request(web_url, path, accept="text/html")
        ledger.check(
            f"page_smoke_{path.strip('/') or 'home'}",
            status == 200 and content_type == "text/html" and b'<div id="root">' in body,
            {"path": path, "status": status, "content_type": content_type},
        )

    return ledger.output()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", type=local_base_url, default="http://127.0.0.1:8000")
    parser.add_argument("--web-url", type=local_base_url, default="http://127.0.0.1:8080")
    parser.add_argument(
        "--reset-demo",
        action="store_true",
        help="first reset only the configured synthetic personas (never non-synthetic data)",
    )
    args = parser.parse_args()
    try:
        result = run_acceptance(args.api_url, args.web_url, reset_demo=args.reset_demo)
    except AssertionError as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False, indent=2))
        sys.exit(1)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
