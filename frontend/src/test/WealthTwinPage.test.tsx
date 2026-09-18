import { run } from "axe-core";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { WealthTwinPage } from "../pages/WealthTwinPage";
import { TwinSnapshotReport } from "../components/wealth/TwinSnapshotReport";
import { RouterProvider } from "../router/RouterProvider";
import {
  changedTimelineFixture,
  changedWealthTwinFixture,
  emptyTimelineFixture,
  salaryEventResponseFixture,
  wealthTwinFixture,
} from "./persistentTwinFixture";
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

describe("WealthTwinPage", () => {
  it("binds the required snapshot and CFS version fields without adding a report chapter", () => {
    render(<TwinSnapshotReport twin={wealthTwinFixture} solution={cfsFixture} />);
    expect(screen.getByRole("heading", { name: "这份规划引用了哪一版家庭状态" })).toBeInTheDocument();
    expect(screen.getByText("snapshot-0")).toBeInTheDocument();
    expect(screen.getByText("P1")).toBeInTheDocument();
    expect(screen.getByText("liability-v1")).toBeInTheDocument();
    expect(screen.getByText("CFS 1")).toBeInTheDocument();
    expect(screen.getByText("cfs-decision-hash-0123456789")).toBeInTheDocument();
    expect(screen.getByText(/不新增第九章/)).toBeInTheDocument();
  });

  it("shows persistent state and applies a salary event only through confirmation", async () => {
    const user = userEvent.setup();
    let eventCreated = false;
    const fetchMock = vi.fn((request: RequestInfo | URL, init?: RequestInit) => {
      const url = String(request);
      if (url.includes("/households?page=")) {
        return Promise.resolve(jsonResponse({
          items: [{ id: "household-b", code: "DEMO_B", name: "成长三口之家" }],
        }));
      }
      if (url.endsWith("/life-events") && init?.method === "POST") {
        eventCreated = true;
        expect(init.headers).toMatchObject({ "X-Confirm-Action": "create_life_event" });
        return Promise.resolve(jsonResponse(salaryEventResponseFixture, 201));
      }
      if (url.endsWith("/wealth-twin")) {
        return Promise.resolve(jsonResponse(eventCreated
          ? changedWealthTwinFixture
          : wealthTwinFixture));
      }
      if (url.endsWith("/event-timeline")) {
        return Promise.resolve(jsonResponse(eventCreated
          ? changedTimelineFixture
          : emptyTimelineFixture));
      }
      return Promise.resolve(jsonResponse({ error: { message: "未匹配请求" } }, 404));
    });
    vi.stubGlobal("fetch", fetchMock);

    const { container } = render(
      <RouterProvider initialPath="/wealth/twin"><WealthTwinPage /></RouterProvider>,
    );

    expect(await screen.findByRole("heading", { name: "当前家庭状态" })).toBeInTheDocument();
    expect(screen.getByText("¥360,000")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "工资收入发生变化" })).toBeInTheDocument();
    expect(screen.getByText(/当前快照未绑定 CFS 版本/)).toBeInTheDocument();
    const submit = screen.getByRole("button", { name: "确认并生成新快照" });
    expect(submit).toBeDisabled();
    await user.click(screen.getByRole("checkbox"));
    expect(submit).toBeEnabled();
    await user.click(submit);

    expect(await screen.findByText(/新快照已生成/)).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("¥252,000")).toBeInTheDocument();
      expect(screen.getByText("¥36万 → ¥25.2万")).toBeInTheDocument();
    }, { timeout: 5_000 });
    expect(screen.getByText(/工资收入调整 -30.0%/)).toBeInTheDocument();

    const results = await run(container, {
      rules: { "color-contrast": { enabled: false } },
    });
    expect(results.violations.map((violation) => ({
      id: violation.id,
      targets: violation.nodes.map((node) => node.target),
    }))).toEqual([]);
  }, 15_000);

  it("does not fabricate a snapshot when the service fails", async () => {
    vi.stubGlobal("fetch", vi.fn((request: RequestInfo | URL) => {
      if (String(request).includes("/households?page=")) {
        return Promise.resolve(jsonResponse({
          items: [{ id: "household-b", code: "DEMO_B", name: "成长三口之家" }],
        }));
      }
      return Promise.resolve(jsonResponse({
        error: { message: "快照服务暂不可用" },
      }, 503));
    }));

    render(
      <RouterProvider initialPath="/wealth/twin"><WealthTwinPage /></RouterProvider>,
    );

    expect(await screen.findByRole("heading", { name: "家庭财富孪生暂时无法读取" }))
      .toBeInTheDocument();
    expect(screen.getByText(/不会用模拟值替代缺失快照/)).toBeInTheDocument();
  });
});
