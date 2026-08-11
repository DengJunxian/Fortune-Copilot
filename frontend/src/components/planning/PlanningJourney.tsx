import {
  CheckIcon,
  ClipboardTextIcon,
  HouseLineIcon,
  SpinnerGapIcon,
} from "@phosphor-icons/react";
import { useEffect, useMemo, useState } from "react";
import {
  fetchFinancialAnalysis,
  fetchHouseholds,
  type FinancialAnalysis,
} from "../../api/financial";
import {
  createGoalRecords,
  createPlanningCase,
  requestPlanNarrative,
  requestRatioExplanations,
  type PlanNarrative,
  type PlanningGoalDraft,
  type PlanningIntake,
  type RatioExplanationItem,
} from "../../api/wealthPlanning";
import type { PlanningResponse } from "../../api/planning";
import { financialGraphFeatureEnabled } from "../../api/financialGraph";
import { PositionEditor } from "../wealth/PositionEditor";
import { FinancialStatementForm } from "./FinancialStatementForm";
import { GoalsAndExpensesForm } from "./GoalsAndExpensesForm";
import { PlanBookView } from "./PlanBookView";
import { PlanningProfileForm } from "./PlanningProfileForm";
import { RatioAnalysisView } from "./RatioAnalysisView";
import {
  createDefaultGoals,
  createDefaultIntake,
  createDefaultMajorExpenses,
  type MajorExpenseDraft,
} from "./planningDraft";

type JourneyStep = "profile" | "statements" | "positions" | "analysis" | "goals" | "report";

const steps: Array<{ id: JourneyStep; label: string }> = [
  { id: "profile", label: "基本情况" },
  { id: "statements", label: "财务报表" },
  ...(financialGraphFeatureEnabled
    ? [{ id: "positions" as const, label: "精细资产" }]
    : []),
  { id: "analysis", label: "财务分析" },
  { id: "goals", label: "目标计划" },
  { id: "report", label: "规划书" },
];

const draftStorageKey = "fortune-copilot:planning-draft:v3";
const legacyDraftStorageKey = "wealthtwin:planning-draft:v2";
const selectedCaseKey = "fortune-copilot:selected-case";
const legacySelectedCaseKey = "wealthtwin:selected-case";

function storage(kind: "localStorage" | "sessionStorage"): Storage | null {
  try {
    return window[kind] ?? null;
  } catch {
    return null;
  }
}

function loadDraft(): PlanningIntake {
  try {
    const stored = storage("localStorage")?.getItem(draftStorageKey)
      ?? storage("localStorage")?.getItem(legacyDraftStorageKey);
    if (!stored) return createDefaultIntake();
    const parsed = JSON.parse(stored) as PlanningIntake;
    const defaults = createDefaultIntake();
    return parsed.members?.length && parsed.assets?.length && parsed.incomes?.length
      ? { ...defaults, ...parsed, kyc: parsed.kyc ?? defaults.kyc }
      : defaults;
  } catch {
    return createDefaultIntake();
  }
}

function yearStartFromAge(age: number): string {
  return `${new Date().getFullYear() - age}-01-01`;
}

function goalsFromAnalysis(analysis: FinancialAnalysis): PlanningGoalDraft[] {
  const goals = analysis.statements.goal_funding.goals.map((goal) => ({
    name: goal.name,
    goal_type: goal.goal_type as PlanningGoalDraft["goal_type"],
    target_amount: goal.target_amount,
    target_date: goal.target_date,
    prepared_amount: goal.prepared_amount,
    rigidity: goal.rigidity as PlanningGoalDraft["rigidity"],
    priority: goal.priority,
    can_defer: goal.can_defer,
  }));
  return goals.length ? goals : createDefaultGoals();
}

function draftFromAnalysis(analysis: FinancialAnalysis): PlanningIntake {
  const assets = analysis.statements.balance_sheet.assets.map((item) => {
    const category: PlanningIntake["assets"][number]["category"] =
      item.subcategory === "cash_and_equivalents" || item.liquidity_days <= 1
        ? "cash_and_equivalents"
        : item.subcategory === "time_deposit_and_bank_wealth" || item.category.includes("bank")
          ? "time_deposit_and_bank_wealth"
          : item.property_use === "primary_residence" || item.asset_group === "primary_residence"
            ? "primary_residence"
            : item.property_use === "investment_property" || item.asset_group === "investment_property"
              ? "investment_property"
              : ["financial", "investable_financial", "restricted_financial"].includes(item.asset_group)
                ? "non_bank_financial"
                : "vehicle_and_other";
    return { category, label: item.name, amount: item.market_value };
  });
  const liabilities = analysis.statements.balance_sheet.liabilities.map((item) => {
    const category: PlanningIntake["liabilities"][number]["category"] =
      item.category === "mortgage" ? "mortgage"
        : item.category === "auto_loan" ? "auto_loan"
          : item.category === "consumer_loan" ? "consumer_loan"
            : item.category === "credit_card_unpaid" ? "credit_card_unpaid"
              : item.category === "non_bank_loan" ? "non_bank_loan" : "other";
    return {
      category,
      label: item.name,
      balance: item.outstanding_balance,
      monthly_payment: item.monthly_payment,
      annual_interest_rate: item.annual_interest_rate,
    };
  });
  const incomes = analysis.statements.cash_flow.income_lines.map((item, index) => ({
    category: (item.category === "investment" ? "asset_income" : item.category === "rental" ? "rental_income" : index === 1 ? "spouse_employment" : "self_employment") as PlanningIntake["incomes"][number]["category"],
    label: item.name,
    annual_amount: item.annual_amount,
  }));
  const expenses = analysis.statements.cash_flow.expense_lines.map((item) => ({
    category: (item.category === "basic_living" ? "living"
      : item.category === "parent_support" ? "parent_support"
        : item.category === "child_education" ? "child_education"
          : item.category === "insurance_premium" ? "insurance_premium"
            : item.category === "debt_service" ? "debt_service" : "other") as PlanningIntake["expenses"][number]["category"],
    label: item.name,
    annual_amount: item.annual_amount,
  }));
  return {
    planning_scope: analysis.profile.members.length > 1 ? "family" : "individual",
    case_name: analysis.profile.name,
    region: analysis.profile.region,
    kyc: createDefaultIntake().kyc,
    members: analysis.profile.members.map((member) => ({
      display_name: member.display_name,
      relationship: member.relationship,
      birth_date: yearStartFromAge(member.age),
      occupation: member.occupation ?? (member.age < 18 ? "学生／学龄前" : ""),
      employment_stability: (["low", "medium", "high"].includes(member.employment_stability) ? member.employment_stability : "medium") as PlanningIntake["members"][number]["employment_stability"],
      expected_retirement_age: member.relationship === "子女" ? null : 60,
    })),
    assets: assets.length ? assets : createDefaultIntake().assets,
    liabilities,
    incomes: incomes.length ? incomes : createDefaultIntake().incomes,
    expenses: expenses.length ? expenses : createDefaultIntake().expenses,
  };
}

function profileError(draft: PlanningIntake): string | null {
  if (!draft.case_name.trim()) return "请填写规划名称。";
  if (!draft.region.trim()) return "请填写常住地区。";
  if (!draft.members.length || !draft.members.some((member) => member.relationship === "本人")) return "请至少填写本人情况。";
  if (draft.members.some((member) => !member.display_name.trim() || !member.birth_date)) return "请补全每位成员的姓名和出生日期。";
  if (draft.members.some((member) => member.relationship !== "子女" && !member.occupation.trim())) return "请补全成年家庭成员的职业或身份。";
  if (Number(draft.kyc.growth_entry_threshold) < 300000 || Number(draft.kyc.growth_entry_threshold) > 1000000) return "长期资金启动门槛应在30万至100万元之间。";
  if (!draft.kyc.funds_sources.length) return "请至少选择一项主要资金来源。";
  return null;
}

function statementError(draft: PlanningIntake): string | null {
  if (draft.assets.some((item) => !item.label.trim())) return "请补全资产项目名称。";
  if (draft.liabilities.some((item) => !item.label.trim())) return "请补全负债项目名称。";
  if (draft.incomes.some((item) => !item.label.trim()) || draft.expenses.some((item) => !item.label.trim())) return "请补全年收入和年支出项目名称。";
  if (draft.incomes.reduce((sum, item) => sum + Number(item.annual_amount || 0), 0) <= 0) return "年收入合计需要大于零。";
  return null;
}

function goalsError(goals: PlanningGoalDraft[], expenses: MajorExpenseDraft[]): string | null {
  const meaningfulGoals = goals.filter((goal) => goal.name.trim() || Number(goal.target_amount) > 0);
  if (!meaningfulGoals.length) return "请至少填写一项理财目标。";
  if (meaningfulGoals.some((goal) => !goal.name.trim() || Number(goal.target_amount) <= 0 || !goal.target_date)) return "请补全每项目标的名称、金额和日期。";
  const meaningfulExpenses = expenses.filter((expense) => expense.name.trim() || Number(expense.target_amount) > 0);
  if (meaningfulExpenses.some((expense) => !expense.name.trim() || Number(expense.target_amount) <= 0 || !expense.target_date)) return "请补全每项大额支出计划的事项、金额和日期。";
  return null;
}

export function PlanningJourney() {
  const [step, setStep] = useState<JourneyStep>("profile");
  const [furthestStep, setFurthestStep] = useState(0);
  const [draft, setDraft] = useState<PlanningIntake>(loadDraft);
  const [goals, setGoals] = useState<PlanningGoalDraft[]>(createDefaultGoals);
  const [majorExpenses, setMajorExpenses] = useState<MajorExpenseDraft[]>(createDefaultMajorExpenses);
  const [householdId, setHouseholdId] = useState("");
  const [analysis, setAnalysis] = useState<FinancialAnalysis | null>(null);
  const [explanations, setExplanations] = useState<RatioExplanationItem[]>([]);
  const [planning, setPlanning] = useState<PlanningResponse | null>(null);
  const [narrative, setNarrative] = useState<PlanNarrative | null>(null);
  const [explanationLoading, setExplanationLoading] = useState(false);
  const [explanationError, setExplanationError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [showcaseLoading, setShowcaseLoading] = useState(false);
  const [showcaseLabel, setShowcaseLabel] = useState<string | null>(null);
  const [reportMessage, setReportMessage] = useState<string | null>(null);

  const currentIndex = steps.findIndex((item) => item.id === step);
  const progress = useMemo(() => ((currentIndex + 1) / steps.length) * 100, [currentIndex]);

  useEffect(() => {
    storage("localStorage")?.setItem(draftStorageKey, JSON.stringify(draft));
  }, [draft]);

  useEffect(() => {
    const selectedCode = storage("sessionStorage")?.getItem(selectedCaseKey)
      ?? storage("sessionStorage")?.getItem(legacySelectedCaseKey);
    if (!selectedCode) return;
    storage("sessionStorage")?.removeItem(selectedCaseKey);
    storage("sessionStorage")?.removeItem(legacySelectedCaseKey);
    const controller = new AbortController();
    setShowcaseLoading(true);
    setFormError(null);
    fetchHouseholds(controller.signal)
      .then((households) => {
        const household = households.find((item) => item.code === selectedCode);
        if (!household) throw new Error("case_not_found");
        setShowcaseLabel(household.name);
        return fetchFinancialAnalysis(household.id, controller.signal);
      })
      .then((payload) => {
        setHouseholdId(payload.meta.household_id);
        setAnalysis(payload);
        setDraft(draftFromAnalysis(payload));
        setGoals(goalsFromAnalysis(payload));
        setMajorExpenses(createDefaultMajorExpenses());
        setStep("analysis");
        setFurthestStep(steps.findIndex((item) => item.id === "analysis"));
        void loadExplanations(payload.meta.household_id, controller.signal);
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setFormError("案例数据暂时无法读取，您仍可从自己的基本情况开始填写。 ");
      })
      .finally(() => setShowcaseLoading(false));
    return () => controller.abort();
  }, []);

  async function loadExplanations(id: string, signal?: AbortSignal) {
    setExplanationLoading(true);
    setExplanationError(null);
    try {
      const payload = await requestRatioExplanations(id, signal);
      setExplanations(payload.items);
      if (payload.degraded) setExplanationError("家庭解读暂时未完成。");
    } catch (error: unknown) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      setExplanationError("家庭解读暂时未完成。");
    } finally {
      setExplanationLoading(false);
    }
  }

  function goTo(nextStep: JourneyStep) {
    const nextIndex = steps.findIndex((item) => item.id === nextStep);
    setStep(nextStep);
    setFurthestStep((current) => Math.max(current, nextIndex));
    setFormError(null);
    window.scrollTo({ top: 0, behavior: "auto" });
  }

  function continueProfile() {
    const error = profileError(draft);
    setFormError(error);
    if (!error) goTo("statements");
  }

  async function submitStatements() {
    const error = statementError(draft);
    setFormError(error);
    if (error) return;
    setSubmitting(true);
    try {
      const payload = await createPlanningCase(draft);
      setHouseholdId(payload.household_id);
      setAnalysis(payload.analysis);
      setExplanations([]);
      setPlanning(null);
      setNarrative(null);
      if (financialGraphFeatureEnabled) {
        goTo("positions");
      } else {
        goTo("analysis");
        void loadExplanations(payload.household_id);
      }
    } catch (submitError) {
      setFormError(submitError instanceof Error ? submitError.message : "财务报表提交失败，请稍后再试。 ");
    } finally {
      setSubmitting(false);
    }
  }

  function continueFromPositions() {
    if (!householdId) return;
    goTo("analysis");
    void loadExplanations(householdId);
  }

  async function submitGoals() {
    if (!analysis || !householdId) return;
    const error = goalsError(goals, majorExpenses);
    setFormError(error);
    if (error) return;
    const meaningfulGoals = goals.filter((goal) => goal.name.trim() && Number(goal.target_amount) > 0);
    const validMajorExpenses = majorExpenses
      .filter((expense) => expense.name.trim() && Number(expense.target_amount) > 0);
    const meaningfulExpenses: PlanningGoalDraft[] = validMajorExpenses
      .map((expense, index) => ({
        name: expense.name,
        goal_type: "other",
        target_amount: expense.target_amount,
        target_date: expense.target_date,
        prepared_amount: expense.prepared_amount,
        rigidity: "important",
        priority: meaningfulGoals.length + index + 1,
        can_defer: true,
      }));
    setSubmitting(true);
    setReportMessage(null);
    try {
      if (showcaseLabel) {
        setReportMessage("案例规划书已生成，可直接阅读或使用浏览器保存为 PDF。");
      } else {
        await createGoalRecords(householdId, [...meaningfulGoals, ...meaningfulExpenses]);
      }
      const generated = await requestPlanNarrative(
        householdId,
        meaningfulGoals,
        validMajorExpenses,
      );
      setPlanning(generated.planning);
      setNarrative(generated.narrative);
      setReportMessage(
        generated.degraded
          ? "规划书已生成。部分文字采用基础说明，金额和建议不受影响。"
          : "规划书已结合家庭资料和目标生成，可以逐章阅读或保存为 PDF。",
      );
      goTo("report");
    } catch (submitError) {
      setFormError(submitError instanceof Error ? submitError.message : "目标保存失败，请稍后再试。 ");
    } finally {
      setSubmitting(false);
    }
  }

  function startNew() {
    const nextDraft = createDefaultIntake();
    storage("localStorage")?.removeItem(draftStorageKey);
    setDraft(nextDraft);
    setGoals(createDefaultGoals());
    setMajorExpenses(createDefaultMajorExpenses());
    setHouseholdId("");
    setAnalysis(null);
    setExplanations([]);
    setPlanning(null);
    setNarrative(null);
    setShowcaseLabel(null);
    setReportMessage(null);
    setFurthestStep(0);
    goTo("profile");
  }

  return (
    <main className="planning-journey-shell" id="main-content">
      <header className="journey-topbar">
        <div className="journey-brand-context"><HouseLineIcon size={18} weight="fill" aria-hidden="true" /><span>家庭财富规划</span></div>
        <nav className="journey-steps" aria-label="规划进度">
          <ol>
            {steps.map((item, index) => (
              <li key={item.id} data-state={index < currentIndex ? "complete" : index === currentIndex ? "current" : "upcoming"}>
                <button
                  type="button"
                  disabled={index > furthestStep}
                  aria-current={index === currentIndex ? "step" : undefined}
                  onClick={() => index <= furthestStep && goTo(item.id)}
                >
                  <span>{index < currentIndex ? <CheckIcon size={14} weight="bold" aria-hidden="true" /> : index + 1}</span>
                  {item.label}
                </button>
              </li>
            ))}
          </ol>
          <div className="journey-progress" aria-hidden="true"><span style={{ width: `${progress}%` }} /></div>
        </nav>
        <div className="journey-save-state"><ClipboardTextIcon size={17} aria-hidden="true" /> 已自动保存</div>
      </header>

      {showcaseLabel ? (
        <aside className="showcase-context" role="status">
          <strong>客户案例：{showcaseLabel}</strong>
          <span>您可以继续查看分析、补充目标，也可以返回前面修改资料。</span>
        </aside>
      ) : null}

      {showcaseLoading ? (
        <section className="journey-loading" role="status">
          <SpinnerGapIcon size={32} className="spin" aria-hidden="true" />
          <div><h1>正在准备客户案例</h1><p>财务报表和比率正在载入。</p></div>
        </section>
      ) : (
        <div className="journey-content">
          {step === "profile" ? <PlanningProfileForm draft={draft} error={formError} onChange={setDraft} onContinue={continueProfile} /> : null}
          {step === "statements" ? <FinancialStatementForm draft={draft} error={formError} submitting={submitting} onChange={setDraft} onBack={() => goTo("profile")} onSubmit={() => void submitStatements()} /> : null}
          {step === "positions" && householdId ? <PositionEditor householdId={householdId} onBack={() => goTo("statements")} onContinue={continueFromPositions} /> : null}
          {step === "analysis" && analysis ? <RatioAnalysisView analysis={analysis} explanations={explanations} explanationLoading={explanationLoading} explanationError={explanationError} onBack={() => goTo(financialGraphFeatureEnabled ? "positions" : "statements")} onContinue={() => goTo("goals")} /> : null}
          {step === "goals" ? <GoalsAndExpensesForm goals={goals} majorExpenses={majorExpenses} error={formError} submitting={submitting} onGoalsChange={setGoals} onMajorExpensesChange={setMajorExpenses} onBack={() => goTo("analysis")} onSubmit={() => void submitGoals()} /> : null}
          {step === "report" && analysis && planning && narrative ? <PlanBookView analysis={analysis} explanations={explanations} goals={goals} majorExpenses={majorExpenses} kyc={draft.kyc} planning={planning} narrative={narrative} reportMessage={reportMessage} onBack={() => goTo("goals")} onStartNew={startNew} /> : null}
          {!analysis && (step === "analysis" || step === "report") ? <p className="inline-form-error" role="alert">尚未生成财务分析，请返回填写财务报表。</p> : null}
        </div>
      )}
    </main>
  );
}
