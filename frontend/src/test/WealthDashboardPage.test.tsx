import { run } from "axe-core";
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { WealthDashboardPage } from "../pages/WealthDashboardPage";
import { RouterProvider } from "../router/RouterProvider";
import { wealthNeedsFixture } from "./clientProfileFixture";
import { financialFixture } from "./financialFixture";
import { eligibleCapitalFixture, liabilityCalendarFixture } from "./liabilityFixture";
import { emptyTimelineFixture, wealthTwinFixture } from "./persistentTwinFixture";

function jsonResponse(payload: unknown, status = 200): Pick<Response, "ok" | "status" | "json"> {
  return { ok: status >= 200 && status < 300, status, json: async () => payload };
}

afterEach(() => {
  vi.restoreAllMocks();
  window.sessionStorage.clear();
});

describe("WealthDashboardPage", () => {
  it("answers the four first-fold questions from deterministic household evidence", async () => {
    vi.stubGlobal("fetch", vi.fn((request: RequestInfo | URL) => {
      const url = String(request);
      if (url.includes("/households?page=")) return Promise.resolve(jsonResponse({ items: [{ id: "household-b", code: "DEMO_B", name: "成长三口之家" }] }));
      if (url.endsWith("/financial-analysis")) return Promise.resolve(jsonResponse(financialFixture));
      if (url.endsWith("/wealth-needs")) return Promise.resolve(jsonResponse(wealthNeedsFixture));
      if (url.endsWith("/liability-calendar")) return Promise.resolve(jsonResponse(liabilityCalendarFixture));
      if (url.endsWith("/eligible-capital")) return Promise.resolve(jsonResponse(eligibleCapitalFixture));
      if (url.endsWith("/wealth-twin")) return Promise.resolve(jsonResponse(wealthTwinFixture));
      if (url.endsWith("/event-timeline")) return Promise.resolve(jsonResponse(emptyTimelineFixture));
      return Promise.resolve(jsonResponse({ error: { message: "未匹配请求" } }, 404));
    }));

    const { container } = render(<RouterProvider initialPath="/wealth"><WealthDashboardPage /></RouterProvider>);

    expect(await screen.findByRole("heading", { name: /今天先看最重要的四件事/ })).toBeInTheDocument();
    expect(await screen.findByText("家庭现在安全吗？")).toBeInTheDocument();
    expect(screen.getByText("目标还有多少缺口？")).toBeInTheDocument();
    expect(screen.getByText("下一笔钱先做什么？")).toBeInTheDocument();
    expect(screen.getByText("最近值得重规划吗？")).toBeInTheDocument();
    expect(screen.getByText("¥110万")).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "财富需要优先顺序" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "持续监控提醒" })).toBeInTheDocument();

    const results = await run(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations).toEqual([]);
  });

  it("does not fabricate a dashboard when all core services fail", async () => {
    vi.stubGlobal("fetch", vi.fn((request: RequestInfo | URL) => {
      if (String(request).includes("/households?page=")) return Promise.resolve(jsonResponse({ items: [{ id: "household-b", code: "DEMO_B", name: "成长三口之家" }] }));
      return Promise.resolve(jsonResponse({ error: { message: "服务不可用" } }, 503));
    }));
    render(<RouterProvider initialPath="/wealth"><WealthDashboardPage /></RouterProvider>);
    expect(await screen.findByRole("heading", { name: "家庭财富总览暂时无法读取" })).toBeInTheDocument();
    expect(screen.queryByText("¥110万")).not.toBeInTheDocument();
  });
});
