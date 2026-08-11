#!/usr/bin/env node

import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(SCRIPT_DIR, "..");
const WORKSPACE = path.join(ROOT, "tmp", "presentations", "wealthtwin");
const MODULE_PATH = path.join(
  WORKSPACE,
  "node_modules",
  "@oai",
  "artifact-tool",
  "dist",
  "artifact_tool.mjs",
);
const { Presentation, PresentationFile } = await import(pathToFileURL(MODULE_PATH).href);

const OUT_DIR = path.join(ROOT, "output", "presentations");
const RENDER_DIR = path.join(WORKSPACE, "rendered");
const FINAL_PPTX = path.join(OUT_DIR, "wealthtwin_competition_deck.pptx");

const W = 1280;
const H = 720;
const M = 68;
const NAVY = "#17324D";
const NAVY_2 = "#234A68";
const INK = "#25323D";
const MUTED = "#62717C";
const PAPER = "#F6F2E9";
const WHITE = "#FFFFFF";
const RED = "#B3262D";
const RED_LIGHT = "#F6E7E7";
const GOLD = "#B48A3A";
const GOLD_LIGHT = "#F2EBD9";
const ORANGE = "#C8782E";
const GREEN = "#35735A";
const GREEN_LIGHT = "#E7F1EC";
const LINE = "#CBD5DC";
const BLUE_LIGHT = "#E7EEF4";
const TYPEFACE = "PingFang SC";

function rect(slide, x, y, width, height, fill, options = {}) {
  return slide.shapes.add({
    geometry: options.geometry ?? "rect",
    name: options.name,
    position: { left: x, top: y, width, height },
    fill,
    line: options.line ?? { style: "solid", fill: options.lineFill ?? fill, width: options.lineWidth ?? 0 },
    borderRadius: options.borderRadius,
    shadow: options.shadow,
  });
}

function textBox(slide, text, x, y, width, height, options = {}) {
  const shape = slide.shapes.add({
    geometry: "textbox",
    name: options.name,
    position: { left: x, top: y, width, height },
    fill: options.fill ?? "none",
    line: options.line ?? { style: "solid", fill: "none", width: 0 },
    borderRadius: options.borderRadius,
  });
  shape.text = text;
  shape.text.style = {
    fontSize: options.fontSize ?? 18,
    bold: options.bold ?? false,
    color: options.color ?? INK,
    alignment: options.align ?? "left",
    verticalAlignment: options.vertical ?? "top",
    autoFit: options.autoFit ?? "shrinkText",
    wrap: "square",
    insets: options.insets ?? { top: 2, right: 4, bottom: 2, left: 4 },
    typeface: TYPEFACE,
    lineSpacing: options.lineSpacing ?? 1.12,
  };
  return shape;
}

function richText(slide, paragraphs, x, y, width, height, options = {}) {
  const shape = textBox(slide, "", x, y, width, height, options);
  shape.text.set(paragraphs);
  shape.text.style = {
    fontSize: options.fontSize ?? 18,
    color: options.color ?? INK,
    autoFit: options.autoFit ?? "shrinkText",
    wrap: "square",
    verticalAlignment: options.vertical ?? "top",
    alignment: options.align ?? "left",
    insets: options.insets ?? { top: 4, right: 4, bottom: 4, left: 4 },
    typeface: TYPEFACE,
    lineSpacing: options.lineSpacing ?? 1.1,
  };
  return shape;
}

function pill(slide, label, x, y, width, fill = BLUE_LIGHT, color = NAVY) {
  const shape = rect(slide, x, y, width, 34, fill, {
    geometry: "roundRect",
    borderRadius: "rounded-full",
    lineFill: fill,
  });
  shape.text = label;
  shape.text.style = {
    fontSize: 16,
    bold: true,
    color,
    alignment: "center",
    verticalAlignment: "middle",
    autoFit: "shrinkText",
    insets: { top: 1, right: 6, bottom: 1, left: 6 },
    typeface: TYPEFACE,
  };
  return shape;
}

function rule(slide, x, y, width, color = LINE, weight = 2) {
  return slide.shapes.add({
    geometry: "line",
    position: { left: x, top: y, width, height: 0 },
    fill: "none",
    line: { style: "solid", fill: color, width: weight },
  });
}

function verticalRule(slide, x, y, height, color = LINE, weight = 2) {
  return slide.shapes.add({
    geometry: "line",
    position: { left: x, top: y, width: 0, height },
    fill: "none",
    line: { style: "solid", fill: color, width: weight },
  });
}

function circle(slide, x, y, size, fill, options = {}) {
  return rect(slide, x, y, size, size, fill, {
    geometry: "ellipse",
    lineFill: options.lineFill ?? fill,
    lineWidth: options.lineWidth ?? 0,
  });
}

function addHeader(slide, index, title, kicker) {
  textBox(slide, kicker, M, 34, 420, 25, { fontSize: 16, bold: true, color: RED });
  textBox(slide, title, M, 65, 1080, 56, { fontSize: 36, bold: true, color: NAVY });
  textBox(slide, String(index).padStart(2, "0"), 1166, 44, 50, 30, {
    fontSize: 18,
    bold: true,
    color: MUTED,
    align: "right",
  });
  rule(slide, M, 126, W - 2 * M, LINE, 1);
}

function addFooter(slide, label = "竞赛原型 · 合成数据 · Mock 接口 · 非工商银行官方产品") {
  textBox(slide, label, M, 683, 850, 22, { fontSize: 14, color: MUTED });
  textBox(slide, "Fortune Copilot 0.14.0", 1000, 683, 216, 22, {
    fontSize: 14,
    bold: true,
    color: NAVY,
    align: "right",
  });
}

function addNotes(slide, body, sources) {
  slide.speakerNotes.textFrame.setText(
    `${body}\n\n[Sources]\n${sources.map((source) => `- ${source}`).join("\n")}\n[/Sources]`,
  );
  slide.speakerNotes.setVisible(true);
}

async function readImage(imagePath) {
  const bytes = await fs.readFile(imagePath);
  return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
}

function addScreenshot(slide, bytes, alt, x, y, width, height, options = {}) {
  rect(slide, x - 5, y - 5, width + 10, height + 10, WHITE, {
    geometry: "roundRect",
    borderRadius: "rounded-xl",
    lineFill: LINE,
    lineWidth: 1,
    shadow: "shadow-sm",
  });
  return slide.images.add({
    blob: bytes,
    contentType: "image/png",
    alt,
    fit: options.fit ?? "cover",
    ...(options.crop ? { crop: options.crop } : {}),
    position: { left: x, top: y, width, height },
    geometry: "roundRect",
    borderRadius: "rounded-lg",
  });
}

function callout(slide, value, label, x, y, width, options = {}) {
  textBox(slide, value, x, y, width, 52, {
    fontSize: options.valueSize ?? 38,
    bold: true,
    color: options.color ?? NAVY,
    align: options.align ?? "left",
  });
  textBox(slide, label, x, y + 54, width, 50, {
    fontSize: 16,
    color: MUTED,
    align: options.align ?? "left",
  });
}

function bulletParagraphs(items, color = INK) {
  return items.map(([lead, body]) => ({
    bulletCharacter: "•",
    marginLeft: 24,
    indent: -13,
    spaceAfter: 10,
    runs: [
      { run: lead, textStyle: { bold: true, color } },
      { run: body, textStyle: { color } },
    ],
  }));
}

async function buildDeck() {
  await fs.mkdir(OUT_DIR, { recursive: true });
  await fs.mkdir(RENDER_DIR, { recursive: true });

  const assets = {
    demo: await readImage(path.join(ROOT, "output", "playwright", "e14-v5-release-demo-1440x768.png")),
    client: await readImage(path.join(ROOT, "output", "playwright", "stage9-client-balance-1366x768.png")),
    twin: await readImage(path.join(ROOT, "output", "stage6-client-1366x768.png")),
    behavior: await readImage(path.join(ROOT, "output", "presentation_assets", "behavior-profile.png")),
    advisor: await readImage(path.join(ROOT, "output", "screenshots", "stage10", "advisor-1366.png")),
    risk: await readImage(path.join(ROOT, "output", "screenshots", "stage10", "risk-1440.png")),
  };

  const presentation = Presentation.create({ slideSize: { width: W, height: H } });

  // 1 — Cover
  {
    const slide = presentation.slides.add();
    slide.background.fill = NAVY;
    rect(slide, 0, 0, 18, H, RED);
    textBox(slide, "智运财富", 86, 112, 560, 82, { fontSize: 58, bold: true, color: WHITE });
    textBox(slide, "WEALTHTWIN", 90, 198, 400, 40, { fontSize: 24, bold: true, color: "#D8E3EB" });
    textBox(slide, "中国家庭财富数字孪生\n与智能投顾操作系统", 86, 282, 650, 128, {
      fontSize: 36,
      bold: true,
      color: WHITE,
      lineSpacing: 1.05,
    });
    rule(slide, 88, 440, 510, "#47677F", 2);
    textBox(slide, "目标先于产品 · 约束先于收益 · 证据先于解释", 86, 464, 650, 38, {
      fontSize: 19,
      bold: true,
      color: "#E2C888",
    });
    const c1 = circle(slide, 842, 132, 280, "none", { lineFill: "#507089", lineWidth: 3 });
    const c2 = circle(slide, 900, 190, 164, "none", { lineFill: "#A56763", lineWidth: 3 });
    const c3 = circle(slide, 949, 239, 66, RED, { lineFill: RED });
    c1.sendToBack();
    c2.sendToBack();
    c3.text = "家";
    c3.text.style = { fontSize: 28, bold: true, color: WHITE, alignment: "center", verticalAlignment: "middle", typeface: TYPEFACE };
    textBox(slide, "一核", 768, 214, 90, 30, { fontSize: 17, bold: true, color: "#D5E0E7", align: "right" });
    textBox(slide, "四账", 1081, 277, 90, 30, { fontSize: 17, bold: true, color: "#D5E0E7" });
    textBox(slide, "三尺 · 六阶段 · 双画像", 850, 440, 300, 34, { fontSize: 18, color: "#D5E0E7", align: "center" });
    pill(slide, "离线 Mock 完整运行", 86, 590, 210, RED, WHITE);
    textBox(slide, "竞赛交付版 · 2026.08", 980, 626, 220, 28, { fontSize: 16, color: "#C7D4DD", align: "right" });
    addNotes(
      slide,
      "开场只讲定位：这不是预测市场的机器人，而是先把家庭目标、约束和行动放进可计算、可追溯的系统。明确竞赛原型与离线 Mock 边界。",
      ["repo:README.md", "repo:docs/technical_whitepaper.md"],
    );
  }

  // 2 — Pain
  {
    const slide = presentation.slides.add();
    slide.background.fill = PAPER;
    addHeader(slide, 2, "100 万金融资产，不等于同一张比例图", "01 · 痛点");
    textBox(slide, "同样的起点", 74, 164, 260, 28, { fontSize: 18, bold: true, color: MUTED });
    callout(slide, "¥1,000,000", "概念设问：金融资产相同", 70, 198, 310, { color: NAVY, valueSize: 42 });
    verticalRule(slide, 410, 178, 356, NAVY, 3);
    const rows = [
      ["家庭甲", "房贷 + 十年教育目标", RED_LIGHT, RED],
      ["家庭乙", "初入职场 + 收入波动", BLUE_LIGHT, NAVY],
      ["家庭丙", "临近退休 + 养老现金流", GOLD_LIGHT, GOLD],
    ];
    const resultShapes = [];
    rows.forEach(([name, detail, fill, color], i) => {
      const y = 166 + i * 124;
      const source = rect(slide, 456, y, 276, 84, fill, { geometry: "roundRect", borderRadius: "rounded-lg", lineFill: color, lineWidth: 1 });
      textBox(slide, name, 474, y + 12, 92, 24, { fontSize: 17, bold: true, color });
      textBox(slide, detail, 474, y + 40, 238, 28, { fontSize: 17, color: INK });
      const target = rect(slide, 882, y, 308, 84, WHITE, { geometry: "roundRect", borderRadius: "rounded-lg", lineFill: LINE, lineWidth: 1 });
      textBox(slide, i === 0 ? "先补安全层" : i === 1 ? "保留流动缓冲" : "控制波动与提取风险", 902, y + 18, 266, 30, { fontSize: 18, bold: true, color: NAVY });
      textBox(slide, "账户金额与期限不同", 902, y + 50, 266, 22, { fontSize: 16, color: MUTED });
      slide.shapes.connect(source, target, { kind: "straight", fromSide: "right", toSide: "left", line: { style: "solid", fill: MUTED, width: 2 }, tail: { type: "arrow", width: "sm", length: "sm" } });
      resultShapes.push(target);
    });
    rect(slide, 68, 548, 1122, 82, NAVY, { geometry: "roundRect", borderRadius: "rounded-lg", lineFill: NAVY });
    textBox(slide, "关键问题不是“分几份”，而是：为谁、何时、需要多少钱、先满足什么约束。", 94, 568, 1070, 42, { fontSize: 22, bold: true, color: WHITE, align: "center", vertical: "middle" });
    textBox(slide, "注：100 万元为答辩设问；A/B/C 演示家庭的实际资产并不相同。", 72, 648, 790, 22, { fontSize: 14, color: MUTED });
    addFooter(slide);
    addNotes(
      slide,
      "用20秒建立反例。不要暗示演示三户都拥有100万元；明确这是概念设问。真实证据在Demo三家庭对照：三套配置签名不同，fixed_ratio_model=false。",
      ["repo:docs/demo_script_3min.md", "repo:backend/app/services/demo_release.py", "repo:backend/tests/test_demo_release.py"],
    );
  }

  // 3 — Framework
  {
    const slide = presentation.slides.add();
    slide.background.fill = WHITE;
    addHeader(slide, 3, "华衡：从家庭目标到可执行行动的自主框架", "02 · 中国自主框架");
    const core = circle(slide, 88, 196, 246, NAVY, { lineFill: NAVY });
    core.text = "一核\n家庭人生目标\n韧性与长期生活质量";
    core.text.style = { fontSize: 21, bold: true, color: WHITE, alignment: "center", verticalAlignment: "middle", autoFit: "shrinkText", insets: { top: 18, right: 18, bottom: 18, left: 18 }, typeface: TYPEFACE };
    const accounts = [
      ["要花", "日常 + 应急", RED_LIGHT, RED],
      ["保命", "保费 + 缺口", GOLD_LIGHT, GOLD],
      ["稳钱", "1—5 年目标", BLUE_LIGHT, NAVY_2],
      ["生钱", "真实长期资金", GREEN_LIGHT, GREEN],
    ];
    accounts.forEach(([name, detail, fill, color], i) => {
      const y = 162 + i * 104;
      const box = rect(slide, 416, y, 286, 74, fill, { geometry: "roundRect", borderRadius: "rounded-lg", lineFill: color, lineWidth: 1 });
      textBox(slide, name, 436, y + 14, 80, 30, { fontSize: 22, bold: true, color });
      textBox(slide, detail, 526, y + 16, 154, 28, { fontSize: 17, color: INK });
      slide.shapes.connect(core, box, { kind: "straight", fromSide: "right", toSide: "left", line: { style: "solid", fill: LINE, width: 2 }, tail: { type: "arrow", width: "sm", length: "sm" } });
    });
    verticalRule(slide, 760, 160, 430, LINE, 2);
    const framework = [
      ["三尺", "总资产 / 可投资金融资产 / 年度新增结余"],
      ["五硬一软", "流动性、偿债、保障、期限、适当性 + 行为"],
      ["双画像", "客观能力与问卷/实验；行为只能下调"],
      ["六阶段", "初入职场 → 婚姻 → 育儿 → 成熟 → 退休 → 传承"],
    ];
    framework.forEach(([name, detail], i) => {
      const y = 165 + i * 105;
      textBox(slide, name, 806, y, 142, 32, { fontSize: 22, bold: true, color: i === 1 ? RED : NAVY });
      textBox(slide, detail, 806, y + 38, 388, 48, { fontSize: 17, color: MUTED });
      if (i < framework.length - 1) rule(slide, 806, y + 92, 382, LINE, 1);
    });
    pill(slide, "不是固定比例", 88, 514, 176, RED, WHITE);
    textBox(slide, "账户是资金用途；比例必须说清分母和前置条件。", 88, 562, 620, 38, { fontSize: 20, bold: true, color: NAVY });
    addFooter(slide);
    addNotes(
      slide,
      "解释方法体系时始终把一核放在账户前。强调四账户是用途账，三尺解决分母混乱，五硬一软决定能否进入长期增长，双画像防止问卷自述抬高风险。",
      ["repo:docs/domain_glossary.md", "repo:docs/planning_engine.md", "repo:docs/behavior_engine.md"],
    );
  }

  // 4 — Product flow
  {
    const slide = presentation.slides.add();
    slide.background.fill = PAPER;
    addHeader(slide, 4, "从一句家庭语言，到一份可审计的八章规划书", "03 · 产品流程");
    const steps = ["建档确认", "五表体检", "目标规划", "动态四账", "三道闸门", "孪生 + 行为", "三端 + 八章"];
    const boxes = [];
    steps.forEach((label, i) => {
      const x = 68 + i * 162;
      const box = rect(slide, x, 158, 132, 62, i === 6 ? NAVY : WHITE, { geometry: "roundRect", borderRadius: "rounded-lg", lineFill: i === 6 ? NAVY : LINE, lineWidth: 1 });
      textBox(slide, `${i + 1}`, x + 10, 169, 26, 30, { fontSize: 17, bold: true, color: i === 6 ? WHITE : RED, align: "center" });
      textBox(slide, label, x + 36, 169, 86, 30, { fontSize: 16, bold: true, color: i === 6 ? WHITE : NAVY, align: "center" });
      boxes.push(box);
      if (i > 0) {
        slide.shapes.connect(boxes[i - 1], box, { kind: "straight", fromSide: "right", toSide: "left", line: { style: "solid", fill: MUTED, width: 2 }, tail: { type: "triangle", width: "sm", length: "sm" } });
      }
    });
    rect(slide, 68, 262, 322, 326, NAVY, { geometry: "roundRect", borderRadius: "rounded-xl", lineFill: NAVY });
    textBox(slide, "离线主链", 94, 290, 258, 36, { fontSize: 24, bold: true, color: WHITE });
    richText(slide, bulletParagraphs([
      ["事实：", "合成家庭与本地规则"],
      ["计算：", "Decimal + 固定 seed"],
      ["语言：", "Mock/模板可降级"],
      ["连接：", "银行适配全部 Mock"],
      ["依赖：", "外部网络 = 0"],
    ], WHITE), 92, 344, 270, 196, { fontSize: 18, color: WHITE });
    pill(slide, "关键数字不经过 LLM", 92, 538, 246, RED, WHITE);
    addScreenshot(slide, assets.demo, "Fortune Copilot完整Demo实际页面", 430, 262, 760, 326, { fit: "cover" });
    textBox(slide, "实际 /demo 页面：十阶段编排、三家庭对照、发布边界与三端入口", 446, 600, 730, 28, { fontSize: 16, color: MUTED, align: "center" });
    addFooter(slide);
    addNotes(
      slide,
      "按照从事实到行动的顺序讲产品流程。屏幕截图来自当前仓库运行中的 /demo 页面，不是设计稿。强调外部网络、模型和银行接口都不是主链前置条件。",
      ["repo:output/playwright/e14-v5-release-demo-1440x768.png", "repo:docs/demo_runbook.md", "repo:backend/app/services/demo_release.py"],
    );
  }

  // 5 — Dynamic accounts
  {
    const slide = presentation.slides.add();
    slide.background.fill = WHITE;
    addHeader(slide, 5, "金额由七步瀑布算出，比例只是带分母的结果", "04 · 动态四账户");
    textBox(slide, "B 家庭 · 双收入育儿", 70, 150, 330, 28, { fontSize: 18, bold: true, color: RED });
    const waterfall = [
      ["1", "高息债务"], ["2", "日常资金"], ["3", "应急储备"], ["4", "必要保障"],
      ["5", "一年内支出"], ["6", "1—5 年目标"], ["7", "剩余长期资金"],
    ];
    const wfShapes = [];
    waterfall.forEach(([n, label], i) => {
      const x = 70 + (i % 4) * 144;
      const y = 194 + Math.floor(i / 4) * 82;
      const width = i === 6 ? 196 : 126;
      const box = rect(slide, x, y, width, 54, i === 6 ? GREEN_LIGHT : PAPER, { geometry: "roundRect", borderRadius: "rounded-md", lineFill: i === 6 ? GREEN : LINE, lineWidth: 1 });
      textBox(slide, n, x + 8, y + 13, 24, 26, { fontSize: 17, bold: true, color: RED, align: "center" });
      textBox(slide, label, x + 34, y + 13, width - 42, 26, { fontSize: 16, bold: true, color: NAVY });
      wfShapes.push(box);
      if (i > 0 && i < 4) slide.shapes.connect(wfShapes[i - 1], box, { kind: "straight", fromSide: "right", toSide: "left", line: { style: "solid", fill: MUTED, width: 1.5 }, tail: { type: "arrow", width: "sm", length: "sm" } });
    });
    textBox(slide, "三把尺", 70, 396, 220, 32, { fontSize: 24, bold: true, color: NAVY });
    const rulers = [
      ["家庭总资产", "285 万"],
      ["可投资金融资产", "32 万"],
      ["年度新增结余", "7.2 万"],
    ];
    rulers.forEach(([label, value], i) => {
      const y = 446 + i * 52;
      textBox(slide, label, 72, y, 220, 28, { fontSize: 17, color: MUTED });
      textBox(slide, value, 286, y, 112, 28, { fontSize: 19, bold: true, color: NAVY, align: "right" });
      rule(slide, 72, y + 36, 326, LINE, 1);
    });
    rect(slide, 690, 158, 500, 452, PAPER, { geometry: "roundRect", borderRadius: "rounded-xl", lineFill: LINE, lineWidth: 1 });
    textBox(slide, "实时结果", 724, 184, 160, 28, { fontSize: 18, bold: true, color: MUTED });
    const accountRows = [
      ["要花的钱", "13.3 万", "目标；缺口 8.3 万", RED],
      ["保命的钱", "1.2 万/年", "必要保费；缺口另列", GOLD],
      ["稳钱的钱", "25.1 万", "近期目标 + 安全留存", NAVY_2],
      ["生钱的钱", "0 元", "前置约束未通过", GREEN],
    ];
    accountRows.forEach(([name, value, note, color], i) => {
      const y = 232 + i * 78;
      circle(slide, 724, y + 4, 14, color, { lineFill: color });
      textBox(slide, name, 750, y, 150, 28, { fontSize: 18, bold: true, color: NAVY });
      textBox(slide, value, 968, y - 2, 184, 34, { fontSize: i === 3 ? 28 : 22, bold: true, color: i === 3 ? RED : NAVY, align: "right" });
      textBox(slide, note, 750, y + 34, 402, 24, { fontSize: 16, color: MUTED });
      if (i < accountRows.length - 1) rule(slide, 724, y + 66, 428, LINE, 1);
    });
    rect(slide, 710, 548, 460, 42, RED_LIGHT, { geometry: "roundRect", borderRadius: "rounded-md", lineFill: "#E8C2C2", lineWidth: 1 });
    textBox(slide, "70% 只看通过闸门后的长期可规划资源，不看家庭总资产。", 724, 557, 432, 24, { fontSize: 16, bold: true, color: RED, align: "center" });
    addFooter(slide);
    addNotes(
      slide,
      "用B家庭说明动态逻辑。先说七步顺序，再说三种分母，最后指出B家庭生钱账户新增为0。这是最直观的非固定比例证据。保命账户1.2万元是年保费，不是保障缺口或资产。",
      ["repo:docs/planning_engine.md", "repo:data/expected/demo_b_planning_v1.json", "repo:backend/tests/test_planning.py"],
    );
  }

  // 6 — Twin
  {
    const slide = presentation.slides.add();
    slide.background.fill = PAPER;
    addHeader(slide, 6, "不预测市场，只检验家庭能否穿越冲击", "05 · 家庭财富数字孪生");
    addScreenshot(slide, assets.twin, "客户端数字孪生与压力测试实际页面", 68, 158, 724, 414, { fit: "cover" });
    pill(slide, "失业 6 个月 + 权益下跌 30%", 830, 158, 360, RED_LIGHT, RED);
    const metrics = [
      ["目标成功率", "53%", "100%"],
      ["资金耗尽", "39%", "0%"],
      ["被迫出售", "100%", "4%"],
    ];
    textBox(slide, "原方案", 876, 218, 112, 28, { fontSize: 16, bold: true, color: MUTED, align: "center" });
    textBox(slide, "优化后", 1054, 218, 112, 28, { fontSize: 16, bold: true, color: GREEN, align: "center" });
    metrics.forEach(([label, before, after], i) => {
      const y = 258 + i * 86;
      textBox(slide, label, 818, y + 10, 132, 28, { fontSize: 17, bold: true, color: NAVY });
      textBox(slide, before, 948, y, 96, 44, { fontSize: 30, bold: true, color: RED, align: "center" });
      textBox(slide, "→", 1030, y + 4, 52, 36, { fontSize: 24, bold: true, color: MUTED, align: "center" });
      textBox(slide, after, 1082, y, 96, 44, { fontSize: 30, bold: true, color: GREEN, align: "center" });
      if (i < metrics.length - 1) rule(slide, 818, y + 62, 360, LINE, 1);
    });
    rect(slide, 816, 526, 372, 70, NAVY, { geometry: "roundRect", borderRadius: "rounded-lg", lineFill: NAVY });
    textBox(slide, "固定 seed · 100 条路径 · 共同随机数", 832, 538, 340, 28, { fontSize: 17, bold: true, color: WHITE, align: "center" });
    textBox(slide, "条件模拟，不是收益预测", 832, 567, 340, 20, { fontSize: 15, color: "#D7E2E9", align: "center" });
    textBox(slide, "实际页面截图；分位数图同时提供等价数据表。", 84, 586, 684, 24, { fontSize: 15, color: MUTED, align: "center" });
    addFooter(slide);
    addNotes(
      slide,
      "强调同一组随机路径下比较原方案和优化方案。所有概率来自合成参数与100条路径，只用于演示可复现压力机制，不是市场或收益预测。",
      ["repo:output/stage6-client-1366x768.png", "repo:docs/twin_engine.md", "repo:data/expected/demo_b_twin_v1.json"],
    );
  }

  // 7 — Behavior
  {
    const slide = presentation.slides.add();
    slide.background.fill = WHITE;
    addHeader(slide, 7, "用户说“能承受”，不等于真实选择也能承受", "06 · 行为金融");
    addScreenshot(slide, assets.behavior, "客户端行为金融双画像实际页面", 68, 158, 650, 410, { fit: "cover" });
    textBox(slide, "双画像冲突", 758, 158, 260, 30, { fontSize: 23, bold: true, color: NAVY });
    const profileRows = [
      ["问卷自述", "medium_high", NAVY_2],
      ["客观能力", "medium", GOLD],
      ["-10% 选择", "清仓", RED],
      ["最终上限", "low", RED],
    ];
    profileRows.forEach(([label, value, color], i) => {
      const y = 208 + i * 58;
      textBox(slide, label, 760, y, 164, 26, { fontSize: 17, color: MUTED });
      textBox(slide, value, 962, y - 2, 210, 32, { fontSize: i === 3 ? 25 : 20, bold: true, color, align: "right" });
      rule(slide, 760, y + 38, 412, LINE, 1);
    });
    rect(slide, 758, 452, 414, 116, RED_LIGHT, { geometry: "roundRect", borderRadius: "rounded-lg", lineFill: "#E6BABB", lineWidth: 1 });
    textBox(slide, "48 小时冷静期", 782, 470, 364, 36, { fontSize: 26, bold: true, color: RED, align: "center" });
    textBox(slide, "损失厌恶 + 追涨杀跌有逐项选择证据\n不自动交易，不保证减少损失", 782, 514, 364, 42, { fontSize: 16, color: INK, align: "center" });
    textBox(slide, "行为只能维持或下调客观风险上限", 758, 590, 414, 30, { fontSize: 18, bold: true, color: NAVY, align: "center" });
    addFooter(slide);
    addNotes(
      slide,
      "先指问卷与客观能力，再指出-10%清仓和上涨追买/下跌卖出证据。最终上限取审慎最低等级。冷静期是可退出的干预，不等于强制交易限制或效果保证。",
      ["repo:output/presentation_assets/behavior-profile.png", "repo:docs/behavior_engine.md", "repo:data/expected/demo_b_behavior_v1.json"],
    );
  }

  // 8 — AI and algorithms
  {
    const slide = presentation.slides.add();
    slide.background.fill = PAPER;
    addHeader(slide, 8, "AI负责语言，确定性工具负责金融结论", "07 · AI 与算法");
    const llm = rect(slide, 96, 170, 1088, 84, BLUE_LIGHT, { geometry: "roundRect", borderRadius: "rounded-xl", lineFill: "#B9CBD8", lineWidth: 1 });
    textBox(slide, "LLM 语言层", 124, 190, 210, 34, { fontSize: 23, bold: true, color: NAVY });
    textBox(slide, "理解自然语言 · 生成追问 · 受控解释 · Mock/失败可降级", 348, 190, 790, 34, { fontSize: 19, color: INK, align: "center" });
    const engine = rect(slide, 96, 300, 1088, 142, WHITE, { geometry: "roundRect", borderRadius: "rounded-xl", lineFill: NAVY, lineWidth: 2 });
    textBox(slide, "确定性金融工具层", 124, 320, 270, 34, { fontSize: 23, bold: true, color: NAVY });
    const tools = ["五表 / 20 指标", "目标 / 七步瀑布", "组合 / 三闸门", "孪生 / Monte Carlo"];
    tools.forEach((label, i) => pill(slide, label, 130 + i * 258, 372, 224, i === 3 ? GREEN_LIGHT : PAPER, i === 3 ? GREEN : NAVY));
    const governance = rect(slide, 96, 490, 1088, 112, NAVY, { geometry: "roundRect", borderRadius: "rounded-xl", lineFill: NAVY });
    textBox(slide, "治理与审计层", 124, 514, 220, 32, { fontSize: 22, bold: true, color: WHITE });
    textBox(slide, "9 智能体固定状态机 · 工具白名单 · 版本哈希 · 引用有效期 · 注入隔离 · 10 项发布门禁", 348, 509, 800, 46, { fontSize: 18, color: WHITE, align: "center", vertical: "middle" });
    textBox(slide, "关键金额 / 比率 / 配置 / 概率：LLM 无写权限", 348, 558, 800, 26, { fontSize: 17, bold: true, color: "#E5C67D", align: "center" });
    slide.shapes.connect(llm, engine, { kind: "straight", fromSide: "bottom", toSide: "top", line: { style: "solid", fill: MUTED, width: 2 }, tail: { type: "arrow", width: "sm", length: "sm" } });
    slide.shapes.connect(engine, governance, { kind: "straight", fromSide: "bottom", toSide: "top", line: { style: "solid", fill: MUTED, width: 2 }, tail: { type: "arrow", width: "sm", length: "sm" } });
    addFooter(slide);
    addNotes(
      slide,
      "这页回答大模型可靠性。语言层没有关键数字写权限；确定性工具先计算，智能体只能调用白名单工具并把结构化结果交给治理层。无密钥时Mock与模板仍可运行。",
      ["repo:docs/model_card.md", "repo:docs/trusted_ai.md", "repo:backend/app/services/trust/orchestrator.py", "repo:backend/app/services/security/quality_gate.py"],
    );
  }

  // 9 — Three-end loop
  {
    const slide = presentation.slides.add();
    slide.background.fill = WHITE;
    addHeader(slide, 9, "同一家庭、同一版本，三端按职责渐进披露", "08 · 三端闭环");
    const panels = [
      ["客户", "看懂结论、目标与行动", assets.client, "客户端资产负债与任务工作区"],
      ["客户经理", "比较方案、沟通与复盘", assets.advisor, "客户经理工作台"],
      ["风险合规", "复核规则、引用与门禁", assets.risk, "风险合规控制台"],
    ];
    const imageBoxes = [];
    panels.forEach(([label, detail, bytes, alt], i) => {
      const x = 68 + i * 384;
      addScreenshot(slide, bytes, alt, x, 190, 344, 202, { fit: "cover" });
      const name = pill(slide, label, x + 74, 146, 196, i === 2 ? RED_LIGHT : BLUE_LIGHT, i === 2 ? RED : NAVY);
      imageBoxes.push(name);
      textBox(slide, detail, x + 8, 412, 328, 42, { fontSize: 17, bold: true, color: NAVY, align: "center" });
    });
    const states = ["Draft", "Calculated", "Suitability\nChecked", "Advisor\nReviewed", "Compliance\nReviewed", "Customer\nConfirmed", "Active", "Superseded"];
    textBox(slide, "不可跳步版本链", 70, 490, 220, 28, { fontSize: 18, bold: true, color: RED });
    const stateBoxes = [];
    states.forEach((state, i) => {
      const x = 70 + i * 143;
      const width = 128;
      const box = rect(slide, x, 534, width, 48, i === 4 ? RED_LIGHT : PAPER, { geometry: "roundRect", borderRadius: "rounded-md", lineFill: i === 4 ? RED : LINE, lineWidth: 1 });
      textBox(slide, state, x + 5, 540, width - 10, 36, { fontSize: 13.5, bold: true, color: i === 4 ? RED : NAVY, align: "center", vertical: "middle", lineSpacing: 1.0 });
      stateBoxes.push(box);
    });
    stateBoxes.slice(0, -1).forEach((box, i) => slide.shapes.connect(box, stateBoxes[i + 1], {
      kind: "straight",
      fromSide: "right",
      toSide: "left",
      line: { style: "solid", fill: MUTED, width: 1.5 },
      tail: { type: "triangle", width: "sm", length: "sm" },
    }));
    rect(slide, 70, 612, 1120, 38, NAVY, { geometry: "roundRect", borderRadius: "rounded-md", lineFill: NAVY });
    textBox(slide, "客户只看到合规后的裁剪版本；内部请求 ID、操作者与完整历史不进入客户资源树。", 86, 620, 1088, 22, { fontSize: 16, bold: true, color: WHITE, align: "center" });
    addFooter(slide);
    addNotes(
      slide,
      "三张图都是当前项目实际页面。强调三端不是复制三份数据，而是读取同一版本并按最小必要原则披露。八状态不可跳步；客户不能读取合规前内部报告。",
      ["repo:output/playwright/stage9-client-balance-1366x768.png", "repo:output/screenshots/stage10/advisor-1366.png", "repo:output/screenshots/stage10/risk-1440.png", "repo:docs/review_workflow.md"],
    );
  }

  // 10 — Case
  {
    const slide = presentation.slides.add();
    slide.background.fill = PAPER;
    addHeader(slide, 10, "典型案例 B：先补韧性，再谈长期增长", "09 · 典型案例");
    rect(slide, 68, 154, 310, 474, NAVY, { geometry: "roundRect", borderRadius: "rounded-xl", lineFill: NAVY });
    textBox(slide, "35 岁双收入育儿家庭", 92, 184, 262, 52, { fontSize: 25, bold: true, color: WHITE });
    richText(slide, bulletParagraphs([
      ["资产：", "285.0 万"],
      ["负债：", "120.8 万"],
      ["年结余：", "7.2 万"],
      ["目标：", "十年教育 + 养老"],
      ["模式：", "合成事实 / Mock"],
    ], WHITE), 92, 264, 254, 218, { fontSize: 18, color: WHITE });
    textBox(slide, "不是代表性样本；只用于验证完整链路。", 92, 544, 254, 44, { fontSize: 15, color: "#D5E0E7", align: "center" });
    const diagnosis = [
      ["4.17 月", "应急覆盖", "目标 7 月"],
      ["84.21%", "房产集中", "总资产分母"],
      ["145.2 万", "保障缺口", "最大单项风险"],
    ];
    diagnosis.forEach(([value, label, note], i) => {
      const x = 430 + i * 244;
      callout(slide, value, `${label}\n${note}`, x, 168, 210, { color: i === 2 ? RED : NAVY, valueSize: 31, align: "center" });
    });
    rule(slide, 430, 294, 760, LINE, 1);
    textBox(slide, "确定性行动顺序", 430, 326, 280, 32, { fontSize: 23, bold: true, color: NAVY });
    const actions = [
      ["1", "先补 8.3 万安全层", RED],
      ["2", "近期目标与保障进入稳健层", GOLD],
      ["3", "长期新增金额暂为 0 元", NAVY_2],
      ["4", "压力测试后形成复盘动作", GREEN],
    ];
    const actionBoxes = [];
    actions.forEach(([n, label, color], i) => {
      const y = 382 + i * 56;
      const box = rect(slide, 430, y, 728, 42, WHITE, { geometry: "roundRect", borderRadius: "rounded-md", lineFill: LINE, lineWidth: 1 });
      circle(slide, 444, y + 7, 28, color, { lineFill: color });
      textBox(slide, n, 448, y + 10, 20, 20, { fontSize: 15, bold: true, color: WHITE, align: "center" });
      textBox(slide, label, 486, y + 8, 640, 24, { fontSize: 17, bold: true, color: NAVY });
      actionBoxes.push(box);
    });
    pill(slide, "所有数字可回到公式、输入、规则版本与审计 ID", 430, 620, 728, NAVY, WHITE);
    addFooter(slide);
    addNotes(
      slide,
      "案例只使用主Demo B标准答案。不要把三户合成数据扩展为中国家庭统计结论。按诊断到行动讲：应急不足、房产集中、保障缺口，因此长期新增不是固定70%，而是0元。",
      ["repo:data/expected/demo_b_financial_metrics_v1.json", "repo:data/expected/demo_b_planning_v1.json", "repo:docs/financial_engine.md"],
    );
  }

  // 11 — Evaluation and compliance
  {
    const slide = presentation.slides.add();
    slide.background.fill = WHITE;
    addHeader(slide, 11, "把“可信”变成可以重复执行的门禁", "10 · 评测与合规");
    const bigStats = [
      ["194", "后端 Pytest"],
      ["65", "前端 Vitest"],
      ["0", "浏览器错误/警告"],
      ["24/24", "黑盒验收"],
    ];
    bigStats.forEach(([value, label], i) => {
      const x = 70 + i * 190;
      callout(slide, value, label, x, 154, 158, { color: i === 3 ? RED : NAVY, valueSize: 42, align: "center" });
    });
    rect(slide, 842, 154, 348, 116, NAVY, { geometry: "roundRect", borderRadius: "rounded-lg", lineFill: NAVY });
    textBox(slide, "165 / 196", 866, 172, 300, 46, { fontSize: 36, bold: true, color: WHITE, align: "center" });
    textBox(slide, "OpenAPI 路径 / HTTP 操作", 866, 224, 300, 28, { fontSize: 16, color: "#D7E2E9", align: "center" });
    rule(slide, 70, 300, 1120, LINE, 1);
    textBox(slide, "10 项发布门禁", 70, 332, 270, 30, { fontSize: 23, bold: true, color: NAVY });
    const gates = ["八章结构", "数字账本", "引用覆盖", "适当性", "禁语", "版本完整", "模型边界", "Mock 标识", "隐私", "人工复核"];
    gates.forEach((label, i) => {
      const x = 70 + (i % 5) * 220;
      const y = 382 + Math.floor(i / 5) * 58;
      const gate = rect(slide, x, y, 196, 40, i === 3 || i === 8 ? RED_LIGHT : PAPER, { geometry: "roundRect", borderRadius: "rounded-md", lineFill: i === 3 || i === 8 ? RED : LINE, lineWidth: 1 });
      textBox(slide, `${i + 1}. ${label}`, x + 8, y + 8, 180, 22, { fontSize: 16, bold: true, color: i === 3 || i === 8 ? RED : NAVY, align: "center" });
    });
    rect(slide, 70, 524, 1120, 96, GREEN_LIGHT, { geometry: "roundRect", borderRadius: "rounded-lg", lineFill: "#B8D2C3", lineWidth: 1 });
    textBox(slide, "离线验证边界", 94, 542, 200, 28, { fontSize: 21, bold: true, color: GREEN });
    textBox(slide, "Mock 默认 · 外部调用 0 · Compose healthy · 合成数据备份/隔离恢复通过", 300, 538, 858, 34, { fontSize: 18, bold: true, color: NAVY, align: "center" });
    textBox(slide, "测试环境结果，不是生产 SLA、真实收益或工商银行经营效果。", 300, 576, 858, 24, { fontSize: 16, color: MUTED, align: "center" });
    addFooter(slide);
    addNotes(
      slide,
      "数字必须与最终测试报告一致。强调这些是工程验证，不是生产SLA或客户收益。10项门禁中任何阻断都会禁止发布，UI不会隐藏失败项。",
      ["repo:docs/final_test_report.md", "repo:docs/evaluation.md", "repo:backend/tests", "repo:frontend/e2e/smoke.spec.ts"],
    );
  }

  // 12 — ICBC value
  {
    const slide = presentation.slides.add();
    slide.background.fill = PAPER;
    addHeader(slide, 12, "对工行的价值：从一次销售，转向长期家庭关系", "11 · 工行价值");
    const center = circle(slide, 496, 220, 288, NAVY, { lineFill: NAVY });
    center.text = "家庭综合金融服务\n\n目标 · 约束 · 产品 · 行动";
    center.text.style = { fontSize: 24, bold: true, color: WHITE, alignment: "center", verticalAlignment: "middle", autoFit: "shrinkText", insets: { top: 24, right: 24, bottom: 24, left: 24 }, typeface: TYPEFACE };
    const values = [
      ["资产留存", "长期陪伴", 110, 172, RED_LIGHT, RED],
      ["养老金融", "家庭生命周期", 110, 404, GOLD_LIGHT, GOLD],
      ["顾问效率", "方案一致性", 858, 172, BLUE_LIGHT, NAVY_2],
      ["适当性", "可解释性", 858, 404, GREEN_LIGHT, GREEN],
      ["消费者保护", "销售与服务留痕", 500, 516, WHITE, NAVY],
    ];
    values.forEach(([a, b, x, y, fill, color], i) => {
      const width = i === 4 ? 280 : 274;
      const box = rect(slide, x, y, width, 94, fill, { geometry: "roundRect", borderRadius: "rounded-lg", lineFill: color, lineWidth: 1 });
      textBox(slide, a, x + 18, y + 14, width - 36, 28, { fontSize: 21, bold: true, color, align: "center" });
      textBox(slide, b, x + 18, y + 52, width - 36, 24, { fontSize: 17, color: MUTED, align: "center" });
      const from = x < 400 ? "right" : x > 800 ? "left" : "top";
      const to = x < 400 ? "left" : x > 800 ? "right" : "bottom";
      slide.shapes.connect(box, center, { kind: "straight", fromSide: from, toSide: to, line: { style: "solid", fill: MUTED, width: 1.5 }, tail: { type: "arrow", width: "sm", length: "sm" } });
    });
    rect(slide, 90, 620, 1100, 38, RED_LIGHT, { geometry: "roundRect", borderRadius: "rounded-md", lineFill: "#E8C2C2", lineWidth: 1 });
    textBox(slide, "价值方向已在原型中形成机制；AUM、转化和工时改善仍需真实授权试点验证。", 108, 628, 1064, 22, { fontSize: 16, bold: true, color: RED, align: "center" });
    addFooter(slide);
    addNotes(
      slide,
      "不要只讲促进销售。强调综合金融、养老金、顾问效率、适当性、可解释性、消费者保护、留痕和长期陪伴。所有经营结果仍是待验证假设。",
      ["repo:docs/icbc_business_value.md", "repo:docs/known_limitations.md"],
    );
  }

  // 13 — Business and rollout
  {
    const slide = presentation.slides.add();
    slide.background.fill = WHITE;
    addHeader(slide, 13, "治理先于规模：五道门推进真实落地", "12 · 商业与推广");
    const stages = [
      ["01", "离线共创", "字段 / 规则 / 禁令"],
      ["02", "影子评估", "只读对照 / 不触达客户"],
      ["03", "内部辅助", "顾问准备 / 人工采纳"],
      ["04", "授权试点", "可退出 / 小范围"],
      ["05", "规模评审", "安全与业务双门槛"],
    ];
    const stageShapes = [];
    stages.forEach(([num, title, detail], i) => {
      const x = 68 + i * 228;
      const y = 176 + (i % 2) * 22;
      const box = rect(slide, x, y, 198, 144, i === 4 ? NAVY : PAPER, { geometry: "roundRect", borderRadius: "rounded-xl", lineFill: i === 4 ? NAVY : LINE, lineWidth: 1 });
      textBox(slide, num, x + 16, y + 16, 46, 28, { fontSize: 17, bold: true, color: i === 4 ? "#E5C67D" : RED });
      textBox(slide, title, x + 16, y + 52, 166, 32, { fontSize: 22, bold: true, color: i === 4 ? WHITE : NAVY });
      textBox(slide, detail, x + 16, y + 92, 166, 40, { fontSize: 16, color: i === 4 ? "#D7E2E9" : MUTED, align: "center" });
      stageShapes.push(box);
      if (i > 0) slide.shapes.connect(stageShapes[i - 1], box, { kind: "straight", fromSide: "right", toSide: "left", line: { style: "solid", fill: MUTED, width: 2 }, tail: { type: "triangle", width: "sm", length: "sm" } });
    });
    textBox(slide, "评价不只看销售", 70, 390, 310, 34, { fontSize: 25, bold: true, color: NAVY });
    const measures = [
      ["理解", "分母 / 非保本 / 信用卡边界"],
      ["效率", "顾问准备与复盘工时"],
      ["治理", "适当性一致 / 审计回放"],
      ["行动", "应急 / 保障 / 目标完成"],
      ["关系", "资产留存 / 养老服务 / 投诉"],
    ];
    measures.forEach(([label, detail], i) => {
      const x = 70 + (i % 3) * 370;
      const y = 446 + Math.floor(i / 3) * 82;
      textBox(slide, label, x, y, 90, 28, { fontSize: 20, bold: true, color: i === 2 ? RED : NAVY });
      textBox(slide, detail, x + 92, y, 254, 46, { fontSize: 16, color: MUTED });
    });
    rect(slide, 812, 526, 378, 86, GREEN_LIGHT, { geometry: "roundRect", borderRadius: "rounded-lg", lineFill: "#B8D2C3", lineWidth: 1 });
    textBox(slide, "交易能力另行建设", 834, 542, 334, 28, { fontSize: 21, bold: true, color: GREEN, align: "center" });
    textBox(slide, "持牌 · 授权 · 风控 · 人工复核齐备后再评估", 834, 575, 334, 24, { fontSize: 15, color: INK, align: "center" });
    addFooter(slide);
    addNotes(
      slide,
      "商业路线不是直接上线，而是离线共创、影子评估、内部辅助、授权试点和规模评审。真实接口与交易能力不在当前范围，只有治理与资质齐备后才能单独建设。",
      ["repo:docs/icbc_business_value.md", "repo:docs/final_function_matrix.md", "repo:docs/known_limitations.md"],
    );
  }

  // 14 — Conclusion
  {
    const slide = presentation.slides.add();
    slide.background.fill = NAVY;
    rect(slide, 0, 0, W, 14, RED);
    textBox(slide, "结论", 84, 64, 190, 34, { fontSize: 18, bold: true, color: "#E5C67D" });
    textBox(
      slide,
      "“智运财富不是替用户预测市场，\n而是帮助中国家庭在不确定的市场中，\n仍然能够完成确定的人生目标。”",
      84,
      142,
      830,
      270,
      { fontSize: 39, bold: true, color: WHITE, lineSpacing: 1.18 },
    );
    const proof = [
      ["懂家庭", "A–H 统一管线"],
      ["管住 AI", "数字由工具计算"],
      ["闭环运行", "客户—顾问—合规"],
      ["离线可演示", "外部依赖为零"],
    ];
    proof.forEach(([title, detail], i) => {
      const x = 86 + i * 278;
      rule(slide, x, 492, 230, i === 0 ? RED : "#58758B", 3);
      textBox(slide, title, x, 512, 230, 30, { fontSize: 20, bold: true, color: WHITE });
      textBox(slide, detail, x, 552, 230, 28, { fontSize: 16, color: "#CDD9E1" });
    });
    pill(slide, "Fortune Copilot 0.14.0 · Demo Ready", 84, 626, 316, RED, WHITE);
    textBox(slide, "竞赛原型 · 合成数据 · Mock 接口", 862, 632, 328, 26, { fontSize: 16, color: "#C9D7E0", align: "right" });
    addNotes(
      slide,
      "按原文收束，不增加收益承诺。若还有时间，只重复四个已验证判断：理解家庭、约束AI、三端同源、离线完整运行。",
      ["repo:docs/codex/wealthtwin_codex_prompts.md", "repo:docs/final_acceptance_report.md"],
    );
  }

  for (const [index, slide] of presentation.slides.items.entries()) {
    const stem = `slide-${String(index + 1).padStart(2, "0")}`;
    const png = await presentation.export({ slide, format: "png", scale: 1 });
    await fs.writeFile(path.join(RENDER_DIR, `${stem}.png`), new Uint8Array(await png.arrayBuffer()));
    const layout = await slide.export({ format: "layout" });
    await fs.writeFile(path.join(RENDER_DIR, `${stem}.layout.json`), await layout.text());
  }

  const montage = await presentation.export({ format: "webp", montage: true, scale: 1 });
  await fs.writeFile(path.join(RENDER_DIR, "deck-montage.webp"), new Uint8Array(await montage.arrayBuffer()));

  const inspection = await presentation.inspect({
    kind: "slide,textbox,shape,image,notes,layout",
    maxChars: 60000,
  });
  await fs.writeFile(path.join(RENDER_DIR, "deck-inspect.ndjson"), inspection.ndjson);

  const pptx = await PresentationFile.exportPptx(presentation);
  await pptx.save(FINAL_PPTX);
  console.log(`wrote ${FINAL_PPTX}`);
  console.log(`rendered ${presentation.slides.items.length} slides to ${RENDER_DIR}`);
}

buildDeck().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
