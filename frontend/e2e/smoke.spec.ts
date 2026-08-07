import { expect, test, type Page } from "@playwright/test";

// Connected tests share one SQLite demo household and intentionally exercise writes.
test.describe.configure({ mode: "serial" });

async function openClientTask(page: Page, label: string) {
  await page.getByRole("tab", { name: new RegExp(label) }).click();
}

async function openRiskTechnicalEvidence(page: Page) {
  const summary = page.getByText("查看基础禁令与专项对抗证据", { exact: true });
  await summary.click();
}

test("offline demo exposes all three portal routes", async ({ page }) => {
  await page.route("**/api/**", (route) => route.abort("internetdisconnected"));
  const browserErrors: string[] = [];
  const expectedOfflineErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() !== "error") return;
    if (message.text().includes("ERR_INTERNET_DISCONNECTED")) expectedOfflineErrors.push(message.text());
    else browserErrors.push(message.text());
  });
  page.on("pageerror", (error) => browserErrors.push(error.message));

  await page.goto("/");
  await expect(page.getByRole("heading", { name: "先守住家庭安全底线，再安排长期增长" })).toBeVisible();
  await expect(page.getByText("竞赛原型，非中国工商银行官方产品")).toBeVisible();

  await page.getByRole("link", { name: "客户端", exact: true }).click();
  await expect(page.getByRole("heading", { name: "家庭财富驾驶舱" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "财务测算当前不可用" })).toBeVisible();
  await expect(page.getByText(/纯前端模式不会嵌入家庭金额或伪造计算结果/)).toBeVisible();
  await expect(page.getByText("信用卡只作为支付工具，额度不计入资产", { exact: false })).toBeVisible();

  await page.getByRole("link", { name: "顾问端", exact: true }).click();
  await expect(page.getByRole("heading", { name: "客户经理工作台", exact: true })).toBeVisible();

  await page.getByRole("link", { name: "风险端", exact: true }).click();
  await expect(page.getByRole("heading", { name: "风险与审计控制台", exact: true })).toBeVisible();
  await openRiskTechnicalEvidence(page);
  await expect(page.getByText("最低工资不等于 CPI")).toBeVisible();
  expect(expectedOfflineErrors.length).toBeGreaterThan(0);
  expect(browserErrors).toEqual([]);
});

test("keyboard users can reach the main content", async ({ page }) => {
  await page.goto("/client");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "跳到主要内容" })).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("#main-content")).toBeInViewport();
});

test("connected release page runs the complete offline Demo and seven bounded experiments", async ({ page }) => {
  test.skip(!process.env.PLAYWRIGHT_BASE_URL, "requires the connected Compose demo");
  await page.setViewportSize({ width: 1440, height: 900 });
  const externalRequests: string[] = [];
  const browserIssues: string[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (!["127.0.0.1", "localhost"].includes(url.hostname)) externalRequests.push(request.url());
  });
  page.on("console", (message) => {
    if (["error", "warning"].includes(message.type())) browserIssues.push(message.text());
  });
  page.on("pageerror", (error) => browserIssues.push(error.message));

  await page.goto("/demo");
  await expect(page.getByRole("heading", { name: "从一句家庭描述，到八章规划书与可追溯审核" })).toBeVisible();
  await expect(page.getByText("3 个唯一配置签名")).toBeVisible();
  await expect(page.getByRole("table", { name: /A／B／C.*配置签名/ }).locator("tbody tr")).toHaveCount(3);

  await page.getByRole("button", { name: "重置合成数据" }).click();
  await expect(page.getByText(/只删除并重建了标记为合成数据的家庭/)).toBeVisible();
  await page.getByRole("button", { name: "一键运行完整 Demo" }).click();
  const timeline = page.getByRole("list", { name: "主 Demo 十阶段进度" });
  await expect(timeline.getByRole("listitem")).toHaveCount(10, { timeout: 60_000 });
  await expect(page.getByText("8 / 8", { exact: true })).toBeVisible();
  await expect(page.getByText(/70% 仅约束合格长期资金/)).toBeVisible();
  await expect(page.getByRole("link", { name: "查看客户端规划书" })).toBeVisible();
  await expect(page.getByRole("link", { name: "查看顾问底稿" })).toBeVisible();
  await expect(page.getByRole("link", { name: "查看风险与审计" })).toBeVisible();

  await page.getByRole("button", { name: "运行七项实验" }).click();
  const experiments = page.getByRole("list", { name: "七项发布实验" });
  await expect(experiments.getByRole("listitem")).toHaveCount(7, { timeout: 60_000 });
  await expect(experiments.getByText("协议就绪")).toHaveCount(2);
  await expect(experiments.getByText("未宣称实测")).toHaveCount(2);
  await page.screenshot({ path: "../output/playwright/stage13-complete-demo-1440x900.png", fullPage: true });

  expect(externalRequests).toEqual([]);
  expect(browserIssues).toEqual([]);
});

test("connected advisor, compliance, and client share one immutable plan workflow", async ({ page }) => {
  test.skip(!process.env.PLAYWRIGHT_BASE_URL, "requires the connected Compose demo");
  const externalRequests: string[] = [];
  const browserIssues: string[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (!["127.0.0.1", "localhost"].includes(url.hostname)) externalRequests.push(request.url());
  });
  page.on("console", (message) => {
    if (["error", "warning"].includes(message.type())) browserIssues.push(message.text());
  });
  page.on("pageerror", (error) => browserIssues.push(error.message));

  await page.goto("/advisor");
  await expect(page.getByRole("heading", { name: "从面谈底稿推进到合规与客户确认" })).toBeVisible();
  const demoCRow = page.getByRole("row").filter({ hasText: "DEMO_C" });
  await demoCRow.getByRole("button", { name: "打开底稿" }).click();
  await expect(page.getByRole("heading", { name: /家庭 C｜退休准备/ })).toBeVisible();
  await expect(page.locator(".review-reminders > ol > li")).toHaveCount(12);

  await page.getByRole("button", { name: "创建方案草稿" }).click();
  await expect(page.getByText(/不可变草稿 V1/)).toBeVisible();
  await page.getByRole("button", { name: "运行确定性计算" }).click();
  await expect(page.getByText(/当前为 V2/)).toBeVisible();
  await page.getByRole("button", { name: "执行三道闸门" }).click();
  await expect(page.getByText(/当前为 V3/)).toBeVisible();
  await page.getByRole("checkbox", { name: /我已人工核对较高风险产品类型/ }).check();
  await page.getByRole("button", { name: "完成客户经理复核" }).click();
  await expect(page.getByText(/当前为 V4/)).toBeVisible();

  const draft = page.getByRole("textbox", { name: /AI 沟通话术草稿/ });
  await draft.fill(`${await draft.inputValue()} 本次沟通顺序已经由客户经理人工调整。`);
  await page.getByRole("button", { name: "仅保存沟通稿" }).click();
  await expect(page.getByText(/当前为 V5/)).toBeVisible();
  await page.getByRole("button", { name: "提交合规审核" }).click();
  await expect(page.getByText(/当前为 V6/)).toBeVisible();

  await page.goto("/risk");
  await expect(page.getByRole("heading", { name: "从阻断原因回到每一条证据" })).toBeVisible();
  await page.getByRole("row").filter({ hasText: "DEMO_C" }).getByRole("button", { name: "打开证据" }).click();
  await expect(page.getByRole("heading", { name: "为什么通过或被拦截" })).toBeVisible();
  await expect(page.getByRole("region", { name: "合规控制矩阵，可横向滚动" }).locator("tbody tr")).toHaveCount(10);
  await page.getByRole("checkbox", { name: /人工复核已完成并留痕/ }).check();
  await page.getByRole("button", { name: "审核通过" }).click();
  await expect(page.getByText(/已生成 V7/)).toBeVisible();

  await page.goto("/client");
  await page.getByRole("button", { name: /DEMO_C/ }).click();
  await openClientTask(page, "家庭规划书");
  await expect(page.getByRole("heading", { name: "方案审核与客户确认" })).toBeVisible();
  await page.getByRole("checkbox", { name: /我已阅读风险、流动性与适当性限制/ }).check();
  await page.getByRole("checkbox", { name: /我理解全部银行接口与产品均为合成 Mock/ }).check();
  await page.getByRole("checkbox", { name: /我理解方案不承诺保本或收益/ }).check();
  await page.getByRole("textbox", { name: "演示签署姓名" }).fill("测试客户");
  await page.getByRole("button", { name: "确认当前方案版本" }).click();
  await expect(page.getByText(/客户已逐项确认/)).toBeVisible();

  await page.goto("/advisor");
  await demoCRow.getByRole("button", { name: "打开底稿" }).click();
  await page.getByRole("button", { name: "激活已确认方案" }).click();
  await expect(page.getByText(/当前为 V9/)).toBeVisible();
  await expect(page.getByText(/方案已生效/)).toBeVisible();

  await page.goto("/risk");
  await page.getByRole("row").filter({ hasText: "DEMO_C" }).getByRole("button", { name: "打开证据" }).click();
  await page.getByRole("button", { name: "回放投诉场景" }).click();
  await expect(page.getByText(/完整性 verified/)).toBeVisible();
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "导出审计包" }).click();
  const download = await downloadPromise;
  expect(await download.suggestedFilename()).toMatch(/^wealthtwin-workflow-.*-audit\.json$/);
  expect(externalRequests).toEqual([]);
  expect(browserIssues).toEqual([]);
});

test("connected formal report is shared, exportable, recalculated, and visible in the risk chain", async ({ page }) => {
  test.skip(!process.env.PLAYWRIGHT_BASE_URL, "requires the connected Compose demo");
  const externalRequests: string[] = [];
  const browserIssues: string[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (!["127.0.0.1", "localhost"].includes(url.hostname)) externalRequests.push(request.url());
  });
  page.on("console", (message) => {
    if (["error", "warning"].includes(message.type())) browserIssues.push(message.text());
  });
  page.on("pageerror", (error) => browserIssues.push(error.message));

  await page.goto("/advisor");
  await page.getByRole("row").filter({ hasText: "DEMO_C" }).getByRole("button", { name: "打开底稿" }).click();
  await expect(page.getByRole("heading", { name: "客户与顾问读取同一份报告快照" })).toBeVisible();
  await page.getByRole("button", { name: "生成完整八章规划书" }).click();
  await expect(page.getByText(/正式规划书 R1 已生成/)).toBeVisible();
  await expect(page.getByRole("list", { name: "正式规划书八章目录" }).getByRole("listitem")).toHaveCount(8);
  const pdfDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "导出 PDF" }).click();
  expect((await pdfDownload).suggestedFilename()).toBe("wealthtwin-demo_c-report-r1.pdf");

  await page.goto("/client");
  await page.getByRole("button", { name: /DEMO_C/ }).click();
  await openClientTask(page, "家庭规划书");
  const formalNavigation = page.getByRole("navigation", { name: "规划书八章" });
  await expect(formalNavigation.getByRole("button")).toHaveCount(8);
  for (const title of ["家庭基础情况", "理财目标", "大额支出计划", "理财假设", "家庭财务报表", "家庭财务比率分析", "投资规划建议", "免责声明"]) {
    await expect(formalNavigation.getByText(title, { exact: true })).toBeVisible();
  }
  await expect(page.getByText("当前 R1", { exact: true })).toBeVisible();
  await page.screenshot({ path: "../output/playwright/stage11-formal-report-client-1366x768.png", fullPage: true });

  await openClientTask(page, "行动日历");
  await page.getByRole("tab", { name: /未来 12 个月复盘/ }).click();
  const firstStatus = page.locator(".action-state-controls select").first();
  await expect(firstStatus).toBeEnabled();
  await firstStatus.selectOption("completed");
  await page.locator(".action-state-controls .button").first().click();
  await expect(page.getByText(/生成正式规划书 R2 新快照/)).toBeVisible();

  await page.goto("/risk");
  await page.getByRole("row").filter({ hasText: "DEMO_C" }).getByRole("button", { name: "打开证据" }).click();
  await expect(page.getByLabel("快照、版本、哈希与触发原因").getByText("哈希链已验证", { exact: true })).toBeVisible();
  await expect(page.getByRole("list", { name: "正式报告不可变版本链" }).getByRole("listitem")).toHaveCount(2);
  await expect(page.getByText("2 个快照", { exact: true })).toBeVisible();
  await page.getByRole("checkbox", { name: /我已人工复核报告、授权、数字、来源及适当性证据/ }).check();
  await page.getByRole("button", { name: "运行十项发布门禁" }).click();
  await expect(page.getByRole("list", { name: "报告发布十项门禁" }).getByRole("listitem")).toHaveCount(10);
  await expect(page.getByText("十项门禁全部通过，可执行二次确认发布。", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "二次确认并发布" }).click();
  await expect(page.getByText(/报告已发布，水印/)).toBeVisible();
  expect(externalRequests).toEqual([]);
  expect(browserIssues).toEqual([]);
});

test("connected client completes the eleven-task journey with strict report and display controls", async ({ page }) => {
  test.skip(!process.env.PLAYWRIGHT_BASE_URL, "requires the connected Compose demo");
  await page.setViewportSize({ width: 1366, height: 768 });
  const externalRequests: string[] = [];
  const browserIssues: string[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (!["127.0.0.1", "localhost"].includes(url.hostname)) externalRequests.push(request.url());
  });
  page.on("console", (message) => {
    if (["error", "warning"].includes(message.type())) browserIssues.push(message.text());
  });
  page.on("pageerror", (error) => browserIssues.push(error.message));

  await page.goto("/client");
  const tasks = page.getByRole("tablist", { name: "十一项客户任务" }).getByRole("tab");
  await expect(tasks).toHaveCount(11);
  await tasks.first().focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("tab", { name: /资产负债/ })).toBeFocused();
  await expect(page.getByRole("heading", { name: "每一笔资产与负债都能回到底稿" })).toBeVisible();

  await expect(page.getByRole("button", { name: /DEMO_A/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /DEMO_B/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /DEMO_C/ })).toBeVisible();
  await page.getByRole("button", { name: /DEMO_A/ }).click();
  await expect(page.getByLabel("演示家庭").locator("option:checked")).toContainText("DEMO_A");
  await openClientTask(page, "资产负债");
  const familyABalance = await page.getByRole("figure", { name: "资产负债全景" }).textContent();
  await openClientTask(page, "行动日历");
  await expect(page.getByRole("heading", { name: "把建议变成有期限的家庭任务" })).toBeVisible();
  const familyAActions = await page.locator(".action-horizon-tabs").textContent();

  await page.getByRole("button", { name: /DEMO_B/ }).click();
  await expect(page.getByLabel("演示家庭").locator("option:checked")).toContainText("DEMO_B");
  await openClientTask(page, "资产负债");
  const familyBBalance = await page.getByRole("figure", { name: "资产负债全景" }).textContent();
  expect(familyBBalance).not.toBe(familyABalance);
  await openClientTask(page, "行动日历");
  await expect(page.getByRole("heading", { name: "把建议变成有期限的家庭任务" })).toBeVisible();
  const familyBActions = await page.locator(".action-horizon-tabs").textContent();
  expect(familyBActions).not.toBe(familyAActions);
  await page.getByRole("tab", { name: /未来三个月/ }).click();
  await page.getByText("为什么建议这一步", { exact: true }).first().click();
  await expect(page.getByText("约束／公式", { exact: true }).first()).toBeVisible();

  await openClientTask(page, "资产负债");
  await expect(page.getByRole("figure", { name: "资产负债全景" })).toBeVisible();
  await page.getByText("查看数据表", { exact: true }).first().click();
  await expect(page.getByRole("region", { name: "资产负债全景等价数据表" })).toBeVisible();
  await page.getByRole("button", { name: "比例", exact: true }).click();
  await expect(page.getByText("占家庭总资产", { exact: true }).first()).toBeVisible();
  await page.getByLabel("金额单位").selectOption("wan");
  await page.getByRole("button", { name: "金额", exact: true }).click();
  await expect(page.getByRole("figure", { name: "资产负债全景" })).toContainText("万元");

  await page.getByRole("checkbox", { name: "隐藏金额" }).check();
  await expect(page.getByRole("region", { name: "资产负债金额已隐藏" })).toBeVisible();
  await expect(page.getByText("¥2,850,000", { exact: true })).toHaveCount(0);
  await page.getByRole("checkbox", { name: "隐藏金额" }).uncheck();
  await page.getByRole("button", { name: "深色", exact: true }).click();
  await expect(page.locator('[data-theme="dark"]')).toBeVisible();
  await page.getByRole("checkbox", { name: "大字模式" }).check();
  await expect(page.locator('[data-text-scale="large"]')).toBeVisible();
  await page.getByRole("checkbox", { name: "低金融知识模式" }).check();
  await openClientTask(page, "财务健康");
  await expect(page.getByText("家里真正剩下的钱").first()).toBeVisible();

  await openClientTask(page, "家庭规划书");
  const chapterNavigation = page.getByRole("navigation", { name: "规划书八章" });
  await expect(chapterNavigation.getByRole("button")).toHaveCount(8);
  await expect(page.getByText("8 章", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "正式规划书审核中" })).toBeVisible();
  await expect(page.getByText(/审核完成前仅展示确定性预览/)).toBeVisible();
  await expect(page).toHaveScreenshot("client-report-1366.png", {
    animations: "disabled",
    maxDiffPixelRatio: 0.015,
  });

  await openClientTask(page, "行动日历");
  await page.getByRole("tab", { name: /未来 12 个月复盘/ }).click();
  await expect(page.locator(".action-group > ol > li")).toHaveCount(12);

  await openClientTask(page, "隐私中心");
  const privacyDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "导出家庭数据包" }).click();
  expect((await privacyDownload).suggestedFilename()).toMatch(/^wealthtwin-privacy-export-[a-f0-9]{16}\.json$/);
  await expect(page.getByText(/数据包已导出；本次操作已写入去标识审计记录/)).toBeVisible();
  await page.getByRole("button", { name: "撤回此授权" }).first().click();
  await expect(page.getByRole("heading", { name: "确认撤回授权" })).toBeVisible();
  await page.getByRole("button", { name: "取消" }).first().click();
  await page.getByRole("button", { name: "提交人工复核" }).click();
  await expect(page.getByText(/人工复核请求已写入演示顾问队列/)).toBeVisible();

  await page.getByText("查看完整状态演示", { exact: true }).click();
  await expect(page.getByLabel("状态").locator("option")).toHaveCount(14);
  await page.getByLabel("状态").selectOption("compliance_blocked");
  await expect(page.getByText("方案被合规拦截", { exact: true }).last()).toBeVisible();

  for (const viewport of [
    { width: 1440, height: 900 },
    { width: 1920, height: 1080 },
  ]) {
    await page.setViewportSize(viewport);
    await expect(page.getByRole("tablist", { name: "十一项客户任务" })).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow).toBeLessThanOrEqual(1);
  }
  expect(externalRequests).toEqual([]);
  expect(browserIssues).toEqual([]);
});

test("client task navigation remains contained on mobile and honors reduced motion", async ({ page }) => {
  test.skip(!process.env.PLAYWRIGHT_BASE_URL, "requires the connected Compose demo");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/client");
  await expect(page.getByRole("tablist", { name: "十一项客户任务" })).toBeVisible();
  await openClientTask(page, "家庭规划书");
  await expect(page.getByRole("navigation", { name: "规划书八章" })).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
  expect(await page.evaluate(() => window.matchMedia("(prefers-reduced-motion: reduce)").matches)).toBe(true);
});

test("connected demo exposes auditable financial analysis and JSON export", async ({ page }) => {
  test.skip(!process.env.PLAYWRIGHT_BASE_URL, "requires the connected Compose demo");

  await page.goto("/client");
  await openClientTask(page, "财务健康");
  await expect(page.getByRole("heading", { name: "全量财务健康指标" })).toBeVisible();
  await expect(page.locator(".metric-table tbody tr")).toHaveCount(20);
  await expect(page.getByText("¥1,642,000", { exact: true }).first()).toBeVisible();

  await page.getByRole("button", { name: "查看家庭净资产详情" }).click();
  const inspector = page.getByRole("dialog", { name: "家庭净资产" });
  await expect(inspector).toBeVisible();
  await expect(inspector.getByText("家庭总资产 − 家庭总负债")).toBeVisible();
  await expect(inspector.getByText("deterministic_derived")).toBeVisible();
  await page.getByRole("button", { name: "关闭指标详情" }).click();

  const exportLink = page.getByRole("link", { name: "导出财务底稿" });
  const exportPath = await exportLink.getAttribute("href");
  expect(exportPath).toBeTruthy();
  const response = await page.request.get(exportPath ?? "");
  expect(response.ok()).toBeTruthy();
  expect(response.headers()["content-disposition"]).toContain("wealthtwin-demo_b");
  const exported = (await response.json()) as { meta: { calculation_source: string }; metrics: unknown[] };
  expect(exported.meta.calculation_source).toBe("deterministic_tools");
  expect(exported.metrics).toHaveLength(20);

  await page.getByRole("button", { name: "保存本次体检" }).click();
  await expect(page.getByText(/已保存本次体检：20 项指标/)).toBeVisible();
});

test("connected demo recalculates the dynamic four-account plan", async ({ page }) => {
  test.skip(!process.env.PLAYWRIGHT_BASE_URL, "requires the connected Compose demo");

  await page.goto("/client");
  await openClientTask(page, "四账户");
  await expect(
    page.getByRole("heading", { name: "先过安全闸门，再安排长期资金" }),
  ).toBeVisible();
  for (const accountName of ["要花的钱", "保命的钱", "保本的钱", "生钱的钱"]) {
    await expect(page.getByRole("heading", { name: accountName })).toBeVisible();
  }
  await expect(page.getByText(/不得套用于家庭总资产/)).toBeVisible();

  await page.getByRole("button", { name: "家庭总资产", exact: true }).click();
  await expect(page.getByRole("button", { name: "家庭总资产", exact: true })).toHaveAttribute(
    "aria-pressed",
    "true",
  );

  await openClientTask(page, "目标时间轴");
  await page.getByLabel("补足应急金").fill("10000.00");
  await page.getByRole("button", { name: "重新计算方案" }).click();
  await expect(page.getByText(/反事实方案已由同一确定性规则版本重算/)).toBeVisible();

  const exportPath = await page.getByRole("link", { name: "导出规划 JSON" }).getAttribute("href");
  expect(exportPath).toBeTruthy();
  const response = await page.request.get(exportPath ?? "");
  expect(response.ok()).toBeTruthy();
  const exported = (await response.json()) as {
    meta: { calculation_source: string };
    accounts: unknown[];
    waterfall_steps: unknown[];
  };
  expect(exported.meta.calculation_source).toBe("deterministic_tools");
  expect(exported.accounts).toHaveLength(4);
  expect(exported.waterfall_steps).toHaveLength(7);
});

test("connected demo compares three portfolio candidates with a complete suitability chain", async ({ page }) => {
  test.skip(!process.env.PLAYWRIGHT_BASE_URL, "requires the connected Compose demo");

  await page.goto("/client");
  await openClientTask(page, "四账户");
  await expect(page.getByRole("heading", { name: "长期资金的三种走法" })).toBeVisible();
  await expect(page.getByRole("region", { name: "稳健基准进取方案比较" })).toBeVisible();
  await expect(
    page.getByText("当前没有可执行的长期新增资金", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: /进取/ }).click();
  await expect(page.getByRole("heading", { name: "进取方案的资产类别" })).toBeVisible();
  await expect(page.getByText("专业对冲实验室默认关闭")).toBeVisible();

  const exportPath = await page.getByRole("link", { name: "导出组合 JSON" }).getAttribute("href");
  expect(exportPath).toBeTruthy();
  const response = await page.request.get(exportPath ?? "");
  expect(response.ok()).toBeTruthy();
  const exported = (await response.json()) as {
    meta: { calculation_source: string };
    candidates: Array<{ gates: unknown[] }>;
    catalog: { product_count: number; source_type: string };
  };
  expect(exported.meta.calculation_source).toBe("deterministic_tools");
  expect(exported.candidates).toHaveLength(3);
  expect(exported.candidates.every((candidate) => candidate.gates.length === 3)).toBeTruthy();
  expect(exported.catalog).toMatchObject({ product_count: 19, source_type: "mock" });

  await page.getByRole("button", { name: "保存候选草案" }).click();
  await expect(page.getByText(/已保存 3 套候选与 9 条闸门记录/)).toBeVisible();
});

test("risk portal rejects an adversarial request and leaves an audit reference", async ({ page }) => {
  test.skip(!process.env.PLAYWRIGHT_BASE_URL, "requires the connected Compose demo");

  await page.goto("/risk");
  await expect(page.getByRole("heading", { name: "测试环境安全与模型风险质量门禁" })).toBeVisible();
  await expect(page.getByText("仅测试环境", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "运行八类对抗评测" }).click();
  await expect(page.getByRole("list", { name: "八类对抗用例" }).getByRole("listitem")).toHaveCount(8);
  await expect(page.getByText("八类对抗用例通过 8/8。", { exact: true })).toBeVisible();
  await openRiskTechnicalEvidence(page);
  await expect(page.getByRole("heading", { name: "适当性证据与拒绝链" })).toBeVisible();
  await page.getByRole("button", { name: "运行并写入审计" }).click();
  await expect(page.getByText(/不匹配请求已拒绝并写入审计事件/)).toBeVisible();
  await expect(page.getByText(/审计 [0-9a-f-]{8,}/)).toBeVisible();
});

test("connected demo runs and exports the reproducible household wealth twin", async ({ page }) => {
  test.skip(!process.env.PLAYWRIGHT_BASE_URL, "requires the connected Compose demo");

  await page.goto("/client");
  await openClientTask(page, "数字孪生");
  await expect(page.getByRole("heading", { name: "把家庭未来拆成可检验的路径" })).toBeVisible();
  await expect(page.getByText(/19 个内置场景 · 版本 1.0.0/)).toBeVisible();
  await page.getByRole("button", { name: "运行数字孪生" }).click();

  await expect(page.getByRole("heading", { name: /流动性缓冲使被迫出售概率下降/ })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("region", { name: "数字孪生方案概率对照" })).toBeVisible();
  await expect(page.getByRole("img", { name: "净资产分位数扇形图" })).toBeVisible();
  await expect(page.getByText("wealth-state-transition-v1.0.0", { exact: false }).first()).toBeVisible();

  const exportPath = await page.getByRole("link", { name: "导出完整结果" }).getAttribute("href");
  expect(exportPath).toBeTruthy();
  const response = await page.request.get(exportPath ?? "");
  expect(response.ok()).toBeTruthy();
  const exported = (await response.json()) as {
    meta: { calculation_source: string; scenario_version: string };
    assumptions: { seed: number; path_count: number; parameter_hash: string };
    original_stress: { fan: unknown[]; validation: { all_values_finite: boolean } };
    comparison: { stress_not_better_than_baseline: boolean };
  };
  expect(exported.meta).toMatchObject({ calculation_source: "deterministic_simulation_engine", scenario_version: "1.0.0" });
  expect(exported.assumptions).toMatchObject({ seed: 20260804, path_count: 100 });
  expect(exported.assumptions.parameter_hash).toHaveLength(64);
  expect(exported.original_stress.fan).toHaveLength(31);
  expect(exported.original_stress.validation.all_values_finite).toBe(true);
  expect(exported.comparison.stress_not_better_than_baseline).toBe(true);
});

test("connected demo can cancel a staged wealth-twin run", async ({ page }) => {
  test.skip(!process.env.PLAYWRIGHT_BASE_URL, "requires the connected Compose demo");

  await page.goto("/client");
  await openClientTask(page, "数字孪生");
  await expect(page.getByRole("heading", { name: "把家庭未来拆成可检验的路径" })).toBeVisible();
  await page.getByLabel("模拟路径数").fill("1000");
  await page.getByRole("button", { name: "运行数字孪生" }).click();
  const cancel = page.getByRole("button", { name: "取消运行" });
  await expect(cancel).toBeVisible();
  await cancel.click();
  await expect(page.locator(".twin-progress").getByText("已取消", { exact: true })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText(/结果与审计已固化/)).toHaveCount(0);
});

test("connected demo exposes the behavior dual profile, auditable exit, and A/B metrics", async ({ page }) => {
  test.skip(!process.env.PLAYWRIGHT_BASE_URL, "requires the connected Compose demo");

  await page.goto("/client");
  await openClientTask(page, "行为实验");
  await expect(page.getByRole("heading", { name: "先做选择，再看行为如何影响配置上限" })).toBeVisible();
  await expect(page.getByRole("heading", { name: /行为证据将配置上限从.*下调至/ })).toBeVisible();
  await expect(page.getByText(/损失厌恶.*追涨杀跌.*48 小时冷静期已生成/)).toBeVisible();
  await expect(page.getByRole("region", { name: "六项行为实验记录，可横向滚动" })).toBeVisible();

  const exportPath = await page.getByRole("link", { name: "导出行为底稿" }).getAttribute("href");
  expect(exportPath).toBeTruthy();
  const response = await page.request.get(exportPath ?? "");
  expect(response.ok()).toBeTruthy();
  const exported = (await response.json()) as {
    profile: {
      meta: { calculation_source: string };
      dual_profile: { risk_downshifted: boolean; effective_risk_limit: string };
      biases: unknown[];
      interventions: Array<{ code: string; cooling_period_hours: number | null }>;
      responses: unknown[];
    };
  };
  expect(exported.profile.meta.calculation_source).toBe("deterministic_behavior_engine");
  expect(exported.profile.dual_profile).toMatchObject({ risk_downshifted: true, effective_risk_limit: "low" });
  expect(exported.profile.biases).toHaveLength(11);
  expect(exported.profile.responses).toHaveLength(6);
  expect(exported.profile.interventions).toContainEqual(expect.objectContaining({ code: "cooling_period", cooling_period_hours: 48 }));

  await page.getByRole("button", { name: "开始行为实验" }).click();
  await expect(page.getByRole("heading", { name: "选择 1／6" })).toBeVisible();
  await page.getByRole("button", { name: "退出实验" }).click();
  await expect(page.getByText(/已退出实验；未生成画像或干预/)).toBeVisible();

  await page.goto("/risk");
  await openRiskTechnicalEvidence(page);
  await expect(page.getByRole("heading", { name: "四组配置与合成／授权指标" })).toBeVisible();
  await expect(page.getByRole("region", { name: "行为干预 A/B 指标，可横向滚动" }).locator("tbody tr")).toHaveCount(4);
});

test("connected demo traces controlled knowledge, confirmed intake, graph inference, and nine governed agents", async ({ page }) => {
  test.skip(!process.env.PLAYWRIGHT_BASE_URL, "requires the connected Compose demo");

  await page.goto("/client");
  await expect(page.getByRole("heading", { name: "先筛时效和适用范围，再组织解释" })).toBeVisible();
  await page.getByRole("button", { name: "检索受控依据" }).click();
  await expect(page.getByText("已找到受控依据")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("关于在全国范围实施个人养老金个人所得税优惠政策的公告").first()).toBeVisible();
  await expect(page.getByText(/发布 2024\/12\/12 · 生效 2024\/01\/01 · 核验 2026\/08\/04/).first()).toBeVisible();
  await expect(page.getByRole("img", { name: "35岁上海双收入家庭关系推导图" })).toBeVisible();
  await expect(page.getByText(/不能从家庭总资产套用统一70%/)).toBeVisible();

  await page.getByRole("button", { name: "解析为待确认草稿" }).click();
  await expect(page.getByRole("textbox", { name: "夫妻月工资合计确认值" })).toHaveValue("30000.00");
  await page.locator(".missing-fields > summary").click();
  await expect(page.getByText(/月供不能推导贷款余额/)).toBeVisible();
  const draft = page.getByRole("group", { name: "勾选并核对每一项" });
  const checkboxes = draft.getByRole("checkbox");
  for (let index = 0; index < await checkboxes.count(); index += 1) {
    await checkboxes.nth(index).check();
  }
  await page.getByRole("button", { name: "确认已勾选字段" }).click();
  await expect(page.getByText("提取项已确认")).toBeVisible();

  await page.goto("/risk");
  await openRiskTechnicalEvidence(page);
  await expect(page.getByRole("heading", { name: "每一步都要有工具、Schema、禁令和审计" })).toBeVisible();
  await page.getByRole("button", { name: "运行可信编排" }).click();
  await expect(page.getByText("终检通过")).toBeVisible({ timeout: 30_000 });
  await expect(page.locator(".agent-timeline > li")).toHaveCount(9);
  await expect(page.getByText(/数字工具账本/)).toBeVisible();
});
