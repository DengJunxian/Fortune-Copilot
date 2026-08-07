# 组件清单

## 阶段 1 已实现

| 组件 | 路径 | 变体/状态 | 复用端 |
| --- | --- | --- | --- |
| AppShell | frontend/src/components/layout/AppShell.tsx | API、Offline Mock；client/advisor/risk density | 三端 |
| ErrorBoundary | frontend/src/components/layout/ErrorBoundary.tsx | error、recover action | 三端 |
| Button | frontend/src/components/ui/Button.tsx | primary、secondary、loading、disabled、focus、active | 三端 |
| StatusBadge | frontend/src/components/ui/StatusBadge.tsx | success、warning、info、danger | 三端 |
| DataNumber | frontend/src/components/ui/DataNumber.tsx | tabular numeric wrapper | 三端 |
| Top navigation | AppShell 内部 | active、hover、focus、mobile overflow | 三端 |
| Data table | 样式基元 | density、horizontal overflow、semantic table | 顾问端、风险端 |
| Account flow | ClientPage | 顺序式瀑布说明、mobile stack | 客户端 |
| Offline notice | AppShell | degraded/offline | 三端 |
| Not found | NotFoundPage | 404、back action | 三端 |

## 设计令牌

frontend/src/styles/tokens.css 包含：

- 语义色彩与浅/深模式；
- 中文系统字体与数字字体；
- 字号、间距、圆角、阴影、层级和动效；
- client、advisor、risk 三种密度预设；
- success、warning、danger、info 状态色。

## 阶段 3 已实现

| 组件 | 路径 | 变体／状态 | 关键约束 |
| --- | --- | --- | --- |
| HealthRadar | frontend/src/components/financial/HealthRadar.tsx | loaded、insufficient dimensions、screen-reader summary | 只绘制后端分数；明确非监管评级 |
| MetricInspector | frontend/src/components/financial/MetricInspector.tsx | open、Escape close、focus restore／loop、not-applicable | 展示公式、代入、分子／分母、来源、适用性与行动 |
| StatementWorkspace | frontend/src/components/financial/StatementWorkspace.tsx | 五表 tabs、mobile horizontal scroll | 先底表后比率，不在前端重算 |
| Financial dashboard | frontend/src/pages/ClientPage.tsx | loading、API error、offline blocked、loaded、saving、save error | 金额只来自 API；纯前端不嵌入答案 |
| Metric ledger | ClientPage 内部 | 20 项、status text、audit action | 颜色不是唯一状态信号 |
| JSON export | ClientPage 内部 | connected download | 导出服务端完整分析与版本元数据 |

## 后续阶段组件

| 组件族 | 计划阶段 | 必须状态 |
| --- | --- | --- |
| Field、MoneyInput、Select、DateInput | 2 | idle、focus、invalid、disabled、estimated、confirmed |
| Drawer、Dialog、Stepper、Toast | 5 起 | open、closing、blocked、loading、error |

任何新增组件必须使用项目 token，补齐键盘与读屏行为，并更新本清单。

## 阶段 4 已实现

| 组件 | 路径 | 变体／状态 | 关键约束 |
| --- | --- | --- | --- |
| PlanningWorkspace | frontend/src/components/planning/PlanningWorkspace.tsx | loading、error、base、counterfactual、saved | 只展示 API 计算值；不在前端重算金融结果 |
| Account cockpit | PlanningWorkspace 内部 | amount、total-assets、investable-assets、annual-surplus | 当前／建议值共用同一分母；非固定比例 |
| Goal timeline / entry | PlanningWorkspace 内部 | loaded、conflict、form open、saving、error | 保留未来额、现值、缺口、月投入、刚性与可延期 |
| Constraint panel | PlanningWorkspace 内部 | hard-pass、hard-block、soft-limit | 颜色与文字状态并用；行为不覆盖硬约束 |
| Waterfall panel | PlanningWorkspace 内部 | covered、cashflow-covered、partial、unfunded | 七步顺序固定，金额动态 |
| Counterfactual panel | PlanningWorkspace 内部 | idle、calculating、compared、error、reset | 请求只改变显式变量，后端整套重算 |
| Action draft | PlanningWorkspace 内部 | amount、confirm-first、due-date | 草稿不自动执行，不伪装为产品推荐 |

## 阶段 5 已实现

| 组件 | 路径 | 变体／状态 | 关键约束 |
| --- | --- | --- | --- |
| PortfolioWorkspace | frontend/src/components/portfolio/PortfolioWorkspace.tsx | client、advisor、risk；loading、error、loaded | 关键配置只展示 API 结果；三端共享同一证据模型 |
| Candidate comparison | PortfolioWorkspace 内部 | conservative、balanced、growth；allow、downgrade、reject、education-only | 用对齐矩阵比较，不拆成三张营销卡 |
| Allocation ledger | PortfolioWorkspace 内部 | strategic、tactical；optimizer、fallback | 原生 progress + 文字比例；金额和情景偏移均来自后端 |
| Suitability gate chain | PortfolioWorkspace 内部 | family、customer、product；pass、restrict、block | 状态、观察值、规则、原因和来源同时呈现 |
| Mock product mapping/catalog | PortfolioWorkspace 内部 | mapped、unmatched、education-only、disabled | 强制 Mock 标识并分别显示保证／非保证披露 |
| Rebalance ledger | PortfolioWorkspace 内部 | within-band、due、blocked-by-safety | 5pp／20%／6 个月证据，不把市场观点置于目标之前 |
| Risk probe | PortfolioWorkspace 内部 | five presets、checking、allow、reject、audit-id | 主动越权请求由后端闸门判断，前端不本地放行 |
| Portfolio export/save | PortfolioWorkspace 内部 | downloading、saving、success、error | 保存 3 候选与 9 道候选闸门检查；导出完整版本证据 |

## 阶段 6 已实现

| 组件 | 路径 | 变体／状态 | 关键约束 |
| --- | --- | --- | --- |
| TwinWorkspace | frontend/src/components/twin/TwinWorkspace.tsx | client、advisor、risk；catalog-loading、ready、running、cancelled、failed、completed | 全部金融结果来自确定性孪生 API；最多组合 6 个场景 |
| Scenario picker / controls | TwinWorkspace 内部 | 19 场景、多选、disabled-running、advanced overrides | seed、路径、期限、退休、储蓄、权益、流动性及压力覆盖进入请求和参数哈希 |
| Run progress | TwinWorkspace 内部 | queued、baseline、scenario、stress、completed、cancelled、failed | 原生 progress + 阶段文字；取消不展示部分结果 |
| Comparison ledger | TwinWorkspace 内部 | baseline、original-stress、optimized-stress | 同一矩阵比较概率与金额；共同随机数，非三卡营销布局 |
| WealthFanChart | frontend/src/components/twin/WealthFanChart.tsx | original、optimized、empty、negative values、table fallback | P10／P25／P50／P75／P90、零轴、直接标签、seed／样本／单位／来源和精确数据表 |
| Goal / scenario evidence | TwinWorkspace 内部 | goal outcomes、failure time、worst paths、applicable／not-applicable | 每场景回答八项标准问题；投资房缺失时不虚构自住房作用 |
| Model evidence / export | TwinWorkspace 内部 | collapsed-client、expanded-risk、download | 显示公式／引擎／规则／场景／结果版本、参数哈希、校验、审计 ID 和限制 |

## 阶段 7 已实现

| 组件 | 路径 | 变体／状态 | 关键约束 |
| --- | --- | --- | --- |
| BehaviorWorkspace | frontend/src/components/behavior/BehaviorWorkspace.tsx | client、advisor、risk；loading、error、insufficient、ready、active、completed、exited | 关键分数与上限只展示确定性 API；行为只能维持或下调客观能力 |
| Questionnaire / experiment console | BehaviorWorkspace 内部 | seven sliders、six sequential fieldsets、choice changed、saving、complete-ready、exit | 一次一题；记录选择、反应时间、修改次数；退出不生成新画像 |
| Dual profile ledger | BehaviorWorkspace 内部 | conflict、no-conflict、downshift、maintained | 对齐客观能力／问卷／实验／最终上限，不平均、不使用营销仪表盘 |
| Bias evidence ledger | BehaviorWorkspace 内部 | eleven biases、low、watch、high、details open | 分数旁必须保留来源、贡献和解释；颜色不是唯一信号 |
| Intervention ledger | BehaviorWorkspace 内部 | preview、active、cooling-blocked、completed、dismissed、empty | 显示触发偏差、目标、时间和审计状态；不自动交易或承诺收益 |
| Response evidence table | BehaviorWorkspace 内部 | six complete responses、mobile horizontal scroll | 选择、反应时间、修改、一致性和证据逐行可核验 |
| A/B framework ledger | BehaviorWorkspace 内部 | four variants、empty metric、risk-expanded | 只展示合成／授权测试指标，不作因果或收益结论 |
| Behavior export / family selector | BehaviorWorkspace 内部 | download、A/B/C selection、load error | 导出服务端完整底稿；顾问／风险端默认主 Demo B、可切换家庭 |

## 阶段 8 已实现

| 组件 | 路径 | 变体／状态 | 关键约束 |
| --- | --- | --- | --- |
| TrustWorkspace | frontend/src/components/trust/TrustWorkspace.tsx | client、advisor、risk；loading、error、ready、degraded | 三端共享受控知识和图谱；风险端额外展示真实九步链 |
| KnowledgeLedger | TrustWorkspace 内部 | cited、insufficient、expired-filtered、quarantined-filtered、searching | 答案只来自受控切片；逐条显示机构、版本、日期、范围、段落和来源 |
| IntakeLedger | TrustWorkspace 内部 | idle、parsing、pending-confirmation、partial、confirmed、error | 每项勾选／编辑后确认；缺失金额不猜测，草稿不直接写正式事实 |
| GraphLedger | TrustWorkspace 内部 | shanghai-synthetic、household、empty、mobile-scroll | 五列 SVG + 六项推导 + 等价数据表；图名与描述分离，内部滚动不撑宽页面 |
| AgentChain | TrustWorkspace 内部 | catalog-only、running、completed、degraded、blocked | 只有真实运行才显示九步；每步展示 Schema、工具、禁令、超时和状态 |
| Numeric ledger | AgentChain 内部 | collapsed、expanded、empty | 值、单位、确定性工具与来源路径直接来自运行证据，不在前端计算 |
| TrustPortalWorkspace | frontend/src/components/trust/TrustWorkspace.tsx | advisor、risk、household-loading/error | 顾问／风险端默认主 Demo B 并可切换家庭；API 失败不伪造运行结果 |

## 阶段 9 已实现

| 组件 | 路径 | 变体／状态 | 关键约束 |
| --- | --- | --- | --- |
| ClientExperienceWorkspace | frontend/src/components/client/ClientExperienceWorkspace.tsx | 11 任务、13 步旅程、A／B／C、loading、degraded | roving tab 键盘导航；切换家庭重载事实、图表、报告与行动 |
| ClientPreferences | frontend/src/components/client/ClientPreferences.tsx | light/dark、normal/large、plain language、mask、amount/ratio、yuan/wan | 偏好由 Context 统一；不改变底层 Decimal 或后端结果 |
| FinancialValue | frontend/src/components/ui/FinancialValue.tsx | money、ratio、yuan、wan、masked | 统一格式化；敏感区域遮罩时直接卸载，不把原值留在读屏树 |
| ChartFrame | frontend/src/components/charts/ChartFrame.tsx | ready、loading、empty、error、reduced-motion | 本地 ECharts SVG；固定图名、元数据、来源、结论和等价表格 |
| ChartLegend | frontend/src/components/charts/ChartFrame.tsx | solid、stripe、line | 颜色之外提供文字与图案语义 |
| ChartInsight | frontend/src/components/charts/ChartFrame.tsx | explanatory | 只解释实际数据，不把相关性写成因果或收益承诺 |
| ChartDataTable | frontend/src/components/charts/ChartFrame.tsx | expanded、collapsed、mobile-scroll | 与图表同源精确值；键盘可达且有 region 名称 |
| ChartErrorState | frontend/src/components/charts/ChartFrame.tsx | empty、render-error、data-error | 保留数据表和恢复路径，不补造图形 |
| BalanceOverviewChart | frontend/src/components/charts/FinancialCharts.tsx | amount、ratio、yuan、wan、dark | 信用卡额度不进入资产；资产／负债／净值口径同源 |
| CashFlowWaterfallChart | frontend/src/components/charts/FinancialCharts.tsx | positive、negative、zero-axis | 现金流类别互斥；结余来自后端底表 |
| GoalTimelineChart | frontend/src/components/charts/FinancialCharts.tsx | prepared、gap、conflict | 时间、准备额和缺口来自规划 API；准备率不是成功概率 |
| HealthRadar | frontend/src/components/financial/HealthRadar.tsx | ready、insufficient、table fallback | 已迁入 ChartFrame；仍明确非监管或投资评级 |
| WealthFanChart | frontend/src/components/twin/WealthFanChart.tsx | P10—P90、P25—P75、P50、negative、table fallback | 已迁入 ChartFrame；共同随机数和零轴不变 |
| PlanningReportWorkspace | frontend/src/components/client/PlanningReportWorkspace.tsx | eight chapters、ready、pending-twin、needs-review | 一级目录严格八章；显示依据、引用、数据日和原型边界 |
| ActionCalendar | frontend/src/components/client/ActionCalendar.tsx | immediate、three-months、one-year、long-term、12-month review | 金额与期限来自聚合 API；逐项展开数据／原因、约束公式、重算触发和风险假设；不自动交易或用倒计时催促 |
| PrivacyCenter | frontend/src/components/client/PrivacyCenter.tsx | active、withdrawn、confirm-withdraw、confirm-delete、review-queued | 乐观版本、二次确认、软删除和人工复核；动作均有真实 API |
| ClientStatePreview | frontend/src/components/client/ClientStatePreview.tsx | 14 类合成状态 | 明确是 UI Demo，不冒充当前家庭状态；合规阻断含人工路径 |

## 阶段 10 已实现

| 组件 | 路径 | 变体／状态 | 关键约束 |
| --- | --- | --- | --- |
| Demo actor control | frontend/src/components/layout/AppShell.tsx | client、advisor、compliance、admin | 持久标签；明确仅模拟 RBAC；路由默认角色不替代服务端权限 |
| AdvisorWorkflowWorkspace | frontend/src/components/workflow/AdvisorWorkflowWorkspace.tsx | queue、dossier、draft、calculated、reviewed、submitted、confirmed、active、permission-denied、error | 客户队列、面谈问题、异常／冲突、三方案、可编辑 Mock 沟通稿、人工高风险确认、12 月提醒；关键数字不在前端计算 |
| RiskWorkflowWorkspace | frontend/src/components/workflow/RiskWorkflowWorkspace.tsx | empty queue、reviewable、blocked、warning、approved、returned、human-review、replayed、exported、permission-denied | 十类控制和七类治理版本同屏；阻断不能通过；投诉回放只读 |
| WorkflowStateRail | frontend/src/components/workflow/WorkflowShared.tsx | complete、current、future；8 fixed states | 文字、序号和 aria-current；内部横向滚动，不可点击跳步 |
| WorkflowVersionLedger | frontend/src/components/workflow/WorkflowShared.tsx | current、historical、collapsed | 显示动作、角色、理由、时间、前后哈希和治理版本；每次编辑新行 |
| ClientPlanConfirmation | frontend/src/components/workflow/ClientPlanConfirmation.tsx | waiting、permission-denied、compliance-reviewed、customer-confirmed、active、error | 合规前不展示内部草稿；风险、Mock、非保本逐项确认；姓名仅作非法律演示签署 |
| MockBankLedger | AdvisorWorkflowWorkspace 内部 | 8 interfaces、available、empty、collapsed | 合成 Mock、非官方连接；信用卡额度不进入资产，保险保证／非保证利益分列 |

## 阶段 11 已实现

| 组件 | 路径 | 变体／状态 | 关键约束 |
| --- | --- | --- | --- |
| PlanningReportWorkspace | `frontend/src/components/client/PlanningReportWorkspace.tsx` | preview、generating、current、recalculating、downloading、error | 正式报告优先，尚无报告才显示 Stage 9 预览；一级目录严格八章 |
| ActionCalendar | `frontend/src/components/client/ActionCalendar.tsx` | open、completed、deferred、not-applicable、saving、recalculated | 五个时间分组；状态持久化并创建新报告，不使用打卡激励 |
| AdvisorFormalReportPanel | `frontend/src/components/report/FormalReportPortalPanels.tsx` | empty、current、generating、major-event、exporting、error | 顾问读取客户同一快照；目录、版本与导出对齐，不复制数字 |
| ReportGenerationChainPanel | `frontend/src/components/report/FormalReportPortalPanels.tsx` | empty、verified、needs-review、error | 风险端只读显示父快照、哈希、审核流和治理版本 |
| Formal HTML renderer | `backend/app/services/reporting/render.py` | self-contained、watermarked | 只有八个 `h2`；无脚本、字体下载或外部渲染资源 |
| Formal PDF renderer | `backend/app/services/reporting/render.py` | system/open-font、multi-page、diagnosed | 横向 A4；版本、数据日、页码、哈希、水印；成功／失败均审计 |
