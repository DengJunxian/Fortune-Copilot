import {
  ArrowRightIcon,
  BuildingsIcon,
  ChartLineUpIcon,
  CheckCircleIcon,
  CompassIcon,
  FileTextIcon,
  FlagIcon,
  HouseLineIcon,
  ScalesIcon,
  ShieldCheckIcon,
  TreeStructureIcon,
  UsersThreeIcon,
  WalletIcon,
} from "@phosphor-icons/react";
import { AppLink } from "../router/Link";
import { useRouter } from "../router/context";

const chineseDifferences = [
  {
    topic: "决策单位",
    imported: "以个人风险偏好和可投资资产为中心",
    chinese: "以家庭为单位，同时核对成员、收入、住房、赡养、教育与保障责任",
  },
  {
    topic: "资产结构",
    imported: "用固定比例切分现金、保障与投资",
    chinese: "先识别房产集中、经营性资产、房贷与流动性，再确定各账户边界",
  },
  {
    topic: "制度环境",
    imported: "默认养老、税制和资本流动规则相对统一",
    chinese: "纳入社保、个人养老金、地区生活成本、人民币与跨境约束",
  },
  {
    topic: "服务方式",
    imported: "一次测评后匹配产品，结果随交易结束",
    chinese: "家庭事实变化即重算，方案、解释、复核和行动记录持续留痕",
  },
];

const theoryLayers = [
  {
    icon: TreeStructureIcon,
    title: "家庭事实账本",
    detail: "把成员、收入、支出、资产、负债、保障、企业权益和家庭关系放入同一张可追溯图谱。",
    className: "theory-facts",
  },
  {
    icon: FlagIcon,
    title: "目标与责任边界",
    detail: "住房、教育、养老、医疗、赡养与传承按期限和责任主体分别核算。",
    className: "theory-goals",
  },
  {
    icon: WalletIcon,
    title: "合格长期资金",
    detail: "先扣除日常周转、应急储备、明确负债和近期目标，再讨论长期配置。",
    className: "theory-capital",
  },
  {
    icon: ChartLineUpIcon,
    title: "家庭财富孪生",
    detail: "用时间、情景与家庭事件推演方案承受力，保留每次变化前后的差异。",
    className: "theory-twin",
  },
  {
    icon: ScalesIcon,
    title: "综合财富方案",
    detail: "现金流、保障、负债、投资、退休与传承共同进入方案，产品只能在适当性边界内候选。",
    className: "theory-plan",
  },
];

const fourAccounts = [
  {
    name: "日常账户",
    purpose: "维持家庭运转",
    detail: "覆盖日常支出、账单与短期周转，保持随时可用。",
  },
  {
    name: "保障账户",
    purpose: "承接不可承受的风险",
    detail: "依据家庭责任核对医疗、重疾、意外与寿险缺口。",
  },
  {
    name: "稳健账户",
    purpose: "守住近期目标与安全垫",
    detail: "承接应急金、教育、养老准备和确定期限的大额支出。",
  },
  {
    name: "长期账户",
    purpose: "管理长期购买力",
    detail: "只使用通过前置条件核验的长期资金，重视分散、成本与纪律。",
  },
];

const operatingPath = [
  ["看清家底", "统一资产、负债、收入与支出口径，确认数据日期和责任主体。"],
  ["划清边界", "先满足周转、保障、负债与近期目标，再计算可承担风险的长期资金。"],
  ["形成方案", "把目标、现金流、风险预算和产品适当性写入同一份家庭方案。"],
  ["持续复盘", "收入、家庭成员、市场或政策变化后重算，保留版本与人工复核记录。"],
];

const systemFacts = [
  ["17 类", "家庭关系与财富事实节点"],
  ["10 维", "中国家庭财务健康诊断"],
  ["8 章", "结构化家庭财富规划书"],
  ["全程", "依据、版本与人工复核留痕"],
];

const cases = [
  {
    code: "DEMO_A",
    image: "/personas/early-career.jpg",
    stage: "职业起步期",
    title: "单身职场新人",
    profile: "收入进入上升阶段，先建立应急储备，再安排置业与长期积累。",
    focus: "现金储备、结余能力、购房目标",
  },
  {
    code: "DEMO_B",
    image: "/personas/young-family.jpg",
    stage: "育儿成长期",
    title: "双收入三口之家",
    profile: "房贷、教育和父母责任并行，需要管理偿债压力与资产集中。",
    focus: "住房负债、教育准备、家庭保障",
  },
  {
    code: "DEMO_C",
    image: "/personas/pre-retirement.jpg",
    stage: "退休准备期",
    title: "临近退休夫妻",
    profile: "工作收入期限缩短，需要把养老金、医疗准备与退休现金流接起来。",
    focus: "退休收入、流动性、医疗保障",
  },
];

export function HomePage() {
  const { navigate } = useRouter();

  function openCase(code: string) {
    try {
      window.sessionStorage?.setItem("fortune-copilot:selected-case", code);
    } catch {
      // The planning route remains usable when browser storage is unavailable.
    }
    navigate("/planning");
  }

  return (
    <main className="product-home" id="main-content">
      <section className="home-hero" aria-labelledby="home-hero-title">
        <img
          className="home-hero-image"
              src="/brand/chinese-wealth-system-hero.webp"
          alt="山水层叠、城市建筑与资金流线构成的中国家庭财富管理主视觉"
          fetchPriority="high"
        />
        <div className="home-hero-shade" aria-hidden="true" />
        <div className="home-hero-copy">
          <p className="home-eyebrow"><ShieldCheckIcon size={17} weight="fill" aria-hidden="true" /> 面向每个中国家庭的自主财富管理体系</p>
          <h1 id="home-hero-title">让专业财富规划，<br />走进每个中国家庭</h1>
          <p className="home-hero-lead">先管家底、责任与风险，再谈产品和收益。把复杂财富决策变成看得懂、能核验、可持续调整的家庭方案。</p>
          <div className="home-hero-actions">
            <AppLink className="home-primary-cta" to="/planning">建立家庭规划 <ArrowRightIcon size={19} aria-hidden="true" /></AppLink>
            <a className="home-secondary-cta" href="#china-method">了解中国方法</a>
          </div>
        </div>
      </section>

      <section className="home-assurance-strip" aria-label="体系原则">
        <div><strong>家庭视角</strong><span>从共同生活与共同责任出发</span></div>
        <div><strong>确定计算</strong><span>金额、比率和边界由规则引擎计算</span></div>
        <div><strong>适当性约束</strong><span>产品不能越过风险与资金用途边界</span></div>
        <div><strong>持续管理</strong><span>家庭变化后重算，历史版本可复核</span></div>
      </section>

      <section className="home-section home-china-method" id="china-method" aria-labelledby="china-method-heading">
        <div className="home-manifesto">
          <p>为什么要有中国自己的家庭财富方法</p>
          <h2 id="china-method-heading">中国家庭，不能直接套用一张海外比例表</h2>
          <div className="home-manifesto-copy">
            <p>网传的“标普家庭资产配置图”和固定资产分桶，可用于财商启蒙，却不足以承担真实家庭规划。中国家庭常同时面对住房资产集中、代际赡养、教育投入、社保养老金、经营性资产与跨境规则。</p>
            <p>过去以单次测评和产品销售为中心的方式，也难以应对收入结构、家庭成员和政策环境的持续变化。财富管理需要回到家庭资产负债表，先解决责任，再安排增长。</p>
          </div>
        </div>

        <div className="home-comparison" aria-label="通用海外模板与中国家庭财富方法比较">
          <header><span>比较维度</span><strong>通用海外模板</strong><strong>中国家庭财富方法</strong></header>
          {chineseDifferences.map((item) => (
            <article key={item.topic}>
              <h3>{item.topic}</h3>
              <p>{item.imported}</p>
              <p>{item.chinese}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="home-section home-theory" aria-labelledby="theory-heading">
        <header className="home-section-heading">
          <h2 id="theory-heading">一套从家庭事实出发的自主方法</h2>
          <p>系统不预测市场，也不替家庭做决定。它负责把事实、目标、约束和行动放进同一套账本。</p>
        </header>
        <div className="home-theory-grid">
          {theoryLayers.map((item) => {
            const Icon = item.icon;
            return (
              <article className={item.className} key={item.title}>
                <Icon size={30} weight="duotone" aria-hidden="true" />
                <h3>{item.title}</h3>
                <p>{item.detail}</p>
              </article>
            );
          })}
        </div>
        <p className="home-method-boundary">家庭财务健康诊断只服务于家庭规划，不用于征信或贷款定价；情景推演用于检验方案承受力，不构成市场预测或收益承诺。</p>
      </section>

      <section className="home-section home-account-system" aria-labelledby="account-system-heading">
        <header className="home-section-heading">
          <h2 id="account-system-heading">四类资金用途，顺序比比例更重要</h2>
          <p>固定比例不能替代家庭判断。资金先后经过生活、保障、目标和长期投资四道边界。</p>
        </header>
        <div className="home-account-ledger">
          {fourAccounts.map((account, index) => (
            <article key={account.name}>
              <span>{String(index + 1).padStart(2, "0")}</span>
              <h3>{account.name}</h3>
              <strong>{account.purpose}</strong>
              <p>{account.detail}</p>
            </article>
          ))}
        </div>
        <aside className="home-account-threshold">
          <CompassIcon size={28} weight="duotone" aria-hidden="true" />
          <div><strong>长期投资从哪里开始</strong><p>扣除日常周转、应急储备、全部负债与近期目标后，剩余资金才进入长期配置评估。启动线由家庭所在地区、收入稳定性与责任期限共同决定。</p></div>
          <AppLink to="/wealth/goals">查看资金边界 <ArrowRightIcon size={17} aria-hidden="true" /></AppLink>
        </aside>
      </section>

      <section className="home-section home-operating-system" aria-labelledby="operating-heading">
        <div className="home-operating-copy">
          <h2 id="operating-heading">财富规划不是一份静态报告</h2>
          <p>系统以家庭变化为触发条件，持续更新事实、资金边界与行动建议。每一步都有依据，每次调整都有版本。</p>
          <ol className="home-operating-path">
            {operatingPath.map(([title, detail]) => (
              <li key={title}><CheckCircleIcon size={20} weight="fill" aria-hidden="true" /><div><h3>{title}</h3><p>{detail}</p></div></li>
            ))}
          </ol>
          <AppLink className="home-text-link" to="/wealth">进入财富总览 <ArrowRightIcon size={17} aria-hidden="true" /></AppLink>
        </div>
        <div className="home-system-facts" aria-label="系统能力摘要">
          {systemFacts.map(([value, label], index) => {
            const icons = [UsersThreeIcon, ChartLineUpIcon, FileTextIcon, ShieldCheckIcon];
            const Icon = icons[index]!;
            return <article key={label}><Icon size={25} weight="duotone" aria-hidden="true" /><strong>{value}</strong><span>{label}</span></article>;
          })}
          <aside><BuildingsIcon size={32} weight="duotone" aria-hidden="true" /><div><strong>家庭与企业分账管理</strong><p>企业权益、分红、担保与依赖关系单独建账，避免与个人持仓重复计算。</p></div></aside>
        </div>
      </section>

      <section className="home-section customer-cases" id="customer-cases" aria-labelledby="cases-heading">
        <header className="home-section-heading">
          <h2 id="cases-heading">不同人生阶段，都能找到自己的起点</h2>
          <p>系统不设置财富门槛。收入结构和家庭责任不同，规划顺序也不同。</p>
        </header>
        <div className="case-grid">
          {cases.map((item) => (
            <article className="case-card" key={item.code}>
              <div className="case-image"><img src={item.image} alt={`${item.title}客户形象`} /></div>
              <div className="case-card-body">
                <span>{item.stage}</span>
                <h3>{item.title}</h3>
                <p>{item.profile}</p>
                <dl><dt>规划重点</dt><dd>{item.focus}</dd></dl>
                <button type="button" onClick={() => openCase(item.code)}>查看家庭方案 <ArrowRightIcon size={17} aria-hidden="true" /></button>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="home-final-cta">
        <HouseLineIcon size={42} weight="duotone" aria-hidden="true" />
        <div><h2>从今天的家庭账本，安排未来的生活</h2><p>准备家庭成员、资产负债和近一年收支，即可建立首份规划。</p></div>
        <AppLink to="/planning">开始建档 <ArrowRightIcon size={18} aria-hidden="true" /></AppLink>
      </section>
    </main>
  );
}
