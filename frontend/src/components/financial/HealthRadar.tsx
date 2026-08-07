import type { EChartsOption } from "echarts";
import type { HealthDimension } from "../../api/financial";
import { useDisplayPreferences } from "../../contexts/displayPreferences";
import { ChartFrame } from "../charts/ChartFrame";
import { chartThemeFor } from "../charts/chartTheme";

interface HealthRadarProps {
  dimensions: HealthDimension[];
  dataAsOf?: string;
  ruleVersion?: string;
}

export function HealthRadar({ dimensions, dataAsOf = "当前数据日", ruleVersion = "当前规则" }: HealthRadarProps) {
  const { theme } = useDisplayPreferences();
  const chartTheme = chartThemeFor(theme);
  const option: EChartsOption = {
    tooltip: { trigger: "item" },
    radar: {
      indicator: dimensions.map((dimension) => ({ name: dimension.name, max: 100 })),
      splitNumber: 4,
      axisName: { color: chartTheme.textMuted },
      splitLine: { lineStyle: { color: chartTheme.surface } },
      splitArea: { areaStyle: { color: ["transparent", chartTheme.brandWash] } },
      axisLine: { lineStyle: { color: chartTheme.muted } },
    },
    series: [{
      name: "财务健康维度",
      type: "radar",
      data: [{ value: dimensions.map((dimension) => Number(dimension.score)), name: "当前家庭" }],
      lineStyle: { color: chartTheme.brand, width: 2 },
      itemStyle: { color: chartTheme.action },
      areaStyle: { color: chartTheme.brandWash },
    }],
  };
  return (
    <ChartFrame
      className="health-radar"
      title="家庭财务健康雷达"
      description="后端确定性指标归一化后的辅助展示，不属于监管评级或投资评级。"
      unit="0-100 分"
      timeRange={`截至 ${dataAsOf}`}
      methodology="流动性、偿债、储蓄、保障、分散、养老与目标维度归一化"
      updatedAt={dataAsOf}
      source={`财务健康规则 ${ruleVersion}`}
      insight="雷达图只帮助定位薄弱维度；最终行动应回到原始指标、适用条件和家庭目标。"
      option={option}
      state={dimensions.length < 3 ? "empty" : "ready"}
      columns={[{ key: "dimension", label: "维度" }, { key: "score", label: "得分", numeric: true }, { key: "explanation", label: "解释" }]}
      rows={dimensions.map((dimension) => ({ dimension: dimension.name, score: Number(dimension.score).toFixed(0), explanation: dimension.explanation }))}
      legend={[{ label: "当前家庭", color: chartTheme.brand }]}
    />
  );
}
