import {
  ArrowsClockwiseIcon,
  ClockCounterClockwiseIcon,
  UsersThreeIcon,
  WarningCircleIcon,
} from "@phosphor-icons/react";
import type { ReactNode } from "react";
import type { ProfessionalRoute } from "../../api/specializedCfs";
import type { HouseholdSummary } from "../../api/financial";
import { AppLink } from "../../router/Link";
import { formatDomainLabel } from "../../utils/format";
import { Button } from "../ui/Button";

export function SpecializedHero({
  kicker,
  title,
  description,
  selectId,
  households,
  householdId,
  disabled,
  onHouseholdChange,
  onRefresh,
}: {
  kicker: string;
  title: string;
  description: string;
  selectId: string;
  households: HouseholdSummary[];
  householdId: string;
  disabled: boolean;
  onHouseholdChange: (householdId: string) => void;
  onRefresh: () => void;
}) {
  return (
    <header className="wealth-twin-hero specialized-hero">
      <div>
        <p className="page-kicker">{kicker}</p>
        <h1>{title}</h1>
        <p>{description}</p>
        <AppLink to="/wealth/cfs">返回综合方案</AppLink>
      </div>
      <div className="wealth-profile-controls">
        <label htmlFor={selectId}>当前家庭</label>
        <select
          id={selectId}
          value={householdId}
          onChange={(event) => onHouseholdChange(event.target.value)}
          disabled={households.length === 0 || disabled}
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
          loading={disabled}
          disabled={!householdId}
          onClick={onRefresh}
        >
          <ArrowsClockwiseIcon size={17} aria-hidden="true" /> 核对当前资料
        </Button>
      </div>
    </header>
  );
}

export function SpecializedLoading({ label }: { label: string }) {
  return (
    <section className="profile-loading" role="status" aria-live="polite">
      <ClockCounterClockwiseIcon size={29} weight="duotone" aria-hidden="true" />
      <div><h2>正在核对{label}</h2><p>系统只使用已确认事实与受控规则，不补造缺失数据。</p></div>
    </section>
  );
}

export function SpecializedError({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  return (
    <section className="profile-loading profile-loading-error" role="alert">
      <WarningCircleIcon size={28} weight="duotone" aria-hidden="true" />
      <div><h2>专业方案暂时无法读取</h2><p>{message} 页面不会用估算结果替代缺失记录。</p></div>
      <Button type="button" variant="secondary" onClick={onRetry}>重新连接</Button>
    </section>
  );
}

export function ProfessionalRoutePanel({ route }: { route: ProfessionalRoute }) {
  return (
    <aside className="specialized-route" data-status={route.advisor_workflow_status}>
      <UsersThreeIcon size={28} weight="duotone" aria-hidden="true" />
      <div>
        <span>Complexity Gate · Professional Referral</span>
        <h2>{route.complexity_gate_passed ? "已进入专业协作路由" : "当前无需专业转介"}</h2>
        <p>{route.reason}</p>
      </div>
      <dl>
        <div><dt>复杂度</dt><dd>{formatDomainLabel(route.complexity)}</dd></div>
        <div><dt>协作角色</dt><dd>{route.specialist_type ? formatDomainLabel(route.specialist_type) : "无需转介"}</dd></div>
        <div><dt>顾问工作流</dt><dd>{formatDomainLabel(route.advisor_workflow_status)}</dd></div>
      </dl>
    </aside>
  );
}

export function SpecializedBoundary({ children }: { children: ReactNode }) {
  return <p className="specialized-boundary">边界说明：{children}</p>;
}
