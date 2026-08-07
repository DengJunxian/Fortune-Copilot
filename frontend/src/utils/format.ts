import type { MetricResult } from "../api/financial";

const moneyFormatter = new Intl.NumberFormat("zh-CN", {
  style: "currency",
  currency: "CNY",
  minimumFractionDigits: 0,
  maximumFractionDigits: 2,
});

const compactMoneyFormatter = new Intl.NumberFormat("zh-CN", {
  style: "currency",
  currency: "CNY",
  notation: "compact",
  maximumFractionDigits: 1,
});

export function formatMoney(value: string, compact = false): string {
  const numeric = Number(value);
  return (compact ? compactMoneyFormatter : moneyFormatter).format(numeric);
}

export function formatMoneyInWan(value: string): string {
  const numeric = Number(value) / 10_000;
  return `¥${new Intl.NumberFormat("zh-CN", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(numeric)}万`;
}

export function formatRatio(value: string, digits = 1): string {
  return `${(Number(value) * 100).toFixed(digits)}%`;
}

export function formatPercentagePoint(value: string, digits = 0): string {
  return `${Number(value).toFixed(digits)}%`;
}

export function formatMetricValue(metric: MetricResult, compact = false): string {
  if (metric.result === null) return "不适用";
  if (metric.unit === "CNY") return formatMoney(metric.result, compact);
  if (metric.unit === "ratio") return formatRatio(metric.result);
  if (metric.unit === "months") return `${Number(metric.result).toFixed(2)} 个月`;
  if (metric.unit === "hhi") return Number(metric.result).toFixed(3);
  return metric.result;
}

export function formatDate(value: string): string {
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date(`${value}T00:00:00`));
}

export function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(value));
}

export function safeExternalUrl(value: string): string | null {
  try {
    const parsed = new URL(value);
    return parsed.protocol === "https:" || parsed.protocol === "http:" ? parsed.href : null;
  } catch {
    return null;
  }
}

const domainLabels: Record<string, string> = {
  annual: "每年",
  monthly: "每月",
  weekly: "每周",
  one_time: "一次性",
  employment: "工资薪酬",
  business: "经营收入",
  pension: "养老金",
  rental: "租金收入",
  investment: "投资收入",
  transfer: "转移收入",
  other: "其他",
  basic_living: "基本生活",
  discretionary: "非必要支出",
  parent_support: "父母赡养",
  child_education: "子女教养",
  tax: "税费",
  debt_service: "债务偿付",
  insurance_premium: "保险保费",
  cash: "现金",
  demand_deposit: "活期存款",
  time_deposit: "定期存款",
  bank_wealth_management: "银行理财",
  money_market: "货币市场工具",
  public_fund: "公募基金",
  bond_fund: "债券基金",
  equity_fund: "权益基金",
  bond: "债券",
  stock: "股票",
  pension_account: "养老金账户",
  insurance_cash_value: "保单现金价值",
  trust: "信托",
  primary_residence: "自住住房",
  investment_property: "投资性房产",
  vehicle: "车辆",
  mortgage: "住房按揭",
  auto_loan: "车贷",
  credit_card_unpaid: "信用卡未付",
  consumer_loan: "消费贷",
  bank_loan: "银行贷款",
  non_bank_loan: "非银行借／贷款",
  term_life: "定期寿险",
  whole_life: "终身寿险",
  medical: "医疗险",
  critical_illness: "重疾险",
  accident: "意外险",
  immediate: "即时",
  within_7_days: "7 日内",
  within_30_days: "30 日内",
  within_1_year: "1 年内",
  illiquid: "非流动",
  essential: "刚性",
  flexible: "弹性",
  rigid: "刚性",
  important: "重要",
  early_career: "初入职场",
  family_formation: "婚姻组建",
  family_growth: "家庭成长",
  parenting: "育儿成长",
  mature_family: "家庭成熟",
  retirement_preparation: "退休准备",
  retirement_and_legacy: "养老传承",
  low: "较低",
  medium_low: "中低",
  medium: "中等",
  medium_high: "中高",
  high: "较高",
  investable_financial: "可投资金融资产",
  restricted_financial: "限制性金融资产",
  personal_use: "自用实物资产",
};

export function formatDomainLabel(value: string): string {
  return domainLabels[value] ?? value;
}
