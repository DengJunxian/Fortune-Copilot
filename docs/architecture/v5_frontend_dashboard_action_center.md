# V5 E11：家庭财富总览与顾问行动中心

## 范围

E11 只调整前端信息架构和交互，不新增金融计算，也不改变 E10 的监控规则。客户看到的是已确认家庭事实、确定性结果和持续监控提醒；顾问看到的是复核、教育、冷静期与专业转介，不是销售线索。

本轮没有进入 E12 受限工具型 Agent，也没有新增自治 Agent、交易操作或第九章规划书。

## 受控路由

`App.tsx` 已从路径 `switch` 改为集中注册表，注册表负责精确路径、兼容别名和 feature flag 降级。

| 路径 | 用途 |
| --- | --- |
| `/` | 产品首页 |
| `/planning` | 客户引导式建档；`/client` 保留为兼容别名 |
| `/wealth` | 家庭财富总览 |
| `/wealth/profile` | 动态财富画像 |
| `/wealth/goals` | Need／Goal、责任日历与 ELTC |
| `/wealth/cfs` | 综合财务方案 |
| `/wealth/twin` | Scenario Lab 与已发生事件写入 |
| `/wealth/family-enterprise` | 家企财富底稿 |
| `/wealth/retirement` | 退休收入底线 |
| `/wealth/global` | 币种与跨境暴露 |
| `/wealth/history` | Twin Snapshot Report、差异与事件历史 |
| `/advisor` | Action Center 首屏与折叠后的原顾问流程 |
| `/advisor/actions` | 独立顾问行动中心 |
| `/risk` | 合规与审计工作区 |

既有 `/client/advanced`、`/demo` 和 `/wealth/family` 继续保留，避免破坏 V4／早期 V5 入口。

## 客户端 Dashboard

`WealthDashboardPage` 首屏直接回答四个问题：家庭是否安全、目标缺口、下一笔钱的优先用途、近期变化是否值得重规划。

页面并行读取 Financial Analysis、Wealth Needs、Liability Calendar、ELTC、Persistent Twin、Event Timeline、Monitoring Alerts 和 Next Best Actions。读取采用分区容错：单个域失败只关闭对应卡片；财务、责任与快照三个核心域全部失败时，页面进入显式错误态，不用演示金额补位。

下层组件包含：

- `NeedGraphView`：按受控优先级展示前四项财富需要；
- Goals／Liability：复用 `GoalTimeline` 与 `LiabilityCalendar` 的完整页面入口；
- ELTC、Risk Budget、CFS Status：只显示后端结果；
- Recent Events、Monitoring Alerts、Advisor Follow-up：把变化、客户影响和下一步放在同一上下文；
- CFS 继续使用 `CfsOverview`、`CfsComponentCard`、`ProductCandidateComparison` 与 `ProfessionalReferralCard`，产品仍处于决策链末端。

## Scenario Lab 与快照报告

`/wealth/twin` 将现有持久孪生入口重组为 Scenario Lab。客户可选择收入中断、医疗支出上升、企业估值变化、提前退休和教育成本上升。只有已有、已确认的工资变化可以直接写入事件账本；其他场景进入对应确定性模块，不在浏览器中猜测金额。

`/wealth/history` 增加 Twin Snapshot Report，明确列出 snapshot id、profile version、liability version、CFS version 和 decision hash。它是八章正式规划书的证据附件，不改变八章 Schema，也不产生第九章。

## 顾问 Action Center

行动中心把 E10 Advisor Trigger 分为 `Critical`、`Today`、`This Week`、`Specialist Routing` 和 `No Action Required`。同一触发项只出现一次：紧急项优先，其次当日、专业转介，其他开放项进入周计划并保留真实截止日。

展开客户后显示六段内容：Trigger、Changed Facts、Changed Needs、Changed CFS、Evidence、Recommended Conversation。变化证据来自 Persistent Twin；触发证据来自 E10 冻结记录。建议沟通稿明确要求先确认事实，并继承 `do_not_sell` 边界。

原 Portfolio、Twin Simulator、Behavior、Trust 和方案审核流程没有删除，统一收在 Action Center 之后的渐进披露工作区。

## 响应式与无障碍

- 1440px 使用非对称 12 栅格；1024px 收为双列；768px 与 390px 收为单列或紧凑双列。
- 页面在四档宽度均满足 `document.documentElement.scrollWidth === innerWidth`。
- 语义结构使用 `main`、`section`、`article`、`dl`、`ol`、`fieldset` 和真实 `button`／`a`；跳转、展开、空态、错误态和加载态均可键盘操作。
- 新增页面通过 Testing Library 与 axe-core；真实 Compose 浏览器控制台为 0 error／0 warning。

## 边界

- Dashboard 不自动执行监控评估，也不创建 CFS；写操作仍在原确认流程中完成。
- Action Center 当前是读取与沟通准备入口，E10 没有提供状态变更 API，因此前端不伪造“已处理”按钮。
- CFS 版本只在当前浏览器会话已绑定方案时显示；否则明确显示“当前会话未绑定”。
- 所有金额、缺口、阈值与状态来自后端，前端只做格式化和分组。
