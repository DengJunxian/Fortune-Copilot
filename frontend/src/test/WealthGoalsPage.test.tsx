import { run } from "axe-core";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { WealthGoalsPage } from "../pages/WealthGoalsPage";
import { RouterProvider } from "../router/RouterProvider";
import {
  eligibleCapitalFixture,
  liabilityCalendarFixture,
} from "./liabilityFixture";

function jsonResponse(payload: unknown, status = 200): Pick<Response, "ok" | "status" | "json"> {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => payload,
  };
}

afterEach(() => {
  vi.restoreAllMocks();
  window.history.replaceState({}, "", "/");
  window.sessionStorage.clear();
});

describe("WealthGoalsPage", () => {
  it("shows dated liabilities, funding gaps and the auditable ELTC bridge", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn((request: RequestInfo | URL) => {
      const url = String(request);
      if (url.includes("/households?page=")) {
        return Promise.resolve(jsonResponse({
          items: [
            { id: "household-a", code: "DEMO_A", name: "青年起步家庭" },
            { id: "household-b", code: "DEMO_B", name: "成长三口之家" },
          ],
        }));
      }
      if (url.endsWith("/liability-calendar")) {
        return Promise.resolve(jsonResponse(liabilityCalendarFixture));
      }
      if (url.endsWith("/eligible-capital")) {
        return Promise.resolve(jsonResponse(eligibleCapitalFixture));
      }
      return Promise.resolve(jsonResponse({ error: { message: "未匹配请求" } }, 404));
    });
    vi.stubGlobal("fetch", fetchMock);

    const { container } = render(
      <RouterProvider initialPath="/wealth/goals"><WealthGoalsPage /></RouterProvider>,
    );

    expect(await screen.findByRole("heading", { name: "目标不再只是终点金额" }))
      .toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "当前家庭" })).toHaveValue("household-b");
    expect(screen.getByRole("heading", { name: "每一笔责任何时需要资金" }))
      .toBeInTheDocument();
    expect(screen.getByText("第 4 / 4 期")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "长期可投资资本 ELTC" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "哪些钱可以投资？" })).toBeInTheDocument();
    expect(screen.getByText("为什么不是全部金融资产？")).toBeInTheDocument();
    expect(screen.getByText("暂不进入长期投资")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "专业" }));
    expect(screen.getByText(/公式版本.*输入哈希/)).toBeInTheDocument();
    expect(screen.getByText(/最低工资趋势只进入 IAI/)).toBeInTheDocument();
    expect(screen.getAllByText("锁定制度资产").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("未覆盖")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /重新计算责任/ }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.filter(([request]) =>
        String(request).endsWith("/eligible-capital"))).toHaveLength(2);
    });

    const results = await run(container, {
      rules: { "color-contrast": { enabled: false } },
    });
    expect(results.violations.map((violation) => ({
      id: violation.id,
      targets: violation.nodes.map((node) => node.target),
    }))).toEqual([]);
  });

  it("does not substitute a fixed threshold when the service fails", async () => {
    vi.stubGlobal("fetch", vi.fn((request: RequestInfo | URL) => {
      if (String(request).includes("/households?page=")) {
        return Promise.resolve(jsonResponse({
          items: [{ id: "household-b", code: "DEMO_B", name: "成长三口之家" }],
        }));
      }
      return Promise.resolve(jsonResponse({
        error: { message: "ELTC 服务暂不可用" },
      }, 503));
    }));

    render(
      <RouterProvider initialPath="/wealth/goals"><WealthGoalsPage /></RouterProvider>,
    );

    expect(await screen.findByRole("heading", { name: "责任与 ELTC 暂时无法生成" }))
      .toBeInTheDocument();
    expect(screen.getByText(/不会用固定 30 万或 100 万门槛替代后端结果/))
      .toBeInTheDocument();
  });
});
