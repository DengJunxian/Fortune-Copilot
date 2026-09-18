# Fortune Copilot V6 Competition Edition 仓库审计

审计日期：2026-09-18  
审计范围：本地工作区、V5 Draft PR #1、CI 日志、前后端实现、测试、Demo、产品数据、文档与比赛 PPT 生成资产。

## 1. 审计结论

Fortune Copilot V5 已具备 V6 所需的核心财富管理底座。V6 不需要重写金融引擎，也不需要增加新的 Agent、预测模型或业务域。最有价值的改造方向是把现有确定性能力收束成一条更容易理解的家庭财富决策主线：

1. 先判断家庭是否安全；
2. 再计算长期可投资资本 ELTC；
3. 用 Goal + Risk + Behavior 形成家庭风险预算；
4. 在适当性边界内进行资产配置和产品候选筛选；
5. 家庭事实变化后重算，并保留证据与回放链。

现有实现与该主线高度兼容。主要问题不在能力缺失，而在首页、Dashboard、组合与产品页面的信息层级仍较分散，部分公开叙事继续以技术模块或“中国自主方法”开场，尚未把“有多少钱不等于有多少钱可以投资”放在最前面。

## 2. 仓库与 PR 状态

### 2.1 Git 状态

- 当前分支：`codex/fortune-copilot-v5-upgrade`
- 当前提交：`9cda28e feat: upgrade Fortune Copilot to V5`
- 基线分支：`main`，远端提交 `d6fbeee`
- 远端 PR：[#1 Upgrade Fortune Copilot to V5 wealth management system](https://github.com/DengJunxian/Fortune-Copilot/pull/1)
- PR 状态：Draft、Open、可合并，GitHub 标记为 `UNSTABLE`
- 本地版本：`0.15.0`；PR 提交版本为 `0.14.0`

本地工作区已有未提交的比赛版增量，包括 `/competition` 页面、Competition API、合成基准、竞赛文档草稿与版本更新。这些内容不是 PR #1 当前提交的一部分。后续实施必须在其上小步修改，不回滚或覆盖已有工作。

### 2.2 PR #1 CI

远端最近两次 backend job 均成功，最近两次 frontend job 均失败。失败集中在三个测试：

| 测试 | 远端症状 | 初步判断 |
| --- | --- | --- |
| `planningJourney.test.tsx` | 加载态尚未结束时未找到“规划名称” | 异步等待在 CI 性能下不稳定，页面本地可正常进入 |
| `WealthDashboardPage.test.tsx` | 未找到 `¥110万` | 旧数值断言与异步加载时序耦合 |
| `WealthTwinPage.test.tsx` | 未找到 `¥36万 → ¥25.2万` | 旧格式/异步刷新断言与新 UI 时序耦合 |

本地当前工作区实测：

- Backend：`197 passed`，1 条第三方弃用警告；
- Frontend：`66 passed`；
- Ruff：通过；
- mypy：通过，262 个源文件无错误；
- ESLint：通过；
- TypeScript typecheck：通过；
- Vite build：通过；
- Playwright 离线 smoke：`2 passed, 19 skipped`；19 项连接真实后端的场景按配置跳过，不计为通过；
- Build 非阻断警告：ECharts 相关 chunk 约 596.68 kB，超过 Vite 500 kB 提示线。

结论：远端 frontend 失败更像测试等待与旧断言问题，而不是当前工作区仍存在相同功能回归。Phase 1 应稳定这些测试并以新提交触发 GitHub CI，不删除测试。

## 3. 当前实现盘点

### 3.1 CHFH 与 Household 决策主体

当前家庭事实模型覆盖成员、收入、支出、资产、负债、保险、社保、目标、责任、企业暴露、行为和生命周期。`financial_graph`、`client_profile`、`liability_streams`、`family_enterprise` 与 `financial_twin` 都以 household 为聚合根，没有退回以 Portfolio 为唯一决策主体。

可直接复用：

- `backend/app/services/financial_graph/`
- `backend/app/services/client_profile/`
- `backend/app/services/liability/`
- `backend/app/services/family_enterprise/`
- `backend/app/services/financial_twin/`
- `frontend/src/pages/WealthProfilePage.tsx`
- `frontend/src/components/wealth/dashboard/NeedGraphView.tsx`

### 3.2 ELTC

`backend/app/services/eligible_capital/engine.py` 已按确定性规则计算：

可调度金融资源 − 日常周转 − 应急储备 − 高息债务 − 保障资金 − 短期刚性责任 − 已承诺目标资本 − 锁定制度资产 = ELTC。

算法还包含正式资格闸门：ELTC 为正、适当性资料有效、无待修复高息债务、可持续收入覆盖支出。原“增长启动线”已经降为沟通参考，不决定投资资格。这与 V6 原则一致。

前端已有 `EligibleCapitalBridge`，能够展示每一步扣减前、扣减额、扣减后、未覆盖金额、来源和原因。它应成为 Dashboard 和 Demo 的核心视觉，不需要再创建第二套 ELTC 系统。

需要修改：

- 统一中文名称为“长期可投资资本 ELTC”；
- 把 Dashboard 中的简单 ELTC 数字卡升级为清晰的资金 Bridge 与投资资格视图；
- 增加“为什么不是全部金融资产”的用户解释；
- 让金额用途行直接回答“哪些钱可以投资、哪些钱不能投资”。

### 3.3 GRB 家庭风险画像

现有 `client_profile` 已分别计算：

- `risk_capacity`：风险承担能力；
- `risk_willingness`：风险承受意愿；
- `behavior_limit`：行为风险上限。

`backend/app/services/risk_budget/engine.py` 使用三者最小值作为初始经济风险能力，再按流动性缺口、刚性责任、最短责任期限和现有经济暴露继续下调或封顶。该实现确保行为证据只能保持或降低风险预算，不能自动上调。

可直接复用：

- `backend/app/services/client_profile/engine.py`
- `backend/app/services/risk_budget/engine.py`
- `frontend/src/components/wealth/CFSRiskBudgetPanel.tsx`
- `frontend/src/pages/WealthProfilePage.tsx`

需要修改：

- 新增统一的 Family Risk Profile 展示，将 Capacity、Willingness、Behavior 与最终 Family Risk Budget 放在同一视图；
- 提供 R1–R5 的用户可读映射，同时保留现有金额化经济风险容量；
- 明确写出“行为只允许保持或下调”；
- 组合页面按 ELTC、Risk Budget、Goal、资产方向、解释的顺序展示。

### 3.4 动态四账户

现有首页和规划逻辑已经强调四账户是用途边界，不是固定比例。规则和文档明确禁止把 70% 或固定比例套到家庭总资产。该方法应保留，但对外命名需要统一为：要花的钱、保命的钱、保本的钱、生钱的钱，并解释它们是资金用途账户。

### 3.5 产品智能

V5 已存在一套产品本体、Eligibility、Ranking、CFS 产品映射和 Fund Advisory，不应新建第二套推荐引擎。

当前数据：

- Mock 产品类型：19 个；
- 公开证据核验的真实基金：8 个；
- 未提交 Competition Demo 产品：7 个合成类型。

8 个真实基金覆盖货币、短债、纯债、沪深 300、中证 500 和 3 个个人养老金 Y 类样本。尚未达到 V6 建议的约 30–50 个，也未充分覆盖红利/低波动、黄金、REITs 和更多养老目标产品。

现有产品卡已支持 `why_selected`、`why_not_other_candidates`、费用、流动性、风险、限制和利益冲突披露，符合 Explainable Recommendation 的主要要求。

需要修改：

- 在现有 Eligibility/Ranking 流程上增加真实计算的 Candidate Funnel 阶段计数；
- 将“为什么不是其他候选”改为基于被过滤候选的具体拒绝理由，避免泛化文案；
- 页面统一使用“当前家庭约束下的候选产品”；
- Phase 4 后再评估是否扩充真实目录。只有能保存公开来源、核验日期、用途、风险口径与渠道边界的产品才可加入；
- 始终明确 `public evidence ≠ live ICBC shelf`。

### 3.6 自然语言建档与追问

现有 `trust/intake.py` 提供确定性中文解析、脱敏预览、缺失字段和逐项确认。草稿不会直接写 canonical facts。现有示例可提取夫妻月收入、月供、配偶关系、子女教育阶段、年龄、教育期限和教育金额。

当前差距：

- 对用户给出的 V6 示例，“180 万元房贷”“孩子 4 岁”“国外读大学”“上海工作”等字段覆盖不足；
- 缺失字段列表按静态定义顺序返回，没有按对 ELTC、目标和负债计算的影响排序；
- Intake 位于 Trust 工作区，尚未成为家庭建档主流程的首要入口；
- 确认目前更新 IntakeDraft 状态，未形成清晰的“确认后写入正式 Household Facts”主路径。

后续应增强现有解析器和确认流程，不增加新的 Agent 或让 LLM 获得 canonical write 权限。

### 3.7 AI 解释层

现有架构已贯彻“AI 理解语言，金融引擎计算资金”：金额、比率、ELTC、风险预算、组合和产品资格均来自确定性工具。LLM/模板层只做解释、检索、追问与组织，失败时降级。

需要修改：

- 为 ELTC、GRB、组合和产品候选增加简洁/标准/专业三种解释模式；
- 所有解释引用结构化结果，不能重算或改写数字；
- 首页和 Demo 弱化 Agent、RAG、Monte Carlo 等实现词，把它们放入架构或展开详情。

### 3.8 持续财富管理与 Next Best Action

`financial_twin`、`monitoring` 和 `AdvisorActionCenter` 已支持家庭事件、重算、告警、行为干预、NO_ACTION_REQUIRED 与 do-not-sell 约束。Next Best Action 不是 Next Best Product，监控不会自动追涨、调仓或提高风险上限。

需要修改：

- Advisor 卡片统一展示 Why Now、What Changed、What Matters、Suggested Discussion、What Not To Sell；
- 客户端展示 Before → Event → After；
- Dashboard 只显示 1–3 个最重要的 Next Best Action；
- 统一 monitoring、advisor、dashboard 的术语。

### 3.9 合规与证据链

现有 Decision Evidence、Product Snapshot、rule/model version、input hash、audit event 与 replay 能力充分。Risk 页面目前仍偏工程工作台。V6 应将首屏收束为 Why This Advice、Suitability、Evidence、Replay，并把 hash、版本和 evidence IDs 放入展开详情。

### 3.10 首页、Dashboard 与 Demo

首页当前首屏已经强调家庭、责任和风险，但主标题仍是泛化的“让专业财富规划走进每个中国家庭”，没有在 30 秒内突出 ELTC 的差异化价值。后续页面包含较多方法论和系统能力，核心三问未形成最短路径。

Dashboard 已有“四件事”结构，但当前四项是安全、目标缺口、下一笔钱、是否重规划。ELTC 只是后续小卡，Goal Timeline 与完整 ELTC Bridge 没有进入首屏。因此需要重新排序，而不是重写 Dashboard。

现有 `/competition` 是未提交的一页式比赛总览，聚合了新的 Competition API、量化方法比较与 60 画像基准。它可以保留为技术/评测视图，但当前叙事重新突出 CFS、Agent、MVO、Risk Parity、CVaR 与 Black–Litterman，和 V6“禁止技术堆砌”的主线不一致。后续应降低其导航优先级或将内容改为家庭主剧情，不继续扩展第二套金融逻辑。

现有 PPT 为 14 页，生成脚本是 `scripts/build_competition_deck.mjs`，输出为 `output/presentations/wealthtwin_competition_deck.pptx`。脚本与验证工具可直接复用，后续按 V6 故事最小调整，不重建制作系统。

## 4. 应直接复用的 V5 能力

以下能力已经成立，V6 只调整信息架构、解释或展示：

- CHFH 家庭事实与财务健康框架；
- Household 聚合根与 Financial Graph；
- 动态四账户；
- Liability Streams 与 Goal Timeline；
- ELTC 确定性算法和资格闸门；
- GRB 三层画像与家庭经济风险预算；
- Portfolio Engine 与场景/压力约束；
- Product Ontology、Eligibility、Ranking、Fund Advisory；
- 自然语言 IntakeDraft 与逐项确认边界；
- Financial Twin、Monitoring 与 Next Best Action；
- Decision Evidence、Replay、Audit 与 Human Review；
- 家庭企业、退休、跨境、信托、公益等 V5 后端能力；
- 现有 DESIGN.md、tokens、AppShell、DashboardCard 与页面路由；
- 现有 Demo、PPT 生成和最终验收脚本。

## 5. 不应该修改的内容

- 不重写 ELTC、risk budget、portfolio 或 product eligibility 的核心算法，除非测试证明存在 bug；
- 不删除家庭企业、退休、跨境、信托、公益、Twin、Monitoring 或受限 Agent 能力；
- 不新增第二套产品推荐、家庭画像或组合引擎；
- 不让 LLM 决定金额、比率、风险等级、ELTC、配置、资格、收益率或成功概率；
- 不把四账户改成固定比例；
- 不把风险问卷当成最终风险等级；
- 不创建工行 Live 连接、实时货架、真实客户、交易或自动营销的假象；
- 不在没有实证时声称 AUM、转化率、效率或投诉指标改善；
- 不删除历史分支，不在 CI 未绿、文档未完成前合并 main。

## 6. V6 差距与优先级

### P0

1. 稳定远端 frontend tests，完成 CI 基线；
2. 统一定位、README 与首页首屏；
3. Dashboard 第一屏改为安全、目标、ELTC、Next Best Action；
4. ELTC Bridge 与资金投资资格视图；
5. Family Risk Profile；
6. 组合页面按资金资格和风险预算重新排序；
7. 3 分钟主 Demo 与核心文档。

### P1

1. Product Candidate Funnel；
2. Why Selected / Why Not Others 的真实拒绝理由；
3. Intake 示例字段覆盖、影响优先追问与主流程入口；
4. Advisor Why Now；
5. Compliance Why This Advice；
6. 三档解释模式。

### P2

1. 将公开核验产品目录从 8 个谨慎扩充到约 30–50 个；
2. PPT 视觉与讲述节奏进一步优化；
3. Fixed Ratio、Risk Questionnaire Only 轻量对照；
4. 非阻断的前端大 chunk 优化。

## 7. 预计影响文件

### Phase 1：Engineering Baseline

- `.github/workflows/ci.yml`
- `frontend/src/test/planningJourney.test.tsx`
- `frontend/src/test/WealthDashboardPage.test.tsx`
- `frontend/src/test/WealthTwinPage.test.tsx`
- `docs/v6/V6_CHANGELOG.md`

### Phase 2：Narrative & IA

- `README.md`
- `frontend/src/pages/HomePage.tsx`
- `frontend/src/pages/WealthDashboardPage.tsx`
- `frontend/src/components/layout/AppShell.tsx`
- `frontend/src/styles/global.css`
- `docs/v6/V6_PRODUCT_NARRATIVE.md`

### Phase 3：Core Wealth Experience

- `frontend/src/components/wealth/EligibleCapitalBridge.tsx`
- `frontend/src/components/wealth/CFSRiskBudgetPanel.tsx`
- `frontend/src/pages/WealthProfilePage.tsx`
- `frontend/src/pages/WealthCFSPage.tsx`
- `frontend/src/api/clientProfile.ts`
- `frontend/src/api/liability.ts`
- 相关 fixtures 与测试

### Phase 4：Product Intelligence

- `backend/app/services/product_ontology/engine.py`
- `backend/app/schemas/product_ontology.py`
- `frontend/src/api/productOntology.ts`
- `frontend/src/components/wealth/CFSProductCandidates.tsx`
- `data/products/verified_real_funds_v1.json`（仅在证据充分时）
- 相关 backend/frontend tests

### Phase 5：AI Experience

- `backend/app/services/trust/intake.py`
- `backend/app/schemas/trust.py`
- `frontend/src/components/trust/TrustWorkspace.tsx`
- `frontend/src/components/planning/PlanningJourney.tsx`
- `frontend/src/api/trust.ts`
- 相关 tests

### Phase 6：Advisor & Compliance

- `frontend/src/components/advisor/AdvisorActionCenter.tsx`
- `frontend/src/pages/RiskPage.tsx`
- `frontend/src/components/workflow/DecisionEvidencePanel.tsx`
- `frontend/src/styles/global.css`
- 相关 tests

### Phase 7：Competition Delivery

- `docs/v6/V6_ARCHITECTURE.md`
- `docs/v6/V6_PRODUCT_NARRATIVE.md`
- `docs/v6/V6_DEMO_SCRIPT.md`
- `docs/v6/V6_ACCEPTANCE.md`
- `docs/v6/V6_CHANGELOG.md`
- `docs/technical_whitepaper.md`
- `docs/demo_script_3min.md`
- `docs/defense_qa.md`
- `docs/icbc_business_value.md`
- `scripts/build_competition_deck.mjs`
- `output/presentations/wealthtwin_competition_deck.pptx`
- `scripts/final_delivery_check.py`

## 8. 实施约束与验收策略

后续每个 Phase 保持小步、可审查、可回滚：

1. 先复用现有 API 和组件，再考虑新增字段；
2. 关键数字继续由确定性算法输出；
3. 每个新 UI 数量和判断都有后端或 fixture 证据；
4. 每阶段运行相关单测、lint、typecheck 与 build；
5. Phase 7 再运行完整 backend、frontend、Playwright、PPT 生成与最终验收；
6. 只有在 CI 全绿、工作区无冲突、文档完整且 PR 不再是 Draft 时，才评估合并到 `main`。

## 9. Phase 0 决策

Phase 0 通过。V6 将采用“叙事收束 + 信息架构重排 + 已有能力产品化”的最小改造路径。核心算法保留，新增工作集中在用户可见的 ELTC、GRB、候选漏斗、确认式 Intake、Why Now、Why This Advice 与比赛交付材料。
