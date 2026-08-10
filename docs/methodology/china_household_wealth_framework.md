# CHFH 中国家庭财富健康理论与 GRB 动态账户模型

## 定位

Fortune Copilot 以 CHFH（Chinese Household Financial Health Framework）为总框架，以 GRB（Goal / Risk / Behavior）为动态账户核心。系统首先识别家庭不能违约的责任，其次评估现金流与流动性韧性，再核对社保、年金、公积金与个人养老金等制度覆盖，最后在正式适当性边界内优化目标成功概率和长期购买力。

本框架不采用标准普尔象限的固定比例。四域是用途分类，不是由家庭总资产乘以固定百分比得到的投资组合。

## 单一理论主线

```text
家庭资产负债、现金流、责任与制度覆盖
→ CHFH 家庭财务健康目标
→ GRB 目标、风险、行为决策状态
→ 要花、保命、保本、生钱四账户
→ CHFI 十维诊断与硬风险闸门
→ HFDT 家庭金融数字孪生压力测试
→ 资产类别、合格产品与持续复盘
```

RRI-G 中的责任、韧性、制度账户与目标概率继续作为内部约束组件，不再与 CHFH、GRB 并列成为新的对外概念。这样可避免一个功能对应一个品牌名，保持论文、接口和界面用语一致。

## GRB 决策状态

GRB 不把一次风险问卷直接映射为产品组合。每次规划同时形成：

- Goal：目标金额、期限、刚性、可延期程度、已准备资金和制度覆盖；
- Risk：客观风险承担能力、主观风险意愿、现行风险上限和具体产品适当性；
- Behavior：问卷、下跌情景实验与后续真实行为。行为结果只允许维持或下调风险预算。

配置规则表示为：

```text
Allocation = π(Goal, Risk, Behavior, Household State)
```

正式风险测评与监管适当性仍是独立硬约束。行为画像不能替代监管分类，也不能把客户推向更高风险产品。

## 方法论宪法

受版本控制的 `wealth_methodology_v3.json` 定义七条不可由市场观点、客户滑块、顾问或 LLM 覆盖的原则：

1. 先责任，后投资。
2. 四域按人民币责任金额计算，不使用固定比例。
3. 每个比例必须声明分母。
4. 保险作为风险转移成本，保障和储蓄属性分开记录。
5. “保本的钱”是用途名，不等于底层产品保证本金。
6. 地区最低工资趋势是购买力辅助信号，不是 CPI。
7. LLM 只能理解和解释，不能改变确定性约束。

每次规划把 `methodology_version`、规则版本和快照版本写入 `DecisionEvidencePackage`。规则文件无效、缺失或不满足宪法结构时，系统拒绝加载，而不是临时补造决策参数。

## 三分母纪律

| ID | 定义 | 允许用途 |
| --- | --- | --- |
| `total_household_assets` | 家庭全部资产，包括自住房等非金融资产 | 家庭资产结构、房产集中度、总杠杆 |
| `investable_financial_assets` | 规则认可的可投资金融资产 | 金融资产结构、流动性和战术稳定带 |
| `residual_long_term_plannable_capital` | 完成债务、日用、应急、保障和近期责任后的长期剩余资源 | 正式增长比例、70% 战略目标、学习仓上限 |

旧接口中的 `total_assets` 等字段继续返回，但被标记为兼容口径。新比例同时输出 `denominator_id`；长期增长分母由 schema 限定为 `residual_long_term_plannable_capital`。

## PFNW

`plannable_financial_net_worth`（PFNW）定义为：

```text
eligible investable financial assets - included liabilities
```

房产、信用卡未使用额度和保险保额不进入可投资金融资产。锁定制度账户可按规则进入 PFNW 的长期观察，但不会因此获得短期流动性资格。旧字段 `net_financial_assets_after_debt` 暂时保留，数值与 PFNW 对齐。

## 财务状态旅程

- `FinancialRecovery`：PFNW 不为正、高息债务未处理或现金流不可持续；不销售投资。
- `WealthAccumulation`：PFNW 为正但未达到有效启动线；优先安全垫，满足全部条件后才允许学习仓。
- `WealthGrowth`：达到门槛且硬 Gate 全部通过；进入完整长期组合评估。
- `ComplexWealthManagement`：结构复杂或需要税务、传承、企业主安排；进入人工协同。

系统服务所有家庭，但不会给所有家庭同一种产品建议。

## 版本与验证

比赛版地区参数、最低工资、市场状态、养老金政策和产品目录均为受控演示快照，明确携带 `is_demo`、来源、日期、质量和 lineage。生产接入必须遵循 `Source → Validation → Snapshot → Rule Version → Calculation`，不能把网页实时抓取结果直接用于决策。

自动化不变量覆盖信用额度、保险保额、养老金锁定、三分母、学习仓、硬 Gate、产品陈述、个股集中、存量/流量分离和证据版本完整性。
