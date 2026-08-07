import {
  ArrowLeftIcon,
  BankIcon,
  CurrencyCnyIcon,
  PlusIcon,
  ReceiptIcon,
  WalletIcon,
} from "@phosphor-icons/react";
import type { ReactNode } from "react";
import type {
  AssetIntakeCategory,
  ExpenseIntakeCategory,
  IncomeIntakeCategory,
  LiabilityIntakeCategory,
  PlanningIntake,
} from "../../api/wealthPlanning";

interface FinancialStatementFormProps {
  draft: PlanningIntake;
  error: string | null;
  submitting: boolean;
  onChange: (draft: PlanningIntake) => void;
  onBack: () => void;
  onSubmit: () => void;
}

const assetCategories: Array<{ value: AssetIntakeCategory; label: string }> = [
  { value: "cash_and_equivalents", label: "现金及现金等价物" },
  { value: "time_deposit_and_bank_wealth", label: "定期存款及银行理财" },
  { value: "non_bank_financial", label: "非银行金融资产" },
  { value: "primary_residence", label: "自住房产" },
  { value: "investment_property", label: "投资性房产" },
  { value: "vehicle_and_other", label: "车辆及其他" },
];

const liabilityCategories: Array<{ value: LiabilityIntakeCategory; label: string }> = [
  { value: "mortgage", label: "房产贷款" },
  { value: "auto_loan", label: "车贷" },
  { value: "consumer_loan", label: "消费贷款" },
  { value: "credit_card_unpaid", label: "信用卡未付" },
  { value: "non_bank_loan", label: "非银行借款" },
  { value: "other", label: "其他负债" },
];

const incomeCategories: Array<{ value: IncomeIntakeCategory; label: string }> = [
  { value: "self_employment", label: "本人工作收入" },
  { value: "spouse_employment", label: "配偶工作收入" },
  { value: "asset_income", label: "资产生息收入" },
  { value: "rental_income", label: "出租收入" },
  { value: "other", label: "其他收入" },
];

const expenseCategories: Array<{ value: ExpenseIntakeCategory; label: string }> = [
  { value: "living", label: "生活费" },
  { value: "parent_support", label: "父母赡养费" },
  { value: "child_education", label: "子女教养费" },
  { value: "insurance_premium", label: "保费" },
  { value: "debt_service", label: "还贷" },
  { value: "other", label: "其他支出" },
];

function normalizeMoney(value: string): string {
  if (value === "") return "0";
  return value.replace(/^0+(?=\d)/, "");
}

function MoneyInput({
  id,
  value,
  onChange,
  label,
}: {
  id: string;
  value: string;
  onChange: (value: string) => void;
  label: string;
}) {
  return (
    <label className="money-input" htmlFor={id}>
      <span className="sr-only">{label}</span>
      <input
        id={id}
        type="number"
        min="0"
        step="1000"
        inputMode="decimal"
        value={value}
        onChange={(event) => onChange(normalizeMoney(event.target.value))}
      />
      <span>元</span>
    </label>
  );
}

export function FinancialStatementForm({
  draft,
  error,
  submitting,
  onChange,
  onBack,
  onSubmit,
}: FinancialStatementFormProps) {
  function addAsset() {
    onChange({
      ...draft,
      assets: [...draft.assets, { category: "vehicle_and_other", label: "其他资产", amount: "0" }],
    });
  }

  function addLiability() {
    onChange({
      ...draft,
      liabilities: [...draft.liabilities, {
        category: "other",
        label: "其他负债",
        balance: "0",
        monthly_payment: "0",
        annual_interest_rate: "0",
      }],
    });
  }

  function addIncome() {
    onChange({
      ...draft,
      incomes: [...draft.incomes, { category: "other", label: "其他收入", annual_amount: "0" }],
    });
  }

  function addExpense() {
    onChange({
      ...draft,
      expenses: [...draft.expenses, { category: "other", label: "其他支出", annual_amount: "0" }],
    });
  }

  return (
    <section className="planning-step-panel statement-entry" aria-labelledby="statement-step-heading">
      <header className="planning-step-header">
        <div>
          <span>家庭财务报表</span>
          <h1 id="statement-step-heading">把家底和一年收支填清楚</h1>
          <p>请填写当前余额或市值，以及最近一个完整年度的税后收入和实际支出。</p>
        </div>
        <WalletIcon size={44} weight="duotone" aria-hidden="true" />
      </header>

      <aside className="statement-entry-note">
        <strong>填写口径</strong>
        <p>信用卡只填写已经发生但尚未偿还的金额。信用额度不是资产，也不在本表中填写。</p>
      </aside>

      <StatementSection
        icon={<BankIcon size={24} weight="duotone" aria-hidden="true" />}
        title="资产"
        description="按当前可合理估计的市值填写。银行理财、基金、信托和保险不统一视为保本。"
        actionLabel="新增资产"
        onAdd={addAsset}
      >
        <div className="statement-table" role="group" aria-label="资产明细">
          <div className="statement-table-head"><span>资产类别</span><span>项目名称</span><span>当前金额</span></div>
          {draft.assets.map((item, index) => (
            <div className="statement-entry-row" key={`asset-${index}`}>
              <label><span className="sr-only">资产类别</span><select value={item.category} onChange={(event) => {
                const assets = [...draft.assets];
                assets[index] = { ...item, category: event.target.value as AssetIntakeCategory };
                onChange({ ...draft, assets });
              }}>{assetCategories.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
              <label><span className="sr-only">资产项目名称</span><input type="text" value={item.label} onChange={(event) => {
                const assets = [...draft.assets];
                assets[index] = { ...item, label: event.target.value };
                onChange({ ...draft, assets });
              }} /></label>
              <MoneyInput id={`asset-amount-${index}`} label={`${item.label}当前金额`} value={item.amount} onChange={(amount) => {
                const assets = [...draft.assets];
                assets[index] = { ...item, amount };
                onChange({ ...draft, assets });
              }} />
            </div>
          ))}
        </div>
      </StatementSection>

      <StatementSection
        icon={<ReceiptIcon size={24} weight="duotone" aria-hidden="true" />}
        title="负债"
        description="余额用于计算负债比率，月还款额用于核对偿债压力。"
        actionLabel="新增负债"
        onAdd={addLiability}
      >
        <div className="statement-table liability-table" role="group" aria-label="负债明细">
          <div className="statement-table-head"><span>负债类别</span><span>项目名称</span><span>贷款余额</span><span>月还款</span><span>年利率</span></div>
          {draft.liabilities.map((item, index) => (
            <div className="statement-entry-row" key={`liability-${index}`}>
              <label><span className="sr-only">负债类别</span><select value={item.category} onChange={(event) => {
                const liabilities = [...draft.liabilities];
                liabilities[index] = { ...item, category: event.target.value as LiabilityIntakeCategory };
                onChange({ ...draft, liabilities });
              }}>{liabilityCategories.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
              <label><span className="sr-only">负债项目名称</span><input type="text" value={item.label} onChange={(event) => {
                const liabilities = [...draft.liabilities];
                liabilities[index] = { ...item, label: event.target.value };
                onChange({ ...draft, liabilities });
              }} /></label>
              <MoneyInput id={`liability-balance-${index}`} label={`${item.label}贷款余额`} value={item.balance} onChange={(balance) => {
                const liabilities = [...draft.liabilities];
                liabilities[index] = { ...item, balance };
                onChange({ ...draft, liabilities });
              }} />
              <MoneyInput id={`liability-payment-${index}`} label={`${item.label}月还款`} value={item.monthly_payment} onChange={(monthly_payment) => {
                const liabilities = [...draft.liabilities];
                liabilities[index] = { ...item, monthly_payment };
                onChange({ ...draft, liabilities });
              }} />
              <label className="rate-input"><span className="sr-only">{item.label}年利率</span><input type="number" min="0" max="100" step="0.01" value={Number(item.annual_interest_rate) * 100} onChange={(event) => {
                const liabilities = [...draft.liabilities];
                liabilities[index] = { ...item, annual_interest_rate: (Number(event.target.value || 0) / 100).toFixed(6) };
                onChange({ ...draft, liabilities });
              }} /><span>%</span></label>
            </div>
          ))}
        </div>
      </StatementSection>

      <div className="cashflow-entry-grid">
        <StatementSection
          icon={<CurrencyCnyIcon size={24} weight="duotone" aria-hidden="true" />}
          title="年收入"
          description="使用税后、可支配的年度金额。"
          actionLabel="新增收入"
          onAdd={addIncome}
          compact
        >
          <div className="compact-entry-list">
            {draft.incomes.map((item, index) => (
              <div className="compact-entry-row" key={`income-${index}`}>
                <label><span>收入类别</span><select value={item.category} onChange={(event) => {
                  const incomes = [...draft.incomes];
                  incomes[index] = { ...item, category: event.target.value as IncomeIntakeCategory };
                  onChange({ ...draft, incomes });
                }}>{incomeCategories.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
                <label><span>项目名称</span><input type="text" value={item.label} onChange={(event) => {
                  const incomes = [...draft.incomes];
                  incomes[index] = { ...item, label: event.target.value };
                  onChange({ ...draft, incomes });
                }} /></label>
                <MoneyInput id={`income-amount-${index}`} label={`${item.label}年度金额`} value={item.annual_amount} onChange={(annual_amount) => {
                  const incomes = [...draft.incomes];
                  incomes[index] = { ...item, annual_amount };
                  onChange({ ...draft, incomes });
                }} />
              </div>
            ))}
          </div>
        </StatementSection>

        <StatementSection
          icon={<ReceiptIcon size={24} weight="duotone" aria-hidden="true" />}
          title="年支出"
          description="填写实际发生的全年支出，避免只填预算。"
          actionLabel="新增支出"
          onAdd={addExpense}
          compact
        >
          <div className="compact-entry-list">
            {draft.expenses.map((item, index) => (
              <div className="compact-entry-row" key={`expense-${index}`}>
                <label><span>支出类别</span><select value={item.category} onChange={(event) => {
                  const expenses = [...draft.expenses];
                  expenses[index] = { ...item, category: event.target.value as ExpenseIntakeCategory };
                  onChange({ ...draft, expenses });
                }}>{expenseCategories.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
                <label><span>项目名称</span><input type="text" value={item.label} onChange={(event) => {
                  const expenses = [...draft.expenses];
                  expenses[index] = { ...item, label: event.target.value };
                  onChange({ ...draft, expenses });
                }} /></label>
                <MoneyInput id={`expense-amount-${index}`} label={`${item.label}年度金额`} value={item.annual_amount} onChange={(annual_amount) => {
                  const expenses = [...draft.expenses];
                  expenses[index] = { ...item, annual_amount };
                  onChange({ ...draft, expenses });
                }} />
              </div>
            ))}
          </div>
        </StatementSection>
      </div>

      {error ? <p className="inline-form-error" role="alert">{error}</p> : null}
      <footer className="planning-step-actions">
        <button className="secondary-action" type="button" onClick={onBack}>
          <ArrowLeftIcon size={18} aria-hidden="true" /> 返回基本情况
        </button>
        <button className="primary-action" type="button" disabled={submitting} onClick={onSubmit}>
          {submitting ? "正在生成财务分析" : "生成财务分析"}
        </button>
      </footer>
    </section>
  );
}

function StatementSection({
  icon,
  title,
  description,
  actionLabel,
  onAdd,
  compact = false,
  children,
}: {
  icon: ReactNode;
  title: string;
  description: string;
  actionLabel: string;
  onAdd: () => void;
  compact?: boolean;
  children: ReactNode;
}) {
  return (
    <section className="statement-entry-section" data-compact={compact || undefined}>
      <header>
        <div className="statement-section-title">{icon}<div><h2>{title}</h2><p>{description}</p></div></div>
        <button className="text-action" type="button" onClick={onAdd}><PlusIcon size={16} weight="bold" aria-hidden="true" />{actionLabel}</button>
      </header>
      {children}
    </section>
  );
}
