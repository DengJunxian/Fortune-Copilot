import {
  ArrowsLeftRightIcon,
  CheckCircleIcon,
  ClockIcon,
  CoinsIcon,
  ProhibitIcon,
  ScalesIcon,
  ShieldWarningIcon,
} from "@phosphor-icons/react";
import type {
  CFSProductCandidateGroup,
  CFSProductCompositionResponse,
  RankedProductCandidate,
} from "../../api/productOntology";
import { formatDomainLabel } from "../../utils/format";

const componentNames: Record<CFSProductCandidateGroup["component_type"], string> = {
  liquidity: "流动性安排",
  debt: "债务安排",
  protection: "保障安排",
  housing: "住房安排",
  education: "教育安排",
  retirement: "养老安排",
  investment: "长期配置",
  enterprise_risk: "家企风险",
  cross_border: "跨境与币种",
  succession: "财富传承",
  trust: "信托审查",
  philanthropy: "公益安排",
  professional_service: "专业服务",
  no_action: "当前不新增投资",
};

function ProductCandidate({ candidate }: { candidate: RankedProductCandidate }) {
  const fee = candidate.product.all_in_cost === null
    ? "待渠道补齐"
    : `${(Number(candidate.product.all_in_cost) * 100).toFixed(2)}%`;
  const minimumHolding = candidate.snapshot.liquidity_snapshot.minimum_holding_days ?? 0;
  return (
    <article className="cfs-product-candidate">
      <header>
        <span className="cfs-product-rank">#{candidate.rank}</span>
        <div>
          <small>{formatDomainLabel(candidate.product.product_family)} · {candidate.product.code}</small>
          <h4>{candidate.product.name}</h4>
          <p>{candidate.product.issuer}</p>
        </div>
        <span className="cfs-product-eligibility" data-decision={candidate.eligibility.decision}>
          {formatDomainLabel(candidate.eligibility.decision)}
        </span>
      </header>
      <dl className="cfs-product-facts">
        <div><dt><CoinsIcon size={16} aria-hidden="true" /> 客户总成本</dt><dd>{fee}</dd></div>
        <div><dt><ClockIcon size={16} aria-hidden="true" /> 流动性</dt><dd>{minimumHolding ? `至少持有 ${minimumHolding} 天` : "无最低持有期限制"}</dd></div>
        <div><dt><ShieldWarningIcon size={16} aria-hidden="true" /> 风险</dt><dd>{candidate.snapshot.risk_level.toUpperCase()} · 本金可能损失</dd></div>
      </dl>
      <div className="cfs-product-reasoning">
        <div>
          <strong><CheckCircleIcon size={17} weight="fill" aria-hidden="true" /> Why Selected · 为什么进入候选</strong>
          <ul>{candidate.why_selected.map((reason) => <li key={reason}>{reason}</li>)}</ul>
        </div>
        <div>
          <strong><ArrowsLeftRightIcon size={17} aria-hidden="true" /> Why Not Others · 为什么不是其他候选</strong>
          <ul>{candidate.why_not_other_candidates.map((reason) => <li key={reason}>{reason}</li>)}</ul>
        </div>
      </div>
      <footer>
        <ScalesIcon size={17} aria-hidden="true" />
        <p><strong>利益冲突披露</strong>{candidate.product.distribution_incentive_disclosure}</p>
      </footer>
      {candidate.eligibility.restrictions.length ? (
        <p className="cfs-product-restriction">{candidate.eligibility.restrictions.join("")}</p>
      ) : null}
    </article>
  );
}

function ProductFunnel({ group }: { group: CFSProductCandidateGroup }) {
  if (!group.funnel) return null;
  return (
    <section className="product-candidate-funnel" aria-label={`${componentNames[group.component_type]}产品候选漏斗`}>
      <header><strong>Product Candidate Funnel</strong><span>数量来自确定性产品引擎</span></header>
      <ol>
        {group.funnel.stages.map((stage) => (
          <li key={stage.code} data-final={stage.code === "final_candidates"}>
            <span>{stage.label}</span><strong>{stage.count}</strong>
          </li>
        ))}
      </ol>
      <p>{group.funnel.explanation}</p>
    </section>
  );
}

export function CFSProductCandidates({ composition }: { composition: CFSProductCompositionResponse }) {
  return (
    <section className="cfs-products-section" aria-labelledby="cfs-products-heading">
      <header className="section-heading">
        <div>
          <p className="page-kicker">Buy-side product ontology</p>
          <h2 id="cfs-products-heading">当前家庭约束下的候选产品</h2>
        </div>
        <p>目录证据截至 {composition.catalog_as_of}。先过硬闸门，再按客户利益排序；销售激励不会提高名次。</p>
      </header>
      {composition.catalog_stale ? (
        <p className="cfs-catalog-alert" role="alert">目录已超过复核期限：以下内容只能用于教育比较，不构成可执行建议。</p>
      ) : null}
      <div className="cfs-product-groups">
        {composition.groups.map((group) => (
          <section className="cfs-product-group" key={group.component_id} data-result={group.result}>
            <header><h3>{componentNames[group.component_type]}</h3><p>{group.purpose}</p></header>
            <div className="cfs-product-group-content">
              <ProductFunnel group={group} />
              {group.result === "no_product" ? (
                <div className="cfs-no-product">
                  <ProhibitIcon size={24} weight="duotone" aria-hidden="true" />
                  <div><strong>NO PRODUCT</strong><p>{group.no_product_reason}</p></div>
                </div>
              ) : (
                <>
                  <div className="cfs-product-candidates">
                    {group.candidates.map((candidate) => <ProductCandidate key={candidate.product.id} candidate={candidate} />)}
                  </div>
                  {group.excluded.length ? (
                    <details className="cfs-excluded-products">
                      <summary>查看 {group.excluded.length} 个未进入候选的产品及原因</summary>
                      <ul>{group.excluded.map((product) => (
                        <li key={product.product_id}>
                          <div><strong>{product.product_name}</strong><small>{product.product_code}</small></div>
                          <p>{product.reasons.join("；")}</p>
                        </li>
                      ))}</ul>
                    </details>
                  ) : null}
                </>
              )}
            </div>
          </section>
        ))}
      </div>
      <p className="cfs-product-boundary">{composition.execution_boundary}</p>
    </section>
  );
}
