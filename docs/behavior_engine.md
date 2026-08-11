# Fortune Copilot 行为金融双画像与干预引擎

版本：Stage 7 / 2026-08-04  
规则源：`data/rules/behavior_finance_v1.json` 1.0.0  
公式版本：`behavior-scoring-1.0.0`  
实验版本：`behavior-experiments-1.0.0`

## 1. 适用边界

行为引擎只处理 A-H 八类合成 Persona，或具有未撤回 `behavior`／`risk` scope 授权的测试数据。它不是临床诊断、监管统一风险评级、收益预测或自动交易系统。

最终风险上限始终取客观承担能力、七维问卷和六项行为实验的审慎最低等级。行为证据可以维持或下调客观上限，绝不能提高客观上限；反应时间只作为辅助实验指标，不单独决定配置。缺少客观风险记录、完整问卷或六项答卷时，系统返回信息不足，不猜测人格或补造选择。

## 2. 七维问卷

| 维度 | 权重 | 口径 |
| --- | ---: | --- |
| 风险意愿 `risk_willingness` | 0.20 | 对长期资金短期波动的主观意愿 |
| 自述损失承受 `loss_tolerance_claim` | 0.20 | 下跌时自述坚持原计划的程度 |
| 投资经验 `investment_experience` | 0.15 | 多资产与完整周期的实际经历 |
| 金融知识 `knowledge` | 0.15 | 对波动、分散、期限、费用和流动性的理解 |
| 交易克制度 `trading_frequency` | 0.10 | 避免短期涨跌驱动频繁交易的能力；高分更克制 |
| 注意力稳定 `attention` | 0.08 | 不被热榜、近期收益和高频提醒牵动的程度 |
| 目标纪律 `goal_discipline` | 0.12 | 消费冲动与家庭目标冲突时坚持计划的程度 |

所有输入为 0—1 的十进制定点值；API 拒绝 JSON 二进制浮点数。问卷分数为：

`Q = round6(Σ dimension_value × dimension_weight)`

权重合计严格为 1。`Q` 只形成自述画像，不覆盖客观承担能力。

## 3. 六项行为实验

| 代码 | 情景 | 主要观察 |
| --- | --- | --- |
| `market_up_20` | 长期账户上涨 20%，家庭事实与目标不变 | 保持／阈值再平衡／追涨加仓 |
| `market_down_10` | 下跌 10%，家庭安全条件不变 | 保持／临时减仓／全部卖出 |
| `market_down_30` | 回撤 30%，未来收益未知 | 保持／安全条件下分批／减仓／全部卖出 |
| `hot_product_choice` | 热榜高收益叙事高于家庭适配风险 | 适配优先／先比较／熟悉性选择／追热门 |
| `winner_loser_disposal` | 盈利与亏损资产同时偏离目标权重 | 目标再平衡／卖盈留亏／锚定买入价 |
| `consume_or_goal` | 一次性收入与教育／养老缺口并存 | 目标优先／规则分配／即时消费 |

每项响应持久化选择代码、反应时间、修改次数、回答时间、规则证据和一致性。单项一致性为：

`Cᵢ = round6(1 − |对应问卷维度 − 选项行为分|)`

实验分数为：

`E = round6(0.80 × mean(六项选项行为分) + 0.20 × mean(Cᵢ))`

反应时间不会进入风险分数；六项修改总数仅作为“频繁交易倾向”的一条证据，贡献为 `min(1, 修改总数 ÷ 12)`。

## 4. 风险等级与强制冲突

0—1 分数按版本化阈值映射：低 `≤0.20`、中低 `≤0.40`、中 `≤0.60`、中高 `≤0.80`、高 `≤1.00`。

引擎随后执行三条强制冲突规则：

1. 自述损失承受 `≥0.70`，却在下跌 10% 时全部卖出：实验上限强制降至低风险；
2. 上涨 20% 后追涨加仓、下跌 10% 后减仓或清仓：实验上限最多为中低风险；
3. 金融知识 `≥0.70`，却追逐热门产品或不按目标再平衡：实验上限最多为中低风险。

`behavioral_limit = min(questionnaire_limit, experiment_limit)`  
`effective_risk_limit = min(objective_capacity_limit, behavioral_limit)`

这里的 `min` 按低 → 中低 → 中 → 中高 → 高的审慎顺序取值，不做平均。

## 5. 十一项偏差及证据

引擎固定输出损失厌恶、过度自信、从众、近期偏差、处置效应、锚定、熟悉性偏差、心理账户、现时偏好、追涨杀跌和频繁交易倾向十一项结果。每项都包含分数、文字级别、解释和来源证据；没有观察到信号时也返回零分证据，并明确“未观察到不等于不存在”。

偏差分数不是简单贴标签。问卷证据、具体实验选项和修改次数分别产生 0—1 贡献，最终取该偏差最强证据：

`bias_score = max(all evidence contributions for the bias)`

分级为低信号 `≤0.29`、需要关注 `0.30—0.59`、高信号 `≥0.60`。分数只用于解释、选择干预和审慎下调，不用于提高风险等级。

## 6. 十二类干预

| 代码 | 干预 |
| --- | --- |
| `cooling_period` | 24／48 小时冷静期 |
| `staged_investing` | 分批投入 |
| `recurring_investment` | 自动／定期投入建议 |
| `precommitment` | 预先承诺 |
| `goal_progress_focus` | 目标进度替代日收益 |
| `monetary_drawdown` | 金额化回撤 |
| `long_term_probability_range` | 长期概率区间 |
| `counterfactual_rehearsal` | 反事实与下跌前预演 |
| `redemption_confirmation` | 冲动赎回二次确认 |
| `ranking_deemphasis` | 热榜弱化 |
| `windfall_allocation` | 一次性收入分配 |
| `automatic_rebalancing_reminder` | 自动再平衡提醒 |

候选干预必须命中高于低信号阈值的关联偏差，按最强触发证据降序、规则目录顺序稳定排序，每次最多选择 6 项，并关联家庭最高优先级目标。冷静期只在相关偏差达到 `0.60` 时产生；`0.60—0.79` 为 24 小时，`≥0.80` 为 48 小时。

完成实验后，干预的开始时间、可操作时间、触发偏差、目标、实验组、状态和用户操作写入数据库与审计事件。冷静期未到时，完成操作返回 409；用户仍可退出实验或暂不采用干预。任何干预都不自动下单、不承诺降低损失，也不能越过家庭安全、目标与适当性闸门。

## 7. A/B 框架

`behavior-ab-1.0.0` 固定四个配置：普通提示、个性化提示、数字孪生损失模拟、冷静期／目标提醒。分配使用家庭、实验键、框架版本和会话序号的 SHA-256 确定性哈希，因此可复现；分配哈希和方法进入证据表。

指标只统计 `eligible_data=true` 的合成或明确授权测试会话，包括分配数、完成／退出数、完成率、平均反应时间、风险下调数和已完成干预数。当前小样本指标只用于验证实验管线，不证明干预因果效果或投资收益。

## 8. 会话、退出、持久化与 API

迁移 `0007_behavior_finance` 新增：

- `behavior_experiment_sessions`：问卷、版本、授权依据、实验组、状态与最终上限；
- `behavior_experiment_responses`：六项选择、时间、修改、一致性与证据；
- `behavior_bias_findings`：十一项偏差分数和证据；
- `behavior_interventions`：个性化干预、冷静期和状态；
- `behavior_experiment_assignments`：A/B 分配与合格数据范围。

主要 API：

- `GET /api/v1/behavior/catalog`、`GET /api/v1/behavior/ab-framework`；
- `GET /api/v1/households/{id}/behavior` 与 `/export`；
- `POST /api/v1/households/{id}/behavior/sessions`；
- `GET /api/v1/households/{id}/behavior/sessions/{session_id}`；
- `POST .../responses/{experiment_code}`、`POST .../complete`、`POST .../exit`；
- `POST /api/v1/households/{id}/behavior/interventions/{intervention_id}/actions`。

开始、每项回答、完成、退出和干预状态变化都产生专用审计事件。退出会话保留已答实验作为退出证据，但不创建新的 `BehaviorAssessment`、偏差发现或干预。

## 9. 主 Demo B 标准答案

独立夹具 `data/expected/demo_b_behavior_v1.json` 不被运行时读取。B 家庭的确定性答案为：

- 客观能力 `0.580000 / medium`，问卷 `0.632000 / medium_high`；
- 实验 `0.503333`，因“自述可承受 30% 却在 -10% 清仓”强制降至 `low`；
- 同时命中“上涨追买、下跌卖出”，最终配置上限为 `low`；
- 平均反应时间 2,833 ms、修改 6 次、总体一致性 `0.716667`；
- 损失厌恶与追涨杀跌均为 `1.000000 / high`；
- 生成 48 小时冷静期，并按规则选择分批投入、预先承诺、金额化回撤、长期概率区间和下跌前预演，共 6 项干预。

三套演示家庭的显著偏差组合不同；A 与 B 虽都落在低风险最终上限，触发证据与干预路径不同，C 受客观退休准备能力约束落在中低风险。

## 10. 已知限制

- 当前规则和阈值为 `internal_demo`，不冒充监管标准或心理测量量表；
- 反应时间受设备、无障碍工具和阅读速度影响，因此不直接改变配置；
- A/B 只有合成／授权测试数据与描述性指标，没有统计显著性或因果推断；
- 金额化回撤和概率区间只引用确定性财务／孪生工具，行为引擎本身不计算收益；
- Stage 10 已加入四角色演示 RBAC 与撤回后的工作流阻断；正式身份鉴别、跨系统撤回传播、保留期和行级授权留待提示词 12；
- 外部 LLM 与网络不可用时，问卷、实验、评分、干预、导出和三端主 Demo 仍可在 Mock 模式完整运行。
