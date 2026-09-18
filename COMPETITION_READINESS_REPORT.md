# Fortune-Copilot 工行杯就绪报告

评估日期：2026-09-18
版本：v0.15.0
结论：**代码与主 Demo 已达到上海赛区初赛/市赛的可演示原型水平；全国赛级真实实验、专家盲评和银行生产验证尚未完成。**

## 已完成

| 能力 | 状态 | 可验证证据 |
| --- | --- | --- |
| 全仓事实审计 | 已完成 | `CURRENT_STATE_AUDIT.md` |
| 银行级领域模型 | 已完成 | `backend/app/schemas/competition.py` |
| Family Balance Sheet | 已完成 | 11 项指标、恒等式、页面可视化 |
| 动态四账户 | 已完成 | 无固定比例；输入驱动和金额可回放 |
| Goal-Based Planning | 已完成 | FV/Required Saving/Gap/Probability/资源协调 |
| 三维 Risk Budget | 已完成 | Capacity/Tolerance/Requirement 分离 |
| 独立 Quant Engine | 已完成 | MVO/RP/CVaR/简化 BL 四方法和 Trace |
| 标准产品匹配 | 已完成 | 六阶段管线、Demo 产品 Schema |
| Compliance Agent | 已完成 | 七类规则、拒绝记录、SVR |
| 行为金融 Agent | 已完成 | 六类偏差、证据、风险、干预 |
| Advisor 汇总边界 | 已完成 | `llm_modified_quant_output=false` |
| RM Copilot / Human Escalation | 已完成 | 360、问题、目标、NBA、沟通、人工事项 |
| 五项消融 | 已完成 | benchmark `ablations` |
| 指定上海案例 | 已完成 | 38 岁、65 万收入、180 万金融资产、房贷 |
| 比赛主视图 | 已完成 | `/competition`，响应式和 axe 测试 |
| 十一份指定文档 | 已完成 | 根目录文件齐全 |

## 部分完成

| 能力 | 已有 | 缺口 |
| --- | --- | --- |
| Financial RAG 评估 | 受控知识、Citation、Recall@K/MRR/Unsupported Claim 合成评测 | 真实问句集与独立 Faithfulness 人工标注未完成 |
| A/B/C/D 对比 | 60 画像；B/C/D 可复现离线运行 | A 通用 LLM 无同协议实测，保持未测量 |
| 专家评价 | 指标和盲评协议已定义 | 无真实专家样本，字段保持 `null` |
| 三端银行架构 | 客户、RM、风险/管理端及 Port/Adapter 设计 | 未接工行真实系统，未做银行沙箱验证 |
| 工程发布 | lint、类型、198 后端测试、66 前端测试、生产构建通过 | 本轮未执行真实银行环境、压测、灾备和现场网络演练 |

## 尚未完成

- 中国工商银行任何生产/沙箱系统集成或合作验证。
- 真实在售产品、实时行情、真实客户、真实交易和真实经营结果。
- A 组通用 LLM 的锁版本、多次重复同协议实验。
- 独立财富管理专家盲评和真实用户理解度/客户经理效率实验。
- 机构级完整 Black–Litterman P/Q/Ω、连续优化求解器和真实历史回测。
- 银行级 IdP、KMS/HSM、SIEM、灾备、数据分区、模型网关和正式安全测评。

## 最终质量门禁

2026-09-18 本地执行：

| 门禁 | 结果 |
| --- | --- |
| `make competition-benchmark` | 60 个画像，B/C/D 已测，A 未伪造 |
| Ruff | 通过 |
| Mypy strict | 通过，262 个后端源文件 |
| 后端 Pytest | **198 passed** |
| ESLint | 通过 |
| TypeScript | 通过 |
| 前端 Vitest | **66 passed / 14 files** |
| axe | 新比赛页 0 violation（测试中关闭颜色对比规则，结构/ARIA 全开） |
| Vite production build | 通过 |
| Playwright 真实浏览器验收 | 1440×1000 与 390×844 均无横向溢出；接口最终 200；控制台 0 error / 0 warning |
| `git diff --check` | 通过 |
| Key 扫描 | 未发现已提交真实 Key；README 只有“填写本地密钥”占位说明 |

非阻断告警：Starlette TestClient/httpx 弃用提示；Vitest 的 localStorage 实验提示；ECharts chunk 约 596.68 kB。三项均不影响当前测试，但应在全国赛冻结版前处理或纳入预热脚本。

## 60 画像最新可复现实测

以下仅是合成结构化画像和离线评价函数结果，不是客户效果或投资业绩：

| 系统 | Profile F1 | 规划正确 | SVR | Recall@K | Unsupported | Sharpe | Max DD | CVaR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A 通用 LLM | 未测 | 未测 | 未测 | 未测 | 未测 | 未测 | 未测 | 未测 |
| B 单 Agent 离线基线 | 0.8000 | 0.3167 | 0.1167 | 0.0000 | 1.0000 | 0.4345 | 0.1433 | 0.1175 |
| C RAG Agent 离线基线 | 0.8571 | 0.0000 | 0.1167 | 0.6667 | 0.3333 | 0.4399 | 0.1385 | 0.1136 |
| D 完整 Fortune-Copilot | 1.0000 | 1.0000 | 0.0000 | 1.0000 | 0.0000 | 0.4675 | 0.0326 | 0.0258 |

C 的 RAG 改善引用但不改善其简化规划算法，因此规划正确率没有提升；这正是完整系统必须保留 Goal/Quant/Compliance 的原因。表中 D 的 1.0000 来自结构化输入和确定性金标，不应外推到自然语言真实客户场景。

## 答辩建议

主讲 `/competition` 的上海家庭，控制在 3 分钟；只在追问时展开家企、跨境、传承、数字孪生和治理页。主动说明三项边界：**合成数据、Mock 产品、未连接工行生产**。把“可解释”落实为公式、约束、拒绝原因、Citation 和哈希，不用模块数量代替证据。
