# Fortune Copilot V6 Three-Minute Demo

## Demo promise

Use one synthetic Shanghai household from start to finish. The audience should remember one sequence:

```text
家庭安全吗？ → 多少钱能长期投资？ → 应该怎么配置？ → 家庭变化后如何重算？
```

Do not switch among multiple personas in the main story. Additional personas are regression evidence only.

## 0–20 seconds — Natural-language household intake

**Page:** `/planning`

**Input:**

> 我和爱人在上海工作，每个月税后收入大约4万元，还有180万元房贷，小孩今年4岁，希望以后去国外读大学。

**Action:** show the extracted spouse, joint income, mortgage balance, child age/stage, Shanghai location and overseas-education intent. Point to the missing high-impact questions. Do not confirm automatically.

**Script:**

> “Fortune Copilot 从家庭语言开始。AI 只把信息整理成待确认草稿；没有说出的教育阶段、地区和已准备金额会继续追问。用户确认前，这些内容不会进入正式家庭事实。”

## 20–40 seconds — Is my household safe?

**Page:** `/wealth`

**Action:** show the four first-screen answers: financial health, emergency coverage/debt/protection, goal timeline, ELTC and the first 1–3 actions.

**Script:**

> “系统先回答我家是否安全，而不是先推荐基金。CHFH 把现金流、负债、保障和家庭责任放在同一张图上，教育、住房与退休目标同时显示金额缺口和时间。”

## 40–70 seconds — ELTC bridge

**Page:** `/wealth`, expand the ELTC card.

**Action:** follow the bridge from deployable resources through daily liquidity, emergency reserve, debt, protection, near-term responsibilities, committed goals and locked assets to the final ELTC. Open “为什么不是全部金融资产？” and briefly switch among concise/standard/professional explanations.

**Script:**

> “有多少钱，不等于有多少钱可以投资。只有扣除日常、应急、债务、保障和已承诺目标后的长期可投资资本 ELTC，才有资格进入长期市场风险。解释可以换深度，但金额始终来自同一个确定性计算。”

## 70–95 seconds — GRB family risk profile

**Page:** `/wealth/cfs`

**Action:** show Risk Capacity, Risk Willingness, Behavioral Risk and final Family Risk Budget.

**Script:**

> “风险问卷不是最终答案。能力、意愿和真实行为共同形成 Goal + Risk + Behavior 风险画像。行为证据只能维持或下调预算，不能把客户自动升级为更高风险。”

## 95–125 seconds — Allocation after eligibility

**Page:** `/wealth/cfs`

**Action:** point to the five-step order: configurable ELTC, risk budget, goals, asset direction, rationale. Only then show Cash, Fixed Income, Equity, Gold and REITs where available.

**Script:**

> “配置先说明这次到底能配置多少钱、家庭风险预算和目标，再显示资产方向。流动性、CVaR、购买力和分散度是约束，不是让大模型自由生成比例。”

## 125–150 seconds — Product candidate funnel

**Page:** `/wealth/cfs`, Product Candidate Funnel.

**Action:** show the real current counts through purpose, horizon, risk, liquidity, eligibility/quality and final candidates. Open one candidate’s Why Selected and one excluded product’s Why Not.

**Script:**

> “产品不是起点。候选数量来自真实算法，不是界面写死。系统展示的是当前家庭约束下的候选产品，也说明哪些产品因风险、期限、流动性、证据或客户资格被排除。”

## 150–170 seconds — Continuous wealth management

**Page:** `/wealth/twin` or monitoring/history view.

**Action:** trigger or replay one household event and show `Before → Event → After`, including changed ELTC/risk/goal/action where the existing scenario provides it.

**Script:**

> “收入、失业、孩子、房贷、目标、产品到期、市场冲击或行为发生变化，系统就重新计算，而不是继续沿用旧方案。Financial Twin 是条件模拟和复盘，不是市场预测。”

## 170–180 seconds — Advisor and compliance

**Pages:** `/advisor/actions`, then `/risk`.

**Action:** show Why Now/What Changed/What Matters/Suggested Discussion/What Not To Sell, then Why This Advice/Suitability/Evidence/Replay.

**Closing:**

> “Fortune Copilot 不只是告诉家庭钱怎么投，更先判断哪些钱真正能够承担投资风险。它是连接家庭需求与银行财富产品和专业服务的家庭财富决策智能层。”

## Recovery path

- If intake fails, use the saved draft fixture; do not invent missing fields.
- If a chart fails, use the equivalent table or evidence drawer.
- If a model or network is unavailable, keep the deterministic results and template explanation.
- If workflow state differs, show the saved audit/replay instead of skipping approval.
- Never describe Synthetic, Public Verified or Mock evidence as Live.
