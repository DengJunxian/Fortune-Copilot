import {
  ArrowLeftIcon,
  CalendarBlankIcon,
  FlagIcon,
  PlusIcon,
  ReceiptIcon,
  TrashIcon,
} from "@phosphor-icons/react";
import type { PlanningGoalDraft } from "../../api/wealthPlanning";
import {
  createDefaultGoals,
  createDefaultMajorExpenses,
  type MajorExpenseDraft,
} from "./planningDraft";

interface GoalsAndExpensesFormProps {
  goals: PlanningGoalDraft[];
  majorExpenses: MajorExpenseDraft[];
  error: string | null;
  submitting: boolean;
  onGoalsChange: (goals: PlanningGoalDraft[]) => void;
  onMajorExpensesChange: (expenses: MajorExpenseDraft[]) => void;
  onBack: () => void;
  onSubmit: () => void;
}

const goalTypes: Array<{ value: PlanningGoalDraft["goal_type"]; label: string }> = [
  { value: "emergency_fund", label: "应急储备" },
  { value: "education", label: "子女教育" },
  { value: "home", label: "购房或改善住房" },
  { value: "retirement", label: "退休养老" },
  { value: "medical", label: "医疗保障" },
  { value: "debt_repayment", label: "提前还债" },
  { value: "family_support", label: "家庭支持" },
  { value: "travel", label: "旅行" },
  { value: "wealth_transfer", label: "财富传承" },
  { value: "other", label: "其他目标" },
];

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function MoneyField({
  id,
  label,
  value,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="form-field money-form-field" htmlFor={id}>
      <span>{label}</span>
      <span className="field-with-unit">
        <input
          id={id}
          type="number"
          min="0"
          step="1000"
          inputMode="decimal"
          value={value}
          onChange={(event) => onChange(event.target.value || "0")}
        />
        <b>元</b>
      </span>
    </label>
  );
}

export function GoalsAndExpensesForm({
  goals,
  majorExpenses,
  error,
  submitting,
  onGoalsChange,
  onMajorExpensesChange,
  onBack,
  onSubmit,
}: GoalsAndExpensesFormProps) {
  function updateGoal(index: number, patch: Partial<PlanningGoalDraft>) {
    onGoalsChange(goals.map((goal, goalIndex) => goalIndex === index ? { ...goal, ...patch } : goal));
  }

  function updateExpense(index: number, patch: Partial<MajorExpenseDraft>) {
    onMajorExpensesChange(majorExpenses.map((expense, expenseIndex) => (
      expenseIndex === index ? { ...expense, ...patch } : expense
    )));
  }

  return (
    <section className="planning-step-panel goal-entry" aria-labelledby="goals-step-heading">
      <header className="planning-step-header">
        <div>
          <span>目标与未来安排</span>
          <h1 id="goals-step-heading">明确家庭要完成的事</h1>
          <p>理财目标用于持续安排资金；大额支出计划用于识别明确日期前的现金需求。</p>
        </div>
        <FlagIcon size={44} weight="duotone" aria-hidden="true" />
      </header>

      <section className="goal-form-section" aria-labelledby="financial-goals-heading">
        <header>
          <div>
            <h2 id="financial-goals-heading">理财目标</h2>
            <p>请写清目标金额、计划日期和已经准备的资金。</p>
          </div>
          <button
            className="text-action"
            type="button"
            onClick={() => onGoalsChange([...goals, ...createDefaultGoals()])}
          >
            <PlusIcon size={16} weight="bold" aria-hidden="true" /> 新增目标
          </button>
        </header>
        <div className="goal-editor-list">
          {goals.map((goal, index) => (
            <fieldset className="goal-editor" key={`goal-${index}`}>
              <legend>
                <span>目标 {index + 1}</span>
                {goals.length > 1 ? (
                  <button
                    type="button"
                    aria-label={`删除目标 ${index + 1}`}
                    onClick={() => onGoalsChange(goals.filter((_, goalIndex) => goalIndex !== index))}
                  >
                    <TrashIcon size={17} aria-hidden="true" />
                  </button>
                ) : null}
              </legend>
              <div className="goal-fields-grid">
                <label className="form-field">
                  <span>目标名称</span>
                  <input type="text" value={goal.name} onChange={(event) => updateGoal(index, { name: event.target.value })} />
                </label>
                <label className="form-field">
                  <span>目标类别</span>
                  <select value={goal.goal_type} onChange={(event) => updateGoal(index, { goal_type: event.target.value as PlanningGoalDraft["goal_type"] })}>
                    {goalTypes.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                  </select>
                </label>
                <MoneyField id={`goal-target-${index}`} label="目标金额" value={goal.target_amount} onChange={(target_amount) => updateGoal(index, { target_amount })} />
                <MoneyField id={`goal-prepared-${index}`} label="已准备金额" value={goal.prepared_amount} onChange={(prepared_amount) => updateGoal(index, { prepared_amount })} />
                <label className="form-field">
                  <span><CalendarBlankIcon size={17} aria-hidden="true" /> 计划完成日期</span>
                  <input type="date" min={today()} value={goal.target_date} onChange={(event) => updateGoal(index, { target_date: event.target.value })} />
                </label>
                <label className="form-field">
                  <span>目标重要程度</span>
                  <select value={goal.rigidity} onChange={(event) => updateGoal(index, { rigidity: event.target.value as PlanningGoalDraft["rigidity"] })}>
                    <option value="rigid">必须完成</option>
                    <option value="important">尽量完成</option>
                    <option value="flexible">可以调整</option>
                  </select>
                </label>
                <label className="form-field">
                  <span>优先顺序</span>
                  <input type="number" min="1" max="10" value={goal.priority} onChange={(event) => updateGoal(index, { priority: Number(event.target.value) || 1 })} />
                </label>
                <label className="check-field">
                  <input type="checkbox" checked={goal.can_defer} onChange={(event) => updateGoal(index, { can_defer: event.target.checked })} />
                  <span>资金不足时可以推迟日期</span>
                </label>
              </div>
            </fieldset>
          ))}
        </div>
      </section>

      <section className="goal-form-section major-expense-section" aria-labelledby="major-expenses-heading">
        <header>
          <div>
            <h2 id="major-expenses-heading">大额支出计划</h2>
            <p>例如装修、换车、婚礼、留学、旅行或医疗支出，不与日常年支出重复。</p>
          </div>
          <button
            className="text-action"
            type="button"
            onClick={() => onMajorExpensesChange([...majorExpenses, ...createDefaultMajorExpenses()])}
          >
            <PlusIcon size={16} weight="bold" aria-hidden="true" /> 新增计划
          </button>
        </header>
        <div className="major-expense-list">
          {majorExpenses.map((expense, index) => (
            <fieldset className="major-expense-editor" key={`expense-plan-${index}`}>
              <legend>
                <ReceiptIcon size={18} aria-hidden="true" />
                <span>支出计划 {index + 1}</span>
                {majorExpenses.length > 1 ? (
                  <button
                    type="button"
                    aria-label={`删除支出计划 ${index + 1}`}
                    onClick={() => onMajorExpensesChange(majorExpenses.filter((_, expenseIndex) => expenseIndex !== index))}
                  >
                    <TrashIcon size={17} aria-hidden="true" />
                  </button>
                ) : null}
              </legend>
              <div className="major-expense-fields-grid">
                <label className="form-field">
                  <span>支出事项</span>
                  <input type="text" value={expense.name} onChange={(event) => updateExpense(index, { name: event.target.value })} />
                </label>
                <MoneyField id={`expense-plan-target-${index}`} label="预计金额" value={expense.target_amount} onChange={(target_amount) => updateExpense(index, { target_amount })} />
                <MoneyField id={`expense-plan-prepared-${index}`} label="已准备金额" value={expense.prepared_amount} onChange={(prepared_amount) => updateExpense(index, { prepared_amount })} />
                <label className="form-field">
                  <span>计划日期</span>
                  <input type="date" min={today()} value={expense.target_date} onChange={(event) => updateExpense(index, { target_date: event.target.value })} />
                </label>
                <label className="form-field">
                  <span>计划资金来源</span>
                  <input type="text" value={expense.planned_source} onChange={(event) => updateExpense(index, { planned_source: event.target.value })} />
                </label>
              </div>
            </fieldset>
          ))}
        </div>
      </section>

      {error ? <p className="inline-form-error" role="alert">{error}</p> : null}
      <footer className="planning-step-actions">
        <button className="secondary-action" type="button" onClick={onBack}>
          <ArrowLeftIcon size={18} aria-hidden="true" /> 返回比率分析
        </button>
        <button className="primary-action" type="button" disabled={submitting} onClick={onSubmit}>
          {submitting ? "正在生成规划书" : "生成家庭理财规划书"}
        </button>
      </footer>
    </section>
  );
}
