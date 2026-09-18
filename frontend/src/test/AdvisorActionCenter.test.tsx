import { run } from "axe-core";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AdvisorActionCenter } from "../components/advisor/AdvisorActionCenter";
import { changedWealthTwinFixture } from "./persistentTwinFixture";

function jsonResponse(payload: unknown): Pick<Response, "ok" | "status" | "json"> {
  return { ok: true, status: 200, json: async () => payload };
}

const actionItem = {
  trigger_id: "trigger-1",
  household_id: "household-b",
  household_code: "DEMO_B",
  household_name: "成长三口之家",
  trigger_type: "cashflow_deterioration",
  urgency: "critical",
  reason: "收入下降后应急储备覆盖不足",
  required_role: "advisor",
  follow_up_due: "2026-08-11",
  status: "open",
  action_item_id: "action-1",
  action_code: "review-cashflow",
  action_type: "review",
  title: "核对收入变化与应急储备",
  do_not_sell_flag: true,
  required_specialist: null,
  evidence: { metric: "emergency_reserve_months", threshold: "6" },
} as const;

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("AdvisorActionCenter", () => {
  it("groups triggers and expands the full evidence-to-conversation chain", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(new Date("2026-08-11T08:00:00Z"));
    vi.stubGlobal("fetch", vi.fn((request: RequestInfo | URL) => {
      const url = String(request);
      if (url.endsWith("/advisor/action-center")) return Promise.resolve(jsonResponse({ items: [actionItem], open_count: 1, overdue_count: 0, boundary: "仅生成规划跟进，不生成销售指令。" }));
      if (url.endsWith("/advisor/households")) return Promise.resolve(jsonResponse({ generated_at: "2026-08-11T08:00:00Z", calculation_source: "deterministic_advisor_queue", items: [{ household_id: "household-b", household_code: "DEMO_B", household_name: "成长三口之家" }, { household_id: "household-c", household_code: "DEMO_C", household_name: "稳健退休家庭" }] }));
      if (url.endsWith("/households/household-b/wealth-twin")) return Promise.resolve(jsonResponse(changedWealthTwinFixture));
      throw new Error(`unexpected fetch: ${url}`);
    }));
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    const { container } = render(<AdvisorActionCenter />);

    const critical = await screen.findByRole("heading", { name: "Critical" });
    expect(critical).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "No Action Required" })).toBeInTheDocument();
    expect(screen.getByText("稳健退休家庭")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /成长三口之家/ }));
    const detail = await screen.findByRole("region", { name: "成长三口之家行动证据" });
    for (const title of ["Why Now · 为什么现在", "What Changed · 发生了什么", "What Matters · 影响什么", "Suggested Discussion · 建议沟通", "What Not To Sell · 当前不适合推荐什么"]) {
      expect(within(detail).getByRole("heading", { name: title })).toBeInTheDocument();
    }
    expect(within(detail).getByText(/不要推荐新增投资产品/)).toBeInTheDocument();
    expect(within(detail).getByText(/Evidence · 查看触发证据/)).toBeInTheDocument();
    const results = await run(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations).toEqual([]);
  });
});
