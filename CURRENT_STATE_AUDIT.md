# Fortune-Copilot 当前状态审计

审计日期：2026-09-01
审计基线：`9cda28e`（`codex/fortune-copilot-v5-upgrade`，本轮 v0.15.0 升级前）
审计方法：阅读前后端、数据库模型与 27 个 Alembic 迁移、API、Agent/RAG/量化/画像/推荐实现、数据、测试、配置和既有文档，并运行 `make check`。

## 结论

原仓库不是一般性的聊天 Demo，而是一个已有较完整确定性财富规划链路的竞赛原型。基线质量门禁全部通过：后端 194 项测试、前端 65 项测试，Ruff、Mypy、ESLint、TypeScript 和生产构建均通过。README 对“合成数据、Mock 产品、未连接工行生产、LLM 不修改关键数字”的边界总体诚实。

但它尚未完全满足本次任务：原量化器只有多目标网格搜索，没有分别实现 MVO、Risk Parity、CVaR Optimization 和 Black–Litterman；原统一发布集只有 8 类 Persona，实验协议也不是 50+ 客户的 A/B/C/D 与消融；原 `DEMO_B` 不是指定的 38 岁、65 万年收入、180 万金融资产案例；前端缺少一页可在 3 分钟内讲清 CFS 全闭环的比赛主视图。

## 1. 当前已有功能

- 前端：React 19 + TypeScript + Vite，包含客户端、客户经理端、合规端和 Demo 管理页；有财富总览、家庭建档、目标责任、财富孪生、家企、CFS、养老、跨境、家庭延续、历史、Advisor、行动中心和风险端路由。
- 后端：FastAPI + SQLAlchemy + Alembic，SQLite 默认、PostgreSQL 可选；API 有对象授权、角色控制、请求体限制、限流、安全头和审计事件。
- 数据库：家庭、成员、收入、支出、资产、负债、保险、社保、目标、风险、行为、产品、快照、建议、报告、审核流、金融图谱、CFS、监控和家企实体均有持久模型。
- 财务引擎：资产负债恒等式、年度现金流、流动性、保障缺口、六项比率、CHFI 十维健康度和动态四账户。
- 规划：目标成本增长、FV/PV、月度所需储蓄、目标冲突、资金瀑布、应急/保障/负债/近期目标/长期资本顺序。
- 风险：能力、意愿、知识与行为综合；V5 CFS 还纳入家庭责任、流动性、企业暴露与期限。
- 组合：家庭、客户、产品三层适当性闸门；多目标网格搜索、规则降级、战术偏移和再平衡阈值。
- 产品：受控 Mock 产品库、产品快照、产品本体、资格检查、排名、组合映射和基金资料快照。
- 行为金融：规则库覆盖 11 类偏差、证据、评分、干预、冷静期与 A/B 分组。
- RAG：受控知识文档/切片、有效期与适用范围过滤、字符 n-gram 检索、Citation、注入隔离和最终声明治理。
- Agent：受限 Intake/Goal/Scenario/Product/Advisor 等 Agent，工具白名单、步骤台账、数值账本和 guardrail。
- 报告/工作流：八章规划书、HTML/PDF、数字账本、十项发布门禁、客户确认、客户经理与合规审核。
- 银行架构：真实银行能力只定义 fail-closed Port/Adapter；Mock 银行快照明确 `official_connection=false`。

## 2. 当前实际可运行功能

基线 `make check` 实测结果：

| 项目 | 结果 | 证据 |
| --- | --- | --- |
| Python lint | 通过 | Ruff 检查 app/tests/alembic |
| Python 类型 | 通过 | Mypy strict，256 个源文件 |
| 后端测试 | 194/194 通过 | 51.28 秒，本地 SQLite 内存库 |
| 前端 lint/类型 | 通过 | ESLint + `tsc -b` |
| 前端测试 | 65/65 通过 | 13 个测试文件 |
| 前端构建 | 通过 | Vite production build |
| Docker | 配置齐全 | 后端迁移、Seed、健康检查和前端 Nginx |

默认 `LLM_PROVIDER=mock` 时不需要 API Key 或外网；确定性分析、规划、组合、报告和测试可运行。V5 功能在 Docker Compose 中开启，但 `.env.example` 的本地开发默认关闭，需要显式开启对应开关。

## 3. README 声称但基线未完整实现

| 声称/容易形成的理解 | 基线事实 | 结论 |
| --- | --- | --- |
| “量化配置”可理解为标准组合优化套件 | 原 `optimizer.py` 是确定性网格搜索，不是独立 MVO/RP/CVaR/BL 比较 | 部分实现 |
| “CVaR”可理解为从组合损失分布计算 | 原实现主要对资产级 `cvar_loss` 做线性加权 | 金融口径不足 |
| “八 Persona 发布基准”可支撑比赛实验 | 只有 A-H 8 类，不满足不少于 50 画像 | 未满足本次要求 |
| RAG 评测完整 | 有引用覆盖和固定安全用例，但无正式 Recall@K、MRR、Faithfulness 全套 | 部分实现 |
| 适当性指标充分 | 有阻断率与探针，但无大规模 Suitability Violation Rate 基准 | 部分实现 |
| 主 Demo 对齐本次指定案例 | 原 `DEMO_B` 约 35 岁、年收入 36 万、金融资产约 35 万 | 不对齐 |
| 三端都可讲完整 CFS | 功能分散在多个页面，缺少 3 分钟单页主故事 | 展示不足 |

## 4. Bug 与运行风险

- 基线未发现阻断主链的已知测试失败。
- `httpx`/Starlette TestClient 有弃用警告，升级依赖前需处理。
- 生产构建中 ECharts 主题 chunk 约 597 kB，首屏取决于路由懒加载；弱网演示需预热。
- 本地 `.env.example` 的 V5 开关默认 false，而 Compose 为 true，直接按不同启动方式会看到不同功能面。
- 部分旧设计审计文档仍记录已修复的历史故障，答辩时不能把历史审计当当前运行状态。
- 原有大量 `__pycache__` 出现在工作目录扫描结果中，但被 `.gitignore` 排除；不会进入提交。

## 5. Mock / Hard-code

- 产品：`mock_products_v1.json` 是合成类型库，不是工行在售目录、报价或评级。
- 银行接口：IAM、客户、AML/CDD、产品、交易、CRM、投研均为 Mock 或 fail-closed 契约。
- LLM：默认 Mock 模板；外部 OpenAI-compatible Provider 只有在本地提供 Key 时启用。
- 规则：生活成本、阈值、市场情景、资产假设、行为规则和部分知识是版本化 `internal_demo` JSON。
- 实验：用户理解度和客户经理效率仅有协议，没有真实受试者/员工结果。
- 数据：A-H、Golden、比赛案例和 benchmark 全部是合成数据。

这些 Mock 大多有显式标识，属于合理竞赛边界；风险在于答辩口头表述不能省略“合成/快照/非实时”。

## 6. 技术债

- 服务文件体积偏大：`review_workflow.py`、`reporting/composer.py`、`demo_release.py` 等超过千行，变更回归成本高。
- 全局 CSS 体积较大，页面级样式边界不统一。
- V4/V5 兼容层增加认知负担，领域概念存在 Household/ClientProfile/FinancialGraph 多套投影。
- 原量化规则、产品规则和 CFS 规则之间存在重复字段，需要长期统一 Constraint Schema。
- RAG 是小型受控本地库，缺少离线索引构建、真实问句集和更大规模检索评估。
- 单进程限流与 Demo Header 只适合竞赛环境，生产需要网关、IdP、撤销列表和 SIEM。
- SQLite 适合本地演示；并发、备份、密钥、容灾和数据分区需生产化设计。

## 7. 金融逻辑错误或不足

- 原组合引擎没有协方差矩阵，不能称为 Mean-Variance Optimization。
- 原 `cvar_loss` 和 `max_drawdown` 是资产假设线性加权，不能替代组合收益路径上的尾部损失与峰谷回撤。
- 原产品 Schema 没有统一暴露 ExpectedReturn 字段；资产假设与产品资料需严格分离。
- 原成功概率更多出现在组合/情景输出，尚未形成每个目标统一维护的必填字段和同一资源协调结果。
- 固定网格步长会造成离散化误差；比赛中应解释“可复现优先”的取舍。
- 保障缺口是需要持牌人员复核的规划估算，不能直接等同应购买保额或产品金额。
- “保本的钱”容易被误听为产品承诺；界面和讲稿必须持续使用“目标匹配/低波动用途，不代表保本保收益”。

## 8. 工行杯展示风险

| 风险 | 等级 | 控制 |
| --- | --- | --- |
| 把 Port/Adapter 说成已接工行 | 高 | 所有页面与讲稿固定声明未连接生产 |
| 把 Mock 产品说成工行在售产品 | 高 | 产品卡显示 Demo，禁止真实营销用语 |
| 把 8/8、0% 等小样本结果外推 | 高 | 展示样本量、数据类型、版本和未测项 |
| 评委看不懂模块间因果关系 | 高 | 新增 `/competition` 单页闭环与 3 分钟脚本 |
| LLM 被质疑“拍脑袋给权重” | 高 | 独立量化 Trace + `llm_modified_quant_output=false` |
| 合规 Agent 只是提示词 | 高 | 产品逐条确定性规则、拒绝记录和 60 画像指标 |
| 过度堆砌 V5 专业模块 | 中 | 主讲上海家庭，家企/跨境/传承仅作扩展 |
| 网络/API Key 影响现场 | 中 | 默认离线 Mock、Docker 预热、无外网依赖 |

## 本轮升级决策

保留原 V5 架构和测试，增加隔离的 v0.15.0 竞赛能力层，而非重写：

- `backend/app/schemas/competition.py`：银行级统一领域模型与竞赛输出契约。
- `backend/app/services/competition/`：家庭 CFS、量化四方法、产品合规和 benchmark。
- `data/synthetic/competition_demo_shanghai_38_v1.json`：指定上海家庭。
- `data/benchmarks/competition_personas_v1.json`：60 个六类合成画像。
- `/api/v1/competition/demo`、`/api/v1/competition/benchmark`：可验证接口。
- `/competition`：3 分钟比赛主视图。
