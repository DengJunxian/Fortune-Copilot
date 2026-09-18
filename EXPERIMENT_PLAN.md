# 统一实验与消融计划

## 数据集

`data/benchmarks/competition_personas_v1.json` 由 `scripts/generate_competition_benchmark.py` 确定性生成，包含 60 个合成画像：

- 年轻职场人士 10；
- 中产家庭 10；
- 高净值客户 10；
- 企业主 10；
- 科技创业者 10；
- 退休人士 10。

每个画像含收入、资产、负债、支出、抚养、稳定性、风险意愿、最大亏损、知识、目标和行为信号。没有真实客户数据。

## A/B/C/D

| 组 | 实现 | 当前状态 |
| --- | --- | --- |
| A 通用 LLM | 同一任务协议的外部模型适配器 | 未测量；无授权同协议结果，不填数值 |
| B 单 Agent | 仓库内可复现离线架构基线 | 已运行，不冒充商业 LLM |
| C RAG Agent | B + 受控检索/Citation 基线 | 已运行，不冒充真实模型评测 |
| D 完整 Fortune-Copilot | Goal + Risk + Quant + Product + Compliance + Behavior + RAG | 已运行 |

因此当前只能严谨声明 B/C/D 的合成离线比较；A 仍是协议位。接入真实通用 LLM 后必须锁定模型版本、参数、提示、随机种子/重复次数、网络和计费环境。

## 指标

| 指标 | 定义 |
| --- | --- |
| Profile Extraction F1 | 结构化金标字段 micro F1 |
| Financial Planning Correctness | Required Saving 相对误差 ≤5% 的画像比例 |
| Suitability Violation Rate | 违规可执行建议/全部可执行建议 |
| RAG Recall@K | 命中知识类别/需要类别 |
| MRR | 首个相关结果倒数排名均值 |
| Unsupported Claim Rate | 无 Citation 外部事实/全部外部事实 |
| Response Latency | 同机墙钟总时延与每画像时延 |
| Portfolio Sharpe/Drawdown/CVaR | 同一合成压力场景函数 |
| 个性化程度 | 唯一目标储蓄+风险预算+组合签名/画像 |
| 专家评价 | 盲评协议；当前无样本，必须为 null |

Faithfulness 需要逐声明 NLI/人工复核；当前仓库尚未形成可对外声明的真实人工结果。

## 消融

- `w/o RAG`：关闭检索和 Citation，重算 Recall/MRR/Unsupported Claim。
- `w/o Compliance Agent`：向画像暴露 R5 主题候选，按能力上限实算违规率。
- `w/o Behavioral Agent`：不读取行为证据，干预覆盖率归零。
- `w/o Goal Planning`：不计算 FV/Required Saving/协调，规划正确性按协议归零。
- `w/o Quant Engine`：使用固定 10/35/45/5/5 资产权重，以同一场景重算组合指标。

消融只改变指定模块，其余输入与评价函数不变。结果显示贡献，不证明真实客户因果效果。

## 复现

```bash
python3 scripts/generate_competition_benchmark.py
make competition-benchmark
```

结果写入 `output/competition_benchmark_results.json`，该目录不提交；评委可现场重新生成。后端测试同时验证 60 画像、六客群、A 未伪造、B/C/D 已测、五项消融和边界字段。

## 后续真实实验

1. 由至少两位独立财富管理专家盲评解释正确性和个性化。
2. 在授权条件下运行 A 的真实模型，并重复至少 3 次报告均值与方差。
3. 建立真实问句 RAG 集，独立标注相关文档和声明 Faithfulness。
4. 真实客户/员工研究需伦理、隐私和机构授权；未完成前不得声明效果提升。
