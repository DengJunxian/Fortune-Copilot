import type { EChartsOption } from "echarts";
import type { FanPoint } from "../../api/twin";
import { useDisplayPreferences } from "../../contexts/displayPreferences";
import { formatDate, formatMoney, formatMoneyInWan } from "../../utils/format";
import { ChartFrame } from "../charts/ChartFrame";
import { chartThemeFor } from "../charts/chartTheme";

export function WealthFanChart({
  points,
  label,
  pathCount,
  seed,
  horizonMonths,
}: {
  points: FanPoint[];
  label: string;
  pathCount: number;
  seed: number;
  horizonMonths: number;
}) {
  const { moneyUnit, theme } = useDisplayPreferences();
  const chartTheme = chartThemeFor(theme);
  const divisor = moneyUnit === "wan" ? 10_000 : 1;
  const final = points.at(-1);
  const money = (value: string) => moneyUnit === "wan" ? formatMoneyInWan(value) : formatMoney(value, true);
  const dates = points.map((point) => point.date.slice(0, 7));
  const p10 = points.map((point) => Number(point.p10) / divisor);
  const p25 = points.map((point) => Number(point.p25) / divisor);
  const p50 = points.map((point) => Number(point.p50) / divisor);
  const p75Band = points.map((point) => (Number(point.p75) - Number(point.p25)) / divisor);
  const p90Band = points.map((point) => (Number(point.p90) - Number(point.p10)) / divisor);
  const option: EChartsOption = {
    grid: { left: 76, right: 34, top: 24, bottom: 58 },
    tooltip: { trigger: "axis" },
    xAxis: { type: "category", data: dates, axisLabel: { interval: Math.max(0, Math.floor(points.length / 6)) } },
    yAxis: {
      type: "value",
      axisLabel: { formatter: (value: number) => new Intl.NumberFormat("zh-CN", { notation: "compact", maximumFractionDigits: 1 }).format(value) },
      splitLine: { lineStyle: { color: chartTheme.surface } },
    },
    series: [
      { name: "P10 基线", type: "line", stack: "outer", data: p10, symbol: "none", lineStyle: { opacity: 0 }, areaStyle: { opacity: 0 }, silent: true },
      { name: "P10-P90 区间", type: "line", stack: "outer", data: p90Band, symbol: "none", lineStyle: { opacity: 0 }, areaStyle: { color: chartTheme.brandWash } },
      { name: "P25 基线", type: "line", stack: "inner", data: p25, symbol: "none", lineStyle: { opacity: 0 }, areaStyle: { opacity: 0 }, silent: true },
      { name: "P25-P75 区间", type: "line", stack: "inner", data: p75Band, symbol: "none", lineStyle: { opacity: 0 }, areaStyle: { color: chartTheme.brandWashStrong } },
      {
        name: "P50 中位数",
        type: "line",
        data: p50,
        symbol: "none",
        lineStyle: { color: chartTheme.action, width: 2 },
        markLine: { symbol: "none", label: { formatter: "净资产 0" }, data: [{ yAxis: 0 }], lineStyle: { color: chartTheme.warning, type: "dashed" } },
      },
    ],
  };
  const conclusion = final
    ? `期末中位数为${money(final.p50)}；80% 路径区间为${money(final.p10)}至${money(final.p90)}。`
    : "当前没有足够路径点生成区间。";
  return (
    <ChartFrame
      className="fan-chart"
      title="净资产分位数扇形图"
      description={`${label}。阴影是路径分布，不是收益承诺；中线也不是确定预测。`}
      unit={moneyUnit === "wan" ? "人民币万元" : "人民币元"}
      timeRange={`${horizonMonths / 12} 年`}
      methodology={`${pathCount} 条路径，共同随机数种子 ${seed}`}
      updatedAt={points[0]?.date ? formatDate(points[0].date) : "待运行"}
      source="家庭事实层 + 版本化 internal_demo 假设 + 逐月状态转移"
      insight={conclusion}
      option={option}
      state={points.length < 2 ? "empty" : "ready"}
      columns={[
        { key: "date", label: "日期 / 年龄" },
        { key: "p10", label: "P10", numeric: true },
        { key: "p25", label: "P25", numeric: true },
        { key: "p50", label: "中位数", numeric: true },
        { key: "p75", label: "P75", numeric: true },
        { key: "p90", label: "P90", numeric: true },
      ]}
      rows={points.map((point) => ({
        date: `${formatDate(point.date)} / ${point.primary_age} 岁`,
        p10: money(point.p10),
        p25: money(point.p25),
        p50: money(point.p50),
        p75: money(point.p75),
        p90: money(point.p90),
      }))}
      legend={[
        { label: "P10-P90", color: chartTheme.muted, pattern: "stripe" },
        { label: "P25-P75", color: chartTheme.brand },
        { label: "P50 中位数", color: chartTheme.action, pattern: "line" },
      ]}
    />
  );
}
