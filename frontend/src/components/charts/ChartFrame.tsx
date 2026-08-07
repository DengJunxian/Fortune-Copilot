import {
  useEffect,
  useId,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react";
import { BarChart, LineChart, RadarChart, ScatterChart } from "echarts/charts";
import {
  AriaComponent,
  DatasetComponent,
  GridComponent,
  LegendComponent,
  MarkLineComponent,
  TooltipComponent,
} from "echarts/components";
import type { EChartsOption } from "echarts";
import { init, use as registerEChartsModules, type ECharts } from "echarts/core";
import { SVGRenderer } from "echarts/renderers";

registerEChartsModules([
  BarChart,
  LineChart,
  RadarChart,
  ScatterChart,
  AriaComponent,
  DatasetComponent,
  GridComponent,
  LegendComponent,
  MarkLineComponent,
  TooltipComponent,
  SVGRenderer,
]);

export interface ChartColumn {
  key: string;
  label: string;
  numeric?: boolean;
}

export type ChartRow = Record<string, string | number>;

export interface ChartLegendItem {
  label: string;
  color: string;
  pattern?: "solid" | "stripe" | "line";
}

interface ChartFrameProps {
  title: string;
  description: string;
  unit: string;
  timeRange: string;
  methodology: string;
  updatedAt: string;
  source: string;
  insight: string;
  option: EChartsOption;
  columns: ChartColumn[];
  rows: ChartRow[];
  legend?: ChartLegendItem[];
  state?: "ready" | "loading" | "empty" | "error";
  errorAction?: ReactNode;
  className?: string;
}

export function ChartFrame({
  title,
  description,
  unit,
  timeRange,
  methodology,
  updatedAt,
  source,
  insight,
  option,
  columns,
  rows,
  legend = [],
  state = "ready",
  errorAction,
  className = "",
}: ChartFrameProps) {
  const headingId = useId();
  const descriptionId = useId();
  return (
    <figure className={`chart-frame ${className}`.trim()} aria-labelledby={headingId}>
      <figcaption className="chart-frame-header">
        <div>
          <h3 id={headingId}>{title}</h3>
          <p id={descriptionId}>{description}</p>
        </div>
        <dl className="chart-contract">
          <div><dt>单位</dt><dd>{unit}</dd></div>
          <div><dt>时间范围</dt><dd>{timeRange}</dd></div>
          <div><dt>口径</dt><dd>{methodology}</dd></div>
          <div><dt>更新时间</dt><dd>{updatedAt}</dd></div>
        </dl>
      </figcaption>
      {legend.length > 0 ? <ChartLegend items={legend} /> : null}
      {state === "loading" ? <ChartLoadingState /> : null}
      {state === "empty" ? <ChartErrorState title="暂无可绘制数据" detail="补齐数据后会自动生成图表和等价数据表。" /> : null}
      {state === "error" ? <ChartErrorState title="图表生成失败" detail="原始数据没有被替换或补造。" action={errorAction} /> : null}
      {state === "ready" ? (
        <EChartCanvas option={option} title={title} descriptionId={descriptionId} />
      ) : null}
      <ChartInsight>{insight}</ChartInsight>
      <p className="chart-source">来源：{source}</p>
      <ChartDataTable title={title} columns={columns} rows={rows} />
    </figure>
  );
}

function EChartCanvas({
  option,
  title,
  descriptionId,
}: {
  option: EChartsOption;
  title: string;
  descriptionId: string;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [renderError, setRenderError] = useState(false);

  useEffect(() => {
    const element = containerRef.current;
    if (!element || typeof ResizeObserver === "undefined") return;
    let chart: ECharts | null = null;
    try {
      chart = init(element, undefined, { renderer: "svg" });
      const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      chart.setOption({
        aria: { enabled: true, decal: { show: true } },
        animation: !reduceMotion,
        animationDuration: reduceMotion ? 0 : 220,
        animationDurationUpdate: reduceMotion ? 0 : 180,
        ...option,
      });
      const observer = new ResizeObserver(() => chart?.resize());
      observer.observe(element);
      return () => {
        observer.disconnect();
        chart?.dispose();
      };
    } catch {
      setRenderError(true);
      chart?.dispose();
      return undefined;
    }
  }, [option]);

  if (renderError) {
    return <ChartErrorState title="图表渲染失败" detail="请使用下方等价数据表核对全部数值。" />;
  }
  return (
    <div
      className="echart-accessible-image"
      role="img"
      aria-label={title}
      aria-describedby={descriptionId}
    >
      <div ref={containerRef} className="echart-canvas" aria-hidden="true" />
    </div>
  );
}

export function ChartLegend({ items }: { items: ChartLegendItem[] }) {
  return (
    <ul className="chart-legend" aria-label="图例">
      {items.map((item) => (
        <li key={item.label}>
          <span
            className="chart-legend-swatch"
            data-pattern={item.pattern ?? "solid"}
            style={{ "--legend-color": item.color } as CSSProperties}
            aria-hidden="true"
          />
          {item.label}
        </li>
      ))}
    </ul>
  );
}

export function ChartInsight({ children }: { children: ReactNode }) {
  return (
    <aside className="chart-insight">
      <strong>读图结论</strong>
      <p>{children}</p>
    </aside>
  );
}

export function ChartDataTable({
  title,
  columns,
  rows,
}: {
  title: string;
  columns: ChartColumn[];
  rows: ChartRow[];
}) {
  return (
    <details className="chart-data-table">
      <summary>查看数据表</summary>
      <div className="data-table-wrap" role="region" tabIndex={0} aria-label={`${title}等价数据表`}>
        <table className="data-table">
          <thead><tr>{columns.map((column) => <th key={column.key}>{column.label}</th>)}</tr></thead>
          <tbody>
            {rows.map((row, rowIndex) => (
              <tr key={`${title}-${rowIndex}`}>
                {columns.map((column) => (
                  <td key={column.key} className={column.numeric ? "numeric-cell" : undefined}>
                    {row[column.key]}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

export function ChartErrorState({
  title,
  detail,
  action,
}: {
  title: string;
  detail: string;
  action?: ReactNode;
}) {
  return (
    <div className="chart-error-state" role="status">
      <strong>{title}</strong>
      <p>{detail}</p>
      {action}
    </div>
  );
}

function ChartLoadingState() {
  return (
    <div className="chart-loading-state" aria-live="polite">
      <span />
      <span />
      <span />
      <p>正在根据后端结果重绘</p>
    </div>
  );
}
