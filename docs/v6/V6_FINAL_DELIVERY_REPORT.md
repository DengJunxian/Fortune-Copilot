# Fortune Copilot V6 Final Delivery Report

## 1. Changed

Fortune Copilot V6 Competition Edition 在 V5 基础上完成了最小必要收束：

- 首页统一为“家庭约束驱动型可信智能投顾”，先讲家庭责任与长期可投资资本，再讲技术；
- Wealth Dashboard 第一屏依次回答家庭安全、重要目标、ELTC 与 Next Best Action；
- 增强既有 ELTC Bridge，并增加资金投资资格、三档解释模式与“为什么不是全部金融资产”的说明；
- 将 GRB 产品化为 Capacity、Willingness、Behavior 与 Family Risk Budget 四层视图；
- 复用既有产品引擎生成真实 Product Candidate Funnel、Why Selected 与 Why Not Others；
- 增强受限自然语言建档、影响优先追问与待确认事实界面；
- Advisor Action Center 改为 Why Now / What Changed / What Matters / Suggested Discussion / What Not To Sell；
- 合规首屏收束为 Why This Advice、Suitability、Evidence 与 Replay；
- 重写比赛叙事、三分钟 Demo、五引擎架构、答辩材料、工行业务价值与现有 PPT 生成脚本。

## 2. Preserved

V6 保留了 V5 的核心财富管理口径和专业能力：

- 决策主体仍是 Household，家庭责任与财务安全先于投资；
- CHFH、动态四账户、ELTC、GRB 与 Continuous Wealth Management 均保留；
- 行为证据只能保持或降低风险预算，不能自动上调；
- 关键金额、比例、风险等级、配置和适当性仍由确定性算法、规则或受控数学模型产生；
- Product Ontology、Eligibility、Ranking、Fund Advisory、Financial Twin、Monitoring、RAG、Agent 与审计回放没有被另起一套系统替代；
- 退休、家庭企业、跨境、信托、公益等既有专门能力仍在，只降低了比赛主线中的展示优先级。

## 3. Product Improvements

产品主线现在围绕三个家庭问题展开：我家现在安全吗、我到底有多少钱可以长期投资、这些钱应该怎么配置。评委能够沿同一家庭看到家庭事实进入 CHFH，责任资金从可调度资源中逐层扣除形成 ELTC，再由 GRB 约束配置与产品候选；家庭事件发生后，系统展示 Before → Event → After 并重新规划。

产品输出不再把“有金融资产”直接等同于“可以投资”。资金投资资格视图明确指出应急、周转、保障与近期目标资金为什么不能承担长期市场波动。产品推荐也统一表述为“当前家庭约束下的候选产品”，避免“最佳基金”和销售导向语言。

## 4. AI Improvements

自然语言建档可从比赛家庭描述中提取配偶、税后共同收入、房贷、子女年龄、生命周期、所在地与海外教育意图，并按对计算的影响提出少量追问。所有提取结果先进入待确认草稿；未确认内容不能静默覆盖 canonical Household Facts。

AI 解释层提供简洁、标准、专业三档表达，但复述的是确定性 ELTC、风险预算和产品证据。AI 没有获得金额、风险等级、资产权重、产品资格或成功概率的决定权。

## 5. ICBC Competition Alignment

Fortune Copilot 被明确定位为连接家庭需求与银行财富产品和服务的“家庭财富决策智能层”，而不是替代工行现有产品体系：

- Customer：降低家庭财富管理的理解与行动门槛；
- Advisor：减少资料整理、方案准备和重复解释；
- Bank：支持从单次产品触达延伸到持续家庭财富经营；
- Compliance：让方案可解释、可复核、可追踪。

仓库没有把情景测算写成已观察到的 AUM、转化率、顾问效率或投诉改善，也没有声称存在真实工行客户、实时货架或生产连接。

## 6. Tests

2026-09-18 最终本地发布验证的实际结果：

- Backend Pytest：**198 passed**，一条 Starlette 上游弃用警告；
- Ruff：**passed**；
- Mypy：**passed，262 source files**；
- Frontend Vitest：**66 passed / 14 files**；
- ESLint：**passed**；
- TypeScript：**passed**；
- Vite build：**passed**，保留 `chartTheme` 596.68 kB 分包体积警告；
- Playwright：**21 passed**，使用迁移、播种后的 SQLite、Mock LLM 和 production preview，无跳过；
- Competition benchmark：**60 个 Synthetic 画像完成**，B/C/D 为仓库内确定性离线基线，A 通用 LLM 保持未测量；
- PPT finalizer：**passed**，15 页全部渲染并逐页检查。

本机 Docker/Colima daemon 不可用，因此本轮没有把 Docker Compose 记为通过。浏览器联调改为直接启动同一后端与前端预览栈完成。

## 7. Known Limitations

- 家庭与 Persona 数据为 Synthetic，不是真实工行客户；
- 产品目录为 8 个 Public Verified 样本，不代表实时工行可售货架；未在缺少官方证据时勉强扩充到 30–50 个；
- 银行、模型与部分外围接口为 Mock；没有 Live ICBC integration；
- 不提供开户、交易、自动销售或收益/本金承诺；
- 轻量验证只用于说明规则差异和工程回归，不代表真实客户效果、商业收益、生产 SLA 或投资业绩；
- 前端仍有一个可继续优化的图表分包体积警告。

## 8. Demo Path

主 Demo 使用一个上海三口之家，控制在约三分钟：

1. `/planning`：输入一句自然语言，核对待确认家庭信息；
2. `/wealth`：看家庭安全、目标与 Next Best Action；
3. `/wealth/cfs`：重点讲 ELTC Bridge、资金投资资格与 GRB；
4. `/wealth/cfs`：展示算法产生的 Product Candidate Funnel 与选择/排除理由；
5. `/wealth/twin`：触发家庭事件，展示 Before → Event → After；
6. `/advisor/actions`：展示 Why Now 与 What Not To Sell；
7. `/risk`：以 Why This Advice、Suitability、Evidence 与 Replay 收束。

完整口播见 `docs/v6/V6_DEMO_SCRIPT.md`，比赛演示文稿由 `scripts/build_competition_deck.mjs` 生成。

## 9. Repository State

- Source branch：`codex/fortune-copilot-v5-upgrade`；
- Release-candidate commit：`faffdb8`（最后一个运行时代码/测试修复提交）；
- Pull request：[PR #1](https://github.com/DengJunxian/Fortune-Copilot/pull/1)，记录本节时为 Draft、Open、MERGEABLE；
- Remote CI：GitHub Actions run `35299965812` 的 Backend 与 Frontend jobs 均通过；
- Tag：未创建；
- Working tree：交付提交前为 clean；最终 PPT 为可再生构建产物，按仓库规则保存在被忽略的 `output/`，生成脚本已提交。

本节记录的是最终报告元数据提交前的可验证 release-candidate 状态。PR 是否转为 Ready、是否合并以及合并提交，以 GitHub 上的最终状态和交付回复为准；不在文档中预写尚未发生的结果。
