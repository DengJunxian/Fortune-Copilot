import { run } from "axe-core";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AppRoutes } from "../App";
import {
  behaviorABFixture,
  behaviorCatalogFixture,
  behaviorOverviewFixture,
  behaviorProfileFixture,
  behaviorSessionFixture,
} from "./behaviorFixture";
import { financialFixture } from "./financialFixture";
import { clientExperienceFixture } from "./clientExperienceFixture";
import { planningFixture } from "./planningFixture";
import { portfolioFixture } from "./portfolioFixture";
import { fundAdvisoryFixture } from "./fundAdvisoryFixture";
import { twinFixture } from "./twinFixture";
import {
  agentCatalogFixture,
  householdGraphFixture,
  intakeDraftFixture,
  knowledgeCatalogFixture,
  knowledgeSearchFixture,
  orchestrationFixture,
  shanghaiGraphFixture,
} from "./trustFixture";
import {
  advisorDossierFixture,
  advisorHouseholdsFixture,
  complianceEvidenceFixture,
  complianceQueueFixture,
  decisionEvidenceFixture,
  workflowFixture,
} from "./reviewWorkflowFixture";
import {
  formalReportFixture,
  reportActionListFixture,
  reportGenerationChainFixture,
} from "./formalReportFixture";
import {
  qualityGateFixture,
  securityDashboardFixture,
  securityEvaluationFixture,
} from "./securityFixture";
import {
  demoComparisonFixture,
  demoExperimentsFixture,
  demoLoadFixture,
  demoManifestFixture,
  demoPreheatFixture,
  demoResetFixture,
  demoRunFixture,
} from "./demoFixture";

function jsonResponse(payload: unknown): Pick<Response, "ok" | "status" | "json"> {
  return { ok: true, status: 200, json: async () => payload };
}

function connectedFetch() {
  let behaviorAnsweredCount = 0;
  let currentFormalReport: ReturnType<typeof formalReportFixture> | null = null;
  let reportActions = reportActionListFixture();
  let currentDemoRun: typeof demoRunFixture | null = null;
  let currentDemoExperiments: typeof demoExperimentsFixture | null = null;
  const persistedBehaviorProfile = {
    ...behaviorProfileFixture,
    meta: { ...behaviorProfileFixture.meta, source: "completed_session" as const },
    interventions: behaviorProfileFixture.interventions.map((item, index) => ({
      ...item,
      intervention_id: `behavior-intervention-${index}`,
      starts_at: "2026-08-04T08:05:00Z",
      eligible_at: item.cooling_period_hours ? "2026-08-06T08:05:00Z" : null,
      audit_note: "状态、触发证据与操作均已持久化并写入审计事件。",
    })),
  };
  return vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const role = new Headers(init?.headers).get("X-Actor-Role");
    if (url.includes("/api/v1/meta/capabilities")) {
      return Promise.resolve(jsonResponse({
        version: "0.3.0",
        runtime_mode: "mock",
        mock_mode: true,
        database: { status: "ok", detail: "test" },
        portals: ["client", "advisor", "risk"],
        capabilities: [],
        guardrails: [],
      }));
    }
    if (url.endsWith("/api/v1/integrations/readiness")) {
      return Promise.resolve(jsonResponse({
        assessment_version: "production-readiness-v1",
        assessed_at: "2026-08-08T12:00:00Z",
        runtime_mode: "test",
        production_ready: false,
        has_live_icbc_connection: false,
        has_live_government_connection: false,
        public_data_snapshot_version: "authoritative-public-cn-2026-08-08",
        public_data_integrity_hash: "a".repeat(64),
        capabilities: [{
          capability: "bank_account_and_cashflow_data",
          label: "账户、流水与贷款事实",
          state: "authorization_required",
          adapter_id: "unavailable-production-adapter",
          execution_allowed: false,
          production_blocking: true,
          current_implementation: "生产端口失败关闭。",
          required_prerequisites: ["客户授权", "生产凭据", "对账规则"],
          evidence: ["没有真实工行连接"],
        }],
        operational_controls: [],
        authoritative_sources: [],
        boundary_note: "公开资料不能授予客户数据、交易或银行内部权限。",
      }));
    }
    if (url.endsWith("/api/v1/public-data/authoritative-snapshot")) {
      return Promise.resolve(jsonResponse({
        snapshot: {
          publication_cutoff: "2026-08-08",
          official_cpi: {
            rate: "0.009000",
            statistic_label: "2026年1—4月全国居民消费价格同比平均涨幅",
            source_reference: "https://www.stats.gov.cn/",
            version: "nbs-cpi-2026-jan-apr-v1",
          },
          regional_minimum_wages: {},
          regional_living_cost_observations: {
            "320100": {
              region_name: "江苏省南京市",
              amount: "44578.00",
              period_end: "2024-12-31",
              data_quality: "verified_public_snapshot",
              can_be_used_as_cpi: false,
            },
          },
        },
        integrity_hash: "a".repeat(64),
        update_mode: "controlled_snapshot_not_runtime_scraping",
        boundary_note: "只读快照。",
      }));
    }
    if (url.endsWith("/api/v1/demo/manifest")) {
      return Promise.resolve(jsonResponse({
        ...demoManifestFixture,
        latest_run_id: currentDemoRun?.run_id ?? null,
        latest_run_status: currentDemoRun?.status ?? null,
      }));
    }
    if (url.endsWith("/api/v1/demo/families/comparison")) {
      return Promise.resolve(jsonResponse(demoComparisonFixture));
    }
    if (url.endsWith("/api/v1/demo/load")) {
      return Promise.resolve(jsonResponse(demoLoadFixture));
    }
    if (url.endsWith("/api/v1/demo/reset")) {
      currentDemoRun = null;
      currentDemoExperiments = null;
      return Promise.resolve(jsonResponse(demoResetFixture));
    }
    if (url.endsWith("/api/v1/demo/preheat")) {
      return Promise.resolve(jsonResponse(demoPreheatFixture));
    }
    if (url.endsWith("/api/v1/demo/runs")) {
      currentDemoRun = demoRunFixture;
      return Promise.resolve(jsonResponse(currentDemoRun));
    }
    if (url.endsWith("/api/v1/demo/experiments/latest")) {
      return Promise.resolve(jsonResponse(currentDemoExperiments));
    }
    if (url.endsWith("/api/v1/demo/experiments/run")) {
      currentDemoExperiments = demoExperimentsFixture;
      return Promise.resolve(jsonResponse(currentDemoExperiments));
    }
    if (url.endsWith("/api/v1/security/dashboard")) {
      return Promise.resolve(jsonResponse(securityDashboardFixture));
    }
    if (url.endsWith("/api/v1/security/evaluations/run")) {
      return Promise.resolve(jsonResponse(securityEvaluationFixture));
    }
    if (url.includes("/api/v1/reports/") && url.endsWith("/quality-gate")) {
      return Promise.resolve(jsonResponse(qualityGateFixture));
    }
    if (url.includes("/api/v1/reports/") && url.endsWith("/publish")) {
      return Promise.resolve(jsonResponse({
        report_id: qualityGateFixture.report_id,
        publication_status: "published",
        published_at: "2026-08-04T08:01:00Z",
        gate: qualityGateFixture,
        watermark: "竞赛原型／已人工复核",
        boundary_note: "测试环境发布。",
      }));
    }
    if (url.includes("/api/v1/trust/knowledge/catalog")) {
      return Promise.resolve(jsonResponse(knowledgeCatalogFixture));
    }
    if (url.endsWith("/api/v1/trust/knowledge/search")) {
      return Promise.resolve(jsonResponse(knowledgeSearchFixture));
    }
    if (url.includes("/api/v1/trust/graphs/shanghai-demo")) {
      return Promise.resolve(jsonResponse(shanghaiGraphFixture));
    }
    if (url.includes("/api/v1/households/household-b/trust-graph")) {
      return Promise.resolve(jsonResponse(householdGraphFixture));
    }
    if (url.endsWith("/api/v1/trust/agents/catalog")) {
      return Promise.resolve(jsonResponse(agentCatalogFixture));
    }
    if (url.endsWith("/api/v1/households/household-b/trust-orchestrations/latest")) {
      return Promise.resolve(jsonResponse(null));
    }
    if (url.endsWith("/api/v1/households/household-b/trust-orchestrations")) {
      return Promise.resolve(jsonResponse(orchestrationFixture));
    }
    if (url.endsWith("/api/v1/trust/intake/drafts")) {
      return Promise.resolve(jsonResponse(intakeDraftFixture()));
    }
    if (url.endsWith("/api/v1/trust/intake/drafts/intake-draft-fixture/confirm")) {
      return Promise.resolve(jsonResponse(intakeDraftFixture(true)));
    }
    if (url.endsWith("/api/v1/twin/scenarios")) {
      return Promise.resolve(jsonResponse({
        scenario_version: "1.0.0",
        source_type: "internal_demo",
        source_summary: "测试夹具中的版本化内部演示压力参数。",
        scenario_count: 22,
        scenarios: [{
          code: "unemployment_equity_down_30",
          name: "失业 6 个月 + 权益下跌 30%",
          category: "combined",
          description: "主收入中断六个月，同时首月权益下跌 30%。",
          parameters: { income_interruption_months: 6 },
          explanation: "组合压力使用同一组共同随机数。",
          scenario_version: "1.0.0",
          source_type: "internal_demo",
          is_composable: true,
          enabled: true,
        }],
      }));
    }
    if (url.endsWith("/api/v1/behavior/catalog")) {
      return Promise.resolve(jsonResponse(behaviorCatalogFixture));
    }
    if (url.includes("/api/v1/behavior/ab-framework")) {
      return Promise.resolve(jsonResponse(behaviorABFixture));
    }
    if (url.includes("/api/v1/households?")) {
      return Promise.resolve(jsonResponse({
        items: [{ id: "household-b", code: "DEMO_B", name: "B 家庭（测试夹具）", lifecycle_stage: "family_growth", region: "上海", is_synthetic: true }],
        pagination: { page: 1, page_size: 100, total: 1, pages: 1 },
      }));
    }
    if (url.endsWith("/api/v1/advisor/households")) {
      return Promise.resolve(jsonResponse(advisorHouseholdsFixture));
    }
    if (url.endsWith("/api/v1/households/household-b/advisor-dossier")) {
      return Promise.resolve(jsonResponse(advisorDossierFixture));
    }
    if (url.endsWith("/api/v1/households/household-b/plan-workflows/current")) {
      return Promise.resolve(jsonResponse(role === "client" ? null : workflowFixture));
    }
    if (url.endsWith("/api/v1/compliance/review-queue")) {
      return Promise.resolve(jsonResponse(complianceQueueFixture));
    }
    if (url.endsWith(`/api/v1/plan-workflows/${workflowFixture.workflow_id}/compliance-evidence`)) {
      return Promise.resolve(jsonResponse(complianceEvidenceFixture));
    }
    if (url.endsWith(`/api/v1/plan-workflows/${workflowFixture.workflow_id}`)) {
      return Promise.resolve(jsonResponse(workflowFixture));
    }
    if (url.endsWith(`/api/v1/plan-workflows/${workflowFixture.workflow_id}/complaint-replays`)) {
      return Promise.resolve(jsonResponse({
        replay_id: "complaint-replay-fixture",
        workflow_id: workflowFixture.workflow_id,
        requested_version_id: workflowFixture.current.id,
        household_id: "household-b",
        generated_at: "2026-08-04T10:00:00Z",
        request_id: "complaint-request-fixture",
        timeline: workflowFixture.versions,
        audit_events: [],
        integrity_status: "verified",
        package_hash: "a".repeat(64),
        boundary_note: "投诉回放未修改历史。",
      }));
    }
    if (url.includes("/api/v1/decisions/") && url.endsWith("/evidence")) {
      return Promise.resolve(jsonResponse(decisionEvidenceFixture));
    }
    if (url.includes("/api/v1/decisions/") && url.endsWith("/replay")) {
      return Promise.resolve(jsonResponse({
        decision_id: decisionEvidenceFixture.decision_id,
        decision_type: decisionEvidenceFixture.decision_type,
        household_id: decisionEvidenceFixture.household_id,
        replayed_from: "frozen_decision_evidence",
        stored_decision_hash: decisionEvidenceFixture.decision_hash,
        replay_decision_hash: decisionEvidenceFixture.decision_hash,
        hash_identical: true,
        used_snapshot_versions: {},
        latest_product_data_used: false,
        replayed_at: "2026-08-04T10:30:00Z",
        evidence: decisionEvidenceFixture,
      }));
    }
    if (url.endsWith("/api/v1/households/household-b/financial-analysis")) {
      return Promise.resolve(jsonResponse(financialFixture));
    }
    if (url.endsWith("/api/v1/households/household-b/client-experience")) {
      return Promise.resolve(jsonResponse(clientExperienceFixture));
    }
    if (url.endsWith("/api/v1/households/household-b/reports/current")) {
      return Promise.resolve(jsonResponse(currentFormalReport));
    }
    if (url.endsWith("/api/v1/households/household-b/reports/generation-chain")) {
      return Promise.resolve(jsonResponse(reportGenerationChainFixture));
    }
    if (url.endsWith("/api/v1/households/household-b/reports/recalculate")) {
      currentFormalReport = formalReportFixture((currentFormalReport?.sequence ?? 1) + 1);
      reportActions = { ...reportActions, report_id: currentFormalReport.report_id, report_sequence: currentFormalReport.sequence };
      return Promise.resolve(jsonResponse(currentFormalReport));
    }
    if (url.endsWith("/api/v1/households/household-b/reports")) {
      currentFormalReport = formalReportFixture(1);
      reportActions = reportActionListFixture(1);
      return Promise.resolve(jsonResponse(currentFormalReport));
    }
    if (url.endsWith("/api/v1/households/household-b/report-actions")) {
      return Promise.resolve(jsonResponse(currentFormalReport ? reportActions : {
        household_id: "household-b",
        report_id: null,
        report_sequence: null,
        items: [],
        metrics: { total: 0, open: 0, completed: 0, deferred: 0, not_applicable: 0, completion_ratio: "0.00%" },
      }));
    }
    if (url.includes("/api/v1/households/household-b/report-actions/") && init?.method === "POST") {
      const body = JSON.parse(String(init.body)) as { status: "open" | "completed" | "deferred" | "not_applicable"; deferred_until?: string };
      const actionCode = decodeURIComponent(url.split("/").at(-1) ?? "");
      const oldAction = reportActions.items.find((item) => item.action_code === actionCode)!;
      const action = {
        ...oldAction,
        status: body.status,
        completed_at: body.status === "completed" ? "2026-08-04T09:00:00Z" : null,
        deferred_until: body.status === "deferred" ? body.deferred_until ?? null : null,
        status_reason: "测试行动状态变化",
        record_version: oldAction.record_version + 1,
      };
      const items = reportActions.items.map((item) => item.action_code === actionCode ? action : item);
      const metrics = {
        total: items.length,
        open: items.filter((item) => item.status === "open").length,
        completed: items.filter((item) => item.status === "completed").length,
        deferred: items.filter((item) => item.status === "deferred").length,
        not_applicable: items.filter((item) => item.status === "not_applicable").length,
        completion_ratio: `${((items.filter((item) => item.status === "completed").length / items.length) * 100).toFixed(2)}%`,
      };
      currentFormalReport = formalReportFixture((currentFormalReport?.sequence ?? 1) + 1);
      reportActions = { ...reportActions, report_id: currentFormalReport.report_id, report_sequence: currentFormalReport.sequence, items, metrics };
      return Promise.resolve(jsonResponse({
        action,
        metrics,
        report: { ...reportGenerationChainFixture.items[1], report_id: currentFormalReport.report_id, sequence: currentFormalReport.sequence },
      }));
    }
    if (url.endsWith("/api/v1/households/household-b/privacy/human-review-requests")) {
      return Promise.resolve(jsonResponse({
        request_id: "human-review-fixture-001",
        household_id: "household-b",
        status: "queued",
        queue: "demo_advisor_queue",
        created_at: "2026-08-04T08:00:00Z",
        message: "人工复核请求已记录并进入演示队列。",
      }));
    }
    if (url.endsWith("/api/v1/households/household-b/privacy/consents/consent-fixture/withdraw")) {
      return Promise.resolve(jsonResponse({
        ...clientExperienceFixture.privacy.consents[0],
        withdrawn_at: "2026-08-04T08:00:00Z",
        record_version: 2,
        status: "withdrawn",
        withdrawal_allowed: false,
      }));
    }
    if (url.endsWith("/api/v1/households/household-b/behavior")) {
      return Promise.resolve(jsonResponse(behaviorOverviewFixture));
    }
    if (url.endsWith("/api/v1/households/household-b/behavior/sessions")) {
      behaviorAnsweredCount = 0;
      return Promise.resolve(jsonResponse(behaviorSessionFixture()));
    }
    if (url.includes("/behavior/sessions/behavior-session-fixture/responses/")) {
      behaviorAnsweredCount += 1;
      return Promise.resolve(jsonResponse(behaviorSessionFixture(behaviorAnsweredCount)));
    }
    if (url.endsWith("/behavior/sessions/behavior-session-fixture/complete")) {
      return Promise.resolve(jsonResponse(behaviorSessionFixture(6, persistedBehaviorProfile)));
    }
    if (url.endsWith("/behavior/sessions/behavior-session-fixture/exit")) {
      return Promise.resolve(jsonResponse({
        session_id: "behavior-session-fixture",
        status: "exited",
        exited_at: "2026-08-04T08:01:00Z",
        audit_event_id: "behavior-exit-audit-fixture",
        message: "已退出实验；未生成画像或干预，不影响既有客观风险能力记录。",
      }));
    }
    if (url.includes("/behavior/interventions/") && url.endsWith("/actions")) {
      return Promise.resolve(jsonResponse({
        ...persistedBehaviorProfile.interventions[1],
        status: "dismissed",
        dismissed_at: "2026-08-04T08:06:00Z",
      }));
    }
    if (url.endsWith("/api/v1/households/household-b/planning")) {
      return Promise.resolve(jsonResponse(planningFixture));
    }
    if (url.endsWith("/api/v1/households/household-b/planning/counterfactual")) {
      return Promise.resolve(jsonResponse({
        base: planningFixture,
        scenario: {
          ...planningFixture,
          meta: { ...planningFixture.meta, scenario_type: "counterfactual" },
        },
        changes: [
          {
            code: "daily_recommended",
            label: "日用账户建议金额",
            before: "133000.00",
            after: "143000.00",
            delta: "10000.00",
            explanation: "测试反事实变化",
          },
        ],
        explanation: "所有金额由同一确定性规则版本重算。",
      }));
    }
    if (url.endsWith("/api/v1/households/household-b/goals")) {
      return Promise.resolve(jsonResponse({ id: "created-goal" }));
    }
    if (url.endsWith("/api/v1/households/household-b/planning/runs")) {
      return Promise.resolve(jsonResponse({
        recommendation_id: "recommendation",
        account_plan_ids: ["a", "b", "c", "d"],
        action_item_ids: ["action"],
        household_id: "household-b",
        input_version: "fixture-planning-input",
        rule_version_id: "rule",
        rule_version: "1.0.0",
        account_count: 4,
        action_count: 1,
        created_at: "2026-08-04T00:00:00Z",
        calculation_source: "deterministic_tools",
      }));
    }
    if (url.includes("/api/v1/households/household-b/portfolio?")) {
      const marketScenario = url.includes("market_scenario=risk_on") ? "risk_on" : url.includes("market_scenario=risk_off") ? "risk_off" : "neutral";
      return Promise.resolve(jsonResponse({ ...portfolioFixture, meta: { ...portfolioFixture.meta, market_scenario: marketScenario } }));
    }
    if (url.includes("/api/v1/households/household-b/fund-advisory?")) {
      const icbcOnly = !url.includes("icbc_only=false");
      return Promise.resolve(jsonResponse({
        ...fundAdvisoryFixture,
        meta: { ...fundAdvisoryFixture.meta, icbc_only: icbcOnly },
      }));
    }
    if (url.includes("/api/v1/households/household-b/portfolio/runs")) {
      return Promise.resolve(jsonResponse({
        recommendation_id: "portfolio-recommendation",
        portfolio_plan_ids: ["p1", "p2", "p3"],
        suitability_check_ids: Array.from({ length: 9 }, (_, index) => `s${index}`),
        household_id: "household-b",
        input_version: "fixture-portfolio-input",
        rule_version_id: "portfolio-rule",
        rule_version: "1.0.0",
        candidate_count: 3,
        suitability_check_count: 9,
        created_at: "2026-08-04T00:00:00Z",
        calculation_source: "deterministic_tools",
      }));
    }
    if (url.endsWith("/api/v1/households/household-b/portfolio/suitability-check")) {
      return Promise.resolve(jsonResponse({
        household_id: "household-b",
        decision: "reject",
        gates: portfolioFixture.candidates[0]?.gates ?? [],
        failed_check_codes: ["family_liquidity", "product_leverage"],
        audit_event_id: "audit-event-0123456789",
        rule_version: "1.0.0",
        calculation_source: "deterministic_tools",
        explanation: "不匹配请求已拒绝并写入审计事件；不会绕过三道闸门。",
      }));
    }
    if (url.endsWith("/api/v1/households/household-b/twin/runs")) {
      return Promise.resolve(jsonResponse({
        run_id: twinFixture.meta.run_id,
        household_id: "household-b",
        status: "queued",
        progress_percent: 0,
        phase: "queued",
        scenario_codes: ["unemployment_equity_down_30"],
        path_count: 100,
        horizon_months: 360,
        seed: 20260804,
        input_version: twinFixture.meta.input_version,
        rule_version: twinFixture.meta.rule_version,
        engine_version: twinFixture.meta.engine_version,
        created_at: "2026-08-04T00:00:00Z",
        started_at: null,
        completed_at: null,
        cancel_requested: false,
        audit_event_id: null,
        error_code: null,
        result: null,
      }));
    }
    if (url.endsWith(`/api/v1/households/household-b/twin/runs/${twinFixture.meta.run_id}/advance`)) {
      return Promise.resolve(jsonResponse({
        run_id: twinFixture.meta.run_id,
        household_id: "household-b",
        status: "completed",
        progress_percent: 100,
        phase: "completed",
        scenario_codes: ["unemployment_equity_down_30"],
        path_count: 100,
        horizon_months: 360,
        seed: 20260804,
        input_version: twinFixture.meta.input_version,
        rule_version: twinFixture.meta.rule_version,
        engine_version: twinFixture.meta.engine_version,
        created_at: "2026-08-04T00:00:00Z",
        started_at: "2026-08-04T00:00:01Z",
        completed_at: "2026-08-04T00:00:02Z",
        cancel_requested: false,
        audit_event_id: "audit-twin-fixture-001",
        error_code: null,
        result: twinFixture,
      }));
    }
    if (url.endsWith(`/api/v1/households/household-b/twin/runs/${twinFixture.meta.run_id}/cancel`)) {
      return Promise.resolve(jsonResponse({
        run_id: twinFixture.meta.run_id,
        household_id: "household-b",
        status: "cancelled",
        progress_percent: 0,
        phase: "cancelled",
        scenario_codes: ["unemployment_equity_down_30"],
        path_count: 100,
        horizon_months: 360,
        seed: 20260804,
        input_version: twinFixture.meta.input_version,
        rule_version: twinFixture.meta.rule_version,
        engine_version: twinFixture.meta.engine_version,
        created_at: "2026-08-04T00:00:00Z",
        started_at: null,
        completed_at: "2026-08-04T00:00:01Z",
        cancel_requested: true,
        audit_event_id: "audit-twin-cancelled-001",
        error_code: null,
        result: null,
      }));
    }
    return Promise.reject(new Error(`unexpected fetch: ${url}`));
  });
}

async function openClientTask(user: ReturnType<typeof userEvent.setup>, label: string) {
  const tab = await screen.findByRole("tab", { name: new RegExp(label) });
  await user.click(tab);
}

describe("Fortune Copilot routes", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    window.history.replaceState({}, "", "/");
  });

  it.each([
    ["/demo", "从一句家庭描述，到八章规划书与可追溯审核"],
    ["/client", "先了解您和家人"],
    ["/planning", "先了解您和家人"],
    ["/wealth", "家庭，今天先看最重要的四件事。"],
    ["/client/advanced", "家庭财富驾驶舱"],
    ["/advisor", "客户经理工作台"],
    ["/advisor/actions", "客户行动中心"],
    ["/risk", "风险与审计控制台"],
  ])("renders %s as a real portal route", async (path, heading) => {
    render(<AppRoutes initialPath={path} />);
    expect(await screen.findByRole("heading", { level: 1, name: heading })).toBeInTheDocument();
    expect(screen.getByText(/规划结果用于辅助家庭决策/)).toBeInTheDocument();
  });

  it("shows verified public data separately from blocked ICBC production ports", async () => {
    vi.stubGlobal("fetch", connectedFetch());
    render(<AppRoutes initialPath="/risk" />);

    expect(await screen.findByRole("heading", {
      name: "真实数据与银行系统接入边界",
    })).toBeInTheDocument();
    expect(screen.getByText("原型可用 · 生产未就绪")).toBeInTheDocument();
    expect(screen.getByText("未连接")).toBeInTheDocument();
    expect(screen.getByText("账户、流水与贷款事实")).toBeInTheDocument();
    expect(screen.getByText(/2024 年人均消费支出 ¥44,578/)).toBeInTheDocument();
    expect(screen.getByText(/不是 CPI/)).toBeInTheDocument();
  });

  it("renders the offline-safe Demo manifest and three distinct dynamic family configurations", async () => {
    vi.stubGlobal("fetch", connectedFetch());
    const { container } = render(<AppRoutes initialPath="/demo" />);

    expect(await screen.findByRole("heading", { name: "A／B／C：同一规则，不同配置" })).toBeInTheDocument();
    expect(screen.getByText("3 个唯一配置签名")).toBeInTheDocument();
    const comparison = screen.getByRole("table", { name: /A／B／C 使用各自事实计算/ });
    expect(within(comparison).getAllByRole("row")).toHaveLength(4);
    expect(within(comparison).getByText("a1-fixture-config")).toBeInTheDocument();
    expect(within(comparison).getByText("b2-fixture-config")).toBeInTheDocument();
    expect(within(comparison).getByText("c3-fixture-config")).toBeInTheDocument();
    expect(screen.getByText("0 次")).toBeInTheDocument();

    const result = await run(container, { rules: { "color-contrast": { enabled: false } } });
    expect(result.violations).toEqual([]);
  });

  it("runs the ten-stage Demo and records seven experiments without claiming bank results", async () => {
    const fetchMock = connectedFetch();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<AppRoutes initialPath="/demo" />);

    await screen.findByRole("heading", { name: "演示控制台" });
    await user.click(screen.getByRole("button", { name: "运行完整演示" }));
    const timeline = await screen.findByRole("list", { name: "主 Demo 十阶段进度" });
    expect(within(timeline).getAllByRole("listitem")).toHaveLength(10);
    expect(screen.getByText("8 / 8")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "查看客户端规划书" })).toHaveAttribute("href", "/client");
    expect(screen.getByRole("link", { name: "查看顾问底稿" })).toHaveAttribute("href", "/advisor");
    expect(screen.getByRole("link", { name: "查看风险与审计" })).toHaveAttribute("href", "/risk");

    await user.click(screen.getByRole("button", { name: "运行七项实验" }));
    const experiments = await screen.findByRole("list", { name: "七项发布实验" });
    expect(within(experiments).getAllByRole("listitem")).toHaveLength(7);
    expect(within(experiments).getAllByText("协议就绪")).toHaveLength(2);
    expect(within(experiments).getAllByText("未宣称实测")).toHaveLength(2);

    await user.click(screen.getByRole("button", { name: "重置合成数据" }));
    const resetRequest = fetchMock.mock.calls.find(([input]) => String(input).endsWith("/api/v1/demo/reset"));
    expect(new Headers(resetRequest?.[1]?.headers).get("X-Confirm-Action")).toBe("reset_synthetic_demo");
  });

  it("has no automatically detectable accessibility violations on the entry page", async () => {
    const { container } = render(<AppRoutes initialPath="/" />);
    expect(await screen.findByRole("heading", { name: /每个家庭.*财富答案/ })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /中国家庭财富管理主视觉/ })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "家庭责任先于投资收益" })).toBeInTheDocument();
    expect(screen.getByText(/单一风险问卷或固定比例无法完整表达/)).toBeInTheDocument();
    const result = await run(container, {
      rules: {
        "color-contrast": { enabled: false },
      },
    });
    expect(result.violations).toEqual([]);
  });

  it("opens a homepage customer case in the guided planning journey", async () => {
    vi.stubGlobal("fetch", connectedFetch());
    vi.stubGlobal("scrollTo", vi.fn());
    const user = userEvent.setup();
    window.history.replaceState({}, "", "/");
    render(<AppRoutes />);

    const caseCard = screen.getByRole("heading", { name: "双收入三口之家" }).closest("article");
    expect(caseCard).not.toBeNull();
    await user.click(within(caseCard!).getByRole("button", { name: /查看家庭方案/ }));

    expect(window.location.pathname).toBe("/planning");
    expect(window.location.search).toBe("");
    expect(window.location.hash).toBe("");
    expect(await screen.findByRole("heading", { name: "先看全貌，再看六项关键比率" })).toBeInTheDocument();
    expect(screen.getByText(/客户案例：B 家庭/)).toBeInTheDocument();
  });

  it("renders deterministic results and opens an auditable metric inspector", async () => {
    vi.stubGlobal("fetch", connectedFetch());
    const user = userEvent.setup();
    render(<AppRoutes initialPath="/client/advanced" />);

    await openClientTask(user, "财务健康");
    expect(await screen.findByRole("heading", { name: "全量财务健康指标" })).toBeInTheDocument();
    expect(screen.getAllByText(/1,642,000/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/完整度 83%/).length).toBeGreaterThan(0);
    await user.click(screen.getByRole("button", { name: "查看净资产详情" }));

    const inspector = screen.getByRole("dialog", { name: "净资产" });
    expect(inspector).toBeInTheDocument();
    expect(within(inspector).getByText("总资产 - 总负债")).toBeInTheDocument();
    expect(within(inspector).getByText("2,850,000 - 1,208,000 = 1,642,000")).toBeInTheDocument();
    expect(within(inspector).getByText("internal_demo")).toBeInTheDocument();
  });

  it("has no automatically detectable accessibility violations after analysis loads", async () => {
    vi.stubGlobal("fetch", connectedFetch());
    const user = userEvent.setup();
    const { container } = render(<AppRoutes initialPath="/client/advanced" />);
    await openClientTask(user, "财务健康");
    expect(await screen.findByRole("heading", { name: "全量财务健康指标" })).toBeInTheDocument();
    const radar = screen.getByRole("figure", { name: "十维家庭财务健康" });
    await user.click(within(radar).getByText("查看数据表"));
    expect(within(radar).getAllByRole("row")).toHaveLength(11);
    const result = await run(container, { rules: { "color-contrast": { enabled: false } } });
    expect(result.violations).toEqual([]);
  });

  it("provides twelve keyboard-navigable tasks, display modes, masking, and all fourteen states", async () => {
    vi.stubGlobal("fetch", connectedFetch());
    const user = userEvent.setup();
    const { container } = render(<AppRoutes initialPath="/client/advanced" />);

    const taskList = await screen.findByRole("tablist", { name: "十二项客户任务" });
    expect(within(taskList).getAllByRole("tab")).toHaveLength(12);
    const familyTab = within(taskList).getByRole("tab", { name: /家庭画像/ });
    familyTab.focus();
    await user.keyboard("{ArrowRight}");
    expect(within(taskList).getByRole("tab", { name: /资产负债/ })).toHaveFocus();
    expect(within(taskList).getByRole("tab", { name: /资产负债/ })).toHaveAttribute("aria-selected", "true");

    await user.click(screen.getByRole("button", { name: "深色" }));
    expect(container.querySelector('[data-theme="dark"]')).not.toBeNull();
    await user.click(screen.getByRole("checkbox", { name: "大字模式" }));
    expect(container.querySelector('[data-text-scale="large"]')).not.toBeNull();
    await user.click(screen.getByRole("checkbox", { name: "低金融知识模式" }));
    expect(container.querySelector('[data-language-mode="plain"]')).not.toBeNull();
    await openClientTask(user, "财务健康");
    expect(screen.getAllByText("家里真正剩下的钱").length).toBeGreaterThan(0);
    await openClientTask(user, "资产负债");
    await user.click(screen.getByRole("checkbox", { name: "隐藏金额" }));
    expect(screen.getByRole("region", { name: "资产负债金额已隐藏" })).toBeInTheDocument();
    expect(screen.queryByText(/2,850,000/)).not.toBeInTheDocument();

    await user.click(screen.getByText("查看完整状态演示"));
    expect(within(screen.getByLabelText("状态")).getAllByRole("option")).toHaveLength(14);
  });

  it("uses the owned chart contract with an equivalent table and amount-ratio switches", async () => {
    vi.stubGlobal("fetch", connectedFetch());
    const user = userEvent.setup();
    render(<AppRoutes initialPath="/client/advanced" />);

    await openClientTask(user, "资产负债");
    expect(await screen.findByRole("figure", { name: "资产负债全景" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "资产负债全景" })).toBeInTheDocument();
    await user.click(screen.getAllByText("查看数据表")[0]!);
    expect(screen.getByRole("region", { name: "资产负债全景等价数据表" })).toBeInTheDocument();
    expect(screen.getByText("家庭总负债")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "比例" }));
    expect(screen.getAllByText("占家庭总资产").length).toBeGreaterThan(0);
    await user.click(screen.getByLabelText("金额单位"));
    await user.selectOptions(screen.getByLabelText("金额单位"), "wan");
    await user.click(screen.getByRole("button", { name: "金额" }));
    expect(screen.getAllByText("万元").length).toBeGreaterThan(0);
  });

  it("keeps the planning report at exactly eight chapters and exposes audited privacy actions", async () => {
    const fetchMock = connectedFetch();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<AppRoutes initialPath="/client/advanced" />);

    await openClientTask(user, "家庭规划书");
    expect(await screen.findByRole("heading", { name: "B 家庭（测试夹具）家庭财富规划书" })).toBeInTheDocument();
    const chapterNavigation = screen.getByRole("navigation", { name: "规划书八章" });
    expect(within(chapterNavigation).getAllByRole("button")).toHaveLength(8);
    expect(screen.getByText("8 章")).toBeInTheDocument();
    for (const title of clientExperienceFixture.report.chapters.map((chapter) => chapter.title)) {
      expect(within(chapterNavigation).getByText(title)).toBeInTheDocument();
    }

    await openClientTask(user, "行动日历");
    await user.click(screen.getByText("为什么建议这一步"));
    expect(screen.getByText("家庭数据与原因")).toBeInTheDocument();
    expect(screen.getByText("约束／公式")).toBeInTheDocument();
    expect(screen.getByText("什么变化会重算")).toBeInTheDocument();
    expect(screen.getByText("风险与假设")).toBeInTheDocument();

    await openClientTask(user, "隐私中心");
    expect(await screen.findByRole("heading", { name: "隐私中心" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "撤回此授权" }));
    await user.type(screen.getByLabelText("撤回原因"), "测试客户撤回");
    await user.click(screen.getByRole("button", { name: "确认撤回" }));
    expect(await screen.findByText(/授权已撤回并写入审计记录/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "提交人工复核" }));
    expect(await screen.findByText(/人工复核请求已记录/)).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([input]) => String(input).endsWith("/withdraw"))).toBe(true);
    expect(fetchMock.mock.calls.some(([input]) => String(input).endsWith("/human-review-requests"))).toBe(true);
  });

  it("generates the formal eight-chapter report and persists an action into a new snapshot", async () => {
    const fetchMock = connectedFetch();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<AppRoutes initialPath="/client/advanced" />);

    await openClientTask(user, "家庭规划书");
    await user.click(await screen.findByRole("button", { name: "生成完整八章规划书" }));
    expect(await screen.findByText("当前 R1")).toBeInTheDocument();
    const navigation = screen.getByRole("navigation", { name: "规划书八章" });
    expect(within(navigation).getAllByRole("button")).toHaveLength(8);
    for (const title of ["家庭基础情况", "理财目标", "大额支出计划", "理财假设", "家庭财务报表", "家庭财务比率分析", "投资规划建议", "免责声明"]) {
      expect(within(navigation).getByText(title)).toBeInTheDocument();
    }
    expect(screen.getByRole("link", { name: "下载 HTML" })).toHaveAttribute("download");
    expect(screen.getByRole("link", { name: "下载 PDF" })).toHaveAttribute("download");

    await openClientTask(user, "行动日历");
    const statusSelect = await screen.findByRole("combobox", { name: "补足应急储备执行状态" });
    await user.selectOptions(statusSelect, "completed");
    await user.click(screen.getByRole("button", { name: "保存状态" }));
    expect(await screen.findByText(/生成正式规划书 R2 新快照/)).toBeInTheDocument();
    expect(screen.getAllByText("已完成").length).toBeGreaterThan(0);
    expect(fetchMock.mock.calls.some(([input]) => String(input).includes("/report-actions/action-immediate"))).toBe(true);
  });

  it("renders the four-account waterfall with three denominator views and conflict evidence", async () => {
    vi.stubGlobal("fetch", connectedFetch());
    const user = userEvent.setup();
    render(<AppRoutes initialPath="/client/advanced" />);

    await openClientTask(user, "四账户");
    expect(await screen.findByRole("heading", { name: "先过安全闸门，再安排长期资金" })).toBeInTheDocument();
    expect(screen.getByText("PFNW · 可规划金融净值")).toBeInTheDocument();
    expect(screen.getByText("为什么现在不建议增加投资？")).toBeInTheDocument();
    expect(screen.getByText("中国家庭购买力门槛 PPH")).toBeInTheDocument();
    expect(screen.getByText(/地区最低工资信号不是 CPI/)).toBeInTheDocument();
    expect(screen.getAllByText("个人养老金规划").length).toBeGreaterThan(0);
    expect(screen.getByText("个人养老金是制度账户，不是低风险等级")).toBeInTheDocument();
    for (const name of ["要花的钱", "保命的钱", "保本的钱", "生钱的钱"]) {
      expect(screen.getAllByRole("heading", { name }).length).toBeGreaterThan(0);
    }
    expect(screen.getByText(/不得套用于家庭总资产/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "家庭总资产" }));
    expect(screen.getByRole("button", { name: "家庭总资产" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getAllByText("4.7%").length).toBeGreaterThan(0);

    await user.click(screen.getAllByText("查看公式、三尺与产品教育")[0]!);
    expect(screen.getByText(/信用卡额度不是资产/)).toBeInTheDocument();
    await user.click(screen.getAllByText("查看公式、三尺与产品教育")[2]!);
    expect(
      screen.getByText(/中性口径 · 10.0%—20.0% · 战术锚 15.0%/),
    ).toBeInTheDocument();
    await user.click(screen.getByText("查看 70% 全部适用条件"));
    expect(screen.getByText("五项硬约束全部通过")).toBeInTheDocument();
    await openClientTask(user, "目标时间轴");
    expect(await screen.findByText("目标月投入超过当前新增结余")).toBeInTheDocument();
    await openClientTask(user, "个人养老金");
    expect(await screen.findByRole("heading", { name: "个人养老金不是低风险资产类别" })).toBeInTheDocument();
    expect(screen.getByText(/当前政策与账户数据是受控快照/)).toBeInTheDocument();
  });

  it("supports client goal entry and deterministic counterfactual recomputation", async () => {
    const fetchMock = connectedFetch();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<AppRoutes initialPath="/client/advanced" />);
    await openClientTask(user, "目标时间轴");
    expect(await screen.findByRole("heading", { name: "先过安全闸门，再安排长期资金" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "新增目标" }));
    await user.type(screen.getByLabelText("目标名称"), "两年内进修");
    await user.type(screen.getByLabelText("今日目标金额"), "60000.00");
    await user.type(screen.getByLabelText("目标日期"), "2028-08-04");
    await user.clear(screen.getByLabelText("最低可接受金额"));
    await user.type(screen.getByLabelText("最低可接受金额"), "40000.00");
    await user.click(screen.getByRole("button", { name: "保存并重算" }));
    expect(await screen.findByText(/目标已写入家庭事实层/)).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([input]) => String(input).endsWith("/goals"))).toBe(true);

    await user.clear(screen.getByLabelText("补足应急金"));
    await user.type(screen.getByLabelText("补足应急金"), "10000.00");
    await user.click(screen.getByRole("button", { name: "重新计算方案" }));
    expect(await screen.findByText(/反事实方案已由同一确定性规则版本重算/)).toBeInTheDocument();
    expect(screen.getByText("¥133,000 → ¥143,000")).toBeInTheDocument();
  });

  it("compares three deterministic candidates with Mock mappings and suitability evidence", async () => {
    vi.stubGlobal("fetch", connectedFetch());
    const user = userEvent.setup();
    render(<AppRoutes initialPath="/client/advanced" />);

    await openClientTask(user, "四账户");
    expect(await screen.findByRole("heading", { name: "长期资金的三种走法" })).toBeInTheDocument();
    expect(screen.getByText("当前没有可执行的长期新增资金")).toBeInTheDocument();
    expect(screen.getByText("购买力门槛 PPH")).toBeInTheDocument();
    expect(screen.getByText("单只股票卫星暴露")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "稳健基准进取方案比较" })).toBeInTheDocument();
    expect(screen.getAllByText("仅教育展示").length).toBeGreaterThanOrEqual(3);
    await user.click(screen.getByRole("button", { name: /进取/ }));
    expect(screen.getByRole("heading", { name: "进取方案的资产类别" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "先看这笔钱的用途，再看基金" })).toBeInTheDocument();
    expect(screen.getByText(/基金代码 482002/)).toBeInTheDocument();
    expect(screen.getByText("购买前请再确认")).toBeInTheDocument();
    expect(screen.getByText("专业对冲实验室默认关闭")).toBeInTheDocument();
    expect(screen.getAllByText(/Mock/).length).toBeGreaterThan(0);
  });

  it("runs a risk-side adversarial suitability check and exposes its audit id", async () => {
    vi.stubGlobal("fetch", connectedFetch());
    const user = userEvent.setup();
    render(<AppRoutes initialPath="/risk" />);

    expect(await screen.findByRole("heading", { name: "适当性证据与拒绝链" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "运行并写入审计" }));
    expect(await screen.findByText(/不匹配请求已拒绝并写入审计事件/)).toBeInTheDocument();
    expect(screen.getByText(/审计 audit-event-/)).toBeInTheDocument();
  });

  it("labels all security metrics as test-only and runs all eight adversarial cases", async () => {
    const fetchMock = connectedFetch();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<AppRoutes initialPath="/risk" />);

    expect(await screen.findByRole("heading", { name: "测试环境安全与模型风险质量门禁" })).toBeInTheDocument();
    expect(screen.getByText("仅测试环境")).toBeInTheDocument();
    expect(screen.getAllByText("test fixture")).toHaveLength(6);
    expect(screen.getByRole("list", { name: "八类对抗用例" }).children).toHaveLength(8);
    await user.click(screen.getByRole("button", { name: "运行八类对抗评测" }));
    expect(await screen.findByText("八类对抗用例通过 8/8。")).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([input]) => String(input).endsWith("/security/evaluations/run"))).toBe(true);
  });

  it("requires explicit human review before the ten report release gates and publish action", async () => {
    const fetchMock = connectedFetch();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<AppRoutes initialPath="/risk" />);

    const gateButton = await screen.findByRole("button", { name: "运行十项发布门禁" });
    expect(gateButton).toBeDisabled();
    await user.click(screen.getByRole("checkbox", { name: /我已人工复核报告/ }));
    await user.click(gateButton);
    expect(await screen.findByRole("list", { name: "报告发布十项门禁" })).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "报告发布十项门禁" }).children).toHaveLength(10);
    await user.click(screen.getByRole("button", { name: "二次确认并发布" }));
    expect(await screen.findByText(/报告已发布，水印/)).toBeInTheDocument();
    const publishRequest = fetchMock.mock.calls.find(([input]) => String(input).endsWith("/publish"));
    expect(new Headers(publishRequest?.[1]?.headers).get("X-Confirm-Action")).toBe("publish_report");
  });

  it("runs the household twin, compares common-random paths, and exposes exact chart data", async () => {
    const fetchMock = connectedFetch();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    const { container } = render(<AppRoutes initialPath="/client/advanced" />);

    await openClientTask(user, "数字孪生");
    expect(await screen.findByRole("heading", { name: "把家庭未来拆成可检验的路径" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("button", { name: "运行数字孪生" })).toBeEnabled());
    await user.click(screen.getByRole("button", { name: "运行数字孪生" }));

    expect(await screen.findByRole("heading", { name: /流动性缓冲使被迫出售概率下降 96 个百分点/ })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "数字孪生方案概率对照" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "净资产分位数扇形图" })).toBeInTheDocument();
    expect(screen.getByText("fixture-parameter-hash-0123456789abcdef")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "导出完整结果" })).toHaveAttribute("href", expect.stringContaining("/twin/runs/twin-run-fixture-001/export"));
    expect(fetchMock.mock.calls.some(([input]) => String(input).endsWith("/advance"))).toBe(true);

    const result = await run(container, { rules: { "color-contrast": { enabled: false } } });
    expect(result.violations).toEqual([]);
  });

  it("cancels an in-flight staged twin run and keeps the cancelled evidence state", async () => {
    const regularFetch = connectedFetch();
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith(`/api/v1/households/household-b/twin/runs/${twinFixture.meta.run_id}/advance`)) {
        return new Promise<Pick<Response, "ok" | "status" | "json">>((_resolve, reject) => {
          init?.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")), { once: true });
        });
      }
      return regularFetch(input);
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<AppRoutes initialPath="/client/advanced" />);

    await openClientTask(user, "数字孪生");
    expect(await screen.findByRole("heading", { name: "把家庭未来拆成可检验的路径" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("button", { name: "运行数字孪生" })).toBeEnabled());
    await user.click(screen.getByRole("button", { name: "运行数字孪生" }));
    await user.click(await screen.findByRole("button", { name: "取消运行" }));
    expect(await screen.findByText("已取消")).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([input]) => String(input).endsWith("/cancel"))).toBe(true);
  });

  it("renders the behavior dual profile, eleven evidence-backed biases, cooling intervention, and accessible ledgers", async () => {
    vi.stubGlobal("fetch", connectedFetch());
    const user = userEvent.setup();
    const { container } = render(<AppRoutes initialPath="/client/advanced" />);

    await openClientTask(user, "行为实验");
    expect(await screen.findByRole("heading", { name: "先做选择，再看行为如何影响配置上限" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "行为证据将配置上限从中风险上限下调至低风险上限" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "说法、选择与能力不做平均" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "分数旁必须能看到来源" })).toBeInTheDocument();
    expect(screen.getAllByText("损失厌恶").length).toBeGreaterThan(0);
    expect(screen.getAllByText("追涨杀跌").length).toBeGreaterThan(0);
    expect(screen.getByText(/48 小时冷静期已生成/)).toBeInTheDocument();
    expect(screen.getByText(/claimed_30_percent_but_sold_at_10_percent/)).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "六项行为实验记录，可横向滚动" })).toBeInTheDocument();

    const result = await run(container, { rules: { "color-contrast": { enabled: false } } });
    expect(result.violations).toEqual([]);
  });

  it("records all six behavior choices before deterministic profile completion", async () => {
    const fetchMock = connectedFetch();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<AppRoutes initialPath="/client/advanced" />);

    await openClientTask(user, "行为实验");
    expect(await screen.findByRole("heading", { name: "用真实选择校验自述承受力" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "开始行为实验" }));

    for (const experiment of behaviorCatalogFixture.experiments) {
      const selectedOption = experiment.options[1] ?? experiment.options[0];
      expect(selectedOption).toBeDefined();
      await user.click(await screen.findByRole("radio", { name: selectedOption!.label }));
      await user.click(screen.getByRole("button", { name: "记录选择并继续" }));
    }

    await user.click(await screen.findByRole("button", { name: "生成双画像与干预" }));
    expect(await screen.findByText(/双画像、十一项偏差证据和个性化干预已由确定性规则生成/)).toBeInTheDocument();
    expect(screen.getByText(/双画像结论 · 已持久化/)).toBeInTheDocument();
    expect(fetchMock.mock.calls.filter(([input]) => String(input).includes("/responses/")).length).toBe(6);
    expect(fetchMock.mock.calls.some(([input]) => String(input).endsWith("/complete"))).toBe(true);
  });

  it("lets a participant exit without generating a new behavior profile", async () => {
    const fetchMock = connectedFetch();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<AppRoutes initialPath="/client/advanced" />);

    await openClientTask(user, "行为实验");
    expect(await screen.findByRole("button", { name: "开始行为实验" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "开始行为实验" }));
    await user.click(await screen.findByRole("button", { name: "退出实验" }));

    expect(await screen.findByText(/已退出实验；未生成画像或干预/)).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([input]) => String(input).endsWith("/exit"))).toBe(true);
  });

  it("shows the four A/B variants and authorized-test metrics on the risk portal", async () => {
    vi.stubGlobal("fetch", connectedFetch());
    render(<AppRoutes initialPath="/risk" />);

    expect(await screen.findByRole("heading", { name: "从选择证据复核风险下调与干预状态" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "四组配置与合成／授权指标" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "行为干预 A/B 指标，可横向滚动" })).toBeInTheDocument();
    for (const variant of behaviorABFixture.variants) {
      expect(screen.getByText(variant.name)).toBeInTheDocument();
    }
    expect(screen.getByText(/指标不代表投资收益或干预因果效果/)).toBeInTheDocument();
  });

  it("shows dated RAG citations and an accessible Shanghai relationship graph", async () => {
    vi.stubGlobal("fetch", connectedFetch());
    const { container } = render(<AppRoutes initialPath="/client/advanced" />);

    expect(await screen.findByRole("heading", { name: "先筛时效和适用范围，再组织解释" })).toBeInTheDocument();
    expect(screen.getByText(/每年12000元限额标准/)).toBeInTheDocument();
    expect(screen.getByText("财政部、国家税务总局 · 财政部 税务总局公告2024年第21号")).toBeInTheDocument();
    expect(screen.getByText(/发布 2024\/12\/12 · 生效 2024\/01\/01 · 核验 2026\/08\/04/)).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "35岁上海双收入家庭关系推导图" })).toBeInTheDocument();
    expect(screen.getByText("70%不是家庭总资产统一比例。")).toBeInTheDocument();
    expect(screen.getByText(/运行时网络/)).toBeInTheDocument();

    const result = await run(container, { rules: { "color-contrast": { enabled: false } } });
    expect(result.violations).toEqual([]);
  });

  it("parses natural language into a confirmation-only draft without guessing missing money", async () => {
    const fetchMock = connectedFetch();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<AppRoutes initialPath="/client/advanced" />);

    expect(await screen.findByRole("heading", { name: "先形成草稿，再逐项确认" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "解析为待确认草稿" }));
    expect(await screen.findByText("夫妻月工资合计")).toBeInTheDocument();
    expect(screen.getByDisplayValue("30000.00")).toBeInTheDocument();
    expect(screen.getByText(/房贷余额/)).toBeInTheDocument();
    expect(screen.getByText(/月供不能推导贷款余额/)).toBeInTheDocument();

    const confirmationGroup = screen.getByRole("group", { name: "勾选并核对每一项" });
    for (const checkbox of within(confirmationGroup).getAllByRole("checkbox")) {
      await user.click(checkbox);
    }
    await user.click(screen.getByRole("button", { name: "确认已勾选字段" }));
    expect(await screen.findByText("提取项已确认")).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([input]) => String(input).endsWith("/confirm"))).toBe(true);
  });

  it("runs and exposes the real nine-step governed chain on the risk portal", async () => {
    const fetchMock = connectedFetch();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<AppRoutes initialPath="/risk" />);

    expect(await screen.findByRole("heading", { name: "每一步都有工具约束、数据契约、禁令和审计" })).toBeInTheDocument();
    expect(screen.getByText(/尚无真实调用链/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "运行可信编排" }));
    expect(await screen.findByText("终检通过")).toBeInTheDocument();
    for (const agent of agentCatalogFixture.agents) {
      expect(screen.getByText(agent.name)).toBeInTheDocument();
    }
    expect(screen.getByText(/数字引用 1 · 政策切片 1/)).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([input]) => String(input).endsWith("/trust-orchestrations"))).toBe(true);
  });

  it("renders the advisor queue, three-plan matrix and shared immutable version rail", async () => {
    const fetchMock = connectedFetch();
    vi.stubGlobal("fetch", fetchMock);
    render(<AppRoutes initialPath="/advisor" />);

    expect(await screen.findByRole("heading", { name: "从面谈底稿推进到合规与客户确认" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "客户经理家庭队列，可横向滚动" })).toBeInTheDocument();
    expect(await screen.findByText("应急储备不足")).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "顾问端三方案对比，可横向滚动" })).getAllByRole("radio")).toHaveLength(3);
    expect(within(screen.getByRole("list", { name: "方案八状态" })).getAllByRole("listitem")).toHaveLength(8);
    expect(screen.getByText(/信用卡额度计入资产/)).toBeInTheDocument();

    const advisorRequest = fetchMock.mock.calls.find(([input]) => String(input).endsWith("/api/v1/advisor/households"));
    expect(advisorRequest).toBeDefined();
    expect(new Headers(advisorRequest?.[1]?.headers).get("X-Actor-Role")).toBe("advisor");

    expect(screen.queryByLabelText("模拟账号")).not.toBeInTheDocument();
  });

  it("lets the advisor generate and inspect the same formal eight-chapter snapshot", async () => {
    vi.stubGlobal("fetch", connectedFetch());
    const user = userEvent.setup();
    render(<AppRoutes initialPath="/advisor" />);

    expect(await screen.findByRole("heading", { name: "客户与顾问读取同一份报告快照" })).toBeInTheDocument();
    await user.click(await screen.findByRole("button", { name: "生成完整八章规划书" }));
    const directory = await screen.findByRole("list", { name: "正式规划书八章目录" });
    expect(within(directory).getAllByRole("listitem")).toHaveLength(8);
    expect(screen.getByRole("button", { name: "导出 HTML" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "导出 PDF" })).toBeInTheDocument();
    expect(screen.getByText(/正式规划书 R1 已生成/)).toBeInTheDocument();
  });

  it("explains compliance warnings and replays any selected version without mutation", async () => {
    const fetchMock = connectedFetch();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<AppRoutes initialPath="/risk" />);

    expect(await screen.findByRole("heading", { name: "从阻断原因回到每一条证据" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "规则允许进入人工复核" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "这次决定，当时依据了什么" })).toBeInTheDocument();
    expect(screen.getByText("8 份快照")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "合规控制矩阵，可横向滚动" })).toBeInTheDocument();
    expect(screen.getByText("模型、Prompt、规则、知识、产品与方案")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "回放投诉场景" }));
    expect(await screen.findByText(/完整性 verified/)).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([input]) => String(input).endsWith("/complaint-replays"))).toBe(true);
    await user.click(screen.getByRole("button", { name: "使用冻结快照回放" }));
    expect(await screen.findByText(/未读取最新产品资料/)).toBeInTheDocument();
  });

  it("shows the compliance reviewer a read-only verified formal-report generation chain", async () => {
    vi.stubGlobal("fetch", connectedFetch());
    render(<AppRoutes initialPath="/risk" />);

    expect(await screen.findByRole("heading", { name: "快照、版本、哈希与触发原因" })).toBeInTheDocument();
    const chain = await screen.findByRole("list", { name: "正式报告不可变版本链" });
    expect(within(chain).getAllByRole("listitem")).toHaveLength(2);
    expect(screen.getByText("哈希链已验证")).toBeInTheDocument();
    expect(screen.getByText("3 条关联审计事件")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "生成完整八章规划书" })).not.toBeInTheDocument();
  });

  it("shows only a compliance-reviewed version before client typed confirmation", async () => {
    const baseFetch = connectedFetch();
    const complianceVersion = {
      ...workflowFixture.current,
      id: "workflow-version-00000000000000000000000006",
      version_number: 6,
      prior_version_id: workflowFixture.current.id,
      state: "compliance_reviewed" as const,
      action: "compliance_approve" as const,
      actor_id: "redacted-for-client",
      actor_role: "compliance" as const,
      compliance_decision: "approved",
      request_id: "redacted-for-client",
      before_hash: workflowFixture.current.after_hash,
      after_hash: "6".repeat(64),
      is_current: true,
    };
    const clientWorkflow = {
      ...workflowFixture,
      current: complianceVersion,
      versions: [complianceVersion],
      next_actions: ["customer_confirm" as const],
    };
    const confirmedVersion = {
      ...complianceVersion,
      id: "workflow-version-00000000000000000000000007",
      version_number: 7,
      state: "customer_confirmed" as const,
      action: "customer_confirm" as const,
      actor_role: "client" as const,
      customer_confirmation: { signature_status: "confirmed", signer_hint: "李***" },
    };
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/v1/households/household-b/plan-workflows/current")) {
        return Promise.resolve(jsonResponse(clientWorkflow));
      }
      if (url.endsWith(`/api/v1/plan-workflows/${workflowFixture.workflow_id}/actions`)) {
        return Promise.resolve(jsonResponse({
          ...clientWorkflow,
          current: confirmedVersion,
          versions: [confirmedVersion],
          next_actions: [],
        }));
      }
      return baseFetch(input, init);
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<AppRoutes initialPath="/client/advanced" />);

    await openClientTask(user, "家庭规划书");
    expect(await screen.findByRole("heading", { name: "方案审核与客户确认" })).toBeInTheDocument();
    expect(screen.getByText("合规已复核 · V6")).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "方案八状态" })).toBeInTheDocument();
    await user.click(screen.getByRole("checkbox", { name: /我已阅读风险/ }));
    await user.click(screen.getByRole("checkbox", { name: /我理解全部银行接口/ }));
    await user.click(screen.getByRole("checkbox", { name: /我理解方案不承诺保本/ }));
    await user.type(screen.getByLabelText("演示签署姓名"), "李先生");
    await user.click(screen.getByRole("button", { name: "确认当前方案版本" }));
    expect(await screen.findByText(/客户已逐项确认/)).toBeInTheDocument();
    const confirmationRequest = fetchMock.mock.calls.find(([input]) => String(input).endsWith("/actions"));
    expect(new Headers(confirmationRequest?.[1]?.headers).get("X-Actor-Role")).toBe("client");
  });
});
