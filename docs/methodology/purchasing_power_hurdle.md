# 中国家庭购买力门槛 PPH

## 定义

长期目标不使用单一静态通胀率。系统计算：

```text
PPH = max(
  official_cpi_trend,
  family_weighted_expense_inflation,
  regional_minimum_wage_cagr
)
```

PPH 是家庭层规划门槛，不是产品收益承诺，也不表示某项产品保证本金或保证跑赢该门槛。

## 三个信号

- `official_cpi_trend`：总体消费价格观察值。
- `family_weighted_expense_inflation`：按家庭教育、医疗、养老、生活和居住支出权重计算的变化。
- `regional_minimum_wage_cagr`：所在地区优先采用 3–5 年最低工资序列的年化辅助信号；公开序列不足时必须标记质量降级，不能补造数据。

最低工资由地区政策离散调整，绝不标记为 CPI。API 对该分量固定输出 `is_cpi=false`，总结果固定输出 `minimum_wage_is_cpi=false`。

## 数据治理

`RegionalMinimumWageSnapshot` 保存地区、数值序列、观察日、生效日、接入日、来源引用、版本、数据质量、live/demo 标记和 lineage。当前杭州、南京、广州序列来自地方政府公开文件，经官方域名白名单和结构校验后固化为非实时、非 Demo 快照；数据不足时返回 `degraded` 或 `fallback`，不会伪装成实时人社接口。CPI 观察同样来自国家统计局公开快照。来源明细见[权威公共数据管道](../governance/authoritative_public_data.md)。

组合优化器的新输入为 `purchasing_power_hurdle`。旧 `inflation_rate` 名称仅在兼容证据中保留为 deprecated，不再代表优化语义。输出包括购买力成功概率和费后实际收益。
