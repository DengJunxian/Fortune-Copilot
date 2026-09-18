# 财富管理领域模型与计算口径

## 1. 聚合根

`WealthClientModel` 是竞赛 CFS 的只读聚合，包含：

- `PersonalProfile`：年龄、城市、职业、就业类型、婚姻状态。
- `FamilyProfile`：成员、抚养人数、未成年子女、赡养责任。
- `IncomeProfile`：本人/配偶/被动收入、稳定性、集中度。
- `ExpenseProfile`：必要、可选和年度特殊支出。
- `Asset`、`Liability`、`Insurance`：所有权、流动性、质押、利率、保障。
- `CashFlow`：收入、支出、偿债和结余的派生结果。
- `RiskProfile`：意愿、最大可接受亏损、知识和亏损反应。
- `BehaviorProfile`：可追溯行为证据。
- `FinancialGoal`：八类目标和全部规划字段。
- `Portfolio`、`ProductHolding`：当前持仓事实，不等同推荐。

原关系数据库中的 `Household`、`HouseholdMember`、`IncomeSource`、`ExpenseItem`、`Asset`、`Liability`、`InsurancePolicy`、`FinancialGoal`、`RiskAssessment`、`BehaviorAssessment`、`Position` 和 `Product` 是持久层实体；统一模型是面向 CFS 的契约投影，不重复造表。

## 2. Goal 类型

支持 `emergency_fund`、`housing`、`education`、`retirement`、`entrepreneurship`、`major_purchase`、`wealth_transfer`、`other`。每个目标维护目标金额、日期、当前资产、月投入、预期收益、通胀、优先级和成功概率。

## 3. Family Balance Sheet

```text
TotalAssets = Σ Asset.market_value
FinancialAssets = Σ is_financial_asset
TotalLiabilities = Σ outstanding_balance
NetWorth = TotalAssets − TotalLiabilities
MonthlyCashFlow = (AnnualIncome − AnnualExpense − AnnualDebtService) / 12
DTI = MonthlyDebtService / MonthlyIncome
EmergencyMonths = EmergencyEligibleAssets / EssentialMonthlyExpense
Concentration = max(Asset.market_value) / TotalAssets
```

应急资产只计未质押、7 日内可用的现金/存款口径；“流动资产”可更宽，但不能全部当应急金。保障缺口按家庭支柱收入倍数、负债和已有寿险/重疾保障估算，必须标为规划口径并触发持牌复核。

## 4. 动态四账户

| CFS 域 | 中国居民表达 | 计算逻辑 |
| --- | --- | --- |
| Liquidity | 要花的钱 | 必要月支出 × 动态安全月数 |
| Protection | 保命的钱 | 保费现金预算与保障缺口分离 |
| Liability / Goal Matching | 保本与目标匹配的钱 | 高息债务 + 五年内目标缺口 |
| Growth | 生钱的钱 | 金融资产扣除前三类后的剩余 |

动态安全月数从 3 个月基准出发，按收入不稳定、抚养人数、未成年子女、债务压力和经营就业增加，上限 12 个月。该公式是版本化内部规划规则，不是监管比例。

## 5. Goal-Based Planning

```text
FV_target = TargetAmount × (1 + Inflation/12)^Months
FV_current = CurrentAssets × (1 + ExpectedReturn/12)^Months
FundingGap = max(0, FV_target − FV_current − FV_contributions)
RequiredSaving = (FV_target − FV_current) / AnnuityFactor
```

资源协调按优先级和日期排序，从家庭真实月结余分配；低优先目标不能挤占高优先刚性目标。成功概率是合成情景下的规划指标，不是市场预测；必须同时显示假设、期限和资金受限状态。

## 6. Risk Budget

- Capacity：收入稳定、期限、家庭负担、负债、应急金、净资产。
- Tolerance：风险偏好、最大可接受亏损、知识、亏损反应。
- Requirement：目标资金缺口隐含的收益要求。

`EffectiveRiskBudget = min(Capacity, Tolerance)`。Requirement 高于有效预算时只报告冲突并调整目标/储蓄/期限，禁止提高客户风险上限。

## 7. 状态与版本

事实、派生快照、建议、客户确认和报告分开；任何家庭事件生成新版本，不覆盖历史。关键输出包含分析日、输入哈希、规则/引擎版本、输出哈希、数据来源和是否合成。
