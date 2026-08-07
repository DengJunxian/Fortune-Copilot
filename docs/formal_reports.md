# 正式八章家庭财富规划书契约

阶段：提示词 11  
迁移：`0010_formal_reports`、`0011_report_uniqueness`、`0012_security_privacy_quality`  
实现：`backend/app/services/reporting`、`backend/app/api/v1/endpoints/reports.py`

## 1. 交付边界

正式规划书是家庭事实、确定性财务分析、动态四账户、组合适当性、数字孪生、行为金融、受控知识和人工审核链的不可变快照。语言模型只能理解、追问和解释；报告中的金额、比率、配置、概率、压力结果和行动金额均来自结构化工具账本。Mock 模式不调用外部模型、真实银行接口或运行时网络。

报告不承诺本金或收益，不把压力测试写成预测，不把历史表现写成未来保证；涉及配置、产品、保险、税务或其他重大决定时必须人工复核。`client_ready` 只表示报告已关联客户可见的审核状态，不代表签约、交易或法律电子签名。

## 2. 严格八章目录

一级目录由 Pydantic、数据库检查约束、HTML/PDF 渲染器和测试共同锁定，只能是：

1. 家庭基础情况
2. 理财目标
3. 大额支出计划
4. 理财假设
5. 家庭财务报表
6. 家庭财务比率分析
7. 投资规划建议
8. 免责声明

目录、附录、受控引用索引和“报告结束”适用边界都不是一级章节。第七章固定包含 `7.1`—`7.13`：四账户动态规划、日用与应急资金、债务管理、保险保障、养老与税务、目标规划、三套组合候选、数字孪生与压力测试、行为干预、原 Mock 产品适配、分期限行动、未来 12 个月行动日历和独立真实基金智能投顾补充。真实基金部分不改写前述金额或候选，只追加精确代码、份额、渠道证据、未分配原因和执行边界。

第六章逐项展示名称、公式、实际代入、分子、分母、结果、参考条件、来源和行动；比赛内部阈值明确标记 `internal_demo`。第八章集中记录来源、公式、模型、规则、Prompt、知识、产品目录、输入和审核流版本，以及模型边界、风险揭示和免责声明。

## 3. 结构化来源与一致性

`FormalReportDocument` 同时保存：

- `numeric_ledger`：每个关键数值的原始值、展示值、单位、来源路径和计算来源；只允许确定性工具、确定性仿真或确定性复盘日程；
- `citations` 与 `sourced_claims`：政策事实必须引用受控知识切片，包含机构、文档版本、生效／核验日期、段落、URI 和内容哈希；
- `versions`：报告、输入、公式、规划规则、组合规则、孪生结果、模型模板、Prompt、知识、原 Mock 产品目录、真实基金投顾目录和审核流版本；
- `consistency_checks`：严格八章、数字账本、事实引用、孪生有限值和行动状态平衡；
- `execution_metrics`：待办、完成、延期、不适用及完成率；
- `boundary_note`：每份报告的最终适用边界。

报告生成会复用既有确定性服务；如缺少兼容数字孪生结果，则以固定规则、100 条路径和 30 年期限完成本地可复现运行。受控 RAG 只读取本地版本化知识库。任何一致性检查需要人工处理时，报告显式标记 `needs_review`，不会静默补造事实。

## 4. 快照、行动与重算

`plan_reports` 的 `sequence`、`parent_report_id` 和 SHA-256 `report_hash` 组成不可变生成链。新生成、月度复盘、重大事件和行动状态变化都新增 Rn 快照；旧快照只切换 `is_current`，结构化正文和哈希不被覆盖。写请求携带预期报告序号或行动记录版本，陈旧写入返回 409。

行动状态为 `open`、`completed`、`deferred`、`not_applicable`。完成会记录时间；延期必须填写日期；延期和不适用必须填写原因。每次更新先写行动审计事件，再以 `action_status_change` 触发整份报告重算，因此规划书中的行动指标和持久化行动账本始终来自同一版本。

持续复盘有两条显式入口：`monthly_review` 与 `major_event`。二者都要求说明原因并创建新快照，不存在定时后台自动覆盖或自动交易。

## 5. 审核流与可见性

若家庭已有当前审核流，报告固定关联 `workflow_id` 和具体 `workflow_version_id`：

- 无审核流：`draft_requires_human_review`，使用“待人工复核”水印；客户可以查看自己生成的竞赛 Mock 草稿；
- 合规前审核流：`workflow_linked`，只供顾问、合规和管理员查看，客户读取、导出、生成关联报告或修改报告行动均返回 `report_not_ready_for_client`；
- 合规通过、客户确认、Active 或 Superseded：`client_ready`，客户和顾问读取同一份快照。

顾问复核和客户确认记录会在符合状态时关联新 `PlanReport`，但历史审核事实不会被改写。Stage 12 已增加签名 Bearer 短会话、家庭授权声明和报告 ID 对象授权；Header 角色只在 development／demo／test 兼容。生产仍必须由外部 IdP、MFA、机构层级和在线撤销补全登录治理。

## 6. API

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| GET | `/households/{id}/reports/current` | 读取当前正式报告 |
| POST | `/households/{id}/reports` | 一键生成新报告 |
| POST | `/households/{id}/reports/recalculate` | 月度或重大事件重算 |
| GET | `/households/{id}/reports/generation-chain` | 顾问／合规读取哈希链 |
| GET | `/households/{id}/report-actions` | 读取持久化行动账本 |
| POST | `/households/{id}/report-actions/{action_code}` | 更新行动并生成新报告 |
| GET | `/reports/{report_id}` | 读取指定不可变快照 |
| GET | `/reports/{report_id}/html` | 导出自包含 HTML |
| GET | `/reports/{report_id}/pdf` | 导出 PDF |
| POST | `/reports/{report_id}/quality-gate` | 由合规角色运行固定十项发布门禁 |
| POST | `/reports/{report_id}/publish` | 全部门禁通过后，携带二次确认与报告序号发布 |

导出响应包含报告版本、报告哈希和导出审计 ID。成功和失败都写审计事件；失败诊断只保存渲染阶段、异常类型、截断后的安全错误和报告版本，不保存敏感财务载荷。

## 7. HTML、PDF 与字体

HTML 内联样式且不含脚本、字体下载、CDN 或运行时资源；来源 URI 仅是可点击引用，不是渲染依赖。PDF 使用 ReportLab 和系统／开源字体：macOS 开发环境可使用系统中文字体，Docker 安装开源文泉驿正黑；仓库不分发字体文件。PDF 固定显示水印、报告版本、数据日、生成时间、页码和报告哈希。

稳定验收件位于：

- `output/reports/wealthtwin-demo_b-report-r1.html`
- `output/pdf/wealthtwin-demo_b-report-r1.pdf`

验收件只含合成家庭 B 数据并标记竞赛 Mock。生成诊断和逐页 PNG 位于 `tmp/pdfs/stage11-demo-b`，不是产品运行依赖。

## 8. 三端呈现

- 客户端：家庭规划书工作区负责一键生成、八章阅读、月度／重大事件重算和 HTML/PDF 下载；行动日历直接读取持久化状态。
- 顾问端：从当前家庭底稿查看报告状态、严格八章目录、版本账本和导出，不复制第二份报告数据。
- 风险端：展示生成链、父快照、报告／输入／规则／模型／Prompt／知识／产品／审核流版本、哈希和审计数量；人工勾选后运行十项门禁，只有全 pass 才启用二次确认发布。

UI 遵循渐进披露、原生表格和语义状态，不用营销卡片、收益色彩、倒计时或打卡奖励。详细设计审计见 `docs/design/formal_report_ui_audit.md`。

## 9. 验证

- 后端覆盖目录完整性、229 项关键数值追踪、引用覆盖、HTML 自包含、PDF 可打开、导出审计、行动三状态、月度／重大事件重算、乐观冲突、角色权限与合规前可见性。
- 前端覆盖客户端生成／重算／行动 R2、顾问目录与导出、风险生成链；Playwright 在真实 Compose 中验证 R1 → R2 和两段哈希链。
- PDF 通过 `pypdf`、`pdfinfo`、`pdffonts` 与 `pdftoppm` 验证；32 页均已渲染并逐页检查，无缺字、裁切或无法打开页面。

当前 PDF 不是 PDF/UA 或带数字签名的法律文档；正式签名、加密、归档保留和无障碍标签属于安全发布阶段，不在本阶段伪装完成。
