import { useDisplayPreferences } from "../../contexts/displayPreferences";
import { formatMoney, formatMoneyInWan } from "../../utils/format";

export function MoneyValue({
  value,
  compact = false,
  label = "金额",
}: {
  value: string;
  compact?: boolean;
  label?: string;
}) {
  const { maskAmounts, moneyUnit } = useDisplayPreferences();
  if (maskAmounts) {
    return (
      <span className="money-value money-value-masked" aria-label={`${label}已隐藏`}>
        ••••
      </span>
    );
  }
  return (
    <span className="money-value" aria-label={`${label}${moneyUnit === "wan" ? "，单位万元" : "，单位元"}`}>
      {moneyUnit === "wan" ? formatMoneyInWan(value) : formatMoney(value, compact)}
    </span>
  );
}

const plainTerms: Record<string, { plain: string; explanation: string }> = {
  净资产: {
    plain: "家里真正剩下的钱",
    explanation: "家庭总资产减去家庭总负债。",
  },
  家庭净资产: {
    plain: "家里真正剩下的钱",
    explanation: "家庭总资产减去家庭总负债。",
  },
  "流动储备月数／应急储备月数": {
    plain: "现有现金能撑几个月",
    explanation: "即时可用资金除以每月基本生活支出。",
  },
  "负债比率／资产负债率": {
    plain: "每 100 元资产背了多少债",
    explanation: "家庭总负债除以家庭总资产。",
  },
  结余比率: {
    plain: "收入里真正存下来的比例",
    explanation: "年度税后结余除以年度税后总收入。",
  },
  可投资金融资产: {
    plain: "暂时不用于日常生活的金融资金",
    explanation: "排除自住房等非金融资产后，可进入规划的金融资产。",
  },
  流动性: {
    plain: "急用时能多快取出",
    explanation: "资金在需要时变成可支付现金的速度与成本。",
  },
  目标准备率: {
    plain: "目标的钱已经备了多少",
    explanation: "已准备金额除以当前目标金额，不等同于未来成功概率。",
  },
  适当性: {
    plain: "这类方案是否适合当前家庭",
    explanation: "同时核对家庭安全、客户承受能力和产品条件。",
  },
};

export function FinancialTerm({ term }: { term: string }) {
  const { plainLanguage } = useDisplayPreferences();
  const entry = plainTerms[term];
  if (!plainLanguage || !entry) return <>{term}</>;
  return (
    <span className="financial-term" title={`${term}：${entry.explanation}`}>
      {entry.plain}
      <small>（{term}）</small>
    </span>
  );
}
