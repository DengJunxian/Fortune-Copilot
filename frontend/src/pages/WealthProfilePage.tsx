import {
  ArrowsClockwiseIcon,
  BriefcaseIcon,
  ChartDonutIcon,
  CheckCircleIcon,
  CompassIcon,
  FlagIcon,
  HeartbeatIcon,
  ShieldCheckIcon,
  UsersThreeIcon,
  WarningCircleIcon,
} from "@phosphor-icons/react";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  fetchClientProfile,
  recalculateWealthNeeds,
  type ClientProfileResponse,
  type WealthNeedsResponse,
} from "../api/clientProfile";
import { fetchHouseholds, type HouseholdSummary } from "../api/financial";
import { Button } from "../components/ui/Button";
import { formatDate, formatDomainLabel, formatMoney, formatRatio } from "../utils/format";

const needLabels: Record<string, string> = {
  liquidity: "日常流动资金",
  emergency: "家庭应急储备",
  debt_repayment: "债务偿还",
  medical_protection: "医疗保障",
  death_protection: "身故责任保障",
  education: "教育准备",
  housing: "住房目标",
  retirement: "退休准备",
  long_term_growth: "长期增长",
  enterprise_concentration: "企业集中风险",
  currency_matching: "币种匹配",
  succession: "财富传承",
  trust: "信托专业评估",
  philanthropy: "公益安排",
};

const needStatusLabels: Record<string, string> = {
  identified: "待准备",
  partially_prepared: "部分准备",
  prepared: "已有准备",
  needs_review: "需专业复核",
};

function requestedCaseCode(): string | null {
  const queryCode = new URLSearchParams(window.location.search).get("case");
  if (queryCode) return queryCode;
  try {
    return window.sessionStorage?.getItem("fortune-copilot:selected-case") ?? null;
  } catch {
    return null;
  }
}

export function WealthProfilePage() {
  const [households, setHouseholds] = useState<HouseholdSummary[]>([]);
  const [householdId, setHouseholdId] = useState("");
  const [profile, setProfile] = useState<ClientProfileResponse | null>(null);
  const [needs, setNeeds] = useState<WealthNeedsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadHouseholds = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setError(null);
    try {
      const items = await fetchHouseholds(signal);
      if (items.length === 0) throw new Error("尚无可分析家庭");
      setHouseholds(items);
      const requestedCode = requestedCaseCode();
      const preferred = items.find((item) => item.code === requestedCode)
        ?? items.find((item) => item.code === "DEMO_B")
        ?? items[0];
      if (preferred) setHouseholdId(preferred.id);
    } catch (loadError) {
      if (loadError instanceof DOMException && loadError.name === "AbortError") return;
      setLoading(false);
      setError("无法读取家庭资料，请检查后端服务后重试。");
    }
  }, []);

  const loadSnapshot = useCallback(async (
    selectedHouseholdId: string,
    options: { force?: boolean; signal?: AbortSignal } = {},
  ) => {
    setError(null);
    if (options.force) setRefreshing(true);
    else setLoading(true);
    try {
      const needsPayload = await recalculateWealthNeeds(
        selectedHouseholdId,
        options.signal,
      );
      const profilePayload = await fetchClientProfile(
        selectedHouseholdId,
        options.signal,
      );
      setProfile(profilePayload);
      setNeeds(needsPayload);
    } catch (loadError) {
      if (loadError instanceof DOMException && loadError.name === "AbortError") return;
      setProfile(null);
      setNeeds(null);
      setError(loadError instanceof Error ? loadError.message : "财富画像计算失败");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void loadHouseholds(controller.signal);
    return () => controller.abort();
  }, [loadHouseholds]);

  useEffect(() => {
    if (!householdId) return;
    const controller = new AbortController();
    void loadSnapshot(householdId, { signal: controller.signal });
    return () => controller.abort();
  }, [householdId, loadSnapshot]);

  const selectedHousehold = households.find((item) => item.id === householdId);
  const priorityByNeed = useMemo(
    () => new Map(needs?.priorities.map((item) => [item.wealth_need_id, item]) ?? []),
    [needs],
  );

  return (
    <main className="page-shell wealth-profile-page" id="main-content">
      <header className="wealth-profile-hero">
        <div>
          <p className="page-kicker">动态客户财富画像 · 由家庭事实持续更新</p>
          <h1>先看清家庭，再安排财富。</h1>
          <p>
            把家庭阶段、收入职业、资产负债、责任目标和风险边界放在同一张图上，
            每个判断都能回到已授权的数据与规则。
          </p>
        </div>
        <div className="wealth-profile-controls">
          <label htmlFor="profile-household-select">当前家庭</label>
          <select
            id="profile-household-select"
            value={householdId}
            onChange={(event) => setHouseholdId(event.target.value)}
            disabled={households.length === 0 || refreshing}
          >
            {households.length === 0 ? <option value="">等待家庭资料</option> : null}
            {households.map((household) => (
              <option key={household.id} value={household.id}>
                {household.name} · {household.code}
              </option>
            ))}
          </select>
          <Button
            type="button"
            variant="secondary"
            loading={refreshing}
            disabled={!householdId}
            onClick={() => void loadSnapshot(householdId, { force: true })}
          >
            <ArrowsClockwiseIcon size={17} aria-hidden="true" /> 重新核对画像
          </Button>
        </div>
      </header>

      {loading ? <ProfileLoadingState /> : null}
      {!loading && error ? (
        <ProfileErrorState
          message={error}
          onRetry={() => householdId
            ? void loadSnapshot(householdId)
            : void loadHouseholds()}
        />
      ) : null}
      {!loading && profile && needs ? (
        <>
          <ProfileMeta profile={profile} householdName={selectedHousehold?.name ?? "当前家庭"} />
          <ProfileNarrative profile={profile} />
          <NeedLedger needs={needs} priorityByNeed={priorityByNeed} />
          <DataGapPanel gaps={profile.profile.data_gaps} />
          <aside className="profile-boundary" aria-labelledby="profile-boundary-title">
            <ShieldCheckIcon size={24} weight="duotone" aria-hidden="true" />
            <div>
              <h2 id="profile-boundary-title">这不是营销客群标签</h2>
              <p>
                画像只用于解释家庭事实、资料缺口与规划顺序，不推断敏感身份，
                不替代客户确认，也不直接生成金融产品推荐。
              </p>
            </div>
          </aside>
        </>
      ) : null}
    </main>
  );
}

function ProfileMeta({
  profile,
  householdName,
}: {
  profile: ClientProfileResponse;
  householdName: string;
}) {
  return (
    <section className="profile-meta-strip" aria-label="财富画像元数据">
      <div>
        <span>家庭</span>
        <strong>{householdName}</strong>
      </div>
      <div className="profile-completeness">
        <span>资料完整度</span>
        <strong>{formatRatio(profile.profile.completeness_score, 0)}</strong>
        <progress
          value={Number(profile.profile.completeness_score)}
          max={1}
          aria-label="资料完整度"
        />
      </div>
      <div>
        <span>画像版本</span>
        <strong>第 {profile.profile.profile_version} 版</strong>
      </div>
      <div>
        <span>数据 / 规则</span>
        <strong>{formatDate(profile.meta.analysis_date)} · {profile.meta.rule_version}</strong>
      </div>
    </section>
  );
}

function ProfileNarrative({ profile }: { profile: ClientProfileResponse }) {
  const explanation = profile.profile.explanation;
  const cards = [
    [UsersThreeIcon, "家庭所处阶段", explanation.household_stage],
    [BriefcaseIcon, "收入与职业", explanation.income_and_career],
    [ChartDonutIcon, "资产与负债", explanation.asset_liability_features],
    [FlagIcon, "目标与家庭责任", explanation.goals_and_responsibilities],
  ] as const;
  return (
    <section className="profile-narrative" aria-labelledby="profile-overview-title">
      <header>
        <div>
          <p className="section-eyebrow">家庭全貌</p>
          <h2 id="profile-overview-title">影响规划顺序的四组事实</h2>
        </div>
        <p>画像会随家庭事实和账户持仓变化，不采用固定人物模板。</p>
      </header>
      <div className="profile-story-grid">
        <div className="profile-fact-grid">
          {cards.map(([Icon, title, content], index) => (
            <article key={title} data-sequence={index + 1}>
              <Icon size={22} weight="duotone" aria-hidden="true" />
              <span>0{index + 1}</span>
              <h3>{title}</h3>
              <p>{content ?? "资料待补充"}</p>
            </article>
          ))}
        </div>
        <aside className="profile-risk-rail" aria-labelledby="profile-risk-title">
          <div>
            <CompassIcon size={25} weight="duotone" aria-hidden="true" />
            <p className="section-eyebrow">规划边界</p>
            <h2 id="profile-risk-title">风险不是一个分数</h2>
          </div>
          <dl>
            <div>
              <dt>客观风险能力</dt>
              <dd>{formatDomainLabel(profile.profile.risk_capacity)}</dd>
            </div>
            <div>
              <dt>主观风险意愿</dt>
              <dd>{formatDomainLabel(profile.profile.risk_willingness)}</dd>
            </div>
            <div>
              <dt>行为风险上限</dt>
              <dd>{formatDomainLabel(profile.profile.behavior_limit)}</dd>
            </div>
          </dl>
          <p>{profile.profile.explanation.behavior_risk}</p>
        </aside>
      </div>
    </section>
  );
}

function NeedLedger({
  needs,
  priorityByNeed,
}: {
  needs: WealthNeedsResponse;
  priorityByNeed: Map<string, WealthNeedsResponse["priorities"][number]>;
}) {
  return (
    <section className="wealth-needs-panel" aria-labelledby="wealth-needs-title">
      <header>
        <div>
          <p className="section-eyebrow">财富需求图谱</p>
          <h2 id="wealth-needs-title">先处理刚性责任，再安排长期选择</h2>
        </div>
        <p>{needs.needs.length} 项需求 · {needs.meta.professional_review_count} 项需专业复核</p>
      </header>
      <ol className="wealth-needs-ledger">
        {needs.needs.map((need) => {
          const priority = priorityByNeed.get(need.id);
          return (
            <li key={need.id} data-status={need.status}>
              <span className="need-rank" aria-label={`优先级 ${need.priority}`}>
                {String(need.priority).padStart(2, "0")}
              </span>
              <div className="need-copy">
                <div>
                  <h3>{needLabels[need.need_type] ?? need.need_type}</h3>
                  {priority?.hard_constraint ? <span>刚性约束</span> : null}
                  {need.professional_review_required ? <span>专业复核</span> : null}
                </div>
                <p>{priority?.reason ?? "按目标期限与责任刚性排序"}</p>
              </div>
              <div className="need-amounts">
                <span>目标金额</span>
                <strong>{formatMoney(need.target_amount, true)}</strong>
                <small>最低 {formatMoney(need.minimum_amount, true)}</small>
              </div>
              <span className="need-status">{needStatusLabels[need.status]}</span>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

function DataGapPanel({ gaps }: { gaps: ClientProfileResponse["profile"]["data_gaps"] }) {
  return (
    <section className="profile-gaps" aria-labelledby="profile-gaps-title">
      <header>
        {gaps.length > 0
          ? <WarningCircleIcon size={25} weight="duotone" aria-hidden="true" />
          : <CheckCircleIcon size={25} weight="duotone" aria-hidden="true" />}
        <div>
          <p className="section-eyebrow">资料缺口</p>
          <h2 id="profile-gaps-title">
            {gaps.length > 0 ? `还有 ${gaps.length} 类资料待补充` : "核心规划资料已经齐备"}
          </h2>
        </div>
      </header>
      {gaps.length > 0 ? (
        <ul>
          {gaps.map((gap) => (
            <li key={gap.code}>
              <strong>{gap.label}</strong>
              <p>{gap.detail}</p>
              <span>{gap.action}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p>成员、收支、资产、风险、行为与目标资料均已纳入本次画像。</p>
      )}
    </section>
  );
}

function ProfileLoadingState() {
  return (
    <section className="profile-loading" role="status" aria-live="polite">
      <HeartbeatIcon size={28} weight="duotone" aria-hidden="true" />
      <div>
        <h2>正在核对家庭财富画像</h2>
        <p>确定性引擎正在连接家庭事实、金融图、风险评估和目标责任。</p>
      </div>
    </section>
  );
}

function ProfileErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <section className="profile-loading profile-loading-error" role="alert">
      <WarningCircleIcon size={28} weight="duotone" aria-hidden="true" />
      <div>
        <h2>财富画像暂时无法生成</h2>
        <p>{message} 页面不会用前端估算替代后端结果。</p>
      </div>
      <Button type="button" variant="secondary" onClick={onRetry}>重新连接</Button>
    </section>
  );
}
