# V4 / V5 兼容契约

## 不变量

关闭全部 V5 flags 时，以下 V4 能力继续使用原 loader、原规则与原响应 Schema：

- `POST /api/v1/wealth-planning/cases`
- `GET /api/v1/households/{id}/planning`
- `GET /api/v1/households/{id}/portfolio`
- Twin、Behavior、Advisor Workflow、Formal Report 与 Fund Advisory

V5 不删除 V4 表，不重写 `load_household_facts()`，也不让前端重新计算后端金融结果。

## Compatibility projection

```text
FinancialEntity + FinancialAccount + Position + OwnershipEdge
                          ↓
             project_graph_to_household_facts()
                          ↓
                   HouseholdFacts
```

E01 的 projection 只替换 `HouseholdFacts.assets`，其他事实继续复用 V4 loader。Backfilled Position 用 `legacy_asset_id` 保留资产身份，并在 `evidence_json` 保存 V4 暂未升格为 canonical column 的 subtype、流动性档、用途、质押、房产用途、账户包装、波动率、机构类型、家庭角色、地区和 legacy version。

## Shadow comparison

`compare_legacy_projection()` 比较：

- legacy 与 projected 资产记录数；
- 相同 legacy asset id 的市值；
- 资产总额及 0.01 CNY 容差。

不一致时返回 `mismatch` 并记录 diagnostic 日志，但不会切换 V4 生产规划路径。Graph 完整性同时验证唯一家庭主体、账户／持仓／关系引用、非负金额、本金法律属性和关系有效期。

## V4 contract regression suite

`backend/tests/contracts/v4_demo_contracts_v1.json` 保存 DEMO_A／B／C 的结构性 V4 合同，包括：

- 财务报表核心金额、CHFI 状态与财务规则版本；
- 动态四账户金额、门禁、方法论与规则版本；
- Portfolio eligibility、家庭 gate、有效风险上限与候选状态；
- Twin 初始资产桶、月支出、收入／债务／目标数量；
- 固定八章标题、报告 service 与 composer 版本。

测试不比较整份 JSON 或运行时 ID／时间戳，避免把展示文案和非决策字段错误冻结为业务合同。

## 写入兼容策略

1. 原 `/planning` onboarding 继续先保存 V4 汇总资产并生成分析。
2. 开启 E01 flag 后，新增“精细资产（可选）”步骤，读取这些汇总资产的 backfilled positions。
3. 客户可以补充所有者、账户、币种、期限、风险、用途、锁定和估值证据。
4. 对已有 position 的细节更新不改写 V4 Asset；新增 position 在完成显式对账前也不进入 V4 规划金额，防止重复计入。
5. E02–E03 完成并有更完整的 Profile／Need／Liability／ELTC 合同后，才评估让特定新引擎从 Graph projection 读取。

## 运维与回退

- 本地默认 `ENABLE_V5_FINANCIAL_GRAPH=false`；关闭 flag 后新增 API 返回不泄露资源状态的 404。
- 回退至 `0015` 不触碰任何 legacy row。
- `make check` 覆盖 Ruff、Mypy、Pytest、ESLint、TypeScript、Vitest 和生产构建；21 条 Playwright smoke 同时负责 V4 客户路径、A-H／创始人发布链和 V5 全路由四档宽度。
