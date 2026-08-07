import type {
  PlanningGoalDraft,
  PlanningIntake,
} from "../../api/wealthPlanning";

export interface MajorExpenseDraft {
  name: string;
  target_amount: string;
  target_date: string;
  prepared_amount: string;
  planned_source: string;
}

export function createDefaultIntake(): PlanningIntake {
  return {
    planning_scope: "family",
    case_name: "",
    region: "",
    kyc: {
      city_tier: "developed_city",
      growth_entry_threshold: "500000",
      investment_experience: "basic",
      risk_preference: "balanced",
      loss_tolerance: "medium",
      investment_horizon_years: 5,
      funds_sources: ["salary"],
      personal_pension_status: "not_sure",
    },
    members: [
      {
        display_name: "",
        relationship: "本人",
        birth_date: "",
        occupation: "",
        employment_stability: "medium",
        expected_retirement_age: 60,
      },
    ],
    assets: [
      { category: "cash_and_equivalents", label: "现金、活期存款及货币基金", amount: "0" },
      { category: "time_deposit_and_bank_wealth", label: "定期存款及银行理财", amount: "0" },
      { category: "non_bank_financial", label: "非银行金融资产", amount: "0" },
      { category: "primary_residence", label: "家庭自住房产", amount: "0" },
      { category: "investment_property", label: "投资性房产", amount: "0" },
      { category: "vehicle_and_other", label: "车辆及其他资产", amount: "0" },
    ],
    liabilities: [
      { category: "mortgage", label: "房产贷款余额", balance: "0", monthly_payment: "0", annual_interest_rate: "0" },
      { category: "auto_loan", label: "车贷余额", balance: "0", monthly_payment: "0", annual_interest_rate: "0" },
      { category: "consumer_loan", label: "消费贷款余额", balance: "0", monthly_payment: "0", annual_interest_rate: "0" },
      { category: "credit_card_unpaid", label: "信用卡未付金额", balance: "0", monthly_payment: "0", annual_interest_rate: "0" },
      { category: "non_bank_loan", label: "其他非银行借款", balance: "0", monthly_payment: "0", annual_interest_rate: "0" },
      { category: "other", label: "其他负债", balance: "0", monthly_payment: "0", annual_interest_rate: "0" },
    ],
    incomes: [
      { category: "self_employment", label: "本人税后年收入", annual_amount: "0" },
      { category: "spouse_employment", label: "配偶税后年收入", annual_amount: "0" },
      { category: "asset_income", label: "资产生息收入", annual_amount: "0" },
      { category: "rental_income", label: "家庭出租收入", annual_amount: "0" },
      { category: "other", label: "其他年收入", annual_amount: "0" },
    ],
    expenses: [
      { category: "living", label: "生活费支出", annual_amount: "0" },
      { category: "parent_support", label: "父母赡养费", annual_amount: "0" },
      { category: "child_education", label: "子女教养费", annual_amount: "0" },
      { category: "insurance_premium", label: "保费支出", annual_amount: "0" },
      { category: "debt_service", label: "还贷支出", annual_amount: "0" },
      { category: "other", label: "其他支出", annual_amount: "0" },
    ],
  };
}

function futureDate(years: number): string {
  const date = new Date();
  date.setFullYear(date.getFullYear() + years);
  return date.toISOString().slice(0, 10);
}

export function createDefaultGoals(): PlanningGoalDraft[] {
  return [
    {
      name: "",
      goal_type: "emergency_fund",
      target_amount: "0",
      target_date: futureDate(1),
      prepared_amount: "0",
      rigidity: "important",
      priority: 1,
      can_defer: false,
    },
  ];
}

export function createDefaultMajorExpenses(): MajorExpenseDraft[] {
  return [
    {
      name: "",
      target_amount: "0",
      target_date: futureDate(3),
      prepared_amount: "0",
      planned_source: "年度结余",
    },
  ];
}
