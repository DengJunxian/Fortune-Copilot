import { useState, type FormEvent } from "react";
import {
  deleteHouseholdData,
  exportHouseholdData,
  requestHumanReview,
  withdrawPrivacyConsent,
  type ClientExperience,
} from "../../api/clientExperience";
import { formatDate } from "../../utils/format";
import { Button } from "../ui/Button";
import { StatusBadge } from "../ui/StatusBadge";

export function PrivacyCenter({
  experience,
  onRefresh,
}: {
  experience: ClientExperience;
  onRefresh: () => Promise<void>;
}) {
  const [withdrawId, setWithdrawId] = useState<string | null>(null);
  const [withdrawReason, setWithdrawReason] = useState("");
  const [withdrawing, setWithdrawing] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleteCode, setDeleteCode] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [deleteReason, setDeleteReason] = useState("");
  const [exporting, setExporting] = useState(false);
  const [reviewReason, setReviewReason] = useState("请由人工解释当前方案的授权范围和可撤回影响");
  const [reviewing, setReviewing] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const selectedConsent = experience.privacy.consents.find((item) => item.id === withdrawId);

  async function exportData() {
    setExporting(true);
    setMessage(null);
    try {
      await exportHouseholdData(experience.household_id);
      setMessage("数据包已导出；本次操作已写入去标识审计记录。");
    } catch {
      setMessage("导出失败；请刷新后重试或转人工。");
    } finally {
      setExporting(false);
    }
  }

  async function confirmWithdraw(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedConsent) return;
    setWithdrawing(true);
    setMessage(null);
    try {
      await withdrawPrivacyConsent(experience.household_id, selectedConsent.id, selectedConsent.record_version, withdrawReason);
      setMessage("授权已撤回并写入审计记录；后续新计算将重新核对可用范围。");
      setWithdrawId(null);
      setWithdrawReason("");
      await onRefresh();
    } catch {
      setMessage("撤回失败；授权版本可能已经变化，请刷新后重试或转人工。");
    } finally {
      setWithdrawing(false);
    }
  }

  async function confirmDelete(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (deleteCode !== experience.household_code) return;
    setDeleting(true);
    setMessage(null);
    try {
      await deleteHouseholdData(
        experience.household_id,
        experience.household_version,
        deleteCode,
        deleteReason,
      );
      setMessage("家庭数据已逻辑擦除并去标识；必要审计仅保留不可逆摘要。");
      setDeleteOpen(false);
    } catch {
      setMessage("删除失败；家庭版本可能已经变化，请刷新后重试或转人工。");
    } finally {
      setDeleting(false);
    }
  }

  async function submitHumanReview(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setReviewing(true);
    setMessage(null);
    try {
      const response = await requestHumanReview(experience.household_id, reviewReason);
      setMessage(`${response.message} 请求号 ${response.request_id.slice(0, 8)}。`);
    } catch {
      setMessage("人工复核请求未写入；请检查后端连接后重试。");
    } finally {
      setReviewing(false);
    }
  }

  return (
    <section className="privacy-center" aria-labelledby="client-view-heading">
      <header className="client-view-header">
        <div><p className="page-kicker">授权、导出与删除</p><h2 id="client-view-heading" tabIndex={-1}>隐私中心</h2><p>查看数据用途，撤回授权，导出家庭数据，或明确转交人工决策。</p></div>
        <Button type="button" loading={exporting} onClick={() => void exportData()}>导出家庭数据包</Button>
      </header>

      <section className="consent-ledger" aria-labelledby="consent-heading">
        <header><h3 id="consent-heading">授权范围</h3><span>有效 {experience.privacy.active_consent_count}，已撤回 {experience.privacy.withdrawn_consent_count}</span></header>
        {experience.privacy.consents.length === 0 ? <div className="empty-state"><strong>尚无授权记录</strong><p>先完成授权，再进入深度规划。</p></div> : (
          <ol>
            {experience.privacy.consents.map((consent) => (
              <li key={consent.id}>
                <div><StatusBadge tone={consent.status === "active" ? "success" : "info"}>{consent.status === "active" ? "有效" : "已撤回"}</StatusBadge><strong>{consent.purpose}</strong><small>{consent.sensitive ? "敏感信息独立授权" : "普通场景授权"} · 场景 {consent.scenario} · {consent.explicit ? "明示" : "待核验"} · {consent.minimum_necessary ? "最小必要" : "范围待复核"}</small><small>版本 {consent.consent_version}，授权于 {formatDate(consent.granted_at.slice(0, 10))}</small></div>
                <ul aria-label="授权字段">{consent.scopes.map((scope) => <li key={scope}>{scope}</li>)}</ul>
                <Button type="button" variant="secondary" disabled={!consent.withdrawal_allowed} onClick={() => setWithdrawId(consent.id)}>{consent.withdrawal_allowed ? "撤回此授权" : "已撤回"}</Button>
              </li>
            ))}
          </ol>
        )}
      </section>

      {selectedConsent ? (
        <form className="privacy-confirmation" onSubmit={confirmWithdraw}>
          <h3>确认撤回授权</h3>
          <p>撤回后，范围内数据不再用于新计算；既有审计记录按治理要求保留。</p>
          <label><span>撤回原因</span><textarea required minLength={2} value={withdrawReason} onChange={(event) => setWithdrawReason(event.target.value)} /></label>
          <div><Button type="submit" variant="danger" loading={withdrawing}>确认撤回</Button><Button type="button" variant="secondary" onClick={() => setWithdrawId(null)}>取消</Button></div>
        </form>
      ) : null}

      <div className="privacy-action-grid">
        <section>
          <h3>人工决策入口</h3>
          <p>高风险建议、授权争议或解释不足时，语言模型不能替代人工决定。</p>
          <form onSubmit={submitHumanReview}><label><span>需要人工处理的问题</span><textarea required minLength={2} value={reviewReason} onChange={(event) => setReviewReason(event.target.value)} /></label><Button type="submit" variant="secondary" loading={reviewing}>提交人工复核</Button></form>
        </section>
        <section className="danger-zone">
          <h3>删除家庭数据</h3>
          <p>删除会逻辑擦除业务记录、去标识直接身份字段，只保留必要的不可逆审计摘要；不会调用真实银行接口。</p>
          {!deleteOpen ? <Button type="button" variant="danger" onClick={() => setDeleteOpen(true)}>进入删除确认</Button> : (
            <form onSubmit={confirmDelete}>
              <label><span>输入家庭代码 {experience.household_code}</span><input required value={deleteCode} onChange={(event) => setDeleteCode(event.target.value)} /></label>
              <label><span>删除原因</span><textarea required minLength={2} value={deleteReason} onChange={(event) => setDeleteReason(event.target.value)} /></label>
              <div><Button type="submit" variant="danger" disabled={deleteCode !== experience.household_code || deleteReason.length < 2} loading={deleting}>确认擦除</Button><Button type="button" variant="secondary" onClick={() => setDeleteOpen(false)}>取消</Button></div>
            </form>
          )}
        </section>
      </div>
      <p className="privacy-boundary">{experience.privacy.boundary_note}</p>
      {message ? <p className="privacy-message" role="status">{message}</p> : null}
    </section>
  );
}
