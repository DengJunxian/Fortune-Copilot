import type {
  FormalReport,
  ReportActionList,
  ReportGenerationChain,
} from "../api/formalReport";
import { clientExperienceFixture } from "./clientExperienceFixture";
import { knowledgeSearchFixture } from "./trustFixture";

const chapterTitles = [
  "家庭基础情况",
  "理财目标",
  "大额支出计划",
  "理财假设",
  "家庭财务报表",
  "家庭财务比率分析",
  "投资规划建议",
  "免责声明",
] as const;

const chapterSevenSections = [
  "四账户动态规划",
  "日用与应急安排",
  "负债优化",
  "保险保障",
  "养老与税务",
  "目标资金安排",
  "三候选组合",
  "数字孪生与压力测试",
  "行为干预",
  "产品类型适当性",
  "行动清单",
  "未来 12 个月复盘日历",
];

export function formalReportFixture(sequence = 1): FormalReport {
  const reportId = `formal-report-fixture-${sequence}`;
  return {
    report_id: reportId,
    household_id: "household-b",
    household_code: "DEMO_B",
    household_name: "B 家庭（测试夹具）",
    sequence,
    parent_report_id: sequence > 1 ? `formal-report-fixture-${sequence - 1}` : null,
    workflow_id: "workflow-fixture-00000000000000000001",
    workflow_version_id: "workflow-version-fixture-00000000000005",
    workflow_state: "advisor_reviewed",
    status: "workflow_linked",
    title: "B 家庭（测试夹具）家庭财富规划书",
    subtitle: "确定性计算、受控来源与人工复核共同形成的正式快照",
    watermark: "合成 Mock 数据 · R1 · 待人工复核",
    chapter_count: 8,
    chapters: chapterTitles.map((title, index) => ({
      number: index + 1,
      title,
      summary: index === 6 ? "四账户按家庭目标与安全闸门动态计算；长期增长账户口径不外推为家庭总资产统一配置。" : `第 ${index + 1} 章使用已确认家庭事实与版本化计算。`,
      sections: (index === 6 ? chapterSevenSections : [`${index + 1}.1 核心内容`]).map((sectionTitle, sectionIndex) => ({
        code: index === 6 ? `7.${sectionIndex + 1}` : `${index + 1}.1`,
        title: sectionTitle,
        narratives: index === 7
          ? ["本报告不承诺本金或收益；压力测试是情景分析而非预测，重大决策必须人工确认。"]
          : ["内容来自确定性工具或已确认家庭事实，不由语言模型计算关键金额与比率。"],
        tables: sectionIndex === 0 ? [{
          title: "确定性数字示例",
          columns: ["指标", "当前值", "来源"],
          rows: [["家庭净资产", "1,642,000.00 元", "financial.net_worth"]],
          note: "测试夹具不代表真实家庭。",
          calculation_source: "deterministic_tools",
        }] : [],
        advice: index === 6 && sectionIndex === 10 ? [{
          code: "action-immediate",
          title: "补足应急储备",
          reason: "确定性安全闸门发现应急储备缺口。",
          priority: 1,
          action: "先补足缺口，再考虑长期资金安排。",
          completion_criteria: "目标应急储备到账并由家庭确认。",
          review_cycle: "月度",
          status: "open",
          due_date: "2026-08-18",
          citation_ids: [],
          calculation_source: "deterministic_tools",
        }] : [],
        citation_ids: index === 7 ? ["cite:pension"] : [],
      })),
    })),
    appendices: [{
      code: "A",
      title: "公式、政策、产品、数据与审计附录",
      tables: [],
      narratives: ["附录不改变正式规划书八章一级目录。"],
    }],
    citations: knowledgeSearchFixture.citations,
    sourced_claims: [{ text: "个人养老金政策事实来自受控本地快照。", citation_ids: ["cite:pension"] }],
    numeric_ledger: [{
      code: "net_worth",
      label: "家庭净资产",
      raw_value: "1642000.00",
      display_value: "1,642,000.00 元",
      unit: "CNY",
      source_path: "financial.statements.balance_sheet.net_worth",
      calculation_source: "deterministic_tools",
    }],
    versions: {
      report_version: `formal-report-r${sequence}`,
      input_version: "fixture-input-v1",
      formula_version: "financial-health-v1.0.0",
      planning_rule_version: "planning-rule-v1.1.0",
      portfolio_rule_version: "portfolio-rule-v1.0.0",
      twin_result_version: "twin-result-fixture",
      model_version: "mock-template-v1",
      prompt_version: "formal-report-prompt-v1",
      knowledge_version: "controlled-knowledge-v1.0.0",
      product_catalog_version: "product-catalog-v1.0.0",
      workflow_version: "V5",
    },
    execution_metrics: { total: 1, open: 1, completed: 0, deferred: 0, not_applicable: 0, completion_ratio: "0.00%" },
    consistency_checks: [{ code: "exact_eight_chapters", status: "passed", explanation: "一级目录严格为八章。" }],
    consistency_status: "passed",
    generation_trigger: sequence === 1 ? "manual" : "action_status_change",
    generation_reason: sequence === 1 ? "测试一键生成" : "测试行动状态变化",
    generated_at: `2026-08-04T08:0${Math.min(sequence, 9)}:00Z`,
    analysis_date: "2026-08-04",
    data_as_of: "2025-12-31",
    report_hash: String(sequence).repeat(64),
    mock_mode_supported: true,
    boundary_note: "报告到此结束。本报告基于合成 Mock 数据，不构成保本、收益承诺或自动交易指令；历史表现不代表未来，压力测试不是预测，重大决策须人工确认。",
  };
}

export function reportActionListFixture(reportSequence = 1): ReportActionList {
  const items = clientExperienceFixture.action_calendar.flatMap((group) => group.items.map((item, index) => ({
    id: `report-action-${group.code}-${index}`,
    action_code: item.code,
    group_code: group.code,
    title: item.title,
    detail: item.detail,
    why: item.why,
    completion_criteria: "家庭确认行动已完成并保留凭证。",
    review_cycle: group.code === "next_12_months" ? "月度" : "按期限",
    amount: item.amount,
    due_date: item.due_date,
    priority: item.priority,
    status: "open" as const,
    completed_at: null,
    deferred_until: null,
    status_reason: null,
    record_version: 1,
    calculation_source: item.calculation_source,
  })));
  return {
    household_id: "household-b",
    report_id: `formal-report-fixture-${reportSequence}`,
    report_sequence: reportSequence,
    items,
    metrics: { total: items.length, open: items.length, completed: 0, deferred: 0, not_applicable: 0, completion_ratio: "0.00%" },
  };
}

export const reportGenerationChainFixture: ReportGenerationChain = {
  household_id: "household-b",
  current_report_id: "formal-report-fixture-2",
  chain_verified: true,
  items: [formalReportFixture(1), formalReportFixture(2)].map((report) => ({
    report_id: report.report_id,
    household_id: report.household_id,
    sequence: report.sequence,
    report_version: report.versions.report_version,
    parent_report_id: report.parent_report_id,
    workflow_id: report.workflow_id,
    workflow_version_id: report.workflow_version_id,
    status: report.status,
    consistency_status: report.consistency_status,
    generation_trigger: report.generation_trigger,
    generated_at: report.generated_at,
    data_as_of: report.data_as_of,
    report_hash: report.report_hash,
    watermark: report.watermark,
    html_url: `/api/v1/reports/${report.report_id}/html`,
    pdf_url: `/api/v1/reports/${report.report_id}/pdf`,
  })),
  audit_event_ids: ["audit-report-1", "audit-report-2", "audit-action-1"],
  boundary_note: "报告链只读展示；合规端不能生成或修改正式报告。",
};
