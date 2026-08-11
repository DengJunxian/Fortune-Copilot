import { run } from "axe-core";
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { FamilyNeedsPage } from "../pages/FamilyNeedsPage";
import { GlobalExposurePage } from "../pages/GlobalExposurePage";
import { RetirementPlanPage } from "../pages/RetirementPlanPage";
import { RouterProvider } from "../router/RouterProvider";
import {
  currencyFixture,
  emptyFamilySpecializedFixture,
  familySpecializedFixture,
  retirementFixture,
} from "./specializedCfsFixture";

function jsonResponse(payload: unknown, status = 200): Pick<Response, "ok" | "status" | "json"> {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => payload,
  };
}

function householdPayload(id: string, code: string, name: string) {
  return { items: [{ id, code, name }] };
}

afterEach(() => {
  vi.restoreAllMocks();
  window.history.replaceState({}, "", "/");
  window.sessionStorage.clear();
});

describe("specialized CFS pages", () => {
  it("shows the retirement floor, entitlement ledger and professional route", async () => {
    vi.stubGlobal("fetch", vi.fn((request: RequestInfo | URL) => {
      const url = String(request);
      if (url.includes("/households?page=")) {
        return Promise.resolve(jsonResponse(householdPayload("household-c", "DEMO_C", "退休准备家庭")));
      }
      if (url.endsWith("/retirement-plan")) {
        return Promise.resolve(jsonResponse(retirementFixture));
      }
      return Promise.resolve(jsonResponse({}, 404));
    }));

    const { container } = render(
      <RouterProvider initialPath="/wealth/retirement"><RetirementPlanPage /></RouterProvider>,
    );
    expect(await screen.findByRole("heading", { name: "收入与长寿缺口" })).toBeInTheDocument();
    expect(screen.getByText("¥16.2万")).toBeInTheDocument();
    expect(screen.getByText("基本养老与社保")).toBeInTheDocument();
    expect(screen.getByText("养老规划专家")).toBeInTheDocument();
    expect(screen.getByText(/不承诺养老金待遇/)).toBeInTheDocument();
    const results = await run(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations.map((violation) => violation.id)).toEqual([]);
  });

  it("keeps currency amounts in source currency and shows both directions", async () => {
    vi.stubGlobal("fetch", vi.fn((request: RequestInfo | URL) => {
      const url = String(request);
      if (url.includes("/households?page=")) {
        return Promise.resolve(jsonResponse(householdPayload("household-b", "DEMO_B", "成长三口之家")));
      }
      if (url.endsWith("/currency-exposures")) {
        return Promise.resolve(jsonResponse(currencyFixture));
      }
      return Promise.resolve(jsonResponse({}, 404));
    }));

    render(<RouterProvider initialPath="/wealth/global"><GlobalExposurePage /></RouterProvider>);
    expect(await screen.findByRole("heading", { name: "识别到需要复核的币种暴露" })).toBeInTheDocument();
    expect(screen.getAllByText("USD")).toHaveLength(3);
    expect(screen.getAllByText("$30万")).toHaveLength(2);
    expect(screen.getByText("教育责任")).toBeInTheDocument();
    expect(screen.getByText("跨境服务专家")).toBeInTheDocument();
    expect(screen.getByText(/不提供法律、税务/)).toBeInTheDocument();
  });

  it("renders only confirmed family needs and philanthropy goals", async () => {
    vi.stubGlobal("fetch", vi.fn((request: RequestInfo | URL) => {
      const url = String(request);
      if (url.includes("/households?page=")) {
        return Promise.resolve(jsonResponse(householdPayload("household-c", "DEMO_C", "成熟家庭")));
      }
      if (url.endsWith("/trust-succession-needs")) {
        return Promise.resolve(jsonResponse(familySpecializedFixture.trust));
      }
      if (url.endsWith("/philanthropy-goals")) {
        return Promise.resolve(jsonResponse(familySpecializedFixture.philanthropy));
      }
      return Promise.resolve(jsonResponse({}, 404));
    }));

    render(<RouterProvider initialPath="/wealth/family"><FamilyNeedsPage /></RouterProvider>);
    expect(await screen.findByRole("heading", { name: "家庭照护与延续安排需要专业复核" })).toBeInTheDocument();
    expect(screen.getByText("未成年家庭成员")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "已确认的公益目标" })).toBeInTheDocument();
    expect(screen.getByText("乡村青少年金融教育")).toBeInTheDocument();
    expect(screen.queryByText(/信托中心/)).not.toBeInTheDocument();
  });

  it("does not default a young single household into a trust experience", async () => {
    vi.stubGlobal("fetch", vi.fn((request: RequestInfo | URL) => {
      const url = String(request);
      if (url.includes("/households?page=")) {
        return Promise.resolve(jsonResponse(householdPayload("household-a", "DEMO_A", "职场起步家庭")));
      }
      if (url.endsWith("/trust-succession-needs")) {
        return Promise.resolve(jsonResponse(emptyFamilySpecializedFixture.trust));
      }
      if (url.endsWith("/philanthropy-goals")) {
        return Promise.resolve(jsonResponse(emptyFamilySpecializedFixture.philanthropy));
      }
      return Promise.resolve(jsonResponse({}, 404));
    }));

    render(<RouterProvider initialPath="/wealth/family"><FamilyNeedsPage /></RouterProvider>);
    expect(await screen.findByRole("heading", { name: "当前没有已确认的复杂家庭安排" })).toBeInTheDocument();
    expect(screen.queryByText(/信托中心/)).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "已确认的公益目标" })).not.toBeInTheDocument();
  });
});
