import { useEffect, useMemo, useRef, useState } from "react";
import {
  advanceTwinRun,
  cancelTwinRun,
  createTwinRun,
  fetchTwinScenarios,
  twinExportUrl,
  type ScenarioCatalog,
  type SimulationDistribution,
  type TwinResult,
  type TwinRunRequest,
  type TwinRunStatus,
} from "../../api/twin";
import { fetchHouseholds, type HouseholdSummary } from "../../api/financial";
import { formatDate, formatMoney, formatRatio } from "../../utils/format";
import { Button } from "../ui/Button";
import { StatusBadge } from "../ui/StatusBadge";
import { WealthFanChart } from "./WealthFanChart";

type TwinView = "client" | "advisor" | "risk";
type DistributionKey = "original_stress" | "optimized_stress";

const phaseCopy: Record<string, string> = {
  queued: "等待执行",
  baseline_completed: "基线已完成",
  original_stress_completed: "组合压力已完成",
  completed: "结果与审计已固化",
  cancelled: "运行已取消",
  failed: "运行失败",
};

function optionalNumber(value: string): number | undefined {
  const trimmed = value.trim();
  return trimmed === "" ? undefined : Number(trimmed);
}

function optionalDecimal(value: string): string | undefined {
  const trimmed = value.trim();
  return trimmed === "" ? undefined : trimmed;
}

function signedRatio(value: string): string {
  const numeric = Number(value) * 100;
  return `${numeric > 0 ? "+" : ""}${numeric.toFixed(1)} 个百分点`;
}

export function TwinWorkspace({ householdId, view = "client" }: { householdId: string; view?: TwinView }) {
  const [catalog, setCatalog] = useState<ScenarioCatalog | null>(null);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [selectedCodes, setSelectedCodes] = useState<string[]>(["unemployment_equity_down_30"]);
  const [seed, setSeed] = useState("20260804");
  const [pathCount, setPathCount] = useState("100");
  const [horizonYears, setHorizonYears] = useState("30");
  const [retirementAge, setRetirementAge] = useState("62");
  const [monthlySavings, setMonthlySavings] = useState("2000.00");
  const [equityRatio, setEquityRatio] = useState("0.30");
  const [liquidityBuffer, setLiquidityBuffer] = useState("120000.00");
  const [unemploymentMonths, setUnemploymentMonths] = useState("");
  const [incomeDrop, setIncomeDrop] = useState("");
  const [housePriceChange, setHousePriceChange] = useState("");
  const [educationOverrun, setEducationOverrun] = useState("");
  const [medicalShock, setMedicalShock] = useState("");
  const [inflation, setInflation] = useState("");
  const [incomeGrowth, setIncomeGrowth] = useState("");
  const [run, setRun] = useState<TwinRunStatus | null>(null);
  const [running, setRunning] = useState(false);
  const [canceling, setCanceling] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [distributionKey, setDistributionKey] = useState<DistributionKey>("optimized_stress");
  const controllerRef = useRef<AbortController | null>(null);
  const runIdRef = useRef<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setCatalogError(null);
    fetchTwinScenarios(controller.signal)
      .then((payload) => {
        setCatalog(payload);
        const fallback = payload.scenarios.find((item) => item.code === "unemployment_equity_down_30") ?? payload.scenarios[0];
        if (fallback) setSelectedCodes([fallback.code]);
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setCatalogError("压力场景目录当前不可用；系统不会用前端常量伪造计算结果。");
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    controllerRef.current?.abort();
    runIdRef.current = null;
    setRun(null);
    setRunError(null);
    setRunning(false);
  }, [householdId]);

  useEffect(() => () => controllerRef.current?.abort(), []);

  const selectedScenarioNames = useMemo(
    () => catalog?.scenarios.filter((item) => selectedCodes.includes(item.code)).map((item) => item.name) ?? [],
    [catalog, selectedCodes],
  );

  function toggleScenario(code: string) {
    setSelectedCodes((current) => {
      if (current.includes(code)) return current.length === 1 ? current : current.filter((item) => item !== code);
      return current.length >= 6 ? current : [...current, code];
    });
  }

  function buildRequest(): TwinRunRequest {
    return {
      analysis_date: "2026-08-04",
      seed: Number(seed),
      path_count: Number(pathCount),
      horizon_years: Number(horizonYears),
      output_interval_months: 12,
      scenario_codes: selectedCodes,
      scenario_overrides: {
        ...(optionalNumber(unemploymentMonths) === undefined ? {} : { unemployment_months: optionalNumber(unemploymentMonths) }),
        ...(optionalDecimal(incomeDrop) === undefined ? {} : { income_reduction_ratio: optionalDecimal(incomeDrop) }),
        ...(optionalDecimal(medicalShock) === undefined ? {} : { medical_shock_amount: optionalDecimal(medicalShock) }),
        ...(optionalDecimal(educationOverrun) === undefined ? {} : { education_overrun_amount: optionalDecimal(educationOverrun) }),
        ...(optionalDecimal(housePriceChange) === undefined ? {} : { property_value_change_ratio: optionalDecimal(housePriceChange) }),
      },
      plan_adjustments: {
        primary_retirement_age: Number(retirementAge),
        additional_monthly_savings: monthlySavings,
        equity_ratio: equityRatio,
        liquidity_reallocation_amount: liquidityBuffer,
      },
      assumption_overrides: {
        ...(optionalDecimal(inflation) === undefined ? {} : { inflation_rate: optionalDecimal(inflation) }),
        ...(optionalDecimal(incomeGrowth) === undefined ? {} : { income_growth_rate: optionalDecimal(incomeGrowth) }),
      },
      family_events: [],
    };
  }

  async function startSimulation() {
    if (!catalog || selectedCodes.length === 0) return;
    const controller = new AbortController();
    controllerRef.current = controller;
    setRunError(null);
    setRun(null);
    setRunning(true);
    try {
      let status = await createTwinRun(householdId, buildRequest(), controller.signal);
      runIdRef.current = status.run_id;
      setRun(status);
      for (let step = 0; step < 12 && (status.status === "queued" || status.status === "running"); step += 1) {
        status = await advanceTwinRun(householdId, status.run_id, controller.signal);
        setRun(status);
      }
      if (status.status !== "completed" && status.status !== "cancelled") {
        throw new Error("运行未在预期阶段内完成");
      }
    } catch (error: unknown) {
      if (!(error instanceof DOMException && error.name === "AbortError")) {
        setRunError("数字孪生运行失败；不会展示部分路径或估算结论，请核对输入后重试。");
      }
    } finally {
      setRunning(false);
      controllerRef.current = null;
    }
  }

  async function cancelSimulation() {
    const runId = runIdRef.current;
    if (!runId) return;
    setCanceling(true);
    controllerRef.current?.abort();
    try {
      const status = await cancelTwinRun(householdId, runId);
      setRun(status);
      setRunError(null);
    } catch {
      setRunError("取消请求未被确认；请读取运行状态后再决定是否重试。");
    } finally {
      setRunning(false);
      setCanceling(false);
    }
  }

  const result = run?.result ?? null;
  const distribution = result?.[distributionKey] ?? null;
  const heading = view === "risk" ? "模型运行、取消与审计证据" : view === "advisor" ? "家庭路径与方案反事实复核" : "把家庭未来拆成可检验的路径";

  return (
    <section className="twin-workspace" data-view={view} aria-labelledby={`twin-heading-${view}`}>
      <header className="twin-header">
        <div>
          <p className="section-index">家庭财富数字孪生 · Monte Carlo</p>
          <h2 id={`twin-heading-${view}`}>{heading}</h2>
          <p>大语言模型不参与金额、比率或配置计算；每条路径都由同一版本的确定性状态转移引擎生成。</p>
        </div>
        <aside className="twin-boundary-note">
          <strong>Mock 可独立运行</strong>
          <span>无需外部模型、真实银行接口或网络连接</span>
        </aside>
      </header>

      <form className="twin-control-panel" onSubmit={(event) => { event.preventDefault(); void startSimulation(); }}>
        <fieldset className="twin-scenario-fieldset" disabled={running || canceling || !catalog}>
          <legend>选择可组合压力场景（1—6 个）</legend>
          {catalogError ? <p role="alert">{catalogError}</p> : null}
          {!catalog && !catalogError ? <p aria-live="polite">正在读取版本化场景目录…</p> : null}
          {catalog ? (
            <>
              <p>{catalog.scenario_count} 个内置场景 · 版本 {catalog.scenario_version} · {catalog.source_type}</p>
              <div className="scenario-picker">
                {catalog.scenarios.map((scenario) => (
                  <label key={scenario.code} data-selected={selectedCodes.includes(scenario.code)}>
                    <input type="checkbox" checked={selectedCodes.includes(scenario.code)} onChange={() => toggleScenario(scenario.code)} />
                    <span><strong>{scenario.name}</strong><small>{scenario.description}</small></span>
                  </label>
                ))}
              </div>
            </>
          ) : null}
        </fieldset>

        <div className="twin-control-grid">
          <Control label="随机种子" hint="同一输入与种子可复现">
            <input aria-label="随机种子" type="number" min="0" max="2147483647" value={seed} onChange={(event) => setSeed(event.target.value)} required />
          </Control>
          <Control label="模拟路径数" hint="100—5000；现场默认 100">
            <input aria-label="模拟路径数" type="number" min="100" max="5000" step="100" value={pathCount} onChange={(event) => setPathCount(event.target.value)} required />
          </Control>
          <Control label="模拟期限" hint="5—60 年">
            <input aria-label="模拟期限" type="number" min="5" max="60" value={horizonYears} onChange={(event) => setHorizonYears(event.target.value)} required /><span className="input-unit">年</span>
          </Control>
          <Control label="主收入者退休年龄" hint="就业收入到龄停止">
            <input aria-label="主收入者退休年龄" type="range" min="45" max="75" value={retirementAge} onChange={(event) => setRetirementAge(event.target.value)} /><output>{retirementAge} 岁</output>
          </Control>
          <Control label="每月新增储蓄" hint="优化方案的显式反事实">
            <input aria-label="每月新增储蓄" type="number" min="0" step="100" value={monthlySavings} onChange={(event) => setMonthlySavings(event.target.value)} required /><span className="input-unit">元</span>
          </Control>
          <Control label="权益资产假设" hint="仅针对可投资金融资产，不是家庭总资产">
            <input aria-label="权益资产假设" type="range" min="0" max="0.8" step="0.05" value={equityRatio} onChange={(event) => setEquityRatio(event.target.value)} /><output>{formatRatio(equityRatio, 0)}</output>
          </Control>
          <Control label="转为流动性缓冲" hint="资产内部重分类，起点净资产不变">
            <input aria-label="转为流动性缓冲" type="number" min="0" step="1000" value={liquidityBuffer} onChange={(event) => setLiquidityBuffer(event.target.value)} required /><span className="input-unit">元</span>
          </Control>
        </div>

        <details className="twin-advanced-controls">
          <summary>覆盖场景参数与基础假设</summary>
          <p>留空即沿用所选场景和规则版本；填写后会进入参数哈希与导出证据。</p>
          <div className="twin-control-grid twin-control-grid-advanced">
            <OverrideInput label="失业持续" unit="月" value={unemploymentMonths} onChange={setUnemploymentMonths} min="0" max="36" />
            <OverrideInput label="收入下降" unit="比例，如 0.30" value={incomeDrop} onChange={setIncomeDrop} min="0" max="1" step="0.05" />
            <OverrideInput label="房价变化" unit="比例，如 -0.20" value={housePriceChange} onChange={setHousePriceChange} min="-1" max="1" step="0.05" />
            <OverrideInput label="教育超支" unit="元" value={educationOverrun} onChange={setEducationOverrun} min="0" />
            <OverrideInput label="医疗自付冲击" unit="元" value={medicalShock} onChange={setMedicalShock} min="0" />
            <OverrideInput label="通胀假设" unit="比例" value={inflation} onChange={setInflation} min="0" max="0.2" step="0.005" />
            <OverrideInput label="收入增长假设" unit="比例" value={incomeGrowth} onChange={setIncomeGrowth} min="-0.2" max="0.2" step="0.005" />
          </div>
        </details>

        <div className="twin-run-bar">
          <div>
            <strong>本次压力</strong>
            <span>{selectedScenarioNames.join(" + ") || "等待场景目录"}</span>
          </div>
          <div className="twin-run-actions">
            <Button type="submit" loading={running} disabled={!catalog || selectedCodes.length === 0}>运行数字孪生</Button>
            {(run?.status === "queued" || run?.status === "running") ? <Button type="button" variant="secondary" loading={canceling} onClick={() => void cancelSimulation()}>取消运行</Button> : null}
          </div>
        </div>
      </form>

      {run ? <RunProgress run={run} /> : null}
      {runError ? <p className="twin-run-error" role="alert">{runError}</p> : null}
      {result && distribution && run ? (
        <TwinResultView
          result={result}
          run={run}
          view={view}
          distribution={distribution}
          distributionKey={distributionKey}
          onDistributionChange={setDistributionKey}
        />
      ) : null}
    </section>
  );
}

function Control({ label, hint, children }: { label: string; hint: string; children: React.ReactNode }) {
  return <label className="twin-control"><span>{label}</span><small>{hint}</small><div>{children}</div></label>;
}

function OverrideInput({ label, unit, value, onChange, min, max, step = "1" }: { label: string; unit: string; value: string; onChange: (value: string) => void; min: string; max?: string; step?: string }) {
  return <label className="twin-control"><span>{label}</span><small>可选覆盖 · {unit}</small><div><input aria-label={label} type="number" value={value} min={min} max={max} step={step} placeholder="沿用场景" onChange={(event) => onChange(event.target.value)} /></div></label>;
}

function RunProgress({ run }: { run: TwinRunStatus }) {
  const phase = run.phase.startsWith("scenario_") ? `单场景压力 ${run.phase.replace(/\D/g, " ").trim().replace(" ", " / ")}` : (phaseCopy[run.phase] ?? run.phase);
  const tone = run.status === "cancelled" || run.status === "failed" ? "danger" : run.status === "completed" ? "success" : "info";
  return (
    <section className="twin-progress" aria-live="polite" aria-label="数字孪生运行进度">
      <div><StatusBadge tone={tone}>{run.status === "completed" ? "已完成" : run.status === "cancelled" ? "已取消" : run.status === "failed" ? "失败" : "计算中"}</StatusBadge><strong>{phase}</strong><span>{run.progress_percent}%</span></div>
      <progress max="100" value={run.progress_percent}>{run.progress_percent}%</progress>
      <small>运行 {run.run_id.slice(0, 12)} · 种子 {run.seed} · {run.path_count} 路径 · {run.horizon_months} 月</small>
    </section>
  );
}

function TwinResultView({ result, run, view, distribution, distributionKey, onDistributionChange }: { result: TwinResult; run: TwinRunStatus; view: TwinView; distribution: SimulationDistribution; distributionKey: DistributionKey; onDistributionChange: (value: DistributionKey) => void }) {
  const avoided = Number(result.comparison.avoided_forced_sale_probability);
  return (
    <div className="twin-results">
      <header className="twin-result-header">
        <div>
          <p className="section-index">原方案 / 优化方案 · 共同随机数</p>
          <h3>{avoided > 0 ? `流动性缓冲使被迫出售概率下降 ${(avoided * 100).toFixed(0)} 个百分点` : "本次流动性调整没有降低被迫出售概率"}</h3>
          <p>{result.comparison.liquidity_explanation}</p>
        </div>
        <a className="button export-link" data-variant="primary" href={twinExportUrl(result.meta.household_id, result.meta.run_id)} download>导出完整结果</a>
      </header>

      <ComparisonLedger result={result} />

      <section className="twin-chart-section" aria-labelledby="twin-chart-heading">
        <header>
          <div><p className="section-index">路径切换</p><h3 id="twin-chart-heading">同一坐标检查压力前后的分布</h3></div>
          <div className="segmented-control" role="group" aria-label="选择路径方案">
            <button type="button" aria-pressed={distributionKey === "original_stress"} onClick={() => onDistributionChange("original_stress")}>原方案</button>
            <button type="button" aria-pressed={distributionKey === "optimized_stress"} onClick={() => onDistributionChange("optimized_stress")}>优化方案</button>
          </div>
        </header>
        <WealthFanChart points={distribution.fan} label={distribution.label} pathCount={distribution.path_count} seed={result.assumptions.seed} horizonMonths={distribution.horizon_months} />
      </section>

      <div className="twin-evidence-layout">
        <GoalOutcomes distribution={distribution} />
        <ScenarioImpactLedger result={result} />
      </div>
      <FailureAndWorst distribution={distribution} />
      <ModelEvidence result={result} run={run} view={view} />
    </div>
  );
}

function ComparisonLedger({ result }: { result: TwinResult }) {
  const rows: Array<{ label: string; data: SimulationDistribution; note: string }> = [
    { label: "无冲击基线", data: result.baseline, note: "只使用基础假设" },
    { label: "原方案压力", data: result.original_stress, note: "所选压力，不改家庭计划" },
    { label: "优化方案压力", data: result.optimized_stress, note: "同一压力、种子和路径" },
  ];
  return (
    <section className="twin-comparison" aria-labelledby="twin-comparison-heading">
      <header><div><p className="section-index">方案概率账本</p><h3 id="twin-comparison-heading">压力没有被重新抽样“美化”</h3></div><p>目标成功是所有目标同时达成的路径占比；被迫出售不含退休目标的计划性提取。</p></header>
      <div className="data-table-wrap" tabIndex={0} role="region" aria-label="数字孪生方案概率对照">
        <table className="data-table twin-comparison-table">
          <thead><tr><th>路径集</th><th>目标成功</th><th>资金耗尽</th><th>被迫出售</th><th>出售金额中位数</th><th>期末 P10 / 中位数</th></tr></thead>
          <tbody>{rows.map((row) => (
            <tr key={row.label} data-plan={row.label === "优化方案压力" ? "optimized" : "original"}>
              <td><strong>{row.label}</strong><small>{row.note}</small></td>
              <td className="numeric-cell">{formatRatio(row.data.goal_success_probability)}</td>
              <td className="numeric-cell">{formatRatio(row.data.depletion_probability)}</td>
              <td className="numeric-cell">{formatRatio(row.data.forced_sale_probability)}</td>
              <td className="numeric-cell">{formatMoney(row.data.median_forced_sale_amount)}</td>
              <td className="numeric-cell">{formatMoney(row.data.ending_net_worth_p10, true)} / {formatMoney(row.data.ending_net_worth_median, true)}</td>
            </tr>
          ))}</tbody>
        </table>
      </div>
      <div className="twin-delta-strip">
        <span>压力相对基线 <strong>{signedRatio(result.comparison.stress_change)}</strong></span>
        <span>优化相对原方案 <strong>{signedRatio(result.comparison.optimization_change)}</strong></span>
        <span>被迫出售概率减少 <strong>{signedRatio(result.comparison.avoided_forced_sale_probability)}</strong></span>
      </div>
      {result.comparison.positive_override_explanation ? <p className="twin-positive-override">{result.comparison.positive_override_explanation}</p> : null}
    </section>
  );
}

function GoalOutcomes({ distribution }: { distribution: SimulationDistribution }) {
  return (
    <section className="twin-goals" aria-labelledby="twin-goals-heading">
      <p className="section-index">目标结果</p>
      <h3 id="twin-goals-heading">每个目标独立核对到期扣减</h3>
      <ol>{distribution.goal_outcomes.map((goal) => (
        <li key={goal.goal_id}>
          <div><strong>{goal.name}</strong><span>第 {goal.due_month} 月 · {formatMoney(goal.required_amount)}</span></div>
          <progress max="1" value={goal.success_probability} aria-label={`${goal.name}成功概率 ${formatRatio(goal.success_probability)}`}>{formatRatio(goal.success_probability)}</progress>
          <b>{formatRatio(goal.success_probability)}</b>
          <small>失败路径短缺中位数 {formatMoney(goal.median_shortfall)}</small>
        </li>
      ))}</ol>
    </section>
  );
}

function ScenarioImpactLedger({ result }: { result: TwinResult }) {
  return (
    <section className="twin-impacts" aria-labelledby="twin-impact-heading">
      <p className="section-index">逐场景标准回答</p>
      <h3 id="twin-impact-heading">不止一个成功率</h3>
      <div>{result.scenario_impacts.map((impact) => (
        <details key={impact.scenario_code} open={result.scenario_impacts.length === 1}>
          <summary><span><strong>{impact.name}</strong><small>{impact.scenario_code}</small></span><StatusBadge tone={impact.applicable ? "warning" : "info"}>{impact.applicable ? "已计算" : "不适用"}</StatusBadge></summary>
          <dl>
            <div><dt>应急资金可撑</dt><dd>{impact.emergency_support_months} 个月</dd></div>
            <div><dt>最先失败目标</dt><dd>{impact.first_failed_goal ?? "样本内无目标失败"}</dd></div>
            <div><dt>被迫出售</dt><dd>{formatRatio(impact.forced_sale_probability)} · {formatMoney(impact.median_forced_sale_amount)}</dd></div>
            <div><dt>保险抵扣 / 缺口</dt><dd>{formatMoney(impact.insurance_coverage_applied)} / {formatMoney(impact.remaining_medical_gap)}</dd></div>
            <div><dt>退休需延后</dt><dd>{impact.retirement_delay_needed ? `${impact.suggested_retirement_delay_years} 年` : "当前样本不需要"}</dd></div>
            <div><dt>每月可压缩支出</dt><dd>{formatMoney(impact.monthly_compressible_expenses)}</dd></div>
            <div><dt>所需新增月储蓄</dt><dd>{formatMoney(impact.required_additional_monthly_savings)}</dd></div>
            <div><dt>成功率变化</dt><dd>{signedRatio(impact.success_probability_change)}</dd></div>
          </dl>
          <p>{impact.explanation}</p>
        </details>
      ))}</div>
    </section>
  );
}

function FailureAndWorst({ distribution }: { distribution: SimulationDistribution }) {
  return (
    <section className="twin-tail-risk" aria-labelledby="twin-tail-heading">
      <header><div><p className="section-index">失败时间与最差路径</p><h3 id="twin-tail-heading">尾部风险保留路径编号</h3></div><p>用于解释失败发生在何时，不用于挑选“看起来最好”的随机样本。</p></header>
      <div className="twin-tail-layout">
        <div className="failure-bars">
          <h4>首次目标失败分布</h4>
          {distribution.failure_time_distribution.length === 0 ? <p>本次样本没有目标失败路径。</p> : <ol>{distribution.failure_time_distribution.map((bucket) => (
            <li key={bucket.year}><span>第 {bucket.year} 年</span><progress max="1" value={bucket.probability}>{formatRatio(bucket.probability)}</progress><b>{formatRatio(bucket.probability)}</b><small>{bucket.most_common_goal ?? "—"}</small></li>
          ))}</ol>}
        </div>
        <details className="worst-paths">
          <summary>查看最差 5 条路径</summary>
          <div className="data-table-wrap" tabIndex={0} role="region" aria-label="最差路径明细">
            <table className="data-table"><thead><tr><th>路径</th><th>期末 / 最低净资产</th><th>首次失败</th><th>耗尽月</th><th>被迫出售</th></tr></thead><tbody>{distribution.worst_paths.map((path) => (
              <tr key={path.path_id}><td>#{path.path_id}</td><td>{formatMoney(path.ending_net_worth, true)}<small>{formatMoney(path.minimum_net_worth, true)}</small></td><td>{path.first_failed_goal ?? "无"}<small>{path.first_failure_month ? `第 ${path.first_failure_month} 月` : "—"}</small></td><td>{path.depletion_month ?? "—"}</td><td>{formatMoney(path.forced_sale_amount)}</td></tr>
            ))}</tbody></table>
          </div>
        </details>
      </div>
    </section>
  );
}

function ModelEvidence({ result, run, view }: { result: TwinResult; run: TwinRunStatus; view: TwinView }) {
  return (
    <section className="twin-model-evidence" aria-labelledby="twin-evidence-heading">
      <header><div><p className="section-index">模型与审计证据</p><h3 id="twin-evidence-heading">从家庭事实到参数哈希</h3></div><StatusBadge tone={result.original_stress.validation.all_values_finite ? "success" : "danger"}>{result.original_stress.validation.all_values_finite ? "数值校验通过" : "数值异常"}</StatusBadge></header>
      <div className="twin-version-rail">
        <span>公式 {result.meta.formula_version}</span><span>引擎 {result.meta.engine_version}</span><span>规则 {result.meta.rule_version}</span><span>场景 {result.meta.scenario_version}</span><span>结果 {result.meta.result_version}</span>
      </div>
      <details open={view === "risk"}>
        <summary>查看输入、假设与审计记录</summary>
        <dl className="twin-audit-grid">
          <div><dt>家庭资产 / 负债</dt><dd>{formatMoney(result.initial_state.total_assets)} / {formatMoney(result.initial_state.total_liabilities)}</dd></div>
          <div><dt>年度收入 / 支出</dt><dd>{formatMoney(result.initial_state.annual_income)} / {formatMoney(result.initial_state.annual_expenses_excluding_debt_service)}</dd></div>
          <div><dt>通胀 / 收入增长</dt><dd>{formatRatio(result.assumptions.inflation_rate)} / {formatRatio(result.assumptions.income_growth_rate)}</dd></div>
          <div><dt>时间步长 / 输出</dt><dd>{result.assumptions.time_step_months} 月 / {result.assumptions.output_interval_months} 月</dd></div>
          <div><dt>共同随机数</dt><dd>{result.original_stress.validation.common_random_numbers ? "是；方案之间复用" : "否"}</dd></div>
          <div><dt>失业期主收入支付</dt><dd>{formatMoney(result.original_stress.validation.primary_income_paid_during_interruption_max)}</dd></div>
          <div><dt>参数哈希</dt><dd><code>{result.assumptions.parameter_hash}</code></dd></div>
          <div><dt>输入版本</dt><dd><code>{result.meta.input_version}</code></dd></div>
          <div><dt>审计事件</dt><dd><code>{run.audit_event_id ?? "尚未生成"}</code></dd></div>
          <div><dt>数据 / 分析日</dt><dd>{formatDate(result.meta.data_as_of)} / {formatDate(result.meta.analysis_date)}</dd></div>
        </dl>
        <p>{result.initial_state.counting_note}</p><p>{result.counting_note}</p>
      </details>
      <details>
        <summary>查看模型限制</summary>
        <ul>{result.limitations.map((item) => <li key={item}>{item}</li>)}</ul>
      </details>
    </section>
  );
}

export function TwinPortalWorkspace({ view }: { view: "advisor" | "risk" }) {
  const [households, setHouseholds] = useState<HouseholdSummary[]>([]);
  const [householdId, setHouseholdId] = useState("");
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    fetchHouseholds(controller.signal)
      .then((items) => {
        setHouseholds(items);
        setHouseholdId((items.find((item) => item.code === "DEMO_B") ?? items[0])?.id ?? "");
      })
      .catch(() => setError("无法读取家庭列表；未运行任何数字孪生路径。"));
    return () => controller.abort();
  }, []);
  return (
    <section className="twin-portal-wrapper">
      <label className="portal-household-control"><span>数字孪生复核家庭</span><select value={householdId} onChange={(event) => setHouseholdId(event.target.value)} disabled={households.length === 0}>{households.map((household) => <option key={household.id} value={household.id}>{household.name} · {household.code}</option>)}</select></label>
      {error ? <p role="alert">{error}</p> : null}
      {householdId ? <TwinWorkspace householdId={householdId} view={view} /> : null}
    </section>
  );
}
