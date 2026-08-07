import {
  BriefcaseIcon,
  MapPinIcon,
  PlusIcon,
  TrashIcon,
  UsersThreeIcon,
} from "@phosphor-icons/react";
import type {
  CityTier,
  FundsSource,
  IntakeMember,
  PlanningIntake,
} from "../../api/wealthPlanning";

interface PlanningProfileFormProps {
  draft: PlanningIntake;
  error: string | null;
  onChange: (draft: PlanningIntake) => void;
  onContinue: () => void;
}

const relationshipOptions = ["本人", "配偶", "子女", "父母", "其他家庭成员"];
const cityTierOptions: Array<{ value: CityTier; label: string; hint: string; suggested: string }> = [
  { value: "tier_one_or_new_tier_one", label: "一线及新一线城市", hint: "常用观察区间 50万-100万元", suggested: "700000" },
  { value: "developed_city", label: "其他发达城市", hint: "常用观察区间 40万-70万元", suggested: "500000" },
  { value: "other_city", label: "三四线及其他城市", hint: "常用观察区间 30万-50万元", suggested: "400000" },
];
const fundsSourceOptions: Array<{ value: FundsSource; label: string }> = [
  { value: "salary", label: "工资薪金" },
  { value: "business", label: "经营收入" },
  { value: "accumulated_savings", label: "历年储蓄" },
  { value: "property_income", label: "房产相关收入" },
  { value: "investment_income", label: "投资收益" },
  { value: "family_support", label: "家庭支持" },
  { value: "other", label: "其他合法来源" },
];

function blankMember(relationship: string): IntakeMember {
  return {
    display_name: "",
    relationship,
    birth_date: "",
    occupation: "",
    employment_stability: "medium",
    expected_retirement_age: relationship === "子女" ? null : 60,
  };
}

export function PlanningProfileForm({
  draft,
  error,
  onChange,
  onContinue,
}: PlanningProfileFormProps) {
  function updateMember(index: number, patch: Partial<IntakeMember>) {
    const members = draft.members.map((member, memberIndex) => (
      memberIndex === index ? { ...member, ...patch } : member
    ));
    onChange({ ...draft, members });
  }

  function setScope(scope: PlanningIntake["planning_scope"]) {
    const members = scope === "individual"
      ? [draft.members.find((item) => item.relationship === "本人") ?? blankMember("本人")]
      : draft.members;
    onChange({ ...draft, planning_scope: scope, members });
  }

  function addMember() {
    const used = new Set(draft.members.map((item) => item.relationship));
    const relationship = relationshipOptions.find((item) => !used.has(item) && item !== "本人") ?? "其他家庭成员";
    onChange({ ...draft, members: [...draft.members, blankMember(relationship)] });
  }

  function removeMember(index: number) {
    onChange({ ...draft, members: draft.members.filter((_, memberIndex) => memberIndex !== index) });
  }

  function updateKyc(patch: Partial<PlanningIntake["kyc"]>) {
    onChange({ ...draft, kyc: { ...draft.kyc, ...patch } });
  }

  function setCityTier(cityTier: CityTier) {
    const option = cityTierOptions.find((item) => item.value === cityTier);
    updateKyc({
      city_tier: cityTier,
      growth_entry_threshold: option?.suggested ?? draft.kyc.growth_entry_threshold,
    });
  }

  function toggleFundsSource(source: FundsSource) {
    const selected = draft.kyc.funds_sources.includes(source);
    const next = selected
      ? draft.kyc.funds_sources.filter((item) => item !== source)
      : [...draft.kyc.funds_sources, source];
    if (next.length) updateKyc({ funds_sources: next });
  }

  return (
    <section className="planning-step-panel" aria-labelledby="profile-step-heading">
      <header className="planning-step-header">
        <div>
          <span>建立客户档案</span>
          <h1 id="profile-step-heading">先了解您和家人</h1>
          <p>这些信息用于判断家庭阶段和责任范围。金额将在下一步填写。</p>
        </div>
        <UsersThreeIcon size={44} weight="duotone" aria-hidden="true" />
      </header>

      <fieldset className="scope-choice">
        <legend>本次规划对象</legend>
        <label>
          <input
            type="radio"
            name="planning-scope"
            value="family"
            checked={draft.planning_scope === "family"}
            onChange={() => setScope("family")}
          />
          <span><strong>家庭规划</strong><small>共同分析家庭成员、责任和收支</small></span>
        </label>
        <label>
          <input
            type="radio"
            name="planning-scope"
            value="individual"
            checked={draft.planning_scope === "individual"}
            onChange={() => setScope("individual")}
          />
          <span><strong>个人规划</strong><small>只分析本人财务情况</small></span>
        </label>
      </fieldset>

      <div className="profile-fields-grid">
        <label className="form-field">
          <span>规划名称</span>
          <input
            type="text"
            value={draft.case_name}
            onChange={(event) => onChange({ ...draft, case_name: event.target.value })}
            autoComplete="off"
            aria-describedby="case-name-help"
          />
          <small id="case-name-help">例如：张先生家庭财富规划</small>
        </label>
        <label className="form-field">
          <span><MapPinIcon size={17} aria-hidden="true" /> 常住地区</span>
          <input
            type="text"
            value={draft.region}
            onChange={(event) => onChange({ ...draft, region: event.target.value })}
            autoComplete="address-level1"
            aria-describedby="region-help"
          />
          <small id="region-help">填写省市即可，用于后续政策和生活成本口径</small>
        </label>
      </div>

      <div className="member-section-heading">
        <div>
          <h2>家庭成员</h2>
          <p>请按实际共同承担财务责任的成员填写。</p>
        </div>
        {draft.planning_scope === "family" ? (
          <button className="text-action" type="button" onClick={addMember}>
            <PlusIcon size={17} weight="bold" aria-hidden="true" /> 添加成员
          </button>
        ) : null}
      </div>

      <div className="member-editor-list">
        {draft.members.map((member, index) => (
          <fieldset className="member-editor" key={`${member.relationship}-${index}`}>
            <legend>
              <span>{member.relationship || `成员 ${index + 1}`}</span>
              {member.relationship !== "本人" ? (
                <button type="button" onClick={() => removeMember(index)} aria-label={`删除${member.relationship}`}>
                  <TrashIcon size={17} aria-hidden="true" />
                </button>
              ) : null}
            </legend>
            <div className="member-fields-grid">
              <label className="form-field">
                <span>与本人关系</span>
                <select
                  value={member.relationship}
                  disabled={member.relationship === "本人"}
                  onChange={(event) => updateMember(index, { relationship: event.target.value })}
                >
                  {relationshipOptions.map((option) => <option key={option}>{option}</option>)}
                </select>
              </label>
              <label className="form-field">
                <span>姓名</span>
                <input
                  type="text"
                  value={member.display_name}
                  onChange={(event) => updateMember(index, { display_name: event.target.value })}
                  autoComplete={member.relationship === "本人" ? "name" : "off"}
                />
              </label>
              <label className="form-field">
                <span>出生日期</span>
                <input
                  type="date"
                  value={member.birth_date}
                  max={new Date().toISOString().slice(0, 10)}
                  onChange={(event) => updateMember(index, { birth_date: event.target.value })}
                />
              </label>
              <label className="form-field">
                <span><BriefcaseIcon size={17} aria-hidden="true" /> {member.relationship === "子女" ? "身份（选填）" : "职业或身份"}</span>
                <input
                  type="text"
                  value={member.occupation}
                  placeholder={member.relationship === "子女" ? "例如：学生或学龄前" : undefined}
                  onChange={(event) => updateMember(index, { occupation: event.target.value })}
                />
              </label>
              <label className="form-field">
                <span>收入稳定性</span>
                {member.relationship === "子女" ? (
                  <input type="text" value="不适用" disabled />
                ) : (
                  <select
                    value={member.employment_stability}
                    onChange={(event) => updateMember(index, {
                      employment_stability: event.target.value as IntakeMember["employment_stability"],
                    })}
                  >
                    <option value="high">稳定</option>
                    <option value="medium">一般</option>
                    <option value="low">波动较大</option>
                  </select>
                )}
              </label>
              <label className="form-field">
                <span>预计退休年龄</span>
                {member.relationship === "子女" ? (
                  <input type="text" value="不适用" disabled />
                ) : (
                  <input
                    type="number"
                    min="45"
                    max="80"
                    value={member.expected_retirement_age ?? ""}
                    onChange={(event) => updateMember(index, {
                      expected_retirement_age: event.target.value ? Number(event.target.value) : null,
                    })}
                  />
                )}
              </label>
            </div>
          </fieldset>
        ))}
      </div>

      <section className="kyc-section" aria-labelledby="kyc-heading">
        <header>
          <div>
            <h2 id="kyc-heading">投资适当性与长期资金边界</h2>
            <p>这几项用于判断是否具备安排“生钱的钱”的基础，不会替代后续具体产品测评。</p>
          </div>
          <span>客户识别</span>
        </header>

        <div className="kyc-fields-grid">
          <label className="form-field">
            <span>地区类型</span>
            <select
              value={draft.kyc.city_tier}
              onChange={(event) => setCityTier(event.target.value as CityTier)}
            >
              {cityTierOptions.map((option) => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>
            <small>{cityTierOptions.find((item) => item.value === draft.kyc.city_tier)?.hint}</small>
          </label>

          <label className="form-field kyc-threshold-field">
            <span>“生钱的钱”启动线 <strong>{Number(draft.kyc.growth_entry_threshold) / 10000} 万元</strong></span>
            <input
              type="range"
              min="300000"
              max="1000000"
              step="50000"
              value={draft.kyc.growth_entry_threshold}
              onChange={(event) => updateKyc({ growth_entry_threshold: event.target.value })}
            />
            <small>计算口径：现金类、定期及金融资产合计，扣除全部贷款与信用卡未付余额。</small>
          </label>

          <label className="form-field">
            <span>投资经验</span>
            <select
              value={draft.kyc.investment_experience}
              onChange={(event) => updateKyc({
                investment_experience: event.target.value as PlanningIntake["kyc"]["investment_experience"],
              })}
            >
              <option value="none">没有投资经验</option>
              <option value="basic">了解存款、理财和基金</option>
              <option value="experienced">有长期投资和资产配置经验</option>
            </select>
          </label>

          <label className="form-field">
            <span>风险偏好</span>
            <select
              value={draft.kyc.risk_preference}
              onChange={(event) => updateKyc({
                risk_preference: event.target.value as PlanningIntake["kyc"]["risk_preference"],
              })}
            >
              <option value="conservative">优先保持本金稳定</option>
              <option value="balanced">在波动与长期增长间平衡</option>
              <option value="growth">能接受较明显波动追求长期增长</option>
            </select>
          </label>

          <label className="form-field">
            <span>最大波动承受度</span>
            <select
              value={draft.kyc.loss_tolerance}
              onChange={(event) => updateKyc({
                loss_tolerance: event.target.value as PlanningIntake["kyc"]["loss_tolerance"],
              })}
            >
              <option value="low">短期亏损约 5% 就会影响持有</option>
              <option value="medium">可承受约 10% 的阶段波动</option>
              <option value="high">可承受约 20% 的阶段波动</option>
            </select>
          </label>

          <label className="form-field">
            <span>预计投资期限</span>
            <select
              value={draft.kyc.investment_horizon_years}
              onChange={(event) => updateKyc({ investment_horizon_years: Number(event.target.value) })}
            >
              <option value="1">1-2 年</option>
              <option value="3">3-5 年</option>
              <option value="5">5-10 年</option>
              <option value="10">10 年以上</option>
            </select>
          </label>

          <label className="form-field">
            <span>个人养老金账户</span>
            <select
              value={draft.kyc.personal_pension_status}
              onChange={(event) => updateKyc({
                personal_pension_status: event.target.value as PlanningIntake["kyc"]["personal_pension_status"],
              })}
            >
              <option value="opened">已经开立</option>
              <option value="not_opened">尚未开立</option>
              <option value="not_sure">暂不确定</option>
            </select>
          </label>
        </div>

        <fieldset className="funds-source-fieldset">
          <legend>本次资产的主要合法来源</legend>
          <div>
            {fundsSourceOptions.map((option) => (
              <label key={option.value}>
                <input
                  type="checkbox"
                  checked={draft.kyc.funds_sources.includes(option.value)}
                  onChange={() => toggleFundsSource(option.value)}
                />
                <span>{option.label}</span>
              </label>
            ))}
          </div>
        </fieldset>
      </section>

      {error ? <p className="inline-form-error" role="alert">{error}</p> : null}
      <footer className="planning-step-actions">
        <span>资料会自动保存在当前浏览器中</span>
        <button className="primary-action" type="button" onClick={onContinue}>继续填写财务报表</button>
      </footer>
    </section>
  );
}
