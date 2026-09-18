# Compliance Agent 与适当性设计

## 目标

任何产品候选只有在客户、产品、期限和资金用途全部通过后才能进入 `ProductRecommendation`。Compliance Agent 是确定性规则执行器，不是提示词角色扮演。

## 处理顺序

```text
Asset Allocation
→ Product Filtering
→ Suitability Check
→ Product Ranking
→ Portfolio Construction
→ Compliance Agent Approval
```

资产配置和产品推荐必须分开。产品排名不能反向改变资产类别权重，渠道激励不能提高排名。

## 标准产品字段

`ProductID/ProductName/ProductType/AssetClass/RiskLevel/ExpectedReturn/Volatility/LiquidityDays/DurationMonths/MinimumInvestment/Fees/SuitableCustomer/Tags/is_demo`。

当前比赛产品文件全部 `is_demo=true`，不是工行在售数据。

## 七类规则

| 规则 | 阻断条件 |
| --- | --- |
| 客户风险等级 | 产品风险高于客户有效 R1-R5 上限 |
| 产品适合客群 | 客户等级不在 `SuitableCustomer` |
| 投资期限 | 产品期限超过目标资金期限 |
| 流动性 | 赎回/锁定超过对应资金用途上限 |
| 集中度 | 目标权重超过单类/单产品上限 |
| 最低金额 | 分配金额低于产品最低投资额 |
| 冲突规则 | 主题集中、费用缺失、快照过期等冲突 |

任何违反项都会生成 `ComplianceCheck(passed=false, violations, checked_rules)`。拒绝记录保留在响应和审计链，但不会进入推荐。

## Suitability Violation Rate

```text
SVR = 进入可执行建议但至少含一项违反的建议数 / 全部可执行建议数
```

无建议时单独返回 `no_executable_product=true`，不能用分母为零的“0%”伪装通过。合法规则测试集目标接近 0；该目标只针对版本化合成测试，不代表现实销售零违规。

## Fail-closed 场景

- 无有效风险画像；
- 目标期限或流动性用途不明确；
- 产品快照过期/不是当前可售；
- 最低金额不足；
- 费用、复杂度或底层资产缺失；
- 银行真实交易/渠道接口未连接；
- 客户要求绕过规则；
- 合规终检或审计写入失败。

结果可以是“现金保留”“无可执行产品”或“转人工”，不允许用占位产品填满组合。

## 人工介入

高资产、跨境、家族传承、重大资产变化、严重风险不匹配、强烈情绪、保障缺口和房产/企业集中度可触发 RM。人工复核可以拒绝或要求补充资料，但不能无痕修改既有量化/合规记录；新决定必须形成新版本。
