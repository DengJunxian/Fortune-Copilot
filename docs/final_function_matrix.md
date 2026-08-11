# Fortune Copilot 最终功能矩阵

状态定义：

- **已实现**：仓库内有运行代码、自动化测试和可复现入口；
- **Mock**：流程、契约和边界可运行，但数据、产品、机构连接或人工主体为合成/模拟；
- **计划**：生产或真实业务能力尚未实现，不得在演示中冒充完成。

## 家庭事实与确定性计算

| 能力 | 状态 | 实现与证据 |
| --- | --- | --- |
| 家庭成员、资产、负债、收入、支出、保单、目标、风险、授权 CRUD | 已实现 | `backend/app/api/v1/endpoints/domain.py`；`backend/tests/test_domain_api.py` |
| 金额 Decimal、统一版本、来源、确认、软删除和家庭边界 | 已实现 | `backend/app/models/domain.py`；`backend/tests/test_domain_data.py` |
| A-H 八类 Canonical Persona V2 | Mock | `data/synthetic/v5_personas/`；Golden Outcomes V2；`GET /api/v1/demo/manifest` |
| A/B/C 三家庭兼容对照 | Mock | 同一 A-H 数据集的 A/B/C 视图；三个唯一配置签名 |
| 信用卡额度不计入资产，未付余额计入负债 | 已实现 | 财务事实装载与标准答案；`backend/tests/test_financial_engine.py` |
| 五张财务底表与数据诊断 | 已实现 | `backend/app/services/financial/`；`GET .../financial-analysis` |
| 20 项独立财务指标 | 已实现 | `backend/app/services/financial/metrics.py`；标准答案回归 |
| 四类保障缺口 | 已实现 | `backend/app/services/financial/protection.py` |
| CPI、家庭 CPI、目标专项成本、最低工资辅助基准分开 | 已实现 | `backend/app/services/financial/purchasing_power.py`；信任基准 |
| 自然语言待确认录入 | 已实现 | `/trust/intake/drafts`；`backend/tests/test_trust.py` |
| 外部模型理解/解释 | Mock | 默认 `mock_template`；可选兼容 Provider 需环境变量 |

## V5 全生命周期财富操作链

| 能力 | 状态 | 实现与证据 |
| --- | --- | --- |
| Canonical Financial Graph 与 V4 projection parity | 已实现 | `services/financial_graph/`；账户、币种、用途、期限、所有权与精细资产可选录入 |
| 动态 Client Profile 与 14 类 Wealth Need | 已实现 | 画像、标签、完整度、风险审慎下限、需要优先级与专业复核边界 |
| Liability Streams、责任日历与 ELTC 七步桥 | 已实现 | 刚性责任不消失；锁定资产不进入短期责任；HCI/GCI/IAI 分开 |
| Persistent Financial Twin 与生活事件账本 | 已实现 | 事件确认、哈希幂等、新快照、差异账本与历史回放 |
| Family–Enterprise Twin | 已实现 | 企业股权、估值、现金流、担保、质押、依赖度与家庭风险隔离 |
| CFS Composer、联合风险预算与 Wealth Orchestrator | 已实现 | Need/Liability/Risk Budget first；`NO_ACTION_REQUIRED` 为正式结果 |
| Buy-side Product Ontology、Eligibility 与 Ranking | 已实现 | 0—N 候选、过期阻断、费用与冲突披露；渠道激励不得提权 |
| Decision Evidence V2 与冻结回放 | 已实现 | 14 域证据包、决策材料哈希；最新产品变化不改写历史结论 |
| 养老、币种、信托传承与公益 Specialized CFS | 已实现 | 只识别需要、缺口和资料；法律／税务／外汇／信托结论走专业转介 |
| Continuous Monitoring、行为观察与 NBA | 已实现 | 11 类策略、`do_not_sell`、冷静期、专业转介与 `NO_ACTION_REQUIRED` |
| 六类受限工具型金融 Agent | 已实现 | deny-by-default 工具 Allowlist；自然语言只生成草稿／解释，不取得金融决策权 |
| HCI/GCI/IAI Calibration Registry | 已实现 | controlled demo／empirical／bank-authorized 分层；缺失验证参数时 `needs_review` |
| Continuous Wealth 与 Action Center 前端 | 已实现 | `/wealth/*`、`/advisor/actions`；11 路由通过 1440/1024/768/390 浏览器回归 |

## 目标、四账户、组合与孪生

| 能力 | 状态 | 实现与证据 |
| --- | --- | --- |
| 六阶段生命周期识别与人工反事实覆盖 | 已实现 | `backend/app/services/planning/lifecycle.py` |
| 目标未来金额、现值、缺口、月/年投入 | 已实现 | `backend/app/services/planning/goals.py`；独立标准答案 |
| 动态四账户七步瀑布 | 已实现 | `backend/app/services/planning/waterfall.py` |
| 三尺与五硬一软 | 已实现 | Planning API 元数据与约束证据 |
| 70% 仅用于有条件长期可规划资源 | 已实现 | `backend/tests/test_planning.py`；主 Demo B 长期新增 0 元 |
| 19 项产品目录 | Mock | `data/products/mock_products_v1.json`，逐项风险/期限/流动性/保证边界 |
| 稳健/基准/进取三候选优化与规则降级 | 已实现 | `backend/app/services/portfolio/`；`backend/tests/test_portfolio.py` |
| 家庭/客户/产品三道适当性闸门 | 已实现 | 五类违规请求均拒绝并写审计 |
| 实盘交易、下单和调仓执行 | 计划 | 当前只生成教育性/待审核方案；无交易接口 |
| 逐月家庭财富数字孪生 | 已实现 | `backend/app/services/twin/`；分阶段运行/取消/导出 |
| 固定 seed 相关 Monte Carlo 与 P10–P90 | 已实现 | `backend/tests/test_twin.py`；100 路径主 Demo |
| 19 个可组合压力场景 | 已实现 | `data/rules/twin_simulation_v1.json` |
| 实时行情、生产级资产收益模型 | 计划 | 当前参数是版本化离线情景假设，不是预测 |

## 行为、可信 AI 与治理

| 能力 | 状态 | 实现与证据 |
| --- | --- | --- |
| 七维问卷与六项可退出行为实验 | 已实现 | `backend/app/services/behavior/`；`backend/tests/test_behavior.py` |
| 双画像与行为不得上调客观风险能力 | 已实现 | 三条冲突规则、审慎最低等级 |
| 十一类偏差证据与十二类干预 | 已实现 | 24/48 小时冷静期、状态和审计 |
| A/B 实验分配与指标落账 | Mock | 只聚合合成/授权测试；不代表真实效果 |
| 受控 RAG（9 文档/16 切片） | Mock | 本地政策知识，日期/范围/注入过滤；需人工更新 |
| 17 类家庭关系图谱 | 已实现 | `backend/app/services/trust/graph.py` |
| 九智能体固定状态机 | 已实现 | `backend/app/services/trust/orchestrator.py` |
| 数字/政策/产品/提示注入终检 | 已实现 | `backend/app/services/trust/governance.py` |
| DeepSeek/OpenAI 兼容外部 Provider | Mock | 代码可配置但默认无密钥、无网络；字段白名单与降级 |
| 实时政策自动抓取与自动生效 | 计划 | 当前只接受人工核验、版本化本地知识 |

## 三端、报告、安全与发布

| 能力 | 状态 | 实现与证据 |
| --- | --- | --- |
| 客户端 13 步数据旅程/12 项界面任务 | 已实现 | `/client`；`backend/tests/test_client_experience.py`；Playwright 键盘与移动端回归 |
| 客户经理工作台 | 已实现 | `/advisor`；队列、底稿、三方案、版本和复盘 |
| 风险合规工作台 | 已实现 | `/risk`；十类控制、门禁、投诉和审计包 |
| 四角色模拟 RBAC | Mock | client/advisor/compliance/admin；顶栏模拟账号 |
| 生产 SSO、组织树、职责分离审批 | 计划 | Demo Header 在 production 禁用；机构接入未实现 |
| 八状态不可跳步方案链 | 已实现 | `backend/app/services/review_workflow.py` |
| 客户只读合规后裁剪版本 | 已实现 | 服务端资源门禁；`backend/tests/test_client_experience.py` |
| 客户演示确认 | Mock | 只存姓名哈希/脱敏提示，不是法律电子签名 |
| 严格八章正式规划书 | 已实现 | `backend/app/services/reporting/`；结构测试 |
| 229 项数字账本与受控引用 | 已实现 | 报告版本链、输入/规则/模型/知识/产品/流程版本 |
| 自包含 HTML/PDF | 已实现 | `output/reports/`、`output/pdf/`；导出测试 |
| 八类银行数据适配器 | Mock | 账户、信用卡、房贷、理财/信托、基金/证券、保险、养老金、现金流 |
| 真实工行 API、账户和产品接入 | 计划 | 未实现，演示不得声称真实连接 |
| 短会话、对象授权、二次确认、限流、安全头 | 已实现 | `backend/app/core/`；安全测试 |
| 隐私导出、授权撤回、逻辑擦除、人工复核 | 已实现 | `/privacy/...`；留痕与对象权限 |
| 8 类对抗评测与 10 项发布门禁 | 已实现 | `/security/dashboard`；发布前不可绕过 |

## Demo、部署与比赛材料

| 能力 | 状态 | 实现与证据 |
| --- | --- | --- |
| 十阶段一键主 Demo | 已实现 | `/demo`；运行持久化、进度、恢复 |
| A-H V5 Release Benchmark V2 | 已实现 | 8/8 Persona、9/9 指标、无效告警率 0、冻结决策回放 |
| 创始人融资事件 14 阶段故事 | 已实现 | 初始／融资／确认快照互异，完成画像、需要、风险预算、CFS、审核与客户确认 |
| A/B/C 三家庭唯一配置对照 | 已实现 | 兼容 V4 现场剧情；3 个唯一签名，`fixed_ratio_model=false` |
| 无外部服务离线主链 | 已实现 | `mock_mode=true`、外部调用 0、Compose 黑盒验收 |
| Docker Compose、SQLite、可选 PostgreSQL | 已实现 | `docker-compose.yml`；默认 SQLite，Postgres 显式 profile |
| 合成数据备份与隔离恢复 | 已实现 | `make backup-demo` / `make restore-demo` |
| README、白皮书、三分钟脚本、答辩库、比赛 PPT | 已实现 | `README.md`、`docs/technical_whitepaper.md`、`docs/demo_script_3min.md`、`docs/defense_qa.md`、`output/presentations/` |
| 真实客户研究、业务效果和生产 SLA | 计划 | 只完成实验协议与工程性能测试 |

## 状态结论

比赛版已经形成可运行、可解释、可审计的离线 Mock 闭环；真实工行数据/接口、真实产品、生产身份、交易执行、法律签署、监管报送和真实业务效果仍属于计划项。任何对外材料必须保留这一边界。
