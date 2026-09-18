import { run } from "axe-core";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { WealthCFSPage } from "../pages/WealthCFSPage";
import { RouterProvider } from "../router/RouterProvider";
import { cfsFixture } from "./cfsFixture";

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

describe("WealthCFSPage", () => {
  it("requires confirmation and shows the formal no-action decision chain", async () => {
    const user = userEvent.setup();
    let createConfirmation: string | null = null;
    let recalculateCount = 0;
    vi.stubGlobal("fetch", vi.fn((request: RequestInfo | URL, init?: RequestInit) => {
      const url = String(request);
      if (url.includes("/households?page=")) {
        return Promise.resolve(jsonResponse({
          items: [{ id: "household-b", code: "DEMO_B", name: "成长三口之家" }],
        }));
      }
      if (url.endsWith("/cfs-solutions")) {
        createConfirmation = new Headers(init?.headers).get("X-Confirm-Action");
        return Promise.resolve(jsonResponse(cfsFixture, 201));
      }
      if (url.endsWith("/cfs-solutions/solution-b/recalculate")) {
        recalculateCount += 1;
        return Promise.resolve(jsonResponse({
          ...cfsFixture,
          meta: { ...cfsFixture.meta, idempotent_replay: true },
        }));
      }
      return Promise.resolve(jsonResponse({ error: { message: "未匹配请求" } }, 404));
    }));

    const { container } = render(
      <RouterProvider initialPath="/wealth/cfs">
        <WealthCFSPage />
      </RouterProvider>,
    );

    expect(await screen.findByRole("heading", { name: /生成第一版综合方案/ })).toBeInTheDocument();
    const composeButton = screen.getByRole("button", { name: "确认并生成综合方案" });
    expect(composeButton).toBeDisabled();
    await user.click(screen.getByRole("checkbox"));
    expect(composeButton).toBeEnabled();
    await user.click(composeButton);

    expect(await screen.findByRole("heading", { name: "先还债，当前不新增投资" })).toBeInTheDocument();
    expect(screen.getByText("NO_ACTION_REQUIRED")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "当前不新增投资" })).toBeInTheDocument();
    expect(screen.getByText(/0 元组合伪装/)).toBeInTheDocument();
    expect(screen.getAllByText("风险承担能力")).toHaveLength(2);
    expect(screen.getByRole("heading", { name: "Family Risk Profile" })).toBeInTheDocument();
    expect(screen.getByText("风险承受意愿")).toBeInTheDocument();
    expect(screen.getByText("真实行为约束")).toBeInTheDocument();
    expect(screen.getByText("最终家庭风险预算")).toBeInTheDocument();
    expect(screen.getByText(/行为证据只允许保持或下调预算/)).toBeInTheDocument();
    expect(screen.getByText("最短责任期限")).toBeInTheDocument();
    expect(screen.getByText("保障规划专家")).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/\b\d{6}\.(?:OF|SH|SZ)\b/);
    expect(createConfirmation).toBe("create_cfs_solution");

    await user.click(screen.getByRole("button", { name: /核对并重算/ }));
    await waitFor(() => expect(recalculateCount).toBe(1));
    expect(await screen.findByText("家庭事实没有变化，原方案继续有效。")).toBeInTheDocument();

    const results = await run(container, {
      rules: { "color-contrast": { enabled: false } },
    });
    expect(results.violations.map((violation) => violation.id)).toEqual([]);
  });

  it("restores a saved solution without silently composing a new one", async () => {
    window.sessionStorage.setItem("fortune-copilot:cfs-solution:household-b", "solution-b");
    let createCount = 0;
    vi.stubGlobal("fetch", vi.fn((request: RequestInfo | URL, init?: RequestInit) => {
      const url = String(request);
      if (url.includes("/households?page=")) {
        return Promise.resolve(jsonResponse({
          items: [{ id: "household-b", code: "DEMO_B", name: "成长三口之家" }],
        }));
      }
      if (url.endsWith("/cfs-solutions/solution-b") && init?.method !== "POST") {
        return Promise.resolve(jsonResponse(cfsFixture));
      }
      if (init?.method === "POST") createCount += 1;
      return Promise.resolve(jsonResponse({ error: { message: "未匹配请求" } }, 404));
    }));

    render(
      <RouterProvider initialPath="/wealth/cfs">
        <WealthCFSPage />
      </RouterProvider>,
    );

    expect(await screen.findByRole("heading", { name: "先还债，当前不新增投资" })).toBeInTheDocument();
    expect(createCount).toBe(0);
    expect(screen.queryByRole("button", { name: "确认并生成综合方案" })).not.toBeInTheDocument();
  });

  it("shows only specialized modules triggered by the current CFS", async () => {
    window.sessionStorage.setItem("fortune-copilot:cfs-solution:household-b", "solution-b");
    vi.stubGlobal("fetch", vi.fn((request: RequestInfo | URL) => {
      const url = String(request);
      if (url.includes("/households?page=")) {
        return Promise.resolve(jsonResponse({
          items: [{ id: "household-b", code: "DEMO_B", name: "成长三口之家" }],
        }));
      }
      if (url.endsWith("/cfs-solutions/solution-b")) {
        return Promise.resolve(jsonResponse({
          ...cfsFixture,
          components: [
            ...cfsFixture.components,
            {
              ...cfsFixture.components[0],
              id: "component-retirement",
              component_type: "retirement",
            },
            {
              ...cfsFixture.components[0],
              id: "component-trust",
              component_type: "trust",
            },
          ],
        }));
      }
      return Promise.resolve(jsonResponse({ error: { message: "未匹配请求" } }, 404));
    }));

    render(
      <RouterProvider initialPath="/wealth/cfs">
        <WealthCFSPage />
      </RouterProvider>,
    );

    expect(await screen.findByRole("heading", { name: "按家庭需要展开专业模块" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /退休收入底线/ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /家庭长期安排/ })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /币种与跨境暴露/ })).not.toBeInTheDocument();
  });
});
