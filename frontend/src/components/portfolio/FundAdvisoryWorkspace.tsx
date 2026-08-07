import { InfoIcon, WarningCircleIcon } from "@phosphor-icons/react";
import { useEffect, useState } from "react";
import {
  fetchFundAdvisory,
  type AdvisoryAllocation,
  type AdvisorySleeveStatus,
  type FundAdvisoryResponse,
} from "../../api/fundAdvisory";
import { formatDate, formatMoney, formatRatio } from "../../utils/format";
import { StatusBadge } from "../ui/StatusBadge";
import "./FundAdvisoryWorkspace.css";

const statusCopy: Record<AdvisorySleeveStatus, string> = {
  recommended: "可进一步了解",
  education_only: "先学习，不购买",
  not_applicable: "本次不安排",
  channel_verification_required: "购买前确认渠道",
};

const customerRiskCopy: Record<FundAdvisoryResponse["effective_customer_risk"], string> = {
  low: "低",
  medium_low: "中低",
  medium: "中等",
  medium_high: "中高",
  high: "高",
};

const familyStatusCopy: Record<FundAdvisoryResponse["family_safety_status"], string> = {
  pass: "可以继续了解产品",
  restrict: "只看符合当前条件的产品",
  block: "先完成家庭资金安排",
};

const productRiskCopy: Record<NonNullable<AdvisoryAllocation["product_risk_level"]>, string> = {
  r1: "低风险",
  r2: "中低风险",
  r3: "中风险",
  r4: "中高风险",
  r5: "高风险",
};

const categoryCopy: Record<string, string> = {
  money_market: "货币市场基金",
  short_bond: "短债基金",
  pure_bond: "纯债基金",
  domestic_broad_index: "境内宽基指数基金",
  pension_bond_fof: "个人养老金债券型基金中基金",
  pension_broad_index: "个人养老金宽基指数基金",
};

function statusTone(status: AdvisorySleeveStatus) {
  if (status === "recommended") return "success" as const;
  if (status === "education_only" || status === "channel_verification_required") return "warning" as const;
  return "info" as const;
}

function allocationName(allocation: AdvisoryAllocation) {
  if (allocation.product_name) return allocation.product_name;
  if (allocation.allocation_type === "bank_cash_reserve") return "活期资金或日常支付账户";
  return "暂不购买，资金继续保留";
}

function allocationStatus(allocation: AdvisoryAllocation) {
  if (allocation.allocation_type === "fund") return "已核对产品基础资料";
  if (allocation.allocation_type === "bank_cash_reserve") return "保留日常流动性";
  return "等待条件满足";
}

function joinChineseClauses(items: string[]) {
  return `${items.map((item) => item.trim().replace(/[。；;]+$/u, "")).join("；")}。`;
}

export function FundAdvisoryWorkspace({ householdId }: { householdId: string }) {
  const [advice, setAdvice] = useState<FundAdvisoryResponse | null>(null);
  const [icbcOnly, setIcbcOnly] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    fetchFundAdvisory(householdId, icbcOnly, controller.signal)
      .then((payload) => {
        setAdvice(payload);
        setLoading(false);
      })
      .catch((loadError: unknown) => {
        if (loadError instanceof DOMException && loadError.name === "AbortError") return;
        setAdvice(null);
        setLoading(false);
        setError("具体基金方案暂时没有显示，家庭财务规划不受影响。您可以稍后再查看。 ");
      });
    return () => controller.abort();
  }, [householdId, icbcOnly]);

  if (loading) {
    return (
      <section id="fund-advisory" className="fund-advisory-workspace fund-advisory-loading" aria-live="polite">
        <div className="fund-advisory-loading-copy">
          <strong>正在准备适合本家庭的基金说明</strong>
          <span>我们会依次核对资金用途、风险承受情况、持有时间和可购买渠道。</span>
        </div>
        <div className="fund-advisory-skeleton" aria-hidden="true" />
      </section>
    );
  }

  if (error || !advice) {
    return (
      <section id="fund-advisory" className="fund-advisory-workspace fund-advisory-unavailable" role="status">
        <WarningCircleIcon size={24} weight="duotone" aria-hidden="true" />
        <div><strong>基金方案暂时不可用</strong><p>{error}</p></div>
      </section>
    );
  }

  return (
    <section id="fund-advisory" className="fund-advisory-workspace" aria-labelledby="fund-advisory-heading">
      <header className="fund-advisory-header">
        <div>
          <p className="fund-advisory-kicker">具体产品说明</p>
          <h3 id="fund-advisory-heading">先看这笔钱的用途，再看基金</h3>
          <p>以下金额沿用本章的家庭规划结果。产品选择不会增加可投资金额，也不会跳过排在前面的生活、保障和近期目标。</p>
        </div>
        <label className="fund-channel-control">
          <span>产品渠道</span>
          <select
            value={icbcOnly ? "icbc" : "verified"}
            onChange={(event) => setIcbcOnly(event.target.value === "icbc")}
          >
            <option value="icbc">仅查看工行公开列示的产品</option>
            <option value="verified">同时查看其他已核验渠道</option>
          </select>
          <small>购买时仍以当日账户可售情况和产品文件为准。</small>
        </label>
      </header>

      <div className="fund-advice-summary" aria-label="本次基金方案概况">
        <div><span>产品资料日期</span><strong>{formatDate(advice.meta.catalog_data_date)}</strong></div>
        <div><span>风险承受范围</span><strong>{customerRiskCopy[advice.effective_customer_risk]}</strong></div>
        <div><span>家庭准备情况</span><strong>{familyStatusCopy[advice.family_safety_status]}</strong></div>
      </div>

      <aside className="fund-channel-notice" role="note">
        <InfoIcon size={22} weight="duotone" aria-hidden="true" />
        <div>
          <strong>购买前请再确认</strong>
          <p>页面列出的是工行曾公开展示的产品，并不代表您现在一定可以买到。购买时请在工行手机银行输入六位代码，以当日产品详情、风险测评和交易页面为准。</p>
        </div>
      </aside>

      {advice.meta.catalog_stale ? (
        <p className="fund-catalog-warning" role="alert">产品资料已超过复核日期，本页暂时只用于学习，请先更新资料再购买。</p>
      ) : null}

      <div className="fund-sleeve-list">
        {advice.sleeves.map((sleeve) => (
          <article key={sleeve.sleeve_code} className="fund-sleeve" data-status={sleeve.status}>
            <header>
              <div><h4>{sleeve.name}</h4><p>{sleeve.objective}</p></div>
              <div className="fund-sleeve-amount">
                <StatusBadge tone={statusTone(sleeve.status)}>{statusCopy[sleeve.status]}</StatusBadge>
                <span>本次金额</span>
                <strong>{formatMoney(sleeve.source_amount)}</strong>
              </div>
            </header>

            {sleeve.allocations.length > 0 ? (
              <div className="fund-allocation-list" aria-label={`${sleeve.name}产品安排`}>
                {sleeve.allocations.map((allocation, index) => (
                  <article key={`${sleeve.sleeve_code}-${allocation.product_code ?? allocation.allocation_type}-${index}`}>
                    <header>
                      <div>
                        <span>{allocation.product_code ? `基金代码 ${allocation.product_code}` : allocationStatus(allocation)}</span>
                        <h5>{allocationName(allocation)}</h5>
                      </div>
                      <strong>{formatMoney(allocation.amount)}</strong>
                    </header>
                    <dl>
                      <div><dt>占这项用途</dt><dd>{formatRatio(allocation.ratio)}</dd></div>
                      <div><dt>产品风险</dt><dd>{allocation.product_risk_level ? `${productRiskCopy[allocation.product_risk_level]}（${allocation.product_risk_level.toUpperCase()}）` : "不适用"}</dd></div>
                    </dl>
                    {allocation.reasons.length ? <p><b>为什么考虑：</b>{joinChineseClauses(allocation.reasons)}</p> : null}
                    {allocation.warnings.length ? <p className="fund-allocation-warning"><b>需要留意：</b>{joinChineseClauses(allocation.warnings)}</p> : null}
                    <p className="fund-purchase-route"><b>购买前核对：</b>{allocation.purchase_route}</p>
                  </article>
                ))}
              </div>
            ) : <p className="fund-sleeve-empty">{sleeve.explanation}</p>}

            {sleeve.candidate_products.length > 0 ? (
              <details className="pension-candidate-disclosure">
                <summary>查看个人养老金备选产品</summary>
                <div className="pension-candidate-grid">
                  {sleeve.candidate_products.map((candidate) => (
                    <section key={candidate.product_code}>
                      <div><strong>{candidate.product_code}</strong><span>{candidate.status === "eligible" ? "资料与渠道已核对" : "购买前确认渠道"}</span></div>
                      <h5>{candidate.product_name}</h5>
                      <p>{candidate.role}</p>
                      <small>{candidate.reason}</small>
                    </section>
                  ))}
                </div>
              </details>
            ) : null}

            <details className="fund-guardrail-disclosure">
              <summary>了解这项安排的理由和风险</summary>
              <p>{sleeve.explanation}</p>
              <ul>{sleeve.guardrails.map((item) => <li key={item}>{item}</li>)}</ul>
            </details>
          </article>
        ))}
      </div>

      <details className="verified-fund-catalog">
        <summary>查看产品资料来源</summary>
        <p className="fund-catalog-intro">这些资料用于核对产品身份、风险和渠道，不代表每只产品都适合本家庭。</p>
        <div className="verified-fund-groups">
          {advice.catalog.products.map((product) => (
            <article key={product.code}>
              <header>
                <div><strong>{product.code}</strong><h4>{product.short_name}</h4></div>
                <span>{product.icbc_publicly_listed ? "工行公开列示" : "工行渠道待确认"}</span>
              </header>
              <p>{product.name}</p>
              <dl>
                <div><dt>产品类型</dt><dd>{categoryCopy[product.category] ?? product.category}</dd></div>
                <div><dt>跟踪指数</dt><dd>{product.tracked_index ?? "不适用"}</dd></div>
                <div><dt>最低持有</dt><dd>{product.minimum_holding_days} 天</dd></div>
                <div><dt>个人养老金</dt><dd>{product.personal_pension_eligible ? "名录内" : "普通账户"}</dd></div>
              </dl>
              <p className="fund-channel-copy">{product.icbc_channel_note}</p>
              <ul className="fund-evidence-links">
                {product.evidence.map((evidence) => (
                  <li key={evidence.evidence_id}>
                    <a href={evidence.url} target="_blank" rel="noreferrer">{evidence.issuer}：{evidence.title}</a>
                    <small>核验日期 {formatDate(evidence.verified_on)}</small>
                  </li>
                ))}
              </ul>
            </article>
          ))}
        </div>
      </details>

      <div className="fund-advisory-footer">
        <section><h4>准备购买前</h4><ol>{advice.execution_checklist.map((item) => <li key={item}>{item}</li>)}</ol></section>
        <section><h4>本次安排的范围</h4><ul>{advice.hard_boundaries.map((item) => <li key={item}>{item}</li>)}</ul></section>
      </div>
      <p className="fund-advisory-disclaimer">{advice.disclaimer}</p>
    </section>
  );
}
