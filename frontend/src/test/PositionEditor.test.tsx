import { run } from "axe-core";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { PositionEditor } from "../components/wealth/PositionEditor";
import { RouterProvider } from "../router/RouterProvider";
import { financialGraphFixture, graphPositionFixture } from "./financialGraphFixture";

function jsonResponse(payload: unknown, status = 200): Pick<Response, "ok" | "status" | "json"> {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => payload,
  };
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("PositionEditor", () => {
  it("loads the compatibility projection and lets a client refine an existing position", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn((_: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === "PATCH") {
        return Promise.resolve(jsonResponse({
          ...graphPositionFixture,
          name: "三年期家庭备用金存款",
          version: 2,
        }));
      }
      return Promise.resolve(jsonResponse(financialGraphFixture));
    });
    vi.stubGlobal("fetch", fetchMock);
    const onContinue = vi.fn();

    const { container } = render(
      <RouterProvider initialPath="/planning">
        <PositionEditor
          householdId="household-fixture"
          onBack={vi.fn()}
          onContinue={onContinue}
          showEnterpriseBridge
        />
      </RouterProvider>,
    );

    expect(await screen.findByRole("heading", { name: "完善账户与持仓细节" })).toBeInTheDocument();
    expect(screen.getByText("三年期定期存款")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "补充企业关联" })).toHaveAttribute(
      "href",
      "/wealth/family-enterprise",
    );
    await user.click(screen.getByRole("button", { name: /完善/ }));
    const nameInput = screen.getByRole("textbox", { name: "资产名称" });
    await user.clear(nameInput);
    await user.type(nameInput, "三年期家庭备用金存款");
    await user.click(screen.getByRole("button", { name: "保存修改" }));

    expect(await screen.findByText("资产细节已更新。")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/financial-graph/positions/position-fixture"),
      expect.objectContaining({ method: "PATCH" }),
    );
    await user.click(screen.getByRole("button", { name: "继续查看财务分析" }));
    expect(onContinue).toHaveBeenCalledTimes(1);

    const results = await run(container, {
      rules: { "color-contrast": { enabled: false } },
    });
    expect(results.violations).toHaveLength(0);
  });

  it("keeps the planning journey usable when the optional graph cannot load", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new Error("当前环境尚未启用"))));
    const user = userEvent.setup();
    const onContinue = vi.fn();
    render(
      <RouterProvider initialPath="/planning">
        <PositionEditor
          householdId="household-fixture"
          onBack={vi.fn()}
          onContinue={onContinue}
        />
      </RouterProvider>,
    );

    expect(await screen.findByRole("heading", { name: "精细资产暂时不可用" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "跳过并继续" }));
    await waitFor(() => expect(onContinue).toHaveBeenCalledTimes(1));
  });
});
