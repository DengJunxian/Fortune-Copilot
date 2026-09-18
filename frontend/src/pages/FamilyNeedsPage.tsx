import { HeartIcon, UsersThreeIcon } from "@phosphor-icons/react";
import { fetchFamilySpecializedNeeds } from "../api/specializedCfs";
import {
  ProfessionalRoutePanel,
  SpecializedBoundary,
  SpecializedError,
  SpecializedHero,
  SpecializedLoading,
} from "../components/wealth/SpecializedCFSFrame";
import { useSpecializedHouseholdView } from "../components/wealth/useSpecializedHouseholdView";
import { formatDomainLabel, formatMoneyInWan } from "../utils/format";

export function FamilyNeedsPage() {
  const state = useSpecializedHouseholdView(fetchFamilySpecializedNeeds, "DEMO_C");
  const retry = () => state.householdId
    ? void state.loadView(state.householdId)
    : void state.loadHouseholds();
  const hasAnyNeed = Boolean(
    state.view?.trust.need_detected || state.view?.philanthropy.has_explicit_goal,
  );
  const trustRoutes = state.view?.trust.routes.filter((route, index, routes) => (
    routes.findIndex((candidate) => (
      candidate.specialist_type === route.specialist_type
      && candidate.advisor_workflow_status === route.advisor_workflow_status
    )) === index
  )) ?? [];

  return (
    <main className="page-shell specialized-page family-needs-page" id="main-content">
      <SpecializedHero
        kicker="Specialized CFS · Family continuity"
        title="把照护、代际安排与公益意愿写进家庭财务底稿。"
        description="只有在已确认事实触发时才展示对应模块；系统识别资料和协作需要，不代替法律、税务或信托意见。"
        selectId="family-needs-household-select"
        households={state.households}
        householdId={state.householdId}
        disabled={state.refreshing}
        onHouseholdChange={state.setHouseholdId}
        onRefresh={() => void state.loadView(state.householdId, { force: true })}
      />

      {state.loading ? <SpecializedLoading label="家庭长期安排" /> : null}
      {!state.loading && state.error ? <SpecializedError message={state.error} onRetry={retry} /> : null}
      {!state.loading && state.view && !hasAnyNeed ? (
        <section className="family-needs-empty">
          <UsersThreeIcon size={34} weight="duotone" aria-hidden="true" />
          <div><span>按需呈现</span><h2>当前没有已确认的复杂家庭安排</h2><p>系统不会因为客户年龄、资产或身份，默认展示信托或传承产品。后续资料变化时再重新识别。</p></div>
        </section>
      ) : null}
      {!state.loading && state.view ? (
        <>
          {state.view.trust.need_detected ? (
            <section className="specialized-section trust-needs-section">
              <header>
                <span>{state.view.trust.outcome}</span>
                <h2>家庭照护与延续安排需要专业复核</h2>
                <p>以下是由家庭成员、资产、企业和保单事实触发的资料清单，不是法律结论。</p>
              </header>
              <ol className="trust-needs-ledger">
                {state.view.trust.needs.map((need) => (
                  <li key={need.id}>
                    <div><span>{formatDomainLabel(need.need_type)}</span><strong>{formatDomainLabel(need.complexity)}复杂度</strong></div>
                    <dl>
                      <div><dt>相关家庭成员</dt><dd>{need.beneficiaries.length} 人</dd></div>
                      <div><dt>纳入资产</dt><dd>{need.assets_in_scope.length} 项</dd></div>
                      <div><dt>关联企业</dt><dd>{need.enterprise_in_scope.length} 家</dd></div>
                      <div><dt>紧迫度</dt><dd>{formatDomainLabel(need.urgency)}</dd></div>
                    </dl>
                  </li>
                ))}
              </ol>
              {trustRoutes.map((route) => (
                <ProfessionalRoutePanel
                  key={`${route.specialist_type}-${route.advisor_workflow_status}`}
                  route={route}
                />
              ))}
              <SpecializedBoundary>{state.view.trust.boundary}</SpecializedBoundary>
            </section>
          ) : null}

          {state.view.philanthropy.has_explicit_goal ? (
            <section className="specialized-section philanthropy-section">
              <header><span>Confirmed intention</span><h2>已确认的公益目标</h2><p>公益安排作为家庭目标进入资金与治理规划，不作为营销标签。</p></header>
              <div className="philanthropy-ledger">
                <HeartIcon size={32} weight="duotone" aria-hidden="true" />
                <div>
                  {state.view.philanthropy.goals.map((goal) => (
                    <article key={goal.id}>
                      <div><span>目标方向</span><h3>{goal.target_cause}</h3><p>{goal.family_participation}</p></div>
                      <dl>
                        <div><dt>年度预算</dt><dd>{formatMoneyInWan(goal.annual_budget)}</dd></div>
                        <div><dt>时间安排</dt><dd>{formatDomainLabel(goal.time_horizon)}</dd></div>
                        <div><dt>治理偏好</dt><dd>{goal.governance_preference}</dd></div>
                      </dl>
                    </article>
                  ))}
                </div>
              </div>
              <ProfessionalRoutePanel route={state.view.philanthropy.route} />
              <SpecializedBoundary>{state.view.philanthropy.boundary}</SpecializedBoundary>
            </section>
          ) : null}
        </>
      ) : null}
    </main>
  );
}
