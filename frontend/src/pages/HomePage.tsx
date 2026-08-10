import {
  ArrowRightIcon,
  CalculatorIcon,
  ChartPieSliceIcon,
  CheckCircleIcon,
  ClipboardTextIcon,
  FileTextIcon,
  FlagIcon,
  ShieldCheckIcon,
  UserCircleCheckIcon,
  WalletIcon,
} from "@phosphor-icons/react";
import { AppLink } from "../router/Link";
import { useRouter } from "../router/context";

const workflow = [
  { icon: UserCircleCheckIcon, title: "完成客户识别", detail: "填写家庭成员、职业、收入稳定性、资金来源、投资经验和风险承受情况。" },
  { icon: WalletIcon, title: "完成财务报表", detail: "归集资产、负债、年度收入和年度支出，统一金额口径。" },
  { icon: CalculatorIcon, title: "查看财务分析", detail: "计算六项关键比率，展示公式、代入过程、参考范围和具体解释。" },
  { icon: FlagIcon, title: "明确未来目标", detail: "记录理财目标、大额支出、计划日期和已经准备的资金。" },
  { icon: FileTextIcon, title: "生成八章规划书", detail: "形成结构统一、可以查看和保存的个人或家庭理财规划书。" },
];

const fourAccounts = [
  {
    name: "要花的钱",
    range: "数千元日常周转",
    detail: "只放信用卡结算和货币基金等随取资金，按家庭消费习惯调整。应急金可放到保本账户的稳健、便捷取用工具中，信用卡额度不计入资产。",
  },
  {
    name: "保命的钱",
    range: "年度数千元保障",
    detail: "用于医疗、重疾、意外和车险等风险转移。保险只消费、不投资；多数普通家庭从可持续的年度数千元预算开始，具体金额按全家责任和缺口测算。",
  },
  {
    name: "保本的钱",
    range: "可投资金融资产 5%—30%",
    detail: "用于应急、大额支出、养老金、教育金和债券等稳健安排；行情较好时取较低区间，较弱时提高。个人养老金年度1.2万元额度也可归入这里，但底层产品仍需核对风险和流动性。",
  },
  {
    name: "生钱的钱",
    range: "合格长期资金 70% 以上",
    detail: "只在净金融资金达到地区启动线且安全条件通过后，才以剩余长期资金为分母规划70%以上；优先宽基指数和分散工具，多数人不默认做个股、期指或新增房产投资。",
  },
];

const methodologySpine = [
  { code: "CHFH", title: "家庭财务健康", detail: "以家庭而非单个投资者为决策单位，先看现金流、责任、保障和目标。" },
  { code: "GRB", title: "目标、风险、行为", detail: "目标期限、客观风险能力和真实行为共同决定资金边界。" },
  { code: "四账户", title: "按用途分配", detail: "要花、保命、保本、生钱依次通过前置条件，不套固定象限比例。" },
  { code: "CHFI", title: "十维健康诊断", detail: "几何平均惩罚明显短板，强项不能抵消现金流或保障风险。" },
  { code: "HFDT", title: "家庭压力推演", detail: "用失业、医疗支出和市场下跌等情景检验家庭韧性。" },
];

const cases = [
  {
    code: "DEMO_A",
    image: "/personas/early-career.jpg",
    stage: "职业起步期",
    title: "单身职场新人",
    profile: "28 岁，收入正在上升，准备应急金与首次置业资金。",
    focus: "现金储备、结余能力、购房目标",
  },
  {
    code: "DEMO_B",
    image: "/personas/young-family.jpg",
    stage: "育儿成长期",
    title: "双收入三口之家",
    profile: "夫妻共同收入，有房贷和子女教育安排，需要平衡多项目标。",
    focus: "偿债压力、教育准备、资产集中",
  },
  {
    code: "DEMO_C",
    image: "/personas/pre-retirement.jpg",
    stage: "退休准备期",
    title: "临近退休夫妻",
    profile: "收入稳定但工作年限有限，关注退休现金流与医疗安排。",
    focus: "流动性、退休目标、保障安排",
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
      <section className="home-hero">
        <div className="home-hero-copy">
          <p className="home-eyebrow"><ShieldCheckIcon size={17} weight="fill" aria-hidden="true" /> 普慧金融，家庭财富规划服务</p>
          <h1>把家庭财务看清楚，<br />再决定下一步。</h1>
          <p className="home-hero-lead">金融术语不该挡住家庭做决定。从一张财务报表开始，把资产、负债、收支和目标变成看得懂的判断与行动。</p>
          <div className="home-hero-actions">
            <AppLink className="home-primary-cta" to="/planning">开始我的规划 <ArrowRightIcon size={19} aria-hidden="true" /></AppLink>
            <a className="home-secondary-cta" href="#customer-cases">先看客户案例</a>
          </div>
          <ul className="home-trust-list">
            <li><CheckCircleIcon size={18} weight="fill" aria-hidden="true" /> 金额和比率按统一规则计算</li>
            <li><CheckCircleIcon size={18} weight="fill" aria-hidden="true" /> 每个结论都能看到计算依据</li>
            <li><CheckCircleIcon size={18} weight="fill" aria-hidden="true" /> 规划内容可随家庭变化重新调整</li>
          </ul>
        </div>

        <div className="home-statement-preview" aria-label="家庭财务报表与分析示意">
          <header><span className="preview-brand-mark">智</span><div><strong>家庭财务概览</strong><small>数据更新至本次规划日</small></div><span>人民币</span></header>
          <div className="preview-net-worth"><span>家庭净资产</span><strong>¥ 2,341,400</strong><small>总资产 ¥3,800,000 · 总负债 ¥1,458,600</small></div>
          <div className="preview-chart-area">
            <div className="preview-donut" aria-hidden="true"><span>资产结构</span></div>
            <dl>
              <div><dt><i data-color="red" />房产</dt><dd>61%</dd></div>
              <div><dt><i data-color="gold" />金融资产</dt><dd>29%</dd></div>
              <div><dt><i data-color="gray" />其他资产</dt><dd>10%</dd></div>
            </dl>
          </div>
          <div className="preview-ratios">
            <div><span>流动比率</span><strong>6.2 个月</strong><small>处于常用参考范围</small></div>
            <div><span>负债比率</span><strong>38.4%</strong><small>需要结合房贷期限观察</small></div>
          </div>
          <footer><ChartPieSliceIcon size={18} weight="duotone" aria-hidden="true" /><span>已完成财务报表与六项比率分析</span></footer>
        </div>
      </section>

      <section className="home-value-strip" aria-label="服务特点">
        <div><strong>一张表</strong><span>完整归集家庭家底与年度收支</span></div>
        <div><strong>六项比率</strong><span>公式、代入、范围和解释全部可见</span></div>
        <div><strong>八章规划书</strong><span>从基础情况到行动建议结构统一</span></div>
      </section>

      <section className="home-section home-methodology" aria-labelledby="methodology-heading">
        <header className="home-section-heading">
          <span>一条完整决策主线</span>
          <h2 id="methodology-heading">先看家庭状态，再看产品</h2>
          <p>系统把研究框架压缩成五个连续环节。所有金额由确定性工具计算，人工智能负责理解、追问和解释。</p>
        </header>
        <ol className="home-method-spine">
          {methodologySpine.map((item, index) => (
            <li key={item.code}>
              <span>{String(index + 1).padStart(2, "0")}</span>
              <strong>{item.code}</strong>
              <div><h3>{item.title}</h3><p>{item.detail}</p></div>
            </li>
          ))}
        </ol>
        <p className="home-method-boundary">CHFI 只用于家庭诊断，不用于征信或贷款定价。HFDT 是压力测试，不是市场预测。任何具体产品仍需通过正式风险测评、适当性和交易时点检查。</p>
      </section>

      <section className="home-section home-workflow" aria-labelledby="workflow-heading">
        <header className="home-section-heading">
          <span>规划流程</span>
          <h2 id="workflow-heading">从家庭情况到行动建议，五步完成</h2>
          <p>每一步只处理当前需要的信息，已填写的内容会自动保留。</p>
        </header>
        <ol className="workflow-list">
          {workflow.map((item, index) => {
            const Icon = item.icon;
            return (
              <li key={item.title}>
                <span className="workflow-number">{String(index + 1).padStart(2, "0")}</span>
                <Icon size={27} weight="duotone" aria-hidden="true" />
                <div><h3>{item.title}</h3><p>{item.detail}</p></div>
              </li>
            );
          })}
        </ol>
      </section>

      <section className="home-section home-account-system" aria-labelledby="account-system-heading">
        <header className="home-section-heading">
          <span>从中国家庭生活出发</span>
          <h2 id="account-system-heading">先照顾家庭责任，再讨论长期增长</h2>
          <p>住房、养老、子女教育、父母赡养和收入稳定性都会改变资金安排。四类用途按每个家庭的情况动态计算，不套用固定比例。</p>
        </header>
        <div className="home-account-ledger">
          {fourAccounts.map((account, index) => (
            <article key={account.name}>
              <span>{String(index + 1).padStart(2, "0")}</span>
              <h3>{account.name}</h3>
              <strong>{account.range}</strong>
              <p>{account.detail}</p>
            </article>
          ))}
        </div>
        <aside className="home-account-threshold">
          <strong>什么时候开始长期投资？</strong>
          <p>现金类和合格金融资产扣除全部贷款与信用卡未付后，达到自己选择的30万至100万元起点，才评估正式长期配置。还没达到时，中青年家庭如有稳定结余、没有待处理高息债务，可用多余长期资金中不超过10%的小仓位学习宽基指数基金。</p>
          <AppLink to="/planning">测算我的启动线 <ArrowRightIcon size={17} aria-hidden="true" /></AppLink>
        </aside>
        <p className="home-growth-hurdle">长期增值以本金安全和购买力增长为目标，目标增幅至少高于地区最低工资的长期涨幅；该信号不是 CPI，也不是任何产品的收益保证。</p>
      </section>

      <section className="home-section ratio-intro" aria-labelledby="ratio-intro-heading">
        <div className="ratio-intro-copy">
          <span>看得懂的财务分析</span>
          <h2 id="ratio-intro-heading">不只给一个数字，还要说明为什么</h2>
          <p>比率由财务报表直接计算。每一项都展示计算方式、本次代入、常用参考范围和对家庭的实际影响。</p>
          <AppLink to="/planning">填写我的财务报表 <ArrowRightIcon size={17} aria-hidden="true" /></AppLink>
        </div>
        <div className="ratio-intro-ledger">
          {[
            ["流动比率", "家庭应急资金可覆盖的生活月数"],
            ["负债比率", "负债占总资产的比例"],
            ["结余比率", "年度结余占收入的比例"],
            ["财务负担率", "年度还贷占收入的比例"],
            ["投资与净资产比率", "可投资资产占净资产的比例"],
            ["房产与资产比率", "房产占总资产的比例"],
          ].map(([title, detail], index) => <div key={title}><span>{String(index + 1).padStart(2, "0")}</span><div><strong>{title}</strong><small>{detail}</small></div></div>)}
        </div>
      </section>

      <section className="home-section customer-cases" id="customer-cases" aria-labelledby="cases-heading">
        <header className="home-section-heading">
          <span>客户案例</span>
          <h2 id="cases-heading">不同家庭，关注重点也不同</h2>
          <p>选择一个案例，查看从财务报表到规划书的完整结果。</p>
        </header>
        <div className="case-grid">
          {cases.map((item) => (
            <article className="case-card" key={item.code}>
              <div className="case-image"><img src={item.image} alt={`${item.title}客户形象`} /><span>{item.stage}</span></div>
              <div className="case-card-body">
                <h3>{item.title}</h3>
                <p>{item.profile}</p>
                <dl><dt>重点关注</dt><dd>{item.focus}</dd></dl>
                <button type="button" onClick={() => openCase(item.code)}>查看这类家庭的分析 <ArrowRightIcon size={17} aria-hidden="true" /></button>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="home-final-cta">
        <ClipboardTextIcon size={38} weight="duotone" aria-hidden="true" />
        <div><span>准备好了吗？</span><h2>用一份财务报表，开始家庭财富规划</h2><p>通常需要准备资产余额、贷款余额、最近一年收入和支出。</p></div>
        <AppLink to="/planning">立即开始 <ArrowRightIcon size={18} aria-hidden="true" /></AppLink>
      </section>
    </main>
  );
}
