# Fortune Copilot V6 三分钟演示脚本

版本：Competition Edition V6
主路径：`/planning` → `/wealth` → `/wealth/cfs` → `/wealth/twin` → `/advisor/actions` → `/risk`
演示边界：Synthetic household、Public Verified product snapshot、Mock bank adapter；非工商银行官方产品，无 Live 工行连接。

## 演示前准备

1. 执行 `docker compose up --build`，确认前后端健康。
2. 预先打开主路径页面，保留一个核心家庭，不在主剧情切换八个 Persona。
3. 确认 ELTC、GRB、产品漏斗和事件重算都有确定性结果；模型不可用时使用模板解释。
4. 不输入真实身份证、账号、手机号、银行卡或 API Key。

## 0–20 秒：一句话建立家庭档案

在 `/planning` 输入：

> “我和爱人在上海工作，每个月税后收入大约4万元，还有180万元房贷，小孩今年4岁，希望以后去国外读大学。”

系统提取配偶、家庭月收入、房贷、子女年龄/阶段、上海和教育意向，生成“待确认家庭信息”。指出教育阶段、目的地和已准备金额等高影响缺失项。

台词：

> “AI 负责理解家庭语言，但不会补造金融事实。确认前，这些信息不会进入正式 Household Facts。”

## 20–40 秒：我家现在安全吗？

进入 `/wealth`，依次指向财务健康、应急/债务/保障、目标时间轴、ELTC 和 1–3 个 Next Best Action。

台词：

> “Fortune Copilot 的决策主体是家庭。CHFH 先看现金流、负债、保障和人生责任，不从产品推荐开始。”

## 40–70 秒：真正能长期投资的钱

展开 ELTC Bridge：可调度金融资源依次扣除日常周转、应急、高息债务、保障、近期责任、已承诺目标和锁定资金。展示最终“长期可投资资本 ELTC”，并打开“为什么不是全部金融资产？”。

台词：

> “有多少钱，不等于有多少钱可以投资。只有 ELTC 才正式进入长期资产配置。四账户是用途账户，不是 10/20/30/40 固定比例。”

切换简洁/标准/专业解释时补充：

> “AI 只改变表达深度；金额、扣减和公式始终来自确定性引擎。”

## 70–95 秒：Goal + Risk + Behavior

进入 `/wealth/cfs`，展示 Risk Capacity、Risk Willingness、Behavioral Risk 和 Family Risk Budget。

台词：

> “单次问卷不是最终风险等级。能力、意愿和真实行为共同约束风险预算；行为只能维持或下调，不能自动上调。”

## 95–125 秒：先资格，再配置

按页面五步指向：本次可配置 ELTC、家庭风险预算、家庭目标、资产方向、配置理由。最后才展示 Cash、Fixed Income、Equity、Gold、REITs 等方向。

台词：

> “系统先确认可以配置多少钱，再结合目标和风险预算给出资产方向。流动性、CVaR、购买力和分散度是可复核约束。”

## 125–150 秒：产品候选漏斗

展示 Product Candidate Funnel 的实际输出数量，再展开一个 Why Selected 和一个 Why Not Others。

台词：

> “这不是‘最佳基金’榜单，而是当前家庭约束下的候选产品。风险、期限、流动性、证据或资格不匹配的产品会被排除，数量来自算法而不是 UI 写死。”

## 150–170 秒：家庭变化后重新规划

在 `/wealth/twin` 或历史/监控页重放一个家庭事件，展示 `Before → Event → After`。

台词：

> “收入、失业、孩子、房贷、目标、产品到期、市场冲击或行为变化都会触发复核。Financial Twin 用于条件模拟和重算，不是市场预测。”

## 170–180 秒：客户经理与合规

在 `/advisor/actions` 展示 Why Now、What Changed、What Matters、Suggested Discussion、What Not To Sell；在 `/risk` 展示 Why This Advice、Suitability、Evidence、Replay。

收束：

> “Fortune Copilot 不只是告诉家庭钱怎么投，更先判断哪些钱真正能够承担投资风险。它是把家庭需求连接到银行财富产品与专业服务的家庭财富决策智能层。”

## 现场恢复

| 情况 | 处理方式 |
| --- | --- |
| Intake 或模型不可用 | 使用已保存的待确认草稿；不补造缺失字段 |
| 图表异常 | 打开等价数据表或证据详情 |
| 产品数据不可用 | 明确显示证据不足/快照状态；不声称当前工行可售 |
| 状态不一致 | 使用 Decision Replay；不跳过人工复核 |
| 网络中断 | 继续运行本地确定性主链和 Mock 适配器 |

更完整的逐屏证据见 [V6 Demo Script](v6/V6_DEMO_SCRIPT.md)。
