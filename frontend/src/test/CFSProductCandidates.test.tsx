import { run } from "axe-core";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CFSProductCandidates } from "../components/wealth/CFSProductCandidates";
import { productOntologyFixture } from "./productOntologyFixture";

describe("CFSProductCandidates", () => {
  it("treats no product as a first-class outcome and discloses buy-side constraints", async () => {
    const { container } = render(
      <CFSProductCandidates composition={productOntologyFixture} />,
    );

    expect(screen.getByRole("heading", { name: "从行动映射候选，不把产品当成方案。" })).toBeInTheDocument();
    expect(screen.getByText("NO PRODUCT")).toBeInTheDocument();
    expect(screen.getByText(/专业服务本身就是正确承接方式/)).toBeInTheDocument();
    expect(screen.getByText(/005102/)).toBeInTheDocument();
    expect(screen.getByText("客户总成本")).toBeInTheDocument();
    expect(screen.getByText("待渠道补齐")).toBeInTheDocument();
    expect(screen.getByText("利益冲突披露")).toBeInTheDocument();
    expect(screen.getByText(/公开列示不等于当日可售/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /购买|申购|执行/ })).not.toBeInTheDocument();

    const results = await run(container, {
      rules: { "color-contrast": { enabled: false } },
    });
    expect(results.violations.map((violation) => violation.id)).toEqual([]);
  });

  it("makes stale catalog education-only status explicit", () => {
    render(
      <CFSProductCandidates composition={{
        ...productOntologyFixture,
        catalog_stale: true,
      }} />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("只能用于教育比较");
  });
});
