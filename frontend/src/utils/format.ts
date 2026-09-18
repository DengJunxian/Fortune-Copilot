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

export function formatMoneyInWanByCurrency(value: string, currency: string): string {
  const numeric = Number(value) / 10_000;
  return `${new Intl.NumberFormat("zh-CN", {
    style: "currency",
    currency,
    currencyDisplay: "narrowSymbol",
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
  education: "教育",
  housing: "住房",
  retirement: "退休养老",
  family_support: "家庭照护",
  protection: "风险保障",
  living: "日常生活",
  succession: "财富传承",
  philanthropy: "公益安排",
  liquidity: "日常流动资金",
  emergency: "应急储备",
  debt_repayment: "债务偿还",
  medical_protection: "医疗保障",
  death_protection: "身故保障",
  long_term_growth: "长期增长",
  enterprise_concentration: "企业集中度",
  currency_matching: "币种匹配",
  debt: "债务安排",
  enterprise_risk: "家企风险",
  cross_border: "跨境与币种",
  professional_service: "专业服务",
  no_action: "当前不新增投资",
  recommended: "建议执行",
  no_action_required: "无新增行动",
  professional_review_required: "待专业复核",
  short_term: "近期",
  medium_term: "中期",
  long_term: "长期",
  ongoing: "持续安排",
  open: "风险预算已开放",
  repair_first: "先修复前置责任",
  professional_only: "仅限专业复核",
  active: "当前有效",
  superseded: "已被新版替代",
  private_banker: "私行客户经理",
  investment_advisor: "投资顾问",
  pension_specialist: "养老规划专家",
  insurance_specialist: "保障规划专家",
  cross_border_specialist: "跨境服务专家",
  trust_specialist: "信托服务专家",
  legal_tax_professional: "法律税务专家",
  philanthropy_specialist: "公益规划专家",
  social_security: "基本养老与社保",
  enterprise_pension: "企业年金",
  occupational_pension: "职业年金",
  personal_pension: "个人养老金",
  annuity: "年金保险",
  financial_withdrawal: "金融资产提取",
  asset_currency: "资产币种",
  income_currency: "收入币种",
  liability_currency: "负债币种",
  education_liability: "教育责任",
  enterprise_revenue: "企业收入",
  future_obligation: "未来责任",
  inflow: "流入",
  outflow: "流出／责任",
  current: "当前",
  minor_beneficiary: "未成年家庭成员",
  special_care: "特殊照护",
  multi_generation: "多代家庭安排",
  enterprise_succession: "企业延续安排",
  ownership_complexity: "权属关系复杂",
  insurance_trust_coordination: "保单与家庭安排协同",
  not_required: "无需转介",
  cfs_required: "待形成综合方案",
  referral_open: "转介已建立",
  in_progress: "专业协作中",
  early_career: "初入职场",
  family_formation: "婚姻组建",
  family_growth: "家庭成长",
  parenting: "育儿成长",
  mature_family: "家庭成熟",
  retirement_preparation: "退休准备",
  retirement_and_legacy: "养老传承",
  low: "较低",
  none: "无",
  medium_low: "中低",
  medium: "中等",
  medium_high: "中高",
  high: "较高",
  identified: "已识别",
  partially_prepared: "部分准备",
  prepared: "已准备",
  needs_review: "待复核",
  foundational: "基础阶段",
  emerging_affluent: "成长财富",
  affluent: "稳健积累",
  high_net_worth: "高净值",
  investable_financial: "可投资金融资产",
  restricted_financial: "限制性金融资产",
  personal_use: "自用实物资产",
  startup: "初创期",
  growth: "成长期",
  mature: "成熟期",
  pre_ipo: "上市准备期",
  public: "公众公司",
  exiting: "退出期",
  unlisted: "未上市",
  listed: "已上市",
  delisted: "已退市",
  operating_company: "经营企业",
  holding_company: "控股平台",
  family_business: "家族企业",
  common_equity: "普通股权",
  preferred_equity: "优先股权",
  option: "期权",
  restricted_stock: "限制性股票",
  partnership_interest: "合伙份额",
  salary: "工资薪酬",
  dividend: "企业分红",
  business_distribution: "经营分配",
  management_fee: "管理费收入",
  personal: "个人保证",
  joint_and_several: "连带责任保证",
  property: "财产担保",
  cross_guarantee: "交叉担保",
  funding: "融资",
  ipo: "首次公开发行",
  lockup_expiry: "限售期届满",
  equity_sale: "股权出售",
  dividend_change: "分红变化",
  valuation_change: "估值变化",
  guarantee_change: "担保变化",
  cashflow_deterioration: "现金流恶化",
  planned: "规划中",
  confirmed: "已确认",
  completed: "已完成",
  cancelled: "已取消",
  deposit: "存款",
  money_market_fund: "货币市场基金",
  equity_index_fund: "权益／指数基金",
  bond_treasury: "债券／国债",
  gold: "黄金",
  insurance: "保险",
  personal_pension_product: "个人养老金产品",
  trust_wealth_transfer_tool: "信托／传承工具",
  cash_management: "现金管理",
  info: "提示",
  watch: "关注",
  critical: "紧急",
  salary_change: "工资收入变化",
  processed: "已处理",
  added: "新增",
  removed: "移除",
  changed: "变化",
  monitoring_alert_id: "监控提醒 ID",
  monitoring_policy_id: "监控规则 ID",
  trigger_reason: "触发原因",
  client_impact: "客户影响",
  recommended_action: "建议行动",
  do_not_sell_flag: "禁止销售触发",
  eligible: "符合条件",
  restricted: "受限候选",
  blocked: "不符合条件",
  education_only: "仅限教育",
  professional_review: "待专业复核",
};

export function formatDomainLabel(value: string): string {
  return domainLabels[value] ?? value;
}
