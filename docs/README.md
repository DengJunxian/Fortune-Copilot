# 技术文档导航

当前软件版本以根目录 [`VERSION`](../VERSION) 为准。开发与部署从以下入口开始；带阶段、日期或验收次数的旧报告保留为历史记录，不能代替当前 CI 与运行状态。

## 开发与维护

| 任务 | 入口 |
| --- | --- |
| 安装、启动、常用命令 | [项目 README](../README.md#快速启动) |
| Docker、数据库迁移、备份、排错 | [部署与维护](deployment.md) |
| Render / Sites 托管配置 | [托管说明](hosting_sites_render.md) |
| 检查版本和入口链接 | `make repo-check` |
| 静态检查、类型、单元测试、构建 | `make check` |
| 浏览器检查 | `make test-e2e` |
| 最新远端验证 | [GitHub Actions](https://github.com/DengJunxian/Fortune-Copilot/actions/workflows/ci.yml) |

## 核心技术

| 主题 | 文档 |
| --- | --- |
| 系统组成与五个引擎 | [V6 架构](v6/V6_ARCHITECTURE.md)、[系统架构](../SYSTEM_ARCHITECTURE.md) |
| 数据模型与字段 | [ER 图](er_diagram.md)、[数据字典](data_dictionary.md) |
| 确定性金融计算 | [金融引擎](financial_engine.md)、[规划引擎](planning_engine.md)、[组合引擎](portfolio_engine.md) |
| 家庭责任与长期资本 | [责任瀑布](methodology/four_domain_responsibility_waterfall.md)、[ELTC](architecture/v5_liability_streams_eltc.md) |
| 家庭状态与事件重算 | [持久家庭快照](architecture/v5_persistent_financial_twin.md) |
| 产品资格与证据 | [产品本体](architecture/v5_product_ontology.md)、[决策证据](governance/decision_evidence.md) |
| 受控 AI 与隐私 | [受限 Agent](architecture/v5_bounded_financial_agents.md)、[安全隐私](security_privacy.md) |
| 数据与功能边界 | [已知限制](known_limitations.md)、[公共资料治理](governance/authoritative_public_data.md) |

## 文件维护规则

- 源码、测试、迁移、版本化规则、合成种子、依赖清单和技术文档纳入 Git。
- `.env`、运行数据库、备份、依赖目录及缓存留在本地。
- `output/`、`tmp/` 和 `.codex-finalizer/` 保存本地产物，不是克隆后启动系统的依赖。
- `final_*`、阶段报告、比赛演示脚本及材料生成工具保留历史用途。普通开发使用 `make check`；`make final-acceptance` 会检查比赛成品，不能作为技术仓库完整性的判断标准。
- 修改发布版本时同步相关包与运行配置，执行 `make repo-check`。修改数据库结构必须添加迁移，并通过 SQLite 与 PostgreSQL CI。
