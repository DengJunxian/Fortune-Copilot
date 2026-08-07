# 客户端完整体验契约

版本：Stage 9 客户旅程 + Stage 11 正式报告 + Stage 13 脱敏交付状态 / `client-experience-v1.0.0`  
日期：2026-08-05

## 目标与边界

客户端把已经完成的家庭事实、财务分析、目标规划、组合适当性、数字孪生、行为金融和受控知识能力组织成一条可核验旅程。它不是新的金融计算器：关键金额、比例、配置、状态和行动金额均来自后端确定性工具；浏览器只负责展示、切换口径和收集明确操作。

主 Demo 默认使用 SQLite、Mock LLM、本地受控知识和合成家庭，不需要外部模型、真实银行接口、CDN、外部字体或运行时网络。外部解释模型不可用时只让解释层降级，财务底表和规则计算仍可使用。

## 旅程与任务工作区

后端固定返回 13 个旅程节点：隐私授权、快速体验、深度规划、家庭建档、财务体检、家庭目标、风险与行为测评、动态四账户、方案比较、数字孪生、家庭规划书、行动日历和定期复盘。每个节点都包含文字状态、原因、下一步动作和目标视图。

客户端用 11 个键盘可达的任务工作区承载旅程：

1. 家庭画像：成员责任关系、生命周期、确认状态和下一步；
2. 资产负债：资产、负债和净资产全景，明确信用卡额度不计资产；
3. 家庭现金流：收入、必要支出、还贷、保险、教育赡养、弹性消费和结余；
4. 财务健康：七维辅助雷达、20 项指标及公式审计；
5. 动态四账户：七步瀑布、三尺、五硬一软、候选与适当性；
6. 目标时间轴：未来额、现值、准备率、冲突与反事实；
7. 数字孪生：分位数路径、压力场景和共同随机数比较；
8. 行为实验：双画像、偏差证据、干预和冷静期；
9. 家庭规划书：正式八章不可变快照、受控引用与 HTML/PDF；尚无快照时显示明确标注的确定性预览；
10. 行动日历：立即、三个月、一年、长期和未来 12 个月复盘，状态持久化并触发新报告；
11. 隐私中心：授权、数据导出、软删除确认和人工复核。

任务标签遵守 WAI-ARIA tab 语义，支持左右方向键、Home 和 End。切换任务后焦点进入新任务标题；移动端导航只在自身区域滚动，不扩大文档宽度。

## 聚合服务与 API

`client_experience` 服务在单次请求中复用已有确定性财务和规划引擎，再组合受控知识、授权账本、行动日历和报告预览。聚合不会把浏览器值写回，也不会调用 LLM 计算数字。

| 方法 | 路径 | 行为 |
| --- | --- | --- |
| GET | `/api/v1/households/{id}/client-experience` | 返回 13 步旅程、隐私摘要、五组行动、八章预览、脱敏交付状态、版本和 14 类状态目录 |
| GET | `/api/v1/households/{id}/client-experience/export` | 导出财务分析、规划与客户端体验的完整 JSON 数据包 |
| POST | `/api/v1/households/{id}/privacy/consents/{consent_id}/withdraw` | 按 `expected_version` 撤回授权并写审计；陈旧版本返回 409 |
| POST | `/api/v1/households/{id}/privacy/human-review-requests` | 写入演示顾问队列审计事件，不虚构已完成处理 |
| DELETE | `/api/v1/households/{id}?expected_version=…` | 复用家庭 CRUD 的二次确认软删除；普通查询随后隐藏 |
| GET／POST | `/api/v1/households/{id}/reports/current`、`/reports` | 读取或一键生成正式八章报告 |
| POST | `/api/v1/households/{id}/reports/recalculate` | 月度或重大事件创建新报告快照 |
| GET／POST | `/api/v1/households/{id}/report-actions`、`/report-actions/{code}` | 读取／更新行动；更新创建下一报告快照 |

可选 `analysis_date` 固定分析日，使报告、月度复盘和测试可复现。能力清单将 `client_experience` 标记为 `available / real`。Stage 9 不增加数据库表或迁移；授权撤回和人工复核复用现有 `ConsentRecord` 与 `AuditEvent`。

Stage 13 的 `delivery` 只返回报告、审核流与行动账本是否为 `not_generated`／`not_created`、`under_review` 或 `client_ready`，以及一段边界说明，不返回内部报告 ID、审核意见或草稿内容。客户端遇到 `under_review` 时不会请求受限资源，也不会提供重复生成按钮；它只显示明确标注的确定性预览。顾问和合规端仍通过原有对象授权接口读取完整证据。

每个 `ActionCalendarItem` 除标题、动作、金额、期限和来源记录外，还固定返回 `why`、`constraint_or_formula`、`change_trigger` 与 `risk_and_assumptions`。客户端的“为什么建议这一步”可展开区逐项回答使用了什么家庭数据、哪个约束或公式生效、什么变化会触发重算，以及不自动执行／不保证收益等边界。未来 12 个月的复盘项金额明确为 0，其日期由分析日加自然月确定。生成正式报告后，行动由 `ActionItem` 持久化为待办、已完成、延期或不适用；任何状态更新都会新增 Rn 报告，不覆盖旧快照。

## 八章预览与正式规划书

一级目录的名称、数量与顺序固定为：

1. 家庭画像与生命周期
2. 资产负债与现金流
3. 财务健康与家庭保障
4. 家庭目标与冲突
5. 四账户动态规划
6. 方案比较与数字孪生
7. 行动日历与复盘
8. 计算依据、引用与风险边界

上述目录是 Stage 9 的客户端确定性预览契约，每章包含计算依据、受控引用 ID 和 `ready`、`pending_twin` 或 `needs_review` 状态。第六章在尚未运行数字孪生时明确保持待补，不用模板补造概率。

Stage 11 正式报告是独立 `FormalReportDocument`：一级目录严格为“家庭基础情况、理财目标、大额支出计划、理财假设、家庭财务报表、家庭财务比率分析、投资规划建议、免责声明”。一旦生成且达到客户可见状态，客户端工作区以当前 Rn 正式快照为主，展示结构化数字账本、受控引用、版本、水印、重算和 HTML/PDF 下载；旧预览在没有正式快照或内部快照仍在审核时作为安全降级入口。合规前关联内部审核流的正式报告仍由服务端拒绝；客户端依靠脱敏 `delivery` 状态避免主动请求和暴露内部草稿。完整契约见 `docs/formal_reports.md`。

## 图表协议

所有新图表通过本地 ECharts 6 模块化构建并使用 SVG renderer。共享基元为 `ChartFrame`、`ChartLegend`、`ChartInsight`、`ChartDataTable` 和 `ChartErrorState`。每张图必须同时提供：

- 标题和简短说明；
- 单位、时间范围、方法口径、更新时间和来源；
- 不把相关性说成因果的文字结论；
- 稳定的 `role="img"` 可访问名称；
- 可展开的等价精确数据表；
- Loading、Empty、Error 与 reduced-motion 降级。

已接入资产负债全景、现金流瀑布、目标时间轴、财务健康雷达和 P10—P90 财富扇形。图表颜色只取项目语义 token 映射，不使用绿色庆祝预计收益；颜色之外保留线型、图例和文字。

## 显示与隐私模式

- 深色模式：切换项目深色 token 和自有图表调色板；
- 大字模式：提升全局文本尺度，并保持控件至少 44×44 CSS px；
- 低金融知识模式：把专业术语替换为通俗说明，不改变底层数据；
- 金额遮罩：敏感工作区直接卸载，金额不留在视觉层或辅助技术树；
- 金额／比例：只切换后端已经给出的金额和分母比例，不在前端重算；
- 元／万元：仅改变格式化单位，底层 Decimal 精度不变。

三套合成家庭 A／B／C 可一键切换。家庭成员、生命周期、底表、图表、报告摘要和行动金额从各自事实实时重算，不能只更换姓名或头像。

## 完整状态

状态目录固定覆盖 14 类：Loading、Skeleton、Empty、FirstUse、MissingData、DataConflict、CalculationFailed、ModelDegraded、PermissionDenied、Offline、StaleData、NoSuitableProduct、ComplianceBlocked 和 ReportFailed。页面中的状态预览明确标注为合成 UI 演示，不能冒充当前家庭的真实业务状态。

真实错误路径遵守闭合原则：离线不补造数字；模型降级不停止确定性计算；无合适产品不自动放宽闸门；合规阻断提供人工复核入口；报告失败不生成缺章版本。

## 可访问性与响应式

- 支持跳到主内容、稳定焦点顺序、语义 tab、原生表单和可见 `focus-visible`；
- 图表有读屏名称和数据表替代，金额遮罩对辅助技术同样生效；
- `prefers-reduced-motion: reduce` 下关闭 ECharts 动画与非必要过渡；
- 已验证 390×844、1366×768、1440×900 与 1920×1080；表格和任务导航只在有标签的内部区域滚动；
- 不依赖 hover 暴露关键操作，主触控目标至少 44px。

## 验证命令

```bash
make check
npm --workspace frontend run test:e2e
PLAYWRIGHT_BASE_URL=http://127.0.0.1:18080 npm --workspace frontend run test:e2e -- --workers=1
docker compose ps
```

后端测试锁定 13 步、11 个视图映射、14 类状态、五组行动、12 个月复盘、三家庭差异、预览与正式报告各自八章顺序、确定性导出、信用卡边界、授权版本冲突和审计。前端单元测试覆盖任务导航、显示模式、金额遮罩、图表表格、正式报告、行动 R2 与隐私动作；Playwright 覆盖离线降级、完整旅程、正式报告 R1 → R2、风险哈希链、合规阻断、移动端、reduced-motion、四档视口和无外部请求。
