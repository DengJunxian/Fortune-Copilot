import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import {
  createGoal,
  fetchPlanning,
  persistPlanning,
  planningExportUrl,
  recalculatePlanning,
  type AccountAllocation,
  type CounterfactualResponse,
  type DenominatorId,
  type GoalCreateInput,
  type LifecycleStage,
  type PlanningResponse,
} from "../../api/planning";
import { formatDate, formatDomainLabel, formatMoney, formatRatio } from "../../utils/format";
import { Button } from "../ui/Button";
import { StatusBadge } from "../ui/StatusBadge";

interface PlanningWorkspaceProps {
  householdId: string;
  focus?: "all" | "accounts" | "goals" | "actions";
  preferredValueView?: "amount" | "ratio";
}

type DisplayMode = "amount" | DenominatorId;

const lifecycleLabels: Record<LifecycleStage, string> = {
  early_career: "初入职场",
  family_formation: "婚姻组建",
  parenting: "育儿成长",
  mature_family: "家庭成熟",
  retirement_preparation: "退休准备",
  retirement_and_legacy: "养老传承",
};

const denominatorLabels: Record<DenominatorId, string> = {
  total_assets: "占家庭总资产",
  investable_financial_assets: "占可投资金融资产",
  annual_new_surplus: "占年度新增结余",
};

const initialGoal: GoalCreateInput = {
  name: "",
  goal_type: "education",
  target_amount: "",
  target_date: "",
  rigidity: "important",
  priority: 5,
  can_defer: true,
  minimum_acceptable_amount: "",
  prepared_amount: "0.00",
  annual_cost_growth_rate: "0.030000",
};

function badgeTone(status: string): "success" | "warning" | "info" | "danger" {
  if (status === "pass" || status === "covered" || status === "funded") return "success";
  if (status === "block" || status === "critical" || status === "unfunded") return "danger";
  if (status === "limit" || status === "warning" || status === "partial") return "warning";
  return "info";
}

function measureValue(
  account: AccountAllocation,
  mode: DisplayMode,
  kind: "current" | "recommended",
): string {
  if (mode === "amount") {
    return formatMoney(kind === "current" ? account.current_amount : account.recommended_amount);
  }
  const measures = kind === "current" ? account.current_measures : account.measures;
  const measure = measures.find((item) => item.denominator_id === mode);
  return measure?.ratio === null || measure?.ratio === undefined
    ? "不适用"
    : formatRatio(measure.ratio);
}

export function PlanningWorkspace({
  householdId,
  focus = "all",
  preferredValueView = "amount",
}: PlanningWorkspaceProps) {
  const [basePlan, setBasePlan] = useState<PlanningResponse | null>(null);
  const [displayedPlan, setDisplayedPlan] = useState<PlanningResponse | null>(null);
  const [comparison, setComparison] = useState<CounterfactualResponse | null>(null);
  const [displayMode, setDisplayMode] = useState<DisplayMode>("amount");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [lifecycleOverride, setLifecycleOverride] = useState<LifecycleStage | "">("");
  const [goal, setGoal] = useState<GoalCreateInput>(initialGoal);
  const [goalFormOpen, setGoalFormOpen] = useState(false);
  const [savingGoal, setSavingGoal] = useState(false);
  const [recalculating, setRecalculating] = useState(false);
  const [persisting, setPersisting] = useState(false);
  const [scenario, setScenario] = useState({
    emergency: "0.00",
    debt: "0.00",
    savings: "0.00",
    preparedGoalId: "",
    preparedAmount: "0.00",
    deferGoalId: "",
    deferMonths: "12",
  });

  const load = useCallback(
    async (signal?: AbortSignal, override?: LifecycleStage) => {
      setLoading(true);
      setError(null);
      try {
        const payload = await fetchPlanning(householdId, signal, override);
        setBasePlan(payload);
        setDisplayedPlan(payload);
        setComparison(null);
      } catch (loadError) {
        if (loadError instanceof DOMException && loadError.name === "AbortError") return;
        setError("目标与四账户规划暂时不可用；页面不会补造任何金额或比例。");
      } finally {
        setLoading(false);
      }
    },
    [householdId],
  );

  useEffect(() => {
    const controller = new AbortController();
    setLifecycleOverride("");
    setStatusMessage(null);
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  useEffect(() => {
    setDisplayMode(preferredValueView === "ratio" ? "total_assets" : "amount");
  }, [preferredValueView]);

  const limitingConstraints = useMemo(
    () => displayedPlan?.constraints.filter((item) => item.limits_growth) ?? [],
    [displayedPlan],
  );

  async function updateLifecycle(value: LifecycleStage | "") {
    setLifecycleOverride(value);
    setStatusMessage(null);
    await load(undefined, value || undefined);
  }

  async function submitGoal(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSavingGoal(true);
    setStatusMessage(null);
    try {
      await createGoal(householdId, goal);
      setGoal(initialGoal);
      setGoalFormOpen(false);
      setStatusMessage("目标已写入家庭事实层，并按当前规则重新计算。 ");
      await load(undefined, lifecycleOverride || undefined);
    } catch {
      setStatusMessage("目标保存失败；请检查金额、日期和最低可接受金额。 ");
    } finally {
      setSavingGoal(false);
    }
  }

  async function submitScenario(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setRecalculating(true);
    setStatusMessage(null);
    const goalPrepared =
      scenario.preparedGoalId && Number(scenario.preparedAmount) > 0
        ? { [scenario.preparedGoalId]: scenario.preparedAmount }
        : {};
    try {
      const result = await recalculatePlanning(householdId, {
        analysis_date: basePlan?.meta.analysis_date,
        emergency_fund_addition: scenario.emergency || "0.00",
        high_interest_debt_reduction: scenario.debt || "0.00",
        monthly_savings_increase: scenario.savings || "0.00",
        goal_prepared_additions: goalPrepared,
        defer_goal_ids: scenario.deferGoalId ? [scenario.deferGoalId] : [],
        defer_months: scenario.deferGoalId ? Number(scenario.deferMonths) : 0,
        lifecycle_override: lifecycleOverride || null,
      });
      setComparison(result);
      setDisplayedPlan(result.scenario);
      setStatusMessage("反事实方案已由同一确定性规则版本重算；原方案仍保留用于对照。 ");
    } catch {
      setStatusMessage("反事实重算失败；调整额不能超过相应债务或可重新归类的金融资产。 ");
    } finally {
      setRecalculating(false);
    }
  }

  async function saveDraft() {
    setPersisting(true);
    setStatusMessage(null);
    try {
      const run = await persistPlanning(householdId);
      setStatusMessage(
        `已保存基线规划草案：${run.account_count} 个账户、${run.action_count} 个行动项。`,
      );
    } catch {
      setStatusMessage("规划草案保存失败；当前查看结果未被更改。 ");
    } finally {
      setPersisting(false);
    }
  }

  if (loading) {
    return (
      <section className="planning-workspace planning-loading" aria-live="polite">
        <p className="section-index">00 / 目标与四账户</p>
        <h2>正在按七步顺序核对家庭资金</h2>
        <p>先处理安全底线，再识别真正可用于长期增长的资金。</p>
      </section>
    );
  }

  if (error || !displayedPlan || !basePlan) {
    return (
      <section className="planning-workspace planning-unavailable" role="alert">
        <p className="section-index">00 / 目标与四账户</p>
        <h2>规划计算当前不可用</h2>
        <p>{error}</p>
        <Button type="button" variant="secondary" onClick={() => void load()}>重新计算</Button>
      </section>
    );
  }

  return (
    <section className="planning-workspace" aria-labelledby="planning-heading">
      <header className="planning-header">
        <div>
          <p className="section-index">00 / 目标与四账户</p>
          <h2 id="planning-heading">先过安全闸门，再安排长期资金</h2>
          <p>{displayedPlan.counting_note}</p>
        </div>
        <div className="planning-meta-actions">
          <Button type="button" variant="secondary" loading={persisting} onClick={() => void saveDraft()}>
            保存基线草案
          </Button>
          <a className="button export-link" data-variant="primary" href={planningExportUrl(householdId)} download>
            导出规划 JSON
          </a>
        </div>
      </header>

      {focus !== "actions" ? <div className="planning-control-rail">
        <label>
          <span>生命周期参数</span>
          <select
            value={lifecycleOverride}
            onChange={(event) => void updateLifecycle(event.target.value as LifecycleStage | "")}
          >
            <option value="">采用已记录阶段</option>
            {Object.entries(lifecycleLabels).map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </label>
        <div className="lifecycle-result">
          <span>识别 / 生效</span>
          <strong>
            {lifecycleLabels[displayedPlan.lifecycle.detected_stage]} / {lifecycleLabels[displayedPlan.lifecycle.effective_stage]}
          </strong>
          <small>动态安全期 {displayedPlan.lifecycle.dynamic_safety_months} 个月</small>
        </div>
        <div className="display-switch" aria-label="账户显示口径">
          <span>显示口径</span>
          <div>
            <button type="button" aria-pressed={displayMode === "amount"} onClick={() => setDisplayMode("amount")}>金额</button>
            {(Object.keys(denominatorLabels) as DenominatorId[]).map((id) => (
              <button key={id} type="button" aria-pressed={displayMode === id} onClick={() => setDisplayMode(id)}>
                {denominatorLabels[id].replace("占", "")}
              </button>
            ))}
          </div>
        </div>
      </div> : null}
      {focus === "all" || focus === "accounts" ? <details className="lifecycle-audit">
        <summary>查看生命周期与安全月数依据</summary>
        <p><strong>公式：</strong>{displayedPlan.lifecycle.formula}</p>
        <p><strong>代入：</strong>{displayedPlan.lifecycle.substitution}</p>
        <p>{displayedPlan.lifecycle.explanation}</p>
        <ul>{displayedPlan.lifecycle.evidence.map((item) => <li key={item.factor}><strong>{item.label}</strong><span>{item.observed_value}</span><b>{Number(item.adjustment_months) >= 0 ? "+" : ""}{item.adjustment_months} 月</b></li>)}</ul>
      </details> : null}

      {focus === "all" || focus === "accounts" ? <div className="account-cockpit">
        <div className="account-column-head" aria-hidden="true">
          <span>账户与作用</span><span>当前</span><span>本次建议</span><span>缺口 / 边界</span>
        </div>
        <ol className="account-ledger">
          {displayedPlan.accounts.map((account) => (
            <li key={account.bucket} data-account={account.bucket}>
              <div className="account-purpose">
                <span className="account-sequence">0{account.sequence}</span>
                <div><h3>{account.name}</h3><p>{account.rationale}</p></div>
              </div>
              <strong>{measureValue(account, displayMode, "current")}</strong>
              <strong>{measureValue(account, displayMode, "recommended")}</strong>
              <div className="account-boundary">
                {displayMode === "amount" ? (
                  <><b>缺口 {formatMoney(account.gap_amount)}</b><small>区间 {formatMoney(account.recommended_range_min)}—{formatMoney(account.recommended_range_max)}</small></>
                ) : (
                  <><b>{denominatorLabels[displayMode]}</b><small>{account.measures.find((item) => item.denominator_id === displayMode)?.reason ?? "分母不适用"}</small></>
                )}
              </div>
              <details>
                <summary>查看公式、三尺与产品教育</summary>
                <p><strong>公式：</strong>{account.formula}</p>
                <p><strong>代入：</strong>{account.substitution}</p>
                <ul>{account.measures.map((measure) => <li key={measure.denominator_id}>{measure.denominator_name}：{measure.ratio === null ? "不适用" : formatRatio(measure.ratio)}（{measure.reason}）</li>)}</ul>
                {account.reference_band ? <aside className="reference-band"><strong>{account.reference_band.market_regime_label}口径 · {formatRatio(account.reference_band.minimum_ratio)}—{formatRatio(account.reference_band.maximum_ratio)} · 战术锚 {formatRatio(account.reference_band.target_ratio)}</strong><p>{account.reference_band.explanation}</p><ul>{account.reference_band.conditions.map((condition) => <li key={condition}>{condition}</li>)}</ul></aside> : null}
                {account.product_education.map((item) => <p key={item} className="education-note">{item}</p>)}
              </details>
            </li>
          ))}
        </ol>
        {displayedPlan.investment_learning.applicable ? (
          <aside className="growth-gate" data-eligible={displayedPlan.investment_learning.eligible}>
            <div><span>正式门槛下学习仓</span><strong>{displayedPlan.investment_learning.eligible ? formatMoney(displayedPlan.investment_learning.recommended_amount) : "本次不设置"}</strong></div>
            <p>{displayedPlan.investment_learning.explanation}</p>
            <small>上限 {formatRatio(displayedPlan.investment_learning.cap_ratio)} · 分母 {displayedPlan.investment_learning.denominator_name} {formatMoney(displayedPlan.investment_learning.denominator_value)}</small>
            <details><summary>查看学习仓条件</summary><ul>{displayedPlan.investment_learning.conditions.map((condition) => <li key={condition}>{condition}</li>)}</ul>{displayedPlan.investment_learning.failed_conditions.length > 0 ? <p>当前未通过：{displayedPlan.investment_learning.failed_conditions.join("、")}</p> : null}</details>
          </aside>
        ) : null}
        <aside className="growth-gate" data-eligible={displayedPlan.growth_70.eligible}>
          <div><span>70% 条件核验</span><strong>{displayedPlan.growth_70.eligible ? "满足" : "未满足"}</strong></div>
          <p>{displayedPlan.growth_70.explanation}</p>
          <small>分母：{displayedPlan.growth_70.denominator_name} {formatMoney(displayedPlan.growth_70.denominator_value)}</small>
          <details><summary>查看 70% 全部适用条件</summary><ul>{displayedPlan.growth_70.conditions.map((condition) => <li key={condition}>{condition}</li>)}</ul>{displayedPlan.growth_70.failed_conditions.length > 0 ? <p>当前未通过：{displayedPlan.growth_70.failed_conditions.join("、")}</p> : null}</details>
        </aside>
      </div> : null}

      {focus === "all" || focus === "goals" ? <div className="planning-grid">
        <GoalTimeline
          plan={displayedPlan}
          goalFormOpen={goalFormOpen}
          setGoalFormOpen={setGoalFormOpen}
          goal={goal}
          setGoal={setGoal}
          saving={savingGoal}
          onSubmit={submitGoal}
        />
        <ConstraintPanel plan={displayedPlan} limitingCount={limitingConstraints.length} />
      </div> : null}

      {focus === "all" ? <div className="planning-grid planning-grid-secondary">
        <WaterfallPanel plan={displayedPlan} />
        <CounterfactualPanel
          plan={basePlan}
          scenario={scenario}
          setScenario={setScenario}
          comparison={comparison}
          recalculating={recalculating}
          onSubmit={submitScenario}
          onReset={() => {
            setDisplayedPlan(basePlan);
            setComparison(null);
            setStatusMessage("已回到原方案。 ");
          }}
        />
      </div> : null}

      {focus === "accounts" ? <WaterfallPanel plan={displayedPlan} /> : null}
      {focus === "goals" ? <CounterfactualPanel
        plan={basePlan}
        scenario={scenario}
        setScenario={setScenario}
        comparison={comparison}
        recalculating={recalculating}
        onSubmit={submitScenario}
        onReset={() => {
          setDisplayedPlan(basePlan);
          setComparison(null);
          setStatusMessage("已回到原方案。 ");
        }}
      /> : null}

      {focus === "all" || focus === "actions" ? <ActionPanel plan={displayedPlan} /> : null}
      {statusMessage ? <p className="planning-status" role="status">{statusMessage}</p> : null}
      <footer className="planning-version">
        <span>公式 {displayedPlan.meta.formula_version}</span>
        <span>规则 {displayedPlan.meta.rule_version} · {displayedPlan.meta.rule_source_type}</span>
        <span>输入 {displayedPlan.meta.input_version.slice(0, 12)}</span>
        <span>{displayedPlan.meta.scenario_type === "counterfactual" ? "反事实视图" : "基线视图"}</span>
      </footer>
    </section>
  );
}

interface GoalTimelineProps {
  plan: PlanningResponse;
  goalFormOpen: boolean;
  setGoalFormOpen: (value: boolean) => void;
  goal: GoalCreateInput;
  setGoal: (value: GoalCreateInput) => void;
  saving: boolean;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}

function GoalTimeline({ plan, goalFormOpen, setGoalFormOpen, goal, setGoal, saving, onSubmit }: GoalTimelineProps) {
  return (
    <article className="planning-panel goal-panel">
      <header><div><p className="section-index">目标时间轴</p><h3>每个日期都有资金责任</h3></div><Button type="button" variant="secondary" onClick={() => setGoalFormOpen(!goalFormOpen)}>{goalFormOpen ? "收起录入" : "新增目标"}</Button></header>
      {goalFormOpen ? (
        <form className="goal-entry-form" onSubmit={onSubmit}>
          <label><span>目标名称</span><input required value={goal.name} onChange={(event) => setGoal({ ...goal, name: event.target.value })} /></label>
          <label><span>类型</span><select value={goal.goal_type} onChange={(event) => setGoal({ ...goal, goal_type: event.target.value })}><option value="education">教育</option><option value="home">购房</option><option value="retirement">退休</option><option value="medical">医疗</option><option value="family_support">赡养</option><option value="other">其他</option></select></label>
          <label><span>今日目标金额</span><input required inputMode="decimal" value={goal.target_amount} onChange={(event) => setGoal({ ...goal, target_amount: event.target.value })} /></label>
          <label><span>目标日期</span><input required type="date" value={goal.target_date} onChange={(event) => setGoal({ ...goal, target_date: event.target.value })} /></label>
          <label><span>已准备</span><input required inputMode="decimal" value={goal.prepared_amount} onChange={(event) => setGoal({ ...goal, prepared_amount: event.target.value })} /></label>
          <label><span>最低可接受金额</span><input required inputMode="decimal" value={goal.minimum_acceptable_amount} onChange={(event) => setGoal({ ...goal, minimum_acceptable_amount: event.target.value })} /></label>
          <label><span>刚性</span><select value={goal.rigidity} onChange={(event) => setGoal({ ...goal, rigidity: event.target.value })}><option value="rigid">刚性</option><option value="important">重要</option><option value="flexible">柔性</option></select></label>
          <label><span>成本年增速</span><input required inputMode="decimal" value={goal.annual_cost_growth_rate} onChange={(event) => setGoal({ ...goal, annual_cost_growth_rate: event.target.value })} /></label>
          <label className="checkbox-label"><input type="checkbox" checked={goal.can_defer} onChange={(event) => setGoal({ ...goal, can_defer: event.target.checked })} /><span>允许延期</span></label>
          <Button type="submit" loading={saving}>保存并重算</Button>
        </form>
      ) : null}
      <ol className="goal-timeline">
        {plan.goals.map((item) => (
          <li key={item.goal_id}>
            <time dateTime={item.adjusted_target_date}>{formatDate(item.adjusted_target_date)}</time>
            <div><strong>{item.name}</strong><small>优先级 {item.priority} · {formatDomainLabel(item.rigidity)}{item.can_defer ? " · 可延期" : ""}</small></div>
            <div><span>未来金额 {formatMoney(item.future_amount)}</span><span>已准备 {formatMoney(item.prepared_amount)}</span><b>缺口 {formatMoney(item.funding_gap)}</b><small>{formatMoney(item.monthly_required)}/月</small></div>
            <StatusBadge tone={badgeTone(item.status)}>{item.status === "conflict" ? "存在冲突" : item.status === "funded" ? "已备足" : "需投入"}</StatusBadge>
            <details><summary>计算依据</summary><p>{item.formula}</p><code>{item.substitution}</code></details>
          </li>
        ))}
      </ol>
      {plan.conflicts.map((conflict) => (
        <aside className="goal-conflict" key={conflict.conflict_id}>
          <h4>{conflict.title}</h4><p>{conflict.detail}</p>
          <ol>{conflict.adjustments.map((item) => <li key={`${item.action_code}-${item.affected_goal_ids.join("-")}`}><strong>{item.title}</strong><span>{item.detail}</span></li>)}</ol>
        </aside>
      ))}
    </article>
  );
}

function ConstraintPanel({ plan, limitingCount }: { plan: PlanningResponse; limitingCount: number }) {
  return (
    <article className="planning-panel constraint-panel">
      <header><div><p className="section-index">五硬一软</p><h3>谁在限制长期增长</h3></div><strong>{limitingCount} 项生效</strong></header>
      <ul>
        {plan.constraints.map((item) => (
          <li key={item.constraint_id}>
            <div><StatusBadge tone={badgeTone(item.status)}>{item.constraint_type === "hard" ? "硬约束" : "软修正"} · {item.status}</StatusBadge><strong>{item.name}</strong></div>
            <p>{item.observed_value}</p><small>{item.effect}</small>
          </li>
        ))}
      </ul>
    </article>
  );
}

function WaterfallPanel({ plan }: { plan: PlanningResponse }) {
  return (
    <article className="planning-panel waterfall-panel">
      <header><div><p className="section-index">七步瀑布</p><h3>资金只向下一层流动</h3></div><span>可规划 {formatMoney(plan.denominators.available_planning_resources)}</span></header>
      <ol>
        {plan.waterfall_steps.map((step) => (
          <li key={step.step_code}>
            <span>{step.sequence}</span><div><strong>{step.name}</strong><small>{step.explanation}</small></div><div><b>{formatMoney(step.allocated_amount)}</b><small>需 {formatMoney(step.required_amount)} · 余 {formatMoney(step.remaining_resources)}</small></div><StatusBadge tone={badgeTone(step.status)}>{step.status}</StatusBadge>
          </li>
        ))}
      </ol>
    </article>
  );
}

interface ScenarioState {
  emergency: string;
  debt: string;
  savings: string;
  preparedGoalId: string;
  preparedAmount: string;
  deferGoalId: string;
  deferMonths: string;
}

function CounterfactualPanel({ plan, scenario, setScenario, comparison, recalculating, onSubmit, onReset }: { plan: PlanningResponse; scenario: ScenarioState; setScenario: (value: ScenarioState) => void; comparison: CounterfactualResponse | null; recalculating: boolean; onSubmit: (event: FormEvent<HTMLFormElement>) => void; onReset: () => void }) {
  return (
    <article className="planning-panel counterfactual-panel">
      <header><div><p className="section-index">改变什么会改变方案</p><h3>反事实重算台</h3></div>{comparison ? <Button type="button" variant="secondary" onClick={onReset}>回到原方案</Button> : null}</header>
      <form onSubmit={onSubmit}>
        <label><span>补足应急金</span><input inputMode="decimal" value={scenario.emergency} onChange={(event) => setScenario({ ...scenario, emergency: event.target.value })} /></label>
        <label><span>偿还高息债务</span><input inputMode="decimal" value={scenario.debt} onChange={(event) => setScenario({ ...scenario, debt: event.target.value })} /></label>
        <label><span>每月增加结余</span><input inputMode="decimal" value={scenario.savings} onChange={(event) => setScenario({ ...scenario, savings: event.target.value })} /></label>
        <label><span>提高目标准备率</span><select value={scenario.preparedGoalId} onChange={(event) => setScenario({ ...scenario, preparedGoalId: event.target.value })}><option value="">不调整</option>{plan.goals.map((item) => <option key={item.goal_id} value={item.goal_id}>{item.name}</option>)}</select></label>
        <label><span>增加已准备金额</span><input inputMode="decimal" value={scenario.preparedAmount} disabled={!scenario.preparedGoalId} onChange={(event) => setScenario({ ...scenario, preparedAmount: event.target.value })} /></label>
        <label><span>延期目标</span><select value={scenario.deferGoalId} onChange={(event) => setScenario({ ...scenario, deferGoalId: event.target.value })}><option value="">不延期</option>{plan.goals.filter((item) => item.can_defer).map((item) => <option key={item.goal_id} value={item.goal_id}>{item.name}</option>)}</select></label>
        <label><span>延期月数</span><input type="number" min="1" max="120" value={scenario.deferMonths} disabled={!scenario.deferGoalId} onChange={(event) => setScenario({ ...scenario, deferMonths: event.target.value })} /></label>
        <Button type="submit" loading={recalculating}>重新计算方案</Button>
      </form>
      {comparison ? <div className="scenario-delta"><p>{comparison.explanation}</p><ul>{comparison.changes.map((item) => <li key={item.code}><span>{item.label}</span><strong>{typeof item.before === "string" ? formatMoney(item.before) : String(item.before)} → {typeof item.after === "string" ? formatMoney(item.after) : String(item.after)}</strong></li>)}</ul></div> : <p className="counterfactual-note">调整只在浏览器中组成输入，金额由后端确定性规则整套重算；不会由语言模型猜测。</p>}
    </article>
  );
}

function ActionPanel({ plan }: { plan: PlanningResponse }) {
  return (
    <article className="action-draft-panel">
      <header><div><p className="section-index">行动清单草案</p><h3>按限制因素排优先级</h3></div><span>未经客户确认，不自动执行</span></header>
      <ol>{plan.actions.map((item) => <li key={`${item.priority}-${item.action_code}`}><span>0{item.priority}</span><div><strong>{item.title}</strong><p>{item.detail}</p></div><div><b>{Number(item.amount) > 0 ? formatMoney(item.amount) : "先确认"}</b><small>{item.due_date ? formatDate(item.due_date) : "无自动截止日"}</small></div></li>)}</ol>
    </article>
  );
}
