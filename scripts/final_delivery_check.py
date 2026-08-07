#!/usr/bin/env python3
"""Validate the Fortune Copilot competition delivery against Prompt 14.

The checker uses only the Python standard library. It validates repository
materials and, when URLs are supplied, the running local Mock application.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from dataclasses import asdict, dataclass
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
PROMPT_SHA256 = "49954c74fc76f4d32a6aef0584fa72a81910fa7c34ea9f66f93b50c9d47e6b05"
FINAL_QUOTE = "智运财富不是替用户预测市场，而是帮助中国家庭在不确定的市场中，仍然能够完成确定的人生目标。"
HTTP_METHODS = {"get", "put", "post", "delete", "options", "head", "patch", "trace"}


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    detail: str


def result(name: str, passed: bool, detail: str) -> CheckResult:
    return CheckResult(name=name, passed=passed, detail=detail)


def read_text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def xml_text(payload: bytes) -> str:
    text_nodes = re.findall(
        rb"<(?:[A-Za-z0-9]+:)?t(?:\s[^>]*)?>(.*?)</(?:[A-Za-z0-9]+:)?t>",
        payload,
        re.DOTALL,
    )
    return " ".join(
        unescape(node.decode("utf-8", errors="replace")) for node in text_nodes
    )


def check_required_files() -> list[CheckResult]:
    required = {
        "README.md": 2_000,
        "DESIGN.md": 2_000,
        "docs/codex/wealthtwin_codex_prompts.md": 20_000,
        "docs/technical_whitepaper.md": 10_000,
        "docs/demo_script_3min.md": 2_000,
        "docs/defense_qa.md": 4_000,
        "docs/icbc_business_value.md": 2_000,
        "docs/final_acceptance_report.md": 8_000,
        "docs/final_function_matrix.md": 4_000,
        "docs/final_test_report.md": 2_000,
        "docs/known_limitations.md": 1_500,
        "docs/demo_risk_plan.md": 2_000,
        "docs/file_api_inventory.md": 5_000,
        "scripts/build_final_materials.py": 4_000,
        "scripts/build_competition_deck.mjs": 10_000,
        "scripts/final_delivery_check.py": 4_000,
        "output/doc/wealthtwin_technical_whitepaper.docx": 20_000,
        "output/presentations/wealthtwin_competition_deck.pptx": 200_000,
        "output/presentation_assets/demo-overview.png": 20_000,
        "output/screenshots/stage10/advisor-1366.png": 20_000,
        "output/screenshots/stage10/risk-1440.png": 20_000,
    }
    missing: list[str] = []
    undersized: list[str] = []
    for relative, minimum in required.items():
        path = ROOT / relative
        if not path.is_file():
            missing.append(relative)
        elif path.stat().st_size < minimum:
            undersized.append(f"{relative} ({path.stat().st_size} < {minimum})")
    return [
        result(
            "required_files",
            not missing and not undersized,
            f"{len(required) - len(missing) - len(undersized)}/{len(required)} valid"
            + (f"; missing={missing}" if missing else "")
            + (f"; undersized={undersized}" if undersized else ""),
        )
    ]


def check_prompt_copy() -> list[CheckResult]:
    path = ROOT / "docs/codex/wealthtwin_codex_prompts.md"
    digest = (
        hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "missing"
    )
    return [result("prompt_package_sha256", digest == PROMPT_SHA256, digest)]


def check_readme() -> list[CheckResult]:
    text = read_text("README.md")
    sections = [
        "## 项目定位",
        "## 产品截图",
        "## 架构速览",
        "## 快速启动",
        "## 三端演示账号",
        "## 三分钟演示流程",
        "## 合成数据与 Mock 边界",
        "## 质量检查",
        "## 风险免责声明与核心边界",
    ]
    screenshot_paths = [
        "output/presentation_assets/demo-overview.png",
        "output/playwright/stage9-client-balance-1366x768.png",
        "output/screenshots/stage10/advisor-1366.png",
        "output/screenshots/stage10/risk-1440.png",
    ]
    concepts = [
        "信用卡可用额度不计入资产",
        "不是固定比例图",
        "不等同 CPI",
        "普通家庭默认不推荐个股、杠杆或股指期货",
        "关键金额、比率与配置由确定性工具计算",
        "无密钥、无外部模型、无真实银行接口",
    ]
    missing = [
        item for item in sections + screenshot_paths + concepts if item not in text
    ]
    return [
        result(
            "readme_prompt14_sections",
            not missing,
            f"missing={missing}"
            if missing
            else "all required sections, screenshots and boundaries present",
        )
    ]


def check_whitepaper() -> list[CheckResult]:
    text = read_text("docs/technical_whitepaper.md")
    chapters = [
        int(value) for value in re.findall(r"^##\s+(\d+)\.", text, re.MULTILINE)
    ]
    topics = [
        "中国家庭财富管理问题",
        "一核四账",
        "四重购买力",
        "数据字典",
        "财务指标",
        "动态四账户",
        "组合优化",
        "行为金融",
        "知识图谱",
        "适当性",
        "三端架构",
        "未来路线",
    ]
    missing_topics = [topic for topic in topics if topic not in text]
    return [
        result(
            "whitepaper_12_chapters",
            chapters == list(range(1, 13)),
            f"chapters={chapters}",
        ),
        result(
            "whitepaper_required_topics",
            not missing_topics,
            f"missing={missing_topics}"
            if missing_topics
            else "12 topic families present",
        ),
        result(
            "whitepaper_final_quote",
            FINAL_QUOTE in text,
            "exact closing quote present"
            if FINAL_QUOTE in text
            else "exact closing quote missing",
        ),
    ]


def check_demo_and_defense() -> list[CheckResult]:
    demo = read_text("docs/demo_script_3min.md")
    windows = [
        "0—20 秒",
        "20—50 秒",
        "50—90 秒",
        "90—130 秒",
        "130—160 秒",
        "160—180 秒",
    ]
    missing_windows = [window for window in windows if window not in demo]
    qa = read_text("docs/defense_qa.md")
    question_count = len(re.findall(r"^##\s+\d+\.", qa, re.MULTILINE))
    products = {
        "工行 AI投": ("工行 AI 投", "工行 AI投", "工行“AI投”"),
        "且慢": ("且慢",),
        "蚂蚁财富": ("蚂蚁财富",),
        "Betterment": ("Betterment",),
        "Wealthfront": ("Wealthfront",),
    }
    missing_products = [
        label
        for label, variants in products.items()
        if not any(value in qa for value in variants)
    ]
    return [
        result(
            "demo_exact_time_windows",
            not missing_windows,
            f"missing={missing_windows}" if missing_windows else "6/6 windows present",
        ),
        result(
            "demo_actual_routes",
            "/demo" in demo
            and "/client" in demo
            and "/advisor" in demo
            and "/risk" in demo,
            "four actual page routes referenced",
        ),
        result(
            "defense_questions", question_count >= 11, f"questions={question_count}"
        ),
        result(
            "defense_product_comparison",
            not missing_products,
            f"missing={missing_products}"
            if missing_products
            else "5/5 named products covered",
        ),
    ]


def check_matrices_and_boundaries() -> list[CheckResult]:
    function_matrix = read_text("docs/final_function_matrix.md")
    statuses = {
        status: function_matrix.count(f"| {status} |")
        for status in ("已实现", "Mock", "计划")
    }
    acceptance = read_text("docs/final_acceptance_report.md")
    rows = re.findall(
        r"^\|\s*(\d+)\s*\|.*?\|\s*(已实现|部分实现|未实现)\s*\|",
        acceptance,
        re.MULTILINE,
    )
    row_numbers = [int(number) for number, _ in rows]
    safe_terms = [
        "信用卡额度",
        "动态四账户",
        "稳钱",
        "70%",
        "最低工资",
        "股指期货",
        "确定性工具",
        "严格八章",
        "离线",
        "Mock",
    ]
    missing_terms = [term for term in safe_terms if term not in acceptance]
    return [
        result(
            "function_matrix_statuses",
            all(value > 0 for value in statuses.values()),
            json.dumps(statuses, ensure_ascii=False),
        ),
        result(
            "appendix_d_30_rows",
            row_numbers == list(range(1, 31)),
            f"rows={row_numbers}",
        ),
        result(
            "acceptance_red_lines",
            not missing_terms,
            f"missing={missing_terms}"
            if missing_terms
            else "all core boundaries evidenced",
        ),
        result(
            "acceptance_final_quote",
            FINAL_QUOTE in acceptance,
            "exact closing quote present"
            if FINAL_QUOTE in acceptance
            else "exact closing quote missing",
        ),
    ]


def check_office_packages() -> list[CheckResult]:
    results: list[CheckResult] = []
    docx = ROOT / "output/doc/wealthtwin_technical_whitepaper.docx"
    pptx = ROOT / "output/presentations/wealthtwin_competition_deck.pptx"

    try:
        with zipfile.ZipFile(docx) as archive:
            corrupt = archive.testzip()
            document_text = xml_text(archive.read("word/document.xml"))
        docx_ok = (
            corrupt is None
            and "技术白皮书" in document_text
            and FINAL_QUOTE in document_text
        )
        results.append(
            result(
                "docx_structure",
                docx_ok,
                f"zip_corrupt={corrupt}; exact quote={'yes' if FINAL_QUOTE in document_text else 'no'}",
            )
        )
    except (OSError, KeyError, zipfile.BadZipFile) as exc:
        results.append(result("docx_structure", False, f"{type(exc).__name__}: {exc}"))

    narrative = [
        "痛点",
        "中国自主框架",
        "产品流程",
        "动态四账户",
        "数字孪生",
        "行为金融",
        "AI 与算法",
        "三端闭环",
        "典型案例",
        "评测与合规",
        "工行价值",
        "商业与推广",
        "结论",
    ]
    try:
        with zipfile.ZipFile(pptx) as archive:
            corrupt = archive.testzip()
            names = archive.namelist()
            slide_names = sorted(
                (
                    name
                    for name in names
                    if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)
                ),
                key=lambda value: int(re.search(r"(\d+)", Path(value).stem).group(1)),  # type: ignore[union-attr]
            )
            note_names = [
                name
                for name in names
                if re.fullmatch(r"ppt/notesSlides/notesSlide\d+\.xml", name)
            ]
            slide_texts = [xml_text(archive.read(name)) for name in slide_names]
            note_texts = [xml_text(archive.read(name)) for name in note_names]
        order_ok = len(slide_texts) == 14 and all(
            label in slide_texts[index + 1] for index, label in enumerate(narrative)
        )
        notes_ok = len(note_texts) == 14 and all(
            "[Sources]" in note for note in note_texts
        )
        quote_ok = bool(slide_texts) and re.sub(r"\s+", "", FINAL_QUOTE) in re.sub(
            r"\s+", "", slide_texts[-1]
        )
        results.extend(
            [
                result(
                    "pptx_structure",
                    corrupt is None and len(slide_texts) == 14,
                    f"slides={len(slide_texts)}; zip_corrupt={corrupt}",
                ),
                result(
                    "pptx_narrative_order",
                    order_ok,
                    f"13 required sections in slides 2—14={'yes' if order_ok else 'no'}",
                ),
                result(
                    "pptx_source_notes",
                    notes_ok,
                    f"source_notes={sum('[Sources]' in note for note in note_texts)}/{len(note_texts)}",
                ),
                result(
                    "pptx_final_quote",
                    quote_ok,
                    "exact closing quote present"
                    if quote_ok
                    else "exact closing quote missing",
                ),
            ]
        )
    except (OSError, KeyError, zipfile.BadZipFile) as exc:
        results.append(result("pptx_structure", False, f"{type(exc).__name__}: {exc}"))
    return results


def check_credentials() -> list[CheckResult]:
    excluded_parts = {
        ".git",
        ".venv",
        "node_modules",
        "tmp",
        "dist",
        "playwright-report",
        "test-results",
    }
    text_suffixes = {
        "",
        ".css",
        ".env",
        ".example",
        ".html",
        ".ini",
        ".js",
        ".json",
        ".md",
        ".mjs",
        ".py",
        ".sh",
        ".toml",
        ".ts",
        ".tsx",
        ".txt",
        ".xml",
        ".yaml",
        ".yml",
    }
    patterns = [
        re.compile(r"(?<![A-Za-z0-9_-])sk-(?!test-|example-|mock-)[A-Za-z0-9]{20,}"),
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
        re.compile(
            r"(?im)^[ \t]*(?:LLM_API_KEY|OPENAI_API_KEY|DEEPSEEK_API_KEY)[ \t]*=[ \t]*['\"]?[^\s#'\"]{8,}"
        ),
    ]
    hits: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(
            part in excluded_parts for part in path.relative_to(ROOT).parts
        ):
            continue
        if path.suffix.lower() not in text_suffixes or path.stat().st_size > 2_000_000:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if any(pattern.search(content) for pattern in patterns):
            hits.append(str(path.relative_to(ROOT)))
    return [
        result(
            "credential_scan",
            not hits,
            f"files_with_secret_patterns={hits}"
            if hits
            else "0 secret/private-key patterns",
        )
    ]


def require_local_url(raw_url: str) -> str:
    parsed = urlparse(raw_url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {
        "localhost",
        "127.0.0.1",
        "::1",
    }:
        raise ValueError("only localhost/loopback URLs are permitted")
    return raw_url.rstrip("/") + "/"


def fetch_json(base_url: str, relative: str) -> dict[str, Any]:
    request = Request(
        urljoin(base_url, relative.lstrip("/")), headers={"Accept": "application/json"}
    )
    with urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def check_live(api_url: str | None, web_url: str | None) -> list[CheckResult]:
    results: list[CheckResult] = []
    if api_url:
        try:
            base = require_local_url(api_url)
            health = fetch_json(base, "/api/v1/health")
            openapi = fetch_json(base, "/api/v1/openapi.json")
            paths = openapi.get("paths", {})
            operations = sum(
                1
                for item in paths.values()
                for method in item
                if method.lower() in HTTP_METHODS
            )
            health_ok = (
                health.get("status") == "ok"
                and health.get("mock_mode") is True
                and health.get("version") == "0.13.0"
            )
            results.extend(
                [
                    result(
                        "live_health_mock",
                        health_ok,
                        json.dumps(health, ensure_ascii=False, sort_keys=True),
                    ),
                    result(
                        "live_openapi_inventory",
                        len(paths) == 110 and operations == 140,
                        f"paths={len(paths)}; operations={operations}",
                    ),
                ]
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            results.append(result("live_api", False, f"{type(exc).__name__}: {exc}"))
    if web_url:
        try:
            base = require_local_url(web_url)
            statuses: dict[str, int] = {}
            for route in ("/", "/demo", "/client", "/advisor", "/risk"):
                request = Request(
                    urljoin(base, route.lstrip("/")), headers={"Accept": "text/html"}
                )
                with urlopen(request, timeout=15) as response:
                    statuses[route] = response.status
            results.append(
                result(
                    "live_three_end_pages",
                    all(status == 200 for status in statuses.values()),
                    json.dumps(statuses, sort_keys=True),
                )
            )
        except (OSError, ValueError) as exc:
            results.append(result("live_web", False, f"{type(exc).__name__}: {exc}"))
    return results


def run_checks(api_url: str | None, web_url: str | None) -> list[CheckResult]:
    checks: list[CheckResult] = []
    for checker in (
        check_required_files,
        check_prompt_copy,
        check_readme,
        check_whitepaper,
        check_demo_and_defense,
        check_matrices_and_boundaries,
        check_office_packages,
        check_credentials,
    ):
        checks.extend(checker())
    checks.extend(check_live(api_url, web_url))
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", help="Optional running localhost API base URL")
    parser.add_argument("--web-url", help="Optional running localhost Web base URL")
    parser.add_argument("--json", action="store_true", help="Emit only JSON")
    args = parser.parse_args()

    checks = run_checks(args.api_url, args.web_url)
    passed = sum(item.passed for item in checks)
    payload = {
        "status": "passed" if passed == len(checks) else "failed",
        "passed": passed,
        "total": len(checks),
        "checks": [asdict(item) for item in checks],
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for item in checks:
            marker = "PASS" if item.passed else "FAIL"
            print(f"[{marker}] {item.name}: {item.detail}")
        print(
            json.dumps(
                {key: value for key, value in payload.items() if key != "checks"},
                ensure_ascii=False,
            )
        )
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
