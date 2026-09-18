# 独立量化配置引擎

实现：`backend/app/services/competition/quant.py`
版本：`competition-quant-v1.0.0`

## 边界

量化引擎只决定资产类别权重，不选择具体产品。输入来自家庭目标、有效风险预算和流动性约束；输出随后进入 Product Filtering 和 Compliance Agent。LLM 不能修改权重。

## 输入

- 资产类别：预期收益、波动率、流动性、锁定期、上下限、市场权重、压力场景。
- 相关矩阵：与波动率组合为协方差矩阵。
- 约束：`sum(weights)=1`、long-only、最低现金、单类上限、流动性、波动率、CVaR、目标期限、允许资产类别和风险贡献预算。
- 目标：无风险利率、目标收益、Black–Litterman 观点与置信度。

## 四种方法

### Mean-Variance Optimization

在离散可行域内最小化：

```text
Objective_MVO = 3 × PortfolioVariance − ExpectedReturn
PortfolioVariance = wᵀΣw
```

### Risk Parity

```text
MarginalRisk = Σw
RiskContribution_i = w_i × MarginalRisk_i / PortfolioVariance
Objective_RP = Σ(RiskContribution_i − TargetBudget_i)²
```

未提供资产级预算时使用等风险贡献目标；提供时先归一化。

### CVaR Optimization

使用每个资产的同序压力场景生成组合收益，取最差 20% 损失的均值：

```text
CVaR = mean(largest 20% scenario losses)
Objective_CVaR = CVaR + 3 × max(0, TargetReturn − ExpectedReturn)
```

这是有限合成情景 CVaR，不冒充历史或实时市场分布。

### Black–Litterman

先以 `2.5 × Σ × market_weight` 形成市场隐含收益，再与资产先验收益平均；对有观点的资产按置信度收缩到观点收益，最后执行 MVO。当前是透明、无外部求解依赖的对角观点简化版，不是机构级全 P/Q/Ω 矩阵实现。

## 求解与降级

比赛版使用确定性网格枚举，默认步长 5%；60 画像 benchmark 为控制时延使用 10%。优点是无随机性、可回放、无需 CVXPY；缺点是离散误差和资产类别数量扩展成本。无可行解时返回 100% 现金 fallback，并标记 `status=fallback`，不得包装成最优解。

## 选择规则

四方法全部保留。演示选择器在满足硬约束的方法中最大化 `Sharpe − CVaR`，再最小化最大回撤；该规则版本化并写入 Trace，不是收益预测。答辩应展示“为什么选”，而不是只展示一组饼图。

## 审计记录

每次 `QuantComparison` 保存：

- 完整输入及 SHA-256；
- 协方差矩阵和 BL 后验收益；
- 全部约束；
- 各方法权重、指标、目标值、可行候选数、拒绝原因、绑定约束；
- 选择规则、选择原因、输出 checksum；
- 引擎版本。

## 指标限制

Expected Return、Sharpe、Max Drawdown 和 CVaR 全部基于合成资产假设/压力场景，只用于方法比较和系统验证。不得解释为未来收益、真实回测、工行投研观点或可售组合业绩。
