import { run } from "axe-core";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { WealthProfilePage } from "../pages/WealthProfilePage";
import {
  clientProfileFixture,
  wealthNeedsFixture,
} from "./clientProfileFixture";

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

describe("WealthProfilePage", () => {
  it("shows the dynamic profile, ordered needs and client-safe boundary", async () => {
    const user = userEvent.setup();
    const households = [
      { id: "household-a", code: "DEMO_A", name: "青年起步家庭" },
      { id: "household-b", code: "DEMO_B", name: "成长三口之家" },
    ];
    const fetchMock = vi.fn((request: RequestInfo | URL, init?: RequestInit) => {
      const url = String(request);
      if (url.includes("/households?page=")) {
        return Promise.resolve(jsonResponse({ items: households }));
      }
      if (url.endsWith("/wealth-needs/recalculate") && init?.method === "POST") {
        return Promise.resolve(jsonResponse(wealthNeedsFixture));
      }
      if (url.endsWith("/wealth-needs")) {
        return Promise.resolve(jsonResponse(wealthNeedsFixture));
      }
      if (url.endsWith("/client-profile")) {
        return Promise.resolve(jsonResponse(clientProfileFixture));
      }
      return Promise.resolve(jsonResponse({ error: { message: "未匹配请求" } }, 404));
    });
    vi.stubGlobal("fetch", fetchMock);

    const { container } = render(<WealthProfilePage />);

    expect(await screen.findByRole("heading", { name: "影响规划顺序的四组事实" }))
      .toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "当前家庭" })).toHaveValue("household-b");
    expect(screen.getByText("家庭应急储备")).toBeInTheDocument();
    expect(screen.getByText("财富传承")).toBeInTheDocument();
    expect(screen.getByText("刚性约束")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "这不是营销客群标签" }))
      .toBeInTheDocument();
    expect(screen.queryByText("middle_class_family")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /重新核对画像/ }));
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/wealth-needs/recalculate"),
        expect.objectContaining({ method: "POST" }),
      );
    });

    const results = await run(container, {
      rules: { "color-contrast": { enabled: false } },
    });
    expect(results.violations).toHaveLength(0);
  });

  it("states that no frontend estimate is shown when the profile service fails", async () => {
    vi.stubGlobal("fetch", vi.fn((request: RequestInfo | URL) => {
      if (String(request).includes("/households?page=")) {
        return Promise.resolve(jsonResponse({
          items: [{ id: "household-b", code: "DEMO_B", name: "成长三口之家" }],
        }));
      }
      return Promise.resolve(jsonResponse({
        error: { code: "profile_error", message: "画像服务暂不可用" },
      }, 503));
    }));

    render(<WealthProfilePage />);

    expect(await screen.findByRole("heading", { name: "财富画像暂时无法生成" }))
      .toBeInTheDocument();
    expect(screen.getByText(/不会用前端估算替代后端结果/)).toBeInTheDocument();
  });
});
