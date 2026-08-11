# V5 Decision Evidence V2 与 CFS 审批证据

## 范围

E08 把客户画像、财富需求、责任流、ELTC、家庭风险预算、家企风险、CFS、产品快照、适当性、客户经理复核和客户确认冻结在同一份证据包中。它复用现有 `PlanWorkflowVersion`、`AdvisorReview`、`CustomerConfirmation`、`Recommendation` 和 `PlanReport`，不建立第二套审批流。

迁移为 `0023_v5_decision_evidence_v2`。Recommendation 与 PlanReport 新增八个可索引定位字段：

- `client_profile_version`
- `wealth_need_set_hash`
- `liability_version`
- `twin_snapshot_version`
- `enterprise_snapshot_version`
- `cfs_solution_id`
- `calibration_version`
- `monitoring_trigger_id`

PlanReport 新增 `decision_evidence JSON`；大对象仍留在 JSON，检索键保持为普通索引列。

## Schema

`DecisionEvidenceV2` 固定包含 14 个证据域：

1. `household_input`
2. `financial_graph`
3. `client_profile`
4. `wealth_needs`
5. `liability`
6. `ELTC`
7. `risk_budget`
8. `enterprise`
9. `CFS`
10. `product_snapshot`
11. `suitability`
12. `calibration`
13. `advisor`
14. `client_confirmation`

每个域都带 `status`、`version`、`source_record_ids`、`decision_inputs` 和只读 `snapshot`。尚未产生的数据显式使用 `not_available`，未启用的后续能力使用 `not_applicable`，不会伪造版本。

审批流运行“确定性计算”时一次性冻结外部决策上下文，并在 recommendation snapshot 中加入：

- `cfs_solution_id`
- `cfs_version`
- `selected_components`
- `professional_referrals`
- `decision_evidence`

后续适当性、客户经理复核、合规结论和客户确认只增量更新相应证据域；CFS 与产品快照保持原值。退回草稿后必须重新计算，新版本不会覆盖旧版本的证据包。

## 确定性哈希

哈希输入只包含证据版本、状态和 `decision_inputs`。以下内容不进入哈希：

- `generated_at`
- request id
- decision record id
- 展示标题、标签、解释、理由和 `display_only_text`

需求、产品快照、风险预算、客户画像或任何真正改变决定的版本／编码输入变化都会改变哈希。客户沟通稿原文不直接进入证据哈希，但其 SHA-256 内容哈希会进入客户经理证据域，因此影响合规决定的文案变化仍可追踪。

## 历史回放

- `GET /api/v1/decisions/{decision_id}/evidence`
- `POST /api/v1/decisions/{decision_id}/replay`

`decision_id` 可使用 Recommendation、PlanReport、PlanWorkflowVersion id，或当前 workflow id。接口只允许 advisor、compliance、admin，并继续执行家庭对象授权。

Replay 从已持久化的 Decision Evidence V2 重新规范化并计算哈希，不查询当前产品表，不调用 CFS 重算，也不修改历史。响应固定返回 `latest_product_data_used=false`、存储哈希、回放哈希、是否一致及实际使用的 14 个快照版本。每次 POST 回放写入 AuditEvent。

旧 Recommendation／PlanReport 的 V1 证据仍可读取：服务会在响应时映射为带明确 `not_bound` 状态的 V2 包，不回写或伪造当时不存在的 V5 快照。旧审批草稿若从未运行 E08 计算，原合规页面仍可用，但 Evidence V2 区域保持缺省。

## 前端

合规工作台新增“这次决定，当时依据了什么”：先显示决策校验码、CFS 绑定和产品快照数量，再用两列证据账本呈现 14 个域的冻结状态、版本和来源数。技术 JSON 不直接堆给审核人；需要验证时可点击“使用冻结快照回放”，结果同时用文字和状态标记反馈。

界面延续既有银行红、暖白、细分线和数据字体，不引入新组件库。移动端把三项摘要和两列证据账本收为单列，并保留完整版本文本的 title 提示与键盘焦点。

## 验证

- 相同决策输入在生成时间、request id 和展示文案变化后保持同一哈希；财富需求、产品快照、风险预算或客户画像变化会使哈希改变。
- 自动化场景先冻结 CFS 和 8 份产品快照，再修改数据库中的最新产品快照；Replay 仍返回存储哈希一致和 `latest_product_data_used=false`。
- SQLite 已验证 `0022 → 0023 → 0022` 往返，Alembic `check` 在 `0023 (head)` 返回零待迁移操作。
- 全量质量门禁为 158 项 Pytest、54 项 Vitest，加上 Ruff、Mypy、ESLint、TypeScript 和生产构建。
- 真实 Compose 的 1440×1100 与 390×844 浏览器验收覆盖证据读取、回放 200、14 域账本、CFS／产品摘要、移动端收缩和 0 error／0 warning。

## 边界

- 回放证明“存储证据与当时哈希一致”，不等于证明产品现在仍可售。
- 产品公开资料仍不是实时银行交易主数据；执行前必须完成当日渠道、费用、限额和适当性核验。
- `calibration-v1-not-enabled` 是功能关闭时的明确状态；E13 启用后会冻结注册表版本、三种模式可用性与数据集来源，且不可把受控演示冒充经验校准或银行授权。
- `monitoring_trigger_id` 为 E10 预留可检索键；没有监控触发时保持空值。
