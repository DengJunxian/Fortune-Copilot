import { run } from "axe-core";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { FamilyEnterprisePage } from "../pages/FamilyEnterprisePage";
import { RouterProvider } from "../router/RouterProvider";
import { familyEnterpriseFixture } from "./familyEnterpriseFixture";

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

describe("FamilyEnterprisePage", () => {
  it("shows the hero family-enterprise dependency and refreshes it from source", async () => {
    const user = userEvent.setup();
    let viewRequests = 0;
    vi.stubGlobal("fetch", vi.fn((request: RequestInfo | URL) => {
      const url = String(request);
      if (url.includes("/households?page=")) {
        return Promise.resolve(jsonResponse({
          items: [{ id: "household-b", code: "DEMO_B", name: "成长三口之家" }],
        }));
      }
      if (url.endsWith("/family-enterprise-view")) {
        viewRequests += 1;
        return Promise.resolve(jsonResponse(familyEnterpriseFixture));
      }
      return Promise.resolve(jsonResponse({ error: { message: "未匹配请求" } }, 404));
    }));

    const { container } = render(
      <RouterProvider initialPath="/wealth/family-enterprise">
        <FamilyEnterprisePage />
      </RouterProvider>,
    );

    expect(await screen.findByRole("heading", { name: "家庭资产与企业资产，合在一张底稿里看" })).toBeInTheDocument();
    expect(screen.getAllByText("高 Enterprise Dependency").length).toBeGreaterThan(0);
    expect(screen.getAllByText("¥17,000,000").length).toBeGreaterThan(0);
    expect(screen.getByText("不建议新增权益风险")).toBeInTheDocument();
    expect(screen.getByText(/个人保证/)).toBeInTheDocument();
    expect(screen.getByText(/首次公开发行/)).toBeInTheDocument();
    expect(screen.getByText(/不是监管评级、征信评分或企业估值结论/)).toBeInTheDocument();
    expect(viewRequests).toBe(1);

    await user.click(screen.getByRole("button", { name: /重算家企暴露/ }));
    await waitFor(() => expect(viewRequests).toBe(2));

    const results = await run(container, {
      rules: { "color-contrast": { enabled: false } },
    });
    expect(results.violations.map((violation) => ({
      id: violation.id,
      targets: violation.nodes.map((node) => node.target),
    }))).toEqual([]);
  });

  it("does not fabricate enterprise values when the service fails", async () => {
    vi.stubGlobal("fetch", vi.fn((request: RequestInfo | URL) => {
      if (String(request).includes("/households?page=")) {
        return Promise.resolve(jsonResponse({
          items: [{ id: "household-b", code: "DEMO_B", name: "成长三口之家" }],
        }));
      }
      return Promise.resolve(jsonResponse({
        error: { message: "家企引擎暂不可用" },
      }, 503));
    }));

    render(
      <RouterProvider initialPath="/wealth/family-enterprise">
        <FamilyEnterprisePage />
      </RouterProvider>,
    );

    expect(await screen.findByRole("heading", { name: "家企财富视图暂时无法读取" }))
      .toBeInTheDocument();
    expect(screen.getByText(/不会用模拟企业或估值替代缺失资料/)).toBeInTheDocument();
    expect(screen.queryByText("¥17,000,000")).not.toBeInTheDocument();
  });
});
