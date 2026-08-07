import { describe, expect, it } from "vitest";
import { safeExternalUrl } from "../utils/format";

describe("security utilities", () => {
  it("only turns HTTP(S) citation sources into clickable URLs", () => {
    expect(safeExternalUrl("https://www.gov.cn/policy")).toBe("https://www.gov.cn/policy");
    expect(safeExternalUrl("http://localhost/source")).toBe("http://localhost/source");
    expect(safeExternalUrl("javascript:alert(1)")).toBeNull();
    expect(safeExternalUrl("data:text/html,<script>alert(1)</script>")).toBeNull();
    expect(safeExternalUrl("local://controlled-snapshot")).toBeNull();
  });
});
