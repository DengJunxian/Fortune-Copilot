import type { EChartsOption } from "echarts";
import type { FinancialAnalysis } from "../../api/financial";
import type { PlanningResponse } from "../../api/planning";
import { useDisplayPreferences } from "../../contexts/displayPreferences";
import { formatDate, formatMoney, formatMoneyInWan, formatRatio } from "../../utils/format";
import { ChartFrame, type ChartRow } from "./ChartFrame";
import { chartThemeFor } from "./chartTheme";

function moneyNumber(value: string, unit: "yuan" | "wan"): number {
  return Number(value) / (unit === "wan" ? 10_000 : 1);
}

function moneyLabel(value: string, unit: "yuan" | "wan"): string {
  return unit === "wan" ? formatMoneyInWan(value) : formatMoney(value);
}

function axisMoney(value: number): string {
  return new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 1 }).format(value);
}

export function BalanceOverviewChart({ analysis }: { analysis: FinancialAnalysis }) {
  const { moneyUnit, valueView, theme } = useDisplayPreferences();
  const projectColors = chartThemeFor(theme);
  const balance = analysis.statements.balance_sheet;
  const denominator = Math.max(1, Number(balance.total_assets));
  const raw = [balance.total_assets, balance.total_liabilities, balance.net_worth];
  const values = raw.map((value) =>
    valueView === "ratio" ? Number(value) / denominator : moneyNumber(value, moneyUnit),
  );
  const unit = valueView === "ratio" ? "占家庭总资产" : moneyUnit === "wan" ? "万元" : "元";
  const rows: ChartRow[] = [
    { item: "家庭总资产", value: valueView === "ratio" ? "100.0%" : moneyLabel(balance.total_assets, moneyUnit) },
    { item: "家庭总负债", value: valueView === "ratio" ? formatRatio(String(Number(balance.total_liabilities) / denominator)) : moneyLabel(balance.total_liabilities, moneyUnit) },
    { item: "净资产", value: valueView === "ratio" ? formatRatio(String(Number(balance.net_worth) / denominator)) : moneyLabel(balance.net_worth, moneyUnit) },
  ];
  const option: EChartsOption = {
    textStyle: { color: projectColors.text },
    grid: { left: 72, right: 28, top: 18, bottom: 42 },
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
    xAxis: { type: "category", data: ["总资产", "总负债", "净资产"], axisTick: { show: false }, axisLabel: { color: projectColors.textMuted } },
    yAxis: {
      type: "value",
      axisLabel: { formatter: valueView === "ratio" ? (value: number) => `${Math.round(value * 100)}%` : axisMoney },
      splitLine: { lineStyle: { color: projectColors.surface } },
    },
    series: [{
      name: unit,
      type: "bar",
      data: values.map((value, index) => ({
        value,
        itemStyle: { color: [projectColors.brand, projectColors.warning, projectColors.goal][index] ?? projectColors.brand },
      })),
      barMaxWidth: 66,
      label: {
        show: true,
        position: "top",
        formatter: (params) => {
          const value = typeof params.value === "number" ? params.value : Number(params.value ?? 0);
          return valueView === "ratio" ? `${(value * 100).toFixed(1)}%` : axisMoney(value);
        },
      },
    }],
  };
  return (
    <ChartFrame
      title="资产负债全景"
      description="信用卡额度不进入资产；信用卡未偿余额按负债记录。"
      unit={unit}
      timeRange={`截至 ${formatDate(analysis.meta.data_as_of)}`}
      methodology="家庭总资产 - 家庭总负债 = 净资产"
      updatedAt={formatDate(analysis.meta.analysis_date)}
      source="客户确认的家庭财务报表"
      insight={`当前净资产为${moneyLabel(balance.net_worth, moneyUnit)}。资产、负债和净资产使用同一数据日与货币口径。`}
      option={option}
      columns={[{ key: "item", label: "项目" }, { key: "value", label: unit, numeric: true }]}
      rows={rows}
      legend={[
        { label: "资产", color: projectColors.brand },
        { label: "负债", color: projectColors.warning, pattern: "stripe" },
        { label: "净资产", color: projectColors.goal },
      ]}
    />
  );
}

function sumCategories(analysis: FinancialAnalysis, categories: string[], essential?: boolean): number {
  return analysis.statements.cash_flow.expense_lines
    .filter((line) => categories.includes(line.category) && (essential === undefined || line.essential === essential))
    .reduce((total, line) => total + Number(line.annual_amount), 0);
}

export function CashFlowWaterfallChart({ analysis }: { analysis: FinancialAnalysis }) {
  const { moneyUnit, valueView, theme } = useDisplayPreferences();
  const projectColors = chartThemeFor(theme);
  const cashflow = analysis.statements.cash_flow;
  const income = Number(cashflow.annual_income);
  const denominator = Math.max(1, income);
  const items = [
    { label: "收入", value: income, kind: "income" },
    { label: "必要支出", value: sumCategories(analysis, ["basic_living", "medical", "tax", "other"], true), kind: "outflow" },
    { label: "还贷", value: Number(cashflow.annual_debt_service), kind: "outflow" },
    { label: "保险", value: Number(cashflow.annual_insurance_premiums), kind: "outflow" },
    { label: "教育赡养", value: sumCategories(analysis, ["parent_support", "child_education"]), kind: "outflow" },
    { label: "弹性消费", value: sumCategories(analysis, ["discretionary"], false), kind: "outflow" },
    { label: "结余", value: Number(cashflow.annual_surplus), kind: "result" },
  ];
  let running = income;
  const assists: number[] = [];
  const display: Array<{ value: number; itemStyle: { color: string } }> = [];
  for (const item of items) {
    if (item.kind === "income" || item.kind === "result") {
      assists.push(0);
    } else {
      running -= item.value;
      assists.push(Math.max(0, running));
    }
    const normalized = valueView === "ratio" ? item.value / denominator : item.value / (moneyUnit === "wan" ? 10_000 : 1);
    display.push({
      value: normalized,
      itemStyle: {
        color: item.kind === "income" ? projectColors.brand : item.kind === "result" ? projectColors.goal : projectColors.warning,
      },
    });
  }
  const normalizedAssists = assists.map((value) =>
    valueView === "ratio" ? value / denominator : value / (moneyUnit === "wan" ? 10_000 : 1),
  );
  const unit = valueView === "ratio" ? "占年收入" : moneyUnit === "wan" ? "万元/年" : "元/年";
  const option: EChartsOption = {
    textStyle: { color: projectColors.text },
    grid: { left: 72, right: 28, top: 18, bottom: 64 },
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
    xAxis: { type: "category", data: items.map((item) => item.label), axisLabel: { interval: 0, rotate: 20, color: projectColors.textMuted }, axisTick: { show: false } },
    yAxis: {
      type: "value",
      axisLabel: { formatter: valueView === "ratio" ? (value: number) => `${Math.round(value * 100)}%` : axisMoney },
      splitLine: { lineStyle: { color: projectColors.surface } },
    },
    series: [
      { name: "承接", type: "bar", stack: "cashflow", data: normalizedAssists, itemStyle: { color: "transparent" }, emphasis: { disabled: true }, silent: true },
      {
        name: unit,
        type: "bar",
        stack: "cashflow",
        data: display,
        barMaxWidth: 54,
        label: {
          show: true,
          position: "top",
          formatter: (params) => {
            const value = typeof params.value === "number" ? params.value : Number(params.value ?? 0);
            const prefix = items[params.dataIndex]?.kind === "outflow" ? "-" : "";
            return `${prefix}${valueView === "ratio" ? `${(value * 100).toFixed(1)}%` : axisMoney(value)}`;
          },
        },
      },
    ],
  };
  const rows = items.map((item) => ({
    stage: item.label,
    direction: item.kind === "outflow" ? "流出" : item.kind === "result" ? "结果" : "流入",
    value: valueView === "ratio" ? formatRatio(String(item.value / denominator)) : moneyLabel(String(item.value), moneyUnit),
  }));
  return (
    <ChartFrame
      title="家庭年度现金流瀑布"
      description="从收入依次扣除必要生活、还贷、保险、教育赡养和弹性消费。"
      unit={unit}
      timeRange="最近完整年度的年化口径"
      methodology="各现金流记录先按频率年化，再按用途互斥归类"
      updatedAt={formatDate(analysis.meta.analysis_date)}
      source="客户确认的年度收支记录"
      insight={`年度收入扣除全部已记录支出后，年度结余为${moneyLabel(cashflow.annual_surplus, moneyUnit)}。`}
      option={option}
      columns={[{ key: "stage", label: "环节" }, { key: "direction", label: "方向" }, { key: "value", label: unit, numeric: true }]}
      rows={rows}
      legend={[
        { label: "流入", color: projectColors.brand },
        { label: "支出", color: projectColors.warning, pattern: "stripe" },
        { label: "结余", color: projectColors.goal },
      ]}
    />
  );
}

export function GoalTimelineChart({ plan }: { plan: PlanningResponse }) {
  const { moneyUnit, valueView, theme } = useDisplayPreferences();
  const projectColors = chartThemeFor(theme);
  const goals = [...plan.goals].sort((left, right) => left.adjusted_target_date.localeCompare(right.adjusted_target_date));
  const values = goals.map((goal) => {
    if (valueView === "ratio") {
      const future = Math.max(1, Number(goal.future_amount));
      return Number(goal.prepared_amount) / future;
    }
    return moneyNumber(goal.future_amount, moneyUnit);
  });
  const unit = valueView === "ratio" ? "目标准备率" : moneyUnit === "wan" ? "未来金额，万元" : "未来金额，元";
  const option: EChartsOption = {
    textStyle: { color: projectColors.text },
    grid: { left: 72, right: 34, top: 28, bottom: 76 },
    tooltip: { trigger: "axis" },
    xAxis: { type: "category", data: goals.map((goal) => goal.adjusted_target_date), axisLabel: { formatter: (value: string) => value.slice(0, 7), rotate: 25, color: projectColors.textMuted } },
    yAxis: {
      type: "value",
      min: 0,
      max: valueView === "ratio" ? 1 : undefined,
      axisLabel: { formatter: valueView === "ratio" ? (value: number) => `${Math.round(value * 100)}%` : axisMoney },
      splitLine: { lineStyle: { color: projectColors.surface } },
    },
    series: [{
      name: unit,
      type: "line",
      data: values,
      symbol: "circle",
      symbolSize: 12,
      lineStyle: { color: projectColors.goal, width: 2 },
      itemStyle: { color: projectColors.goal, borderColor: projectColors.brand, borderWidth: 2 },
      label: { show: true, formatter: ({ dataIndex }: { dataIndex: number }) => goals[dataIndex]?.name ?? "" },
    }],
  };
  const rows = goals.map((goal) => ({
    goal: goal.name,
    date: formatDate(goal.adjusted_target_date),
    priority: goal.priority,
    future: moneyLabel(goal.future_amount, moneyUnit),
    prepared: moneyLabel(goal.prepared_amount, moneyUnit),
    readiness: formatRatio(String(Number(goal.prepared_amount) / Math.max(1, Number(goal.future_amount)))),
    probability: "运行数字孪生后显示",
    conflict: goal.status === "conflict" ? "存在冲突" : "未命中冲突",
  }));
  return (
    <ChartFrame
      title="家庭目标时间轴"
      description="目标金额随期限和各自成本增速计算；准备率不冒充成功概率。"
      unit={unit}
      timeRange={`${formatDate(plan.meta.analysis_date)} 至 ${goals.at(-1) ? formatDate(goals.at(-1)!.adjusted_target_date) : "待补目标"}`}
      methodology="目标逐项未来值、现值、已准备金额和刚性约束"
      updatedAt={formatDate(plan.meta.analysis_date)}
      source={`目标事实层，规则 ${plan.meta.rule_version}`}
      insight={plan.conflicts.length > 0 ? `当前有 ${plan.conflicts.length} 组目标冲突。成功概率需运行数字孪生后读取路径分布。` : "当前目标未命中资金冲突；成功概率仍需运行数字孪生验证。"}
      option={option}
      state={goals.length === 0 ? "empty" : "ready"}
      columns={[
        { key: "goal", label: "目标" },
        { key: "date", label: "期限" },
        { key: "priority", label: "优先级", numeric: true },
        { key: "future", label: "未来金额", numeric: true },
        { key: "prepared", label: "已准备", numeric: true },
        { key: "readiness", label: "准备率", numeric: true },
        { key: "probability", label: "成功概率" },
        { key: "conflict", label: "冲突" },
      ]}
      rows={rows}
      legend={[{ label: valueView === "ratio" ? "目标准备率" : "未来目标金额", color: projectColors.goal, pattern: "line" }]}
    />
  );
}
