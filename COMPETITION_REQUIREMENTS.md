# 工行杯竞赛需求与验收口径

版本：v1.0（2026-09-01）

## 产品命题

Fortune-Copilot 定位为“面向商业银行 CFS 的全生命周期 AI 财富管理系统”。核心对象是家庭财务健康与人生目标，不是单只基金，也不是无约束聊天机器人。

## 需求矩阵

| # | 能力 | 最低验收标准 | 仓库证据 |
| --- | --- | --- | --- |
| 1 | 全仓审计 | 源码、DB、API、Agent、RAG、算法、测试、配置、数据、文档均核验 | `CURRENT_STATE_AUDIT.md` |
| 2 | 银行级领域模型 | 覆盖 Personal/Family/Income/Expense/Asset/Liability/Insurance/CashFlow/Risk/Behavior/Goal/Portfolio/Holding | `schemas/competition.py` |
| 3 | 家庭资产负债表 | 11 项自动指标、恒等式、前端可视化 | `competition/engine.py`、`/competition` |
| 4 | 动态四账户 | 不含固定 10/20/30/40；金额和驱动因素可解释 | `build_dynamic_wealth_accounts` |
| 5 | Goal Planning | FV、Required Saving、Gap、Probability、资源协调 | `build_goal_plans` |
| 6 | Risk Budget | Capacity/Tolerance/Requirement 分离，Requirement 不抬高上限 | `build_risk_budget` |
| 7 | Quant Engine | MVO、Risk Parity、CVaR、Black–Litterman；硬约束与 Trace | `competition/quant.py` |
| 8 | 产品匹配 | Allocation→Filter→Suitability→Rank→Construct | `build_product_pipeline` |
| 9 | Compliance Agent | 7 类规则；批准组合违规率可计算 | `_product_check` |
| 10 | 行为金融 | 6 类偏差，逐条证据、风险、干预 | `detect_behavioral_biases` |
| 11 | Financial RAG | 受控知识、Citation、检索/声明评估口径 | `trust/knowledge.py`、benchmark |
| 12 | Advisor Agent | 汇总八类输出，不修改量化权重 | `advisor_summary`、审计字段 |
| 13 | RM Copilot | 360、问题、目标、持仓、机会、NBA、沟通、人工介入 | `/competition` RM 区 |
| 14 | 统一实验 | ≥50 画像，六类客群，A/B/C/D 协议，12 项指标 | 60 画像 + benchmark 脚本 |
| 15 | 消融 | w/o RAG/Compliance/Behavior/Goal/Quant | benchmark `ablations` |
| 16 | 工行业务三端 | 客户端、RM 端、管理/合规端；无真实连接宣称 | 现有三端 + 集成设计 |
| 17 | 指定 Demo | 38 岁、上海、已婚一孩、65 万收入、房贷、180 万金融资产 | competition demo JSON |
| 18 | 3 分钟 UI | 一页可读完整闭环；核心数字首屏可见 | `/competition` |
| 19 | 工程质量 | unit/integration/evaluation/seed/README/Docker/env；无 Key | `make check`、`.env.example` |
| 20 | 文档与就绪报告 | 11 份指定根目录文档 | 本轮交付 |

## 竞赛声明红线

- 不得声称与中国工商银行生产系统、客户、员工、产品或投研系统已连接。
- 不得把 Mock 产品、公开快照或内部规则称为实时工行数据。
- 不得把合成 benchmark 当成真实客户效果、收益或经营提升。
- 不得填写未运行的通用 LLM、专家评分或真实用户实验结果。
- 不得把资产类别权重说成 LLM 生成；权重必须来自量化模块。
- 不得把“保本与目标匹配账户”说成产品保本保收益。

## 现场验收顺序

1. `make check`：代码质量、单元/集成和构建。
2. `make competition-benchmark`：60 画像和消融结果。
3. `docker compose up --build`：离线 Demo。
4. 打开 `/competition`：上海家庭全链路。
5. 查看 `/risk`：治理、适当性、审计与未连接边界。
