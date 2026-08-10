import { useEffect, useState } from "react";
import {
  fetchIntegrationReadiness,
  fetchPublicDataSnapshot,
  type IntegrationReadiness,
  type PublicDataSnapshotSummary,
} from "../../api/integrations";
import { StatusBadge } from "../ui/StatusBadge";

function ratePercent(value: string) {
  return `${(Number(value) * 100).toFixed(1)}%`;
}

export function ProductionReadinessWorkspace() {
  const [readiness, setReadiness] = useState<IntegrationReadiness | null>(null);
  const [publicData, setPublicData] = useState<PublicDataSnapshotSummary | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    void Promise.all([
      fetchIntegrationReadiness(controller.signal),
      fetchPublicDataSnapshot(controller.signal),
    ]).then(([nextReadiness, nextPublicData]) => {
      setReadiness(nextReadiness);
      setPublicData(nextPublicData);
    }).catch(() => setError(true));
    return () => controller.abort();
  }, []);

  if (error) {
    return <p className="empty-state">生产边界台账暂不可用；系统不会因此把 Mock 能力标记为真实接入。</p>;
  }
  if (!readiness || !publicData) {
    return <p className="empty-state">正在核对公共数据版本与生产依赖…</p>;
  }

  const blocked = readiness.capabilities.filter((item) => item.production_blocking);
  const livingCost = Object.values(publicData.snapshot.regional_living_cost_observations);
  return (
    <section className="production-readiness" aria-labelledby="production-readiness-heading">
      <header>
        <div>
          <p className="page-kicker">Production Boundary</p>
          <h2 id="production-readiness-heading">真实数据与银行系统接入边界</h2>
          <p>公开参数已固化为可重演快照；客户、产品、交易和银行内部权限缺失时保持硬阻断。</p>
        </div>
        <StatusBadge tone={readiness.production_ready ? "success" : "warning"}>
          {readiness.production_ready ? "生产就绪" : "原型可用 · 生产未就绪"}
        </StatusBadge>
      </header>

      <dl className="production-readiness-summary">
        <div>
          <dt>银行生产连接</dt>
          <dd>{readiness.has_live_icbc_connection ? "已连接" : "未连接"}</dd>
          <small>不使用公开网页模拟客户或交易接口</small>
        </div>
        <div>
          <dt>生产阻断项</dt>
          <dd>{blocked.length}</dd>
          <small>合同、授权、审批或平台证据尚缺</small>
        </div>
        <div>
          <dt>官方 CPI 观察</dt>
          <dd>{ratePercent(publicData.snapshot.official_cpi.rate)}</dd>
          <small>版本 {publicData.snapshot.official_cpi.version}</small>
        </div>
        <div>
          <dt>公共快照截止</dt>
          <dd>{publicData.snapshot.publication_cutoff}</dd>
          <small>哈希 {publicData.integrity_hash.slice(0, 12)}…</small>
        </div>
      </dl>

      <div className="production-readiness-columns">
        <article>
          <h3>必须由工行生产系统提供</h3>
          <ul>
            {blocked.map((item) => (
              <li key={item.capability}>
                <div>
                  <strong>{item.label}</strong>
                  <small>{item.required_prerequisites.slice(0, 3).join(" · ")}</small>
                </div>
                <StatusBadge tone="danger">硬阻断</StatusBadge>
              </li>
            ))}
          </ul>
        </article>
        <article>
          <h3>已核验的地区生活成本观察</h3>
          <ul>
            {livingCost.map((item) => (
              <li key={item.region_name}>
                <div>
                  <strong>{item.region_name}</strong>
                  <small>{item.period_end.slice(0, 4)} 年人均消费支出 ¥{Number(item.amount).toLocaleString("zh-CN")}</small>
                </div>
                <StatusBadge tone={item.data_quality.includes("stale") ? "warning" : "info"}>
                  {item.data_quality.includes("stale") ? "历史数据" : "已核验"}
                </StatusBadge>
              </li>
            ))}
          </ul>
          <p>这些是名义消费支出观察，不是 CPI，也不直接替代家庭支出通胀。</p>
        </article>
      </div>
      <p className="privacy-boundary">{readiness.boundary_note}</p>
    </section>
  );
}
