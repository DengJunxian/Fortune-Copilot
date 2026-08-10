# Decision Evidence Package

## 目的

每次规划和组合结果都要回答“当时为什么这样建议”。证据包将家庭输入、方法论、规则、地区参数、市场状态、养老金政策、组合规则、产品快照、风险和行为评估绑定到一次决定。

## 字段

- `household_input_version`
- `methodology_version`
- `financial_rule_version` 与 `planning_rule_version`
- `regional_parameter_version`
- `market_regime_version`
- `minimum_wage_snapshot_version`
- `public_data_snapshot_version`
- `pension_policy_version`
- `portfolio_version` 与 `product_snapshot_version`
- `risk_assessment_version` 与 `behavior_assessment_version`
- 可选的 `llm_model_version` 与 `llm_prompt_version`
- 全部 hard gate 结果、生成时间和 `decision_hash`

关键版本为空或为 `unknown` 时，Pydantic 校验拒绝证据包。LLM 未参与时两个 LLM 版本必须为空，不伪造模型调用。

## 哈希和重演

`decision_hash` 对治理字段和 Gate 结果进行规范化 JSON 哈希。`generated_at` 被记录但不参与决策身份，因此相同事实与版本在不同时间重算仍得到相同哈希；任何输入、规则或 Gate 变化都会改变哈希。

Planning Run 和 Recommendation 持久化方法论版本、证据 JSON 和哈希。历史重演时必须读取当时的版本化快照，不能用最新市场或产品状态覆盖旧决定。

## 责任边界

证据包证明系统使用了哪些已知事实和规则，不等于产品成交凭证。真实执行还需要当时的客户身份、授权、AML、渠道、产品可售和交易前 Gate 证据。
