import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AppRoutes } from "../App";
import type { MetricResult } from "../api/financial";
import { financialFixture } from "./financialFixture";
import { fundAdvisoryFixture } from "./fundAdvisoryFixture";
import { planningFixture } from "./planningFixture";

function response(payload: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => payload,
  } as Response;
}

function metric(id: string, name: string, result: string, formula: string): MetricResult {
  return {
    ...financialFixture.metrics[1]!,
    metric_id: id,
    name,
    result,
    numerator: result,
    formula,
    substitution: `${formula} = ${result}`,
    unit: "ratio",
  };
}

const analysis = {
  ...financialFixture,
  profile: {
    ...financialFixture.profile,
    name: "张先生家庭财富规划",
    members: [{
      id: "member-1",
      display_name: "张先生",
      relationship: "本人",
      age: 35,
      occupation: "工程师",
      employment_stability: "high",
      health_risk_level: "low",
    }],
  },
  metrics: [
    financialFixture.metrics.find((item) => item.metric_id === "liquidity_reserve_months")!,
    financialFixture.metrics.find((item) => item.metric_id === "debt_to_asset_ratio")!,
    financialFixture.metrics.find((item) => item.metric_id === "savings_ratio")!,
    metric("debt_service_burden_ratio", "财务负担率", "0.200000", "年度还本付息 / 年收入"),
    metric("investable_assets_to_net_worth", "投资与净资产比率", "0.210000", "可投资资产 / 净资产"),
    metric("property_to_assets_ratio", "房产与资产比率", "0.842105", "房产 / 总资产"),
  ],
};

const explanations = analysis.metrics.map((item) => ({
  metric_id: item.metric_id,
  interpretation: `${item.name}反映了当前家庭的财务结构。`,
  focus: "结合家庭阶段和目标期限观察。",
  next_step: "按照目标日期持续准备资金。",
}));

describe("household planning journey", () => {
  beforeEach(() => {
    window.localStorage?.clear();
    vi.stubGlobal("scrollTo", vi.fn());
    vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => {
      callback(0);
      return 1;
    });
    HTMLElement.prototype.scrollIntoView = vi.fn();
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/api/v1/meta/capabilities")) return Promise.resolve(response({ version: "1.0", runtime_mode: "service", mock_mode: false, portals: [] }));
      if (url.endsWith("/api/v1/wealth-planning/cases")) return Promise.resolve(response({ household_id: "household-b", analysis }, 201));
      if (url.endsWith("/ratio-explanations")) return Promise.resolve(response({ provider: "deepseek", model: "deepseek-v4-flash", used_external_model: true, degraded: false, calculation_source: "deterministic_tools", items: explanations }));
      if (url.endsWith("/plan-narrative")) return Promise.resolve(response({
        provider: "deepseek",
        model: "deepseek-chat",
        used_external_model: true,
        degraded: false,
        calculation_source: "deterministic_tools",
        planning: planningFixture,
        narrative: {
          family_analysis: "家庭成员与责任已纳入本次规划。",
          goal_analysis: "目标应按日期和重要程度依次准备。",
          major_expense_analysis: "大额支出与日常消费分开管理。",
          statement_analysis: "资产负债和年度结余共同决定可规划空间。",
          ratio_analysis_summary: "六项比率应结合家庭阶段逐项判断。",
          four_account_analysis: "先完成生活、保障和近期目标，再安排长期增长。",
          review_triggers: ["家庭收入或目标发生明显变化"],
        },
      }));
      if (url.includes("/fund-advisory?")) return Promise.resolve(response(fundAdvisoryFixture));
      if (url.endsWith("/goals")) return Promise.resolve(response({}, 201));
      return Promise.reject(new Error(`unexpected request: ${url}`));
    }));
  });

  it("allows a minor child without occupation details", async () => {
    const user = userEvent.setup();
    render(<AppRoutes initialPath="/planning" />);

    await user.type(
      await screen.findByLabelText(/规划名称/, {}, { timeout: 5_000 }),
      "王女士家庭财富规划",
    );
    await user.type(screen.getByLabelText(/常住地区/), "杭州");
    await user.type(screen.getByLabelText(/^姓名$/), "王女士");
    await user.type(screen.getByLabelText(/出生日期/), "1992-01-01");
    await user.type(screen.getByLabelText(/职业或身份/), "企业职员");
    await user.click(screen.getByRole("button", { name: "添加成员" }));

    const addedMember = screen.getByRole("group", { name: /配偶/ });
    await user.selectOptions(within(addedMember).getByLabelText("与本人关系"), "子女");
    const child = screen.getByRole("group", { name: /子女/ });
    await user.type(within(child).getByLabelText("姓名"), "王小朋友");
    await user.type(within(child).getByLabelText("出生日期"), "2020-01-01");
    await user.click(screen.getByRole("button", { name: "继续填写财务报表" }));

    expect(await screen.findByRole("heading", { name: "把家底和一年收支填清楚" })).toBeInTheDocument();
  });

  it("moves from client profile to six verified ratios and an exact eight-chapter plan", async () => {
    const user = userEvent.setup();
    render(<AppRoutes initialPath="/planning" />);

    await user.type(
      await screen.findByLabelText(/规划名称/, {}, { timeout: 5_000 }),
      "张先生家庭财富规划",
    );
    await user.type(screen.getByLabelText(/常住地区/), "上海");
    await user.type(screen.getByLabelText(/^姓名$/), "张先生");
    await user.type(screen.getByLabelText(/出生日期/), "1990-01-01");
    await user.type(screen.getByLabelText(/职业或身份/), "工程师");
    await user.click(screen.getByRole("button", { name: "继续填写财务报表" }));

    await user.clear(screen.getByLabelText(/本人税后年收入年度金额/));
    await user.type(screen.getByLabelText(/本人税后年收入年度金额/), "360000");
    await user.click(screen.getByRole("button", { name: "生成财务分析" }));

    expect(await screen.findByRole("heading", { name: "财务比率逐项分析" })).toBeInTheDocument();
    expect(screen.getAllByRole("article")).toHaveLength(6);
    expect(screen.getByText("年度还本付息 / 年收入")).toBeInTheDocument();
    await waitFor(() => expect(screen.getAllByText(/反映了当前家庭的财务结构/)).toHaveLength(6));

    await user.click(screen.getByRole("button", { name: /填写理财目标/ }));
    await user.type(screen.getByLabelText("目标名称"), "子女教育准备");
    await user.clear(screen.getByLabelText(/目标金额/));
    await user.type(screen.getByLabelText(/目标金额/), "500000");
    await user.click(screen.getByRole("button", { name: "生成家庭理财规划书" }));

    expect(await screen.findByRole("heading", { name: "张先生家庭财富规划" })).toBeInTheDocument();
    const directory = screen.getByRole("navigation", { name: "规划书目录" });
    expect(within(directory).getAllByRole("button")).toHaveLength(8);
    expect(within(directory).getByRole("button", { name: /01\s+家庭基础情况/ })).toBeInTheDocument();
    expect(within(directory).getByRole("button", { name: /08\s+免责声明/ })).toBeInTheDocument();
    await user.click(within(directory).getByRole("button", { name: /07\s+投资规划建议/ }));
    const chapterHeading = screen.getByRole("heading", { name: "投资规划建议" });
    const activeChapter = chapterHeading.closest("article");
    expect(activeChapter).not.toBeNull();
    expect(within(activeChapter!).getByText("给您的投资说明")).toBeInTheDocument();
    expect(within(activeChapter!).getByText("小额投资学习")).toBeInTheDocument();
    expect(within(activeChapter!).getByRole("heading", { name: "本次先不安排学习资金" })).toBeInTheDocument();
    expect(within(activeChapter!).getByRole("heading", { name: "先看这笔钱的用途，再看基金" })).toBeInTheDocument();
  });
});
