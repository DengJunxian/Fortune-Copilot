import { run } from "axe-core";
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AppRoutes } from "../App";
import { competitionFixture } from "./competitionFixture";

function response(payload: unknown, status = 200): Pick<Response, "ok" | "status" | "json"> {
  return { ok: status >= 200 && status < 300, status, json: async () => payload };
}

afterEach(() => vi.restoreAllMocks());

describe("CompetitionPage", () => {
  it("shows the auditable Shanghai CFS story without claiming a bank connection", async () => {
    vi.stubGlobal("fetch", vi.fn((request: RequestInfo | URL) => {
      const url = String(request);
      if (url.endsWith("/api/v1/competition/demo")) return Promise.resolve(response(competitionFixture));
      if (url.endsWith("/api/v1/meta/capabilities")) {
        return Promise.resolve(response({ version: "1", runtime_mode: "demo", mock_mode: true, database: { status: "ok", detail: "test" }, portals: ["client", "advisor", "risk"], capabilities: [], guardrails: [] }));
      }
      return Promise.resolve(response({}, 404));
    }));

    const { container } = render(<AppRoutes initialPath="/competition" />);

    expect(await screen.findByRole("heading", { name: /每个家庭，都有自己的财富答案/ })).toBeInTheDocument();
    expect(screen.getByText("未连接工行生产系统")).toBeInTheDocument();
    expect(screen.getByText("长期可投资资本 ELTC").nextElementSibling).toHaveTextContent("¥131.7万");
    expect(screen.getByRole("heading", { name: /先确认 ELTC、家庭目标与风险预算/ })).toBeInTheDocument();
    expect(screen.getByText("违规率 0.0%")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "复杂事项交给客户经理。" })).toBeInTheDocument();

    const results = await run(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations).toEqual([]);
  });
});
